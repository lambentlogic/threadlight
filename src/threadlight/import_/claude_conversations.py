"""
Claude Conversations importer for Threadlight.

Import conversation history from Claude's conversations.json export.
Uses streaming/chunked parsing to handle large files (200MB+).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional
import logging

from threadlight.storage.base import (
    StorageBackend,
    Message,
    Conversation,
)

logger = logging.getLogger(__name__)


@dataclass
class ConversationImportStats:
    """Statistics from a conversation import operation."""

    total_conversations: int = 0
    conversations_imported: int = 0
    conversations_skipped: int = 0  # Empty or invalid
    total_messages: int = 0
    messages_imported: int = 0
    errors: int = 0
    bytes_processed: int = 0

    def __str__(self) -> str:
        return (
            f"Imported {self.conversations_imported} conversations "
            f"({self.messages_imported} messages, "
            f"{self.conversations_skipped} skipped)"
        )


@dataclass
class ConversationImportResult:
    """Result of a conversation import operation."""

    success: bool
    stats: ConversationImportStats
    error: Optional[str] = None


def parse_claude_timestamp(ts: str) -> datetime:
    """Parse Claude's timestamp format to datetime."""
    if not ts:
        return datetime.utcnow()

    try:
        # Claude uses ISO 8601 format with timezone
        # e.g., "2024-03-04T21:09:45.458975Z"
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return datetime.utcnow()


def parse_message_content(chat_message: dict[str, Any]) -> str:
    """
    Extract text content from a Claude chat message.

    Claude messages have a 'content' array with different types.
    We extract the text content.
    """
    # First try the simple 'text' field
    if "text" in chat_message and chat_message["text"]:
        return chat_message["text"]

    # Then try the 'content' array
    content_array = chat_message.get("content", [])
    if not content_array:
        return ""

    text_parts = []
    for item in content_array:
        if isinstance(item, dict) and item.get("type") == "text":
            text_parts.append(item.get("text", ""))
        elif isinstance(item, str):
            text_parts.append(item)

    return "\n".join(text_parts)


def parse_claude_message(
    msg_data: dict[str, Any],
    conversation_id: str,
) -> Optional[Message]:
    """Parse a single Claude message into a Message object."""
    try:
        msg_uuid = msg_data.get("uuid", str(uuid.uuid4()))
        sender = msg_data.get("sender", "")

        # Map Claude's sender to role
        role_map = {
            "human": "user",
            "assistant": "assistant",
        }
        role = role_map.get(sender, sender)

        # Extract content
        content = parse_message_content(msg_data)
        if not content.strip():
            return None

        # Parse timestamp
        timestamp = parse_claude_timestamp(
            msg_data.get("created_at", "") or msg_data.get("updated_at", "")
        )

        # Extract metadata (attachments, files)
        metadata: dict[str, Any] = {}
        if msg_data.get("attachments"):
            metadata["attachments"] = msg_data["attachments"]
        if msg_data.get("files"):
            metadata["files"] = msg_data["files"]

        return Message(
            id=msg_uuid,
            conversation_id=conversation_id,
            role=role,
            content=content,
            timestamp=timestamp,
            source="claude",
            metadata=metadata,
        )

    except Exception as e:
        logger.warning(f"Error parsing message: {e}")
        return None


def parse_claude_conversation(
    conv_data: dict[str, Any],
    profile_scope: Optional[str] = None,
) -> tuple[Optional[Conversation], list[Message]]:
    """
    Parse a single Claude conversation into Conversation and Message objects.

    Args:
        conv_data: Raw conversation data from Claude export
        profile_scope: Optional profile ID to scope this conversation to

    Returns:
        Tuple of (Conversation, list of Messages) or (None, []) if invalid
    """
    try:
        conv_uuid = conv_data.get("uuid", str(uuid.uuid4()))
        name = conv_data.get("name", "") or ""
        summary = conv_data.get("summary", "") or ""

        created_at = parse_claude_timestamp(conv_data.get("created_at", ""))
        updated_at = parse_claude_timestamp(conv_data.get("updated_at", ""))

        # Parse messages
        chat_messages = conv_data.get("chat_messages", [])
        messages: list[Message] = []

        for msg_data in chat_messages:
            msg = parse_claude_message(msg_data, conv_uuid)
            if msg:
                # Set profile_id on messages if profile_scope is provided
                if profile_scope:
                    msg.profile_id = profile_scope
                messages.append(msg)

        # Create conversation object
        conversation = Conversation(
            id=conv_uuid,
            name=name,
            summary=summary,
            created_at=created_at,
            updated_at=updated_at,
            source="claude",
            message_count=len(messages),
            profile_scope=profile_scope,
            model="Claude",  # Mark as imported from Claude
        )

        return conversation, messages

    except Exception as e:
        logger.warning(f"Error parsing conversation: {e}")
        return None, []


