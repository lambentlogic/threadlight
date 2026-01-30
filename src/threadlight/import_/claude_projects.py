"""
Claude Projects importer for Threadlight.

Import custom instructions and project documents from Claude's projects.json export.
Extracts prompt_template as custom instructions and creates StyleProfile or
ImportedMemory capsules from project documents.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import logging

from threadlight.capsules.imported import ImportedMemory, create_imported_memory
from threadlight.capsules.style import StyleProfile, create_style_profile
from threadlight.storage.base import StorageBackend

logger = logging.getLogger(__name__)


@dataclass
class ProjectImportStats:
    """Statistics from a project import operation."""

    total_projects: int = 0
    projects_with_instructions: int = 0
    style_profiles_created: int = 0
    docs_imported: int = 0
    errors: int = 0

    def __str__(self) -> str:
        return (
            f"Imported {self.total_projects} projects "
            f"({self.projects_with_instructions} with instructions, "
            f"{self.docs_imported} docs, {self.style_profiles_created} style profiles)"
        )


@dataclass
class ProjectImportResult:
    """Result of a project import operation."""

    success: bool
    stats: ProjectImportStats
    style_profiles: list[StyleProfile] = field(default_factory=list)
    doc_memories: list[ImportedMemory] = field(default_factory=list)
    custom_instructions: dict[str, str] = field(default_factory=dict)  # project_id -> instructions
    error: Optional[str] = None


@dataclass
class ParsedProject:
    """A parsed Claude project."""

    uuid: str
    name: str
    description: str
    prompt_template: str  # Custom instructions
    docs: list[dict[str, str]]  # [{filename, content}, ...]
    created_at: str
    updated_at: str


def parse_project(data: dict[str, Any]) -> ParsedProject:
    """Parse a single project from the JSON data."""
    return ParsedProject(
        uuid=data.get("uuid", ""),
        name=data.get("name", ""),
        description=data.get("description", ""),
        prompt_template=data.get("prompt_template", ""),
        docs=data.get("docs", []),
        created_at=data.get("created_at", ""),
        updated_at=data.get("updated_at", ""),
    )


def analyze_instructions_for_style(instructions: str) -> dict[str, Any]:
    """
    Analyze custom instructions to extract style-relevant components.

    Looks for patterns indicating:
    - Tone guidance (e.g., "be casual", "formal", "poetic")
    - Permissions (e.g., "you may", "you can", "feel free to")
    - Constraints (e.g., "avoid", "don't", "never")
    - Motifs (e.g., recurring phrases, symbols)

    Returns a dict suitable for creating a StyleProfile.
    """
    instructions_lower = instructions.lower()

    # Detect tone keywords
    tone_keywords = {
        "casual": ["casual", "informal", "relaxed", "conversational"],
        "formal": ["formal", "professional", "business"],
        "poetic": ["poetic", "lyrical", "metaphorical", "mythic"],
        "playful": ["playful", "fun", "witty", "humorous"],
        "analytical": ["analytical", "precise", "technical", "scientific"],
        "warm": ["warm", "friendly", "caring", "supportive"],
        "direct": ["direct", "concise", "brief", "straightforward"],
    }

    detected_tones = []
    for tone, keywords in tone_keywords.items():
        if any(kw in instructions_lower for kw in keywords):
            detected_tones.append(tone)

    tone_base = ", ".join(detected_tones) if detected_tones else "general"

    # Extract permissions (things the AI is allowed/encouraged to do)
    permission_patterns = [
        r"you (?:may|can|should|are (?:allowed|encouraged) to) ([^.!?]+)",
        r"feel free to ([^.!?]+)",
        r"it'?s? (?:ok|okay|fine) to ([^.!?]+)",
    ]
    permissions = []
    for pattern in permission_patterns:
        matches = re.findall(pattern, instructions_lower)
        permissions.extend(m.strip() for m in matches)

    # Extract constraints (things to avoid)
    constraint_patterns = [
        r"(?:avoid|don'?t|do not|never|refrain from) ([^.!?]+)",
        r"(?:shouldn'?t|should not) ([^.!?]+)",
    ]
    constraints = []
    for pattern in constraint_patterns:
        matches = re.findall(pattern, instructions_lower)
        constraints.extend(m.strip() for m in matches)

    return {
        "tone_base": tone_base,
        "permissions": permissions[:10],  # Limit to 10 most prominent
        "constraints": constraints[:10],
        "has_style_content": bool(detected_tones or permissions or constraints),
    }


def create_style_from_instructions(
    project: ParsedProject,
    style_analysis: dict[str, Any],
) -> StyleProfile:
    """Create a StyleProfile from analyzed instructions."""
    style_id = f"claude-project-{project.uuid[:8]}"

    return create_style_profile(
        style_id=style_id,
        tone_base=style_analysis["tone_base"],
        permissions=style_analysis.get("permissions", []),
        constraints=style_analysis.get("constraints", []),
        consent_confirmed=True,
        consent_origin=f"claude-project:{project.name}",
        cue_phrases=[project.name.lower()] if project.name else [],
    )


def import_claude_projects(
    path: str | Path,
    storage: StorageBackend,
    create_styles: bool = True,
    import_docs: bool = True,
    dry_run: bool = False,
) -> ProjectImportResult:
    """
    Import projects from a Claude projects.json export.

    Args:
        path: Path to projects.json
        storage: Storage backend to save capsules to
        create_styles: If True, create StyleProfiles from prompt_templates
        import_docs: If True, import project docs as ImportedMemory capsules
        dry_run: If True, parse but don't save to storage

    Returns:
        ProjectImportResult with statistics and created capsules
    """
    path = Path(path)

    if not path.exists():
        return ProjectImportResult(
            success=False,
            stats=ProjectImportStats(),
            error=f"File not found: {path}"
        )

    stats = ProjectImportStats()
    style_profiles: list[StyleProfile] = []
    doc_memories: list[ImportedMemory] = []
    custom_instructions: dict[str, str] = {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            projects_data = json.load(f)

        if not isinstance(projects_data, list):
            return ProjectImportResult(
                success=False,
                stats=stats,
                error="Expected JSON array of projects"
            )

        for project_data in projects_data:
            try:
                project = parse_project(project_data)
                stats.total_projects += 1

                # Handle prompt_template (custom instructions)
                if project.prompt_template:
                    stats.projects_with_instructions += 1
                    custom_instructions[project.uuid] = project.prompt_template

                    if create_styles:
                        style_analysis = analyze_instructions_for_style(project.prompt_template)
                        if style_analysis["has_style_content"]:
                            style = create_style_from_instructions(project, style_analysis)
                            style_profiles.append(style)
                            stats.style_profiles_created += 1

                            if not dry_run:
                                storage.save_capsule(style)

                # Handle project documents
                if import_docs and project.docs:
                    for doc in project.docs:
                        filename = doc.get("filename", "unknown")
                        content = doc.get("content", "")

                        if not content.strip():
                            continue

                        memory = create_imported_memory(
                            text=content,
                            source=f"claude-project:{project.name}/{filename}",
                            tags=["claude-project", project.name.lower()] if project.name else ["claude-project"],
                            consent_confirmed=True,
                            consent_origin=f"claude-project:{project.name}",
                        )
                        doc_memories.append(memory)
                        stats.docs_imported += 1

                        if not dry_run:
                            storage.save_capsule(memory)

            except Exception as e:
                logger.warning(f"Error processing project: {e}")
                stats.errors += 1

    except json.JSONDecodeError as e:
        return ProjectImportResult(
            success=False,
            stats=stats,
            error=f"Invalid JSON: {e}"
        )
    except Exception as e:
        logger.error(f"Error importing projects: {e}")
        return ProjectImportResult(
            success=False,
            stats=stats,
            error=str(e)
        )

    return ProjectImportResult(
        success=True,
        stats=stats,
        style_profiles=style_profiles,
        doc_memories=doc_memories,
        custom_instructions=custom_instructions,
    )


def preview_projects(path: str | Path, limit: int = 10) -> list[dict[str, Any]]:
    """
    Preview projects from a projects.json file.

    Args:
        path: Path to projects.json
        limit: Maximum number of projects to preview

    Returns:
        List of project previews with name, description, has_instructions, doc_count
    """
    path = Path(path)

    if not path.exists():
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            projects_data = json.load(f)

        previews = []
        for project_data in projects_data[:limit]:
            previews.append({
                "uuid": project_data.get("uuid", "")[:8],
                "name": project_data.get("name", "(unnamed)"),
                "description": (project_data.get("description", "")[:100] + "..."
                               if len(project_data.get("description", "")) > 100
                               else project_data.get("description", "")),
                "has_instructions": bool(project_data.get("prompt_template")),
                "doc_count": len(project_data.get("docs", [])),
            })

        return previews

    except Exception:
        return []


def get_project_instructions(path: str | Path, project_name: str) -> Optional[str]:
    """
    Get the custom instructions for a specific project by name.

    Args:
        path: Path to projects.json
        project_name: Name of the project to look for

    Returns:
        The prompt_template content if found, None otherwise
    """
    path = Path(path)

    if not path.exists():
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            projects_data = json.load(f)

        project_name_lower = project_name.lower()
        for project_data in projects_data:
            if project_data.get("name", "").lower() == project_name_lower:
                return project_data.get("prompt_template", "")

        return None

    except Exception:
        return None
