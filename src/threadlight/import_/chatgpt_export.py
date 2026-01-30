"""
Combined ChatGPT Export importer for Threadlight.

Import from a complete ChatGPT export zip file that contains:
- conversations.json: Full conversation history
- user.json: User information (not currently used)
- message_feedback.json: Feedback data (not currently used)
- model_comparisons.json: A/B test data (not currently used)
- dalle-generations/: Generated images (skipped - text only)
- user_uploaded_files/: User uploaded files (skipped)
"""

from __future__ import annotations

import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import logging

from threadlight.storage.base import StorageBackend
from threadlight.import_.chatgpt_conversations import (
    import_chatgpt_conversations,
    ChatGPTImportStats,
)

logger = logging.getLogger(__name__)


@dataclass
class ChatGPTExportStats:
    """Combined statistics from a full ChatGPT export import."""

    # Conversation stats
    conversations: ChatGPTImportStats = field(default_factory=ChatGPTImportStats)

    # File info
    zip_file: str = ""
    extracted_files: list[str] = field(default_factory=list)

    # Extracted custom instructions
    system_instructions: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"ChatGPT Export Import:\n"
            f"  Conversations: {self.conversations.conversations_imported} "
            f"({self.conversations.messages_imported} messages)\n"
            f"  Skipped: {self.conversations.conversations_skipped}\n"
            f"  System prompts found: {len(self.system_instructions)}"
        )


@dataclass
class ChatGPTExportResult:
    """Result of a full ChatGPT export import."""

    success: bool
    stats: ChatGPTExportStats
    errors: list[str] = field(default_factory=list)

    @property
    def total_conversations(self) -> int:
        return self.stats.conversations.conversations_imported

    @property
    def total_messages(self) -> int:
        return self.stats.conversations.messages_imported


def import_chatgpt_export(
    path: str | Path,
    storage: StorageBackend,
    skip_empty_conversations: bool = True,
    conversation_limit: Optional[int] = None,
    batch_size: int = 100,
    dry_run: bool = False,
    progress_callback: Optional[callable] = None,
    profile_scope: Optional[str] = None,
) -> ChatGPTExportResult:
    """
    Import from a complete ChatGPT export zip file.

    The zip file typically contains:
    - conversations.json (required)
    - user.json (ignored)
    - message_feedback.json (ignored)
    - model_comparisons.json (ignored)
    - dalle-generations/ (ignored - images not supported yet)
    - user_uploaded_files/ (ignored)

    Args:
        path: Path to chatgpt-export.zip or conversations.json directly
        storage: Storage backend to save to
        skip_empty_conversations: Skip conversations with no messages
        conversation_limit: Max conversations to import (for testing)
        batch_size: Messages per save batch
        dry_run: If True, parse but don't save
        progress_callback: Optional callback(stats) for progress
        profile_scope: Optional profile ID to scope imported conversations to

    Returns:
        ChatGPTExportResult with combined statistics
    """
    path = Path(path)

    if not path.exists():
        return ChatGPTExportResult(
            success=False,
            stats=ChatGPTExportStats(),
            errors=[f"File not found: {path}"]
        )

    stats = ChatGPTExportStats(zip_file=str(path))
    errors: list[str] = []

    # Handle direct conversations.json file
    if path.is_file() and path.suffix == ".json":
        logger.info(f"Importing directly from JSON file: {path}")
        _import_conversations_file(
            path,
            storage,
            stats,
            errors,
            skip_empty_conversations=skip_empty_conversations,
            conversation_limit=conversation_limit,
            batch_size=batch_size,
            dry_run=dry_run,
            progress_callback=progress_callback,
            profile_scope=profile_scope,
        )
        return ChatGPTExportResult(
            success=len(errors) == 0,
            stats=stats,
            errors=errors,
        )

    # Handle zip file
    if path.is_file() and path.suffix == ".zip":
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                with zipfile.ZipFile(path, "r") as zf:
                    zf.extractall(tmpdir)
                    stats.extracted_files = zf.namelist()
            except zipfile.BadZipFile as e:
                return ChatGPTExportResult(
                    success=False,
                    stats=stats,
                    errors=[f"Invalid zip file: {e}"]
                )

            # Process extracted files
            _import_from_directory(
                Path(tmpdir),
                storage,
                stats,
                errors,
                skip_empty_conversations=skip_empty_conversations,
                conversation_limit=conversation_limit,
                batch_size=batch_size,
                dry_run=dry_run,
                progress_callback=progress_callback,
                profile_scope=profile_scope,
            )

    elif path.is_dir():
        # Direct directory with extracted files
        _import_from_directory(
            path,
            storage,
            stats,
            errors,
            skip_empty_conversations=skip_empty_conversations,
            conversation_limit=conversation_limit,
            batch_size=batch_size,
            dry_run=dry_run,
            progress_callback=progress_callback,
            profile_scope=profile_scope,
        )
    else:
        return ChatGPTExportResult(
            success=False,
            stats=stats,
            errors=[f"Not a zip file, JSON file, or directory: {path}"]
        )

    return ChatGPTExportResult(
        success=len(errors) == 0,
        stats=stats,
        errors=errors,
    )


