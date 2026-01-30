"""
Text file importer for Threadlight.

Import freeform text memories from plain text files.
Each non-empty line becomes an ImportedMemory capsule.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import logging

from threadlight.capsules.imported import ImportedMemory, create_imported_memory
from threadlight.storage.base import StorageBackend

logger = logging.getLogger(__name__)


@dataclass
class ImportStats:
    """Statistics from an import operation."""

    total_lines: int = 0
    imported: int = 0
    skipped_empty: int = 0
    errors: int = 0
    source_file: str = ""
    source_name: str = ""
    tags: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"Import complete: {self.imported} memories imported "
            f"({self.skipped_empty} empty lines skipped, {self.errors} errors)"
        )


@dataclass
class ImportResult:
    """Result of an import operation."""

    success: bool
    stats: ImportStats
    capsules: list[ImportedMemory] = field(default_factory=list)
    error: Optional[str] = None


def import_text_file(
    path: str | Path,
    storage: StorageBackend,
    source_name: Optional[str] = None,
    tags: Optional[list[str]] = None,
    dry_run: bool = False,
    skip_empty: bool = True,
    consent_confirmed: bool = True,
) -> ImportResult:
    """
    Import memories from a plain text file.

    Each non-empty line in the file becomes an ImportedMemory capsule.
    Memories are auto-confirmed (no proposal needed for imports).

    Args:
        path: Path to the text file to import
        storage: Storage backend to save memories to
        source_name: Override the source name (default: filename)
        tags: Tags to apply to all imported memories
        dry_run: If True, create capsules but don't save to storage
        skip_empty: If True, skip empty lines (default: True)
        consent_confirmed: Mark memories as consent-confirmed (default: True)

    Returns:
        ImportResult with statistics and created capsules

    Example:
        result = import_text_file(
            "fable-memory.txt",
            storage,
            source_name="Fable's memories",
            tags=["fable", "core"]
        )
        print(f"Imported {result.stats.imported} memories")
    """
    path = Path(path)

    # Validate file exists
    if not path.exists():
        return ImportResult(
            success=False,
            stats=ImportStats(),
            error=f"File not found: {path}"
        )

    if not path.is_file():
        return ImportResult(
            success=False,
            stats=ImportStats(),
            error=f"Not a file: {path}"
        )

    # Determine source name
    if source_name is None:
        source_name = path.name

    # Initialize stats
    stats = ImportStats(
        source_file=str(path),
        source_name=source_name,
        tags=tags or [],
    )

    capsules: list[ImportedMemory] = []

    try:
        # Read and process file
        with open(path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                stats.total_lines += 1

                # Strip whitespace
                text = line.strip()

                # Skip empty lines if requested
                if not text:
                    if skip_empty:
                        stats.skipped_empty += 1
                        continue
                    else:
                        # Include empty lines with placeholder text
                        text = "(empty line)"

                try:
                    # Create the capsule
                    capsule = create_imported_memory(
                        text=text,
                        source=source_name,
                        line_number=line_num,
                        tags=list(tags) if tags else [],
                        consent_confirmed=consent_confirmed,
                        consent_origin=f"import:{source_name}",
                    )

                    capsules.append(capsule)

                    # Save to storage unless dry run
                    if not dry_run:
                        storage.save_capsule(capsule)

                    stats.imported += 1

                except Exception as e:
                    logger.warning(f"Error importing line {line_num}: {e}")
                    stats.errors += 1

    except Exception as e:
        logger.error(f"Error reading file {path}: {e}")
        return ImportResult(
            success=False,
            stats=stats,
            capsules=capsules,
            error=str(e)
        )

    return ImportResult(
        success=True,
        stats=stats,
        capsules=capsules,
    )


def preview_import(
    path: str | Path,
    limit: int = 10,
) -> list[dict]:
    """
    Preview what would be imported from a text file.

    Args:
        path: Path to the text file
        limit: Maximum number of lines to preview

    Returns:
        List of dicts with line_number and text preview
    """
    path = Path(path)

    if not path.exists() or not path.is_file():
        return []

    previews = []

    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            text = line.strip()
            if text:
                previews.append({
                    "line_number": line_num,
                    "text": text[:100] + ("..." if len(text) > 100 else ""),
                })
                if len(previews) >= limit:
                    break

    return previews
