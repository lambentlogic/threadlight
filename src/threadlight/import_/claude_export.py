"""
Combined Claude Export importer for Threadlight.

Import from a complete claude-conversations.zip export that contains:
- conversations.json: Full conversation history
- projects.json: Project custom instructions and documents
- users.json: User information (not currently used)
"""

from __future__ import annotations

import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import logging

from threadlight.storage.base import StorageBackend
from threadlight.import_.claude_conversations import (
    import_claude_conversations,
    ConversationImportStats,
)
from threadlight.import_.claude_projects import (
    import_claude_projects,
    ProjectImportStats,
)

logger = logging.getLogger(__name__)


@dataclass
class ClaudeExportStats:
    """Combined statistics from a full Claude export import."""

    # Conversation stats
    conversations: ConversationImportStats = field(default_factory=ConversationImportStats)

    # Project stats
    projects: ProjectImportStats = field(default_factory=ProjectImportStats)

    # File info
    zip_file: str = ""
    extracted_files: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"Claude Export Import:\n"
            f"  Conversations: {self.conversations.conversations_imported} "
            f"({self.conversations.messages_imported} messages)\n"
            f"  Projects: {self.projects.total_projects} "
            f"({self.projects.docs_imported} docs, "
            f"{self.projects.style_profiles_created} styles)"
        )


@dataclass
class ClaudeExportResult:
    """Result of a full Claude export import."""

    success: bool
    stats: ClaudeExportStats
    errors: list[str] = field(default_factory=list)

    @property
    def total_conversations(self) -> int:
        return self.stats.conversations.conversations_imported

    @property
    def total_messages(self) -> int:
        return self.stats.conversations.messages_imported

    @property
    def total_projects(self) -> int:
        return self.stats.projects.total_projects


def import_claude_export(
    path: str | Path,
    storage: StorageBackend,
    import_conversations: bool = True,
    import_projects: bool = True,
    create_styles: bool = True,
    import_docs: bool = True,
    skip_empty_conversations: bool = True,
    conversation_limit: Optional[int] = None,
    batch_size: int = 100,
    dry_run: bool = False,
    progress_callback: Optional[callable] = None,
    profile_scope: Optional[str] = None,
) -> ClaudeExportResult:
    """
    Import from a complete Claude export zip file.

    The zip file should contain:
    - conversations.json
    - projects.json
    - users.json (ignored)

    Args:
        path: Path to claude-conversations.zip
        storage: Storage backend to save to
        import_conversations: Import conversation history
        import_projects: Import project data
        create_styles: Create StyleProfiles from project instructions
        import_docs: Import project documents as memories
        skip_empty_conversations: Skip conversations with no messages
        conversation_limit: Max conversations to import (for testing)
        batch_size: Messages per save batch
        dry_run: If True, parse but don't save
        progress_callback: Optional callback(stats) for progress
        profile_scope: Optional profile ID to scope imported conversations to

    Returns:
        ClaudeExportResult with combined statistics
    """
    path = Path(path)

    if not path.exists():
        return ClaudeExportResult(
            success=False,
            stats=ClaudeExportStats(),
            errors=[f"File not found: {path}"]
        )

    stats = ClaudeExportStats(zip_file=str(path))
    errors: list[str] = []

    # Handle both zip files and directories
    if path.is_file() and path.suffix == ".zip":
        # Extract to temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                with zipfile.ZipFile(path, "r") as zf:
                    zf.extractall(tmpdir)
                    stats.extracted_files = zf.namelist()
            except zipfile.BadZipFile as e:
                return ClaudeExportResult(
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
                import_conversations=import_conversations,
                import_projects=import_projects,
                create_styles=create_styles,
                import_docs=import_docs,
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
            import_conversations=import_conversations,
            import_projects=import_projects,
            create_styles=create_styles,
            import_docs=import_docs,
            skip_empty_conversations=skip_empty_conversations,
            conversation_limit=conversation_limit,
            batch_size=batch_size,
            dry_run=dry_run,
            progress_callback=progress_callback,
            profile_scope=profile_scope,
        )
    else:
        return ClaudeExportResult(
            success=False,
            stats=stats,
            errors=[f"Not a zip file or directory: {path}"]
        )

    return ClaudeExportResult(
        success=len(errors) == 0,
        stats=stats,
        errors=errors,
    )


def _import_from_directory(
    directory: Path,
    storage: StorageBackend,
    stats: ClaudeExportStats,
    errors: list[str],
    **kwargs,
) -> None:
    """Import from an extracted directory."""

    # Find and import conversations
    conversations_file = directory / "conversations.json"
    if conversations_file.exists() and kwargs.get("import_conversations", True):
        logger.info(f"Importing conversations from {conversations_file}")

        result = import_claude_conversations(
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
        if not result.success and result.error:
            errors.append(f"Conversations: {result.error}")

    # Find and import projects
    projects_file = directory / "projects.json"
    if projects_file.exists() and kwargs.get("import_projects", True):
        logger.info(f"Importing projects from {projects_file}")

        result = import_claude_projects(
            path=projects_file,
            storage=storage,
            create_styles=kwargs.get("create_styles", True),
            import_docs=kwargs.get("import_docs", True),
            dry_run=kwargs.get("dry_run", False),
        )

        stats.projects = result.stats
        if not result.success and result.error:
            errors.append(f"Projects: {result.error}")


def preview_claude_export(path: str | Path) -> dict[str, Any]:
    """
    Preview the contents of a Claude export zip file.

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
        "conversations": None,
        "projects": None,
    }

    try:
        if path.suffix == ".zip":
            with zipfile.ZipFile(path, "r") as zf:
                result["contents"] = zf.namelist()
        elif path.is_dir():
            result["contents"] = [f.name for f in path.iterdir()]

    except Exception as e:
        result["error"] = str(e)

    return result
