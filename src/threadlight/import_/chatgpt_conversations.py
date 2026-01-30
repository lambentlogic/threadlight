"""
ChatGPT Conversations importer for Threadlight.

Import conversation history from ChatGPT's conversations.json export.
Handles the tree-based message structure and Unix timestamps.
Uses streaming/chunked parsing to handle large files (189MB+).
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
class ChatGPTImportStats:
    """Statistics from a ChatGPT conversation import operation."""

    total_conversations: int = 0
    conversations_imported: int = 0
    conversations_skipped: int = 0  # Empty or invalid
    total_messages: int = 0
    messages_imported: int = 0
    system_messages_found: int = 0  # Potential custom instructions
    errors: int = 0
    bytes_processed: int = 0

    def __str__(self) -> str:
        return (
            f"Imported {self.conversations_imported} conversations "
            f"({self.messages_imported} messages, "
            f"{self.conversations_skipped} skipped)"
        )


@dataclass
class ChatGPTImportResult:
    """Result of a ChatGPT conversation import operation."""

    success: bool
    stats: ChatGPTImportStats
    error: Optional[str] = None
    system_instructions: list[str] = field(default_factory=list)


def parse_unix_timestamp(ts: float | int | None) -> datetime:
    """
    Parse ChatGPT's Unix timestamp to datetime.

    ChatGPT uses Unix timestamps like 1769726982.517479
    """
    if ts is None:
        return datetime.utcnow()

    try:
        return datetime.utcfromtimestamp(float(ts))
    except (ValueError, OSError, TypeError):
        return datetime.utcnow()


def extract_message_content(message_data: dict[str, Any]) -> str:
    """
    Extract text content from a ChatGPT message.

    ChatGPT messages have content like:
    {
        "content_type": "text",
        "parts": ["message text here"]
    }

    Parts is an array that usually has one string element,
    but can have multiple parts for complex messages.
    """
    if not message_data:
        return ""

    content = message_data.get("content")
    if not content:
        return ""

    # Handle different content types
    content_type = content.get("content_type", "")

    # Text content - extract from parts array
    if content_type == "text":
        parts = content.get("parts", [])
        if not parts:
            return ""

        # Filter out None values and join parts
        text_parts = [str(p) for p in parts if p is not None]
        return "\n".join(text_parts)

    # Code content
    elif content_type == "code":
        code_text = content.get("text", "")
        return f"```\n{code_text}\n```" if code_text else ""

    # Execution output
    elif content_type == "execution_output":
        output = content.get("text", "")
        return f"[Output]: {output}" if output else ""

    # Multimodal content (images, etc.) - extract text if available
    elif content_type == "multimodal_text":
        parts = content.get("parts", [])
        text_parts = []
        for part in parts:
            if isinstance(part, str):
                text_parts.append(part)
            elif isinstance(part, dict) and part.get("content_type") == "text":
                text_parts.append(part.get("text", ""))
        return "\n".join(text_parts)

    # System error or other types
    elif content_type == "system_error":
        return ""  # Skip error messages

    # Fallback: try to get any text-like content
    if "text" in content:
        return content["text"]

    parts = content.get("parts", [])
    if parts:
        text_parts = [str(p) for p in parts if p is not None and isinstance(p, str)]
        return "\n".join(text_parts)

    return ""


def find_root_node(mapping: dict[str, Any]) -> Optional[str]:
    """
    Find the root node in the message tree.

    The root is typically a node with no parent or a special ID like
    "client-created-root" or similar.
    """
    # First, try to find a node with no parent
    for node_id, node in mapping.items():
        parent = node.get("parent")
        if parent is None:
            return node_id

    # If all nodes have parents, look for common root patterns
    for pattern in ["root", "client-created", "aaa"]:
        for node_id in mapping:
            if pattern in node_id.lower():
                return node_id

    # Last resort: find the node that isn't referenced as anyone's child
    all_children = set()
    for node in mapping.values():
        children = node.get("children", [])
        all_children.update(children)

    for node_id in mapping:
        if node_id not in all_children:
            return node_id

    # If nothing works, just return the first node
    if mapping:
        return next(iter(mapping))

    return None


def traverse_message_tree(
    mapping: dict[str, Any],
    skip_empty: bool = True,
) -> list[dict[str, Any]]:
    """
    Traverse the message tree to build a linear sequence.

    ChatGPT stores messages in a tree structure where:
    - Each node has an id, message data, parent, and children
    - Branches occur when responses are regenerated
    - We follow all paths (including branches from regenerated responses)

    Uses iterative traversal to handle very long conversations without
    hitting Python's recursion limit.

    Args:
        mapping: The mapping dict from the conversation
        skip_empty: Whether to skip messages with empty content

    Returns:
        List of message dictionaries in conversation order
    """
    if not mapping:
        return []

    # Find the root node
    root_id = find_root_node(mapping)
    if not root_id:
        return []

    messages = []
    visited = set()

    # Use a stack for iterative DFS traversal
    # Stack contains node IDs to process
    stack = [root_id]

    while stack:
        node_id = stack.pop()

        if node_id in visited or node_id not in mapping:
            continue

        visited.add(node_id)
        node = mapping[node_id]

        # Extract message if it exists
        message_data = node.get("message")
        if message_data:
            author = message_data.get("author", {})
            role = author.get("role", "")

            # Skip system messages that are just metadata
            if role and role != "system":
                content = extract_message_content(message_data)

                if not skip_empty or content.strip():
                    messages.append({
                        "id": node.get("id", str(uuid.uuid4())),
                        "role": role,
                        "content": content,
                        "timestamp": message_data.get("create_time"),
                        "metadata": {
                            "author_name": author.get("name"),
                            "model_slug": message_data.get("metadata", {}).get("model_slug"),
                        },
                    })
            elif role == "system":
                # Track system messages (potential custom instructions)
                content = extract_message_content(message_data)
                if content.strip():
                    messages.append({
                        "id": node.get("id", str(uuid.uuid4())),
                        "role": "system",
                        "content": content,
                        "timestamp": message_data.get("create_time"),
                        "metadata": {"is_system": True},
                    })

        # Add children to stack (reversed to maintain order when popping)
        children = node.get("children", [])
        stack.extend(reversed(children))

    # Sort messages by timestamp to ensure correct order
    # (DFS may not produce chronological order for branching trees)
    messages.sort(key=lambda m: m.get("timestamp") or 0)

    return messages


def parse_chatgpt_message(
    msg_data: dict[str, Any],
    conversation_id: str,
) -> Optional[Message]:
    """Parse a single ChatGPT message into a Message object."""
    try:
        msg_id = msg_data.get("id", str(uuid.uuid4()))
        role = msg_data.get("role", "")

        # Map ChatGPT roles to standard roles
        role_map = {
            "user": "user",
            "assistant": "assistant",
            "system": "system",
            "tool": "assistant",  # Tool outputs as assistant
        }
        role = role_map.get(role, role)

        if not role:
            return None

        content = msg_data.get("content", "")
        if not content.strip():
            return None

        timestamp = parse_unix_timestamp(msg_data.get("timestamp"))

        metadata = msg_data.get("metadata", {})
        # Clean up metadata - remove None values
        metadata = {k: v for k, v in metadata.items() if v is not None}

        return Message(
            id=msg_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            timestamp=timestamp,
            source="chatgpt",
            metadata=metadata,
        )

    except Exception as e:
        logger.warning(f"Error parsing ChatGPT message: {e}")
        return None


def parse_chatgpt_conversation(
    conv_data: dict[str, Any],
    skip_empty_messages: bool = True,
    profile_scope: Optional[str] = None,
) -> tuple[Optional[Conversation], list[Message], list[str]]:
    """
    Parse a single ChatGPT conversation into Conversation and Message objects.

    Args:
        conv_data: Raw conversation data from ChatGPT export
        skip_empty_messages: Skip messages with empty content
        profile_scope: Optional profile ID to scope this conversation to

    Returns:
        Tuple of (Conversation, list of Messages, list of system instructions)
        or (None, [], []) if invalid
    """
    try:
        conv_id = conv_data.get("id") or conv_data.get("conversation_id") or str(uuid.uuid4())
        title = conv_data.get("title", "") or ""

        # Parse timestamps
        created_at = parse_unix_timestamp(conv_data.get("create_time"))
        updated_at = parse_unix_timestamp(conv_data.get("update_time"))

        # Extract messages from the tree structure
        mapping = conv_data.get("mapping", {})
        raw_messages = traverse_message_tree(mapping, skip_empty=skip_empty_messages)

        # Convert to Message objects
        messages: list[Message] = []
        system_instructions: list[str] = []

        for raw_msg in raw_messages:
            # Track system messages separately
            if raw_msg.get("role") == "system":
                content = raw_msg.get("content", "").strip()
                if content and content not in system_instructions:
                    system_instructions.append(content)
                continue

            msg = parse_chatgpt_message(raw_msg, conv_id)
            if msg:
                # Set profile_id on messages if profile_scope is provided
                if profile_scope:
                    msg.profile_id = profile_scope
                messages.append(msg)

        # Try to extract model info from messages metadata
        model_name = "ChatGPT"  # Default
        for msg in messages:
            if msg.metadata and msg.metadata.get("model_slug"):
                model_name = msg.metadata["model_slug"]
                break

        # Create conversation object
        conversation = Conversation(
            id=conv_id,
            name=title,
            summary="",  # ChatGPT doesn't provide summaries in export
            created_at=created_at,
            updated_at=updated_at,
            source="chatgpt",
            message_count=len(messages),
            profile_scope=profile_scope,
            model=model_name,  # Track the model used in this conversation
        )

        return conversation, messages, system_instructions

    except Exception as e:
        logger.warning(f"Error parsing ChatGPT conversation: {e}")
        return None, [], []


def iter_conversations_streaming(path: Path) -> Iterator[dict[str, Any]]:
    """
    Stream conversations from a large JSON file.

    For very large files (100MB+), we use ijson for streaming if available.
    """
    file_size = path.stat().st_size

    # For files under 100MB, just load the whole thing
    if file_size < 100 * 1024 * 1024:  # 100MB
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            yield from data
        return

    # For larger files, use ijson for streaming if available
    try:
        import ijson

        logger.info(f"Using ijson streaming for {file_size / (1024*1024):.1f}MB file")

        with open(path, "rb") as f:
            parser = ijson.items(f, "item")
            yield from parser

    except ImportError:
        logger.warning(
            "ijson not installed. Loading entire file into memory. "
            "Install ijson for better memory usage: pip install ijson"
        )
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            yield from data


def import_chatgpt_conversations(
    path: str | Path,
    storage: StorageBackend,
    batch_size: int = 100,
    skip_empty: bool = True,
    limit: Optional[int] = None,
    dry_run: bool = False,
    progress_callback: Optional[callable] = None,
    profile_scope: Optional[str] = None,
) -> ChatGPTImportResult:
    """
    Import conversations from a ChatGPT conversations.json export.

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
        ChatGPTImportResult with statistics
    """
    path = Path(path)

    if not path.exists():
        return ChatGPTImportResult(
            success=False,
            stats=ChatGPTImportStats(),
            error=f"File not found: {path}"
        )

    stats = ChatGPTImportStats()
    stats.bytes_processed = path.stat().st_size

    message_batch: list[Message] = []
    all_system_instructions: list[str] = []

    try:
        for conv_data in iter_conversations_streaming(path):
            stats.total_conversations += 1

            # Check limit
            if limit and stats.conversations_imported >= limit:
                break

            # Parse conversation with profile scope
            conversation, messages, system_instructions = parse_chatgpt_conversation(
                conv_data,
                skip_empty_messages=skip_empty,
                profile_scope=profile_scope,
            )

            if not conversation:
                stats.errors += 1
                continue

            # Track system instructions
            if system_instructions:
                stats.system_messages_found += len(system_instructions)
                all_system_instructions.extend(system_instructions)

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
        return ChatGPTImportResult(
            success=False,
            stats=stats,
            error=f"Invalid JSON: {e}"
        )
    except Exception as e:
        logger.error(f"Error importing ChatGPT conversations: {e}")
        return ChatGPTImportResult(
            success=False,
            stats=stats,
            error=str(e)
        )

    # Deduplicate system instructions
    unique_instructions = list(dict.fromkeys(all_system_instructions))

    return ChatGPTImportResult(
        success=True,
        stats=stats,
        system_instructions=unique_instructions,
    )


def preview_chatgpt_conversations(
    path: str | Path,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Preview conversations from a ChatGPT conversations.json file.

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
            title = conv_data.get("title", "(unnamed)") or "(unnamed)"
            created = parse_unix_timestamp(conv_data.get("create_time"))

            # Get message count from mapping
            mapping = conv_data.get("mapping", {})
            raw_messages = traverse_message_tree(mapping, skip_empty=True)
            msg_count = len([m for m in raw_messages if m.get("role") != "system"])

            # Get first user message as preview
            first_msg = ""
            for msg in raw_messages:
                if msg.get("role") == "user":
                    first_msg = msg.get("content", "")[:100]
                    if len(msg.get("content", "")) > 100:
                        first_msg += "..."
                    break

            previews.append({
                "title": title[:50],
                "message_count": msg_count,
                "created_at": created.strftime("%Y-%m-%d"),
                "first_message": first_msg,
            })

            if len(previews) >= limit:
                break

        return previews

    except Exception as e:
        logger.error(f"Error previewing ChatGPT conversations: {e}")
        return []


def count_chatgpt_conversations(path: str | Path) -> dict[str, int]:
    """
    Count conversations and messages in a ChatGPT export without fully loading it.

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

            mapping = conv_data.get("mapping", {})
            raw_messages = traverse_message_tree(mapping, skip_empty=True)
            msg_count = len([m for m in raw_messages if m.get("role") != "system"])

            counts["messages"] += msg_count
            if msg_count == 0:
                counts["empty_conversations"] += 1

    except Exception as e:
        logger.error(f"Error counting ChatGPT conversations: {e}")

    return counts