def iter_conversations_streaming(path: Path) -> Iterator[dict[str, Any]]:
    """
    Stream conversations from a large JSON file.

    For very large files (200MB+), we use a streaming approach
    that reads and parses one conversation at a time.
    """
    # For files under 100MB, just load the whole thing
    file_size = path.stat().st_size
    if file_size < 100 * 1024 * 1024:  # 100MB
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            yield from data
        return

    # For larger files, use ijson for streaming if available
    try:
        import ijson

        with open(path, "rb") as f:
            parser = ijson.items(f, "item")
            yield from parser

    except ImportError:
        # Fall back to loading the whole file
        logger.warning(
            "ijson not installed. Loading entire file into memory. "
            "Install ijson for better memory usage: pip install ijson"
        )
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            yield from data


def import_claude_conversations(
    path: str | Path,
    storage: StorageBackend,
    batch_size: int = 100,
    skip_empty: bool = True,
    limit: Optional[int] = None,
    dry_run: bool = False,
    progress_callback: Optional[callable] = None,
    profile_scope: Optional[str] = None,
) -> ConversationImportResult:
    """
    Import conversations from a Claude conversations.json export.

    Args:
        path: Path to conversations.json
        storage: Storage backend to save to
        batch_size: Number of messages to save in each batch
        skip_empty: Skip conversations with no messages
        limit: Maximum conversations to import (for testing)
        dry_run: If True, parse but don't save to storage
        progress_callback: Optional callback(stats) called periodically
        profile_scope: Optional profile ID to scope imported conversations to

    Returns:
        ConversationImportResult with statistics
    """
    path = Path(path)

    if not path.exists():
        return ConversationImportResult(
            success=False,
            stats=ConversationImportStats(),
            error=f"File not found: {path}"
        )

    stats = ConversationImportStats()
    stats.bytes_processed = path.stat().st_size

    message_batch: list[Message] = []

    try:
        for conv_data in iter_conversations_streaming(path):
            stats.total_conversations += 1

            # Check limit
            if limit and stats.conversations_imported >= limit:
                break

            # Parse conversation with profile scope
            conversation, messages = parse_claude_conversation(conv_data, profile_scope=profile_scope)

            if not conversation:
                stats.errors += 1
                continue

            # Skip empty conversations if requested
            if skip_empty and not messages:
                stats.conversations_skipped += 1
                continue

            stats.total_messages += len(messages)

            # Save conversation
            if not dry_run:
                try:
                    storage.save_conversation(conversation)
                except Exception as e:
                    logger.warning(f"Error saving conversation: {e}")
                    stats.errors += 1
                    continue

            stats.conversations_imported += 1

            # Add messages to batch
            message_batch.extend(messages)
            stats.messages_imported += len(messages)

            # Save batch when it reaches the size limit
            if len(message_batch) >= batch_size:
                if not dry_run:
                    storage.save_messages_batch(message_batch)
                message_batch = []

            # Progress callback
            if progress_callback and stats.total_conversations % 100 == 0:
                progress_callback(stats)

        # Save remaining messages
        if message_batch and not dry_run:
            storage.save_messages_batch(message_batch)

    except json.JSONDecodeError as e:
        return ConversationImportResult(
            success=False,
            stats=stats,
            error=f"Invalid JSON: {e}"
        )
    except Exception as e:
        logger.error(f"Error importing conversations: {e}")
        return ConversationImportResult(
            success=False,
            stats=stats,
            error=str(e)
        )

    return ConversationImportResult(
        success=True,
        stats=stats,
    )


def preview_conversations(
    path: str | Path,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Preview conversations from a conversations.json file.

    Args:
        path: Path to conversations.json
        limit: Maximum number of conversations to preview

    Returns:
        List of conversation previews
    """
    path = Path(path)

    if not path.exists():
        return []

    try:
        previews = []
        for conv_data in iter_conversations_streaming(path):
            messages = conv_data.get("chat_messages", [])
            first_msg = ""
            if messages:
                first_msg = parse_message_content(messages[0])[:100]
                if len(parse_message_content(messages[0])) > 100:
                    first_msg += "..."

            previews.append({
                "uuid": conv_data.get("uuid", "")[:8],
                "name": conv_data.get("name", "(unnamed)") or "(unnamed)",
                "message_count": len(messages),
                "created_at": conv_data.get("created_at", "")[:10],
                "first_message": first_msg,
            })

            if len(previews) >= limit:
                break

        return previews

    except Exception:
        return []


def count_conversations(path: str | Path) -> dict[str, int]:
    """
    Count conversations and messages in a file without fully loading it.

    Args:
        path: Path to conversations.json

    Returns:
        Dict with 'conversations', 'messages', 'empty_conversations' counts
    """
    path = Path(path)

    if not path.exists():
        return {"conversations": 0, "messages": 0, "empty_conversations": 0}

    counts = {
        "conversations": 0,
        "messages": 0,
        "empty_conversations": 0,
    }

    try:
        for conv_data in iter_conversations_streaming(path):
            counts["conversations"] += 1
            msg_count = len(conv_data.get("chat_messages", []))
            counts["messages"] += msg_count
            if msg_count == 0:
                counts["empty_conversations"] += 1

    except Exception:
        pass

    return counts