def _import_from_directory(
    directory: Path,
    storage: StorageBackend,
    stats: ChatGPTExportStats,
    errors: list[str],
    **kwargs,
) -> None:
    """Import from an extracted directory."""

    # Find conversations.json - it might be at root or in a subdirectory
    conversations_file = directory / "conversations.json"

    if not conversations_file.exists():
        # Try looking in subdirectories (some exports nest the files)
        for subdir in directory.iterdir():
            if subdir.is_dir():
                potential = subdir / "conversations.json"
                if potential.exists():
                    conversations_file = potential
                    break

    if conversations_file.exists():
        _import_conversations_file(
            conversations_file,
            storage,
            stats,
            errors,
            **kwargs,
        )
    else:
        errors.append(f"conversations.json not found in {directory}")


def _import_conversations_file(
    conversations_file: Path,
    storage: StorageBackend,
    stats: ChatGPTExportStats,
    errors: list[str],
    **kwargs,
) -> None:
    """Import from a conversations.json file."""
    logger.info(f"Importing ChatGPT conversations from {conversations_file}")

    result = import_chatgpt_conversations(
        path=conversations_file,
        storage=storage,
        batch_size=kwargs.get("batch_size", 100),
        skip_empty=kwargs.get("skip_empty_conversations", True),
        limit=kwargs.get("conversation_limit"),
        dry_run=kwargs.get("dry_run", False),
        progress_callback=kwargs.get("progress_callback"),
        profile_scope=kwargs.get("profile_scope"),
    )

    stats.conversations = result.stats
    stats.system_instructions = result.system_instructions

    if not result.success and result.error:
        errors.append(f"Conversations: {result.error}")


def preview_chatgpt_export(path: str | Path) -> dict[str, Any]:
    """
    Preview the contents of a ChatGPT export.

    Returns information about what would be imported without
    actually importing anything.
    """
    path = Path(path)

    if not path.exists():
        return {"error": f"File not found: {path}"}

    result = {
        "file": str(path),
        "file_size_mb": round(path.stat().st_size / (1024 * 1024), 2),
        "contents": [],
        "has_conversations": False,
    }

    try:
        if path.suffix == ".zip":
            with zipfile.ZipFile(path, "r") as zf:
                contents = zf.namelist()
                result["contents"] = contents
                result["has_conversations"] = any("conversations.json" in f for f in contents)

                # Count files by type
                result["file_counts"] = {
                    "json_files": len([f for f in contents if f.endswith(".json")]),
                    "dalle_images": len([f for f in contents if "dalle" in f.lower()]),
                    "user_files": len([f for f in contents if "user_uploaded" in f.lower()]),
                }

        elif path.suffix == ".json":
            result["contents"] = [path.name]
            result["has_conversations"] = "conversations" in path.name.lower()

        elif path.is_dir():
            result["contents"] = [f.name for f in path.iterdir()]
            result["has_conversations"] = (path / "conversations.json").exists()

    except Exception as e:
        result["error"] = str(e)

    return result
