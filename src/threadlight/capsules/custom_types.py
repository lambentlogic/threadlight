"""
Custom Memory Type Definitions.

This module provides a flexible system for users to define their own memory types
with custom fields, validation, and display templates.

Custom types are stored in the database and loaded dynamically, allowing users
to extend Threadlight's memory capabilities without modifying code.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


# Valid field types
FIELD_TYPES = {
    "string": str,
    "text": str,  # Longer text, multiline
    "number": (int, float),
    "date": str,  # ISO format date string
    "list": list,  # List of strings
}


@dataclass
class FieldDefinition:
    """
    Defines a single field in a custom memory type.

    Field types:
    - string: Short text, single line
    - text: Long text, potentially multiline
    - number: Integer or float
    - date: ISO format date string
    - list: List of strings (comma-separated in UI)

    The `output_template` field defines how this field should be rendered in context
    composition. Use {field_name} as a placeholder for the field's value.
    Example: "There is {tone} in your tone when speaking of them."
    If no template is provided, the field will be rendered as "field_name: value".
    """

    name: str
    type: str  # "string", "list", "number", "date", "text"
    required: bool = True
    default: Any = None
    help_text: str = ""
    output_template: str = ""  # Shows how field appears in AI context
    label: str = ""  # Display label (optional, defaults to name)

    def __post_init__(self) -> None:
        if self.type not in FIELD_TYPES:
            raise ValueError(
                f"Invalid field type: {self.type}. "
                f"Must be one of: {', '.join(FIELD_TYPES.keys())}"
            )
        # Normalize the name
        self.name = self._normalize_name(self.name)

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Convert name to a valid identifier (snake_case)."""
        # Remove special chars, replace spaces/hyphens with underscores
        name = re.sub(r'[^\w\s-]', '', name.lower())
        name = re.sub(r'[-\s]+', '_', name)
        return name.strip('_')

    def validate_value(self, value: Any) -> tuple[bool, str]:
        """
        Validate a value against this field definition.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Handle required fields
        if self.required and (value is None or value == "" or value == []):
            return False, f"Field '{self.name}' is required"

        # None is OK for optional fields
        if value is None:
            return True, ""

        # Type validation
        if self.type == "string" or self.type == "text":
            if not isinstance(value, str):
                return False, f"Field '{self.name}' must be a string"
        elif self.type == "number":
            if not isinstance(value, (int, float)):
                return False, f"Field '{self.name}' must be a number"
        elif self.type == "date":
            if not isinstance(value, str):
                return False, f"Field '{self.name}' must be a date string"
            # Try parsing as ISO date
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return False, f"Field '{self.name}' must be a valid ISO date"
        elif self.type == "list":
            if not isinstance(value, list):
                return False, f"Field '{self.name}' must be a list"

        return True, ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "type": self.type,
            "required": self.required,
            "default": self.default,
            "help_text": self.help_text,
            "output_template": self.output_template,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FieldDefinition:
        """Deserialize from dictionary."""
        # Support both output_template (new) and template (legacy)
        output_template = data.get("output_template") or data.get("template") or ""
        return cls(
            name=data["name"],
            type=data["type"],
            required=data.get("required", True),
            default=data.get("default"),
            help_text=data.get("help_text", ""),
            output_template=output_template,
            label=data.get("label", ""),
        )

    def format_value(self, value: Any) -> str:
        """
        Format a field value using the output template.

        If an output_template is defined, substitutes {field_name} or {value}
        with the actual value. Otherwise returns a simple "name: value" format.

        Args:
            value: The field value to format

        Returns:
            Formatted string for context composition
        """
        if value is None or value == "" or value == []:
            return ""

        # Convert lists to comma-separated strings
        if isinstance(value, list):
            value_str = ", ".join(str(v) for v in value)
        else:
            value_str = str(value)

        if self.output_template:
            # Support both {field_name} and {value} as placeholders
            result = self.output_template.replace(f"{{{self.name}}}", value_str)
            result = result.replace("{value}", value_str)
            return result
        else:
            display_name = self.label or self.name
            return f"{display_name}: {value_str}"


@dataclass
class CustomTypeDefinition:
    """
    Defines a complete custom memory type.

    Custom types allow users to create structured memory types with:
    - Defined fields with types and validation
    - Display templates for rendering
    - Icons for UI recognition

    Example:
        creative_project = CustomTypeDefinition(
            type_id="creative_project",
            display_name="Creative Project",
            description="Track creative collaborations and projects",
            fields=[
                FieldDefinition("project_name", "string", required=True),
                FieldDefinition("medium", "string", required=True),
                FieldDefinition("collaborators", "list", required=False),
                FieldDefinition("status", "string", required=False, default="in progress"),
            ],
            display_template="{project_name} ({medium})",
            icon="palette",
        )
    """

    type_id: str  # Unique identifier, e.g., "creative_project"
    display_name: str  # Human-readable name, e.g., "Creative Project"
    description: str
    fields: list[FieldDefinition]
    display_template: str = "{type_id}"  # e.g., "{project_name} ({medium})"
    icon: str = "file-text"  # Icon name for UI
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        # Normalize type_id
        self.type_id = self._normalize_type_id(self.type_id)

        # Convert field dicts to FieldDefinition objects if needed
        normalized_fields = []
        for f in self.fields:
            if isinstance(f, dict):
                normalized_fields.append(FieldDefinition.from_dict(f))
            else:
                normalized_fields.append(f)
        self.fields = normalized_fields

    @staticmethod
    def _normalize_type_id(type_id: str) -> str:
        """Normalize type_id to a valid identifier."""
        # Remove special chars, lowercase, replace spaces with underscores
        type_id = re.sub(r'[^\w\s-]', '', type_id.lower())
        type_id = re.sub(r'[-\s]+', '_', type_id)
        return type_id.strip('_')

    def validate_instance(self, content: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate that content matches field definitions.

        Args:
            content: Dictionary of field values

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        for field_def in self.fields:
            value = content.get(field_def.name)
            is_valid, error = field_def.validate_value(value)
            if not is_valid:
                errors.append(error)

        return len(errors) == 0, errors

    def format_display(self, content: dict[str, Any]) -> str:
        """
        Format content using display template.

        Args:
            content: Dictionary of field values

        Returns:
            Formatted display string
        """
        try:
            # Use safe formatting that won't raise on missing keys
            result = self.display_template
            for field_def in self.fields:
                key = field_def.name
                value = content.get(key, "")
                if isinstance(value, list):
                    value = ", ".join(str(v) for v in value)
                result = result.replace(f"{{{key}}}", str(value))
            return result
        except Exception:
            # Fall back to simple format
            return f"{self.display_name}: {content}"

    def format_for_context(self, content: dict[str, Any]) -> str:
        """
        Format content using field-level templates for context composition.

        This method uses the template defined on each field to create
        natural-feeling context for the AI. Fields without templates
        are formatted as "field_name: value".

        Args:
            content: Dictionary of field values

        Returns:
            Formatted context string with all non-empty fields
        """
        parts = []
        for field_def in self.fields:
            value = content.get(field_def.name)
            formatted = field_def.format_value(value)
            if formatted:
                parts.append(formatted)

        if not parts:
            # Fall back to display template if no fields formatted
            return self.format_display(content)

        return " ".join(parts)

    def get_field(self, name: str) -> Optional[FieldDefinition]:
        """Get a field definition by name."""
        for f in self.fields:
            if f.name == name:
                return f
        return None

    def get_required_fields(self) -> list[FieldDefinition]:
        """Get all required fields."""
        return [f for f in self.fields if f.required]

    def get_default_content(self) -> dict[str, Any]:
        """Get default content with default values filled in."""
        content = {}
        for field_def in self.fields:
            if field_def.default is not None:
                content[field_def.name] = field_def.default
            elif field_def.type == "list":
                content[field_def.name] = []
        return content

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "type_id": self.type_id,
            "display_name": self.display_name,
            "description": self.description,
            "fields": [f.to_dict() for f in self.fields],
            "display_template": self.display_template,
            "icon": self.icon,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            "updated_at": self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CustomTypeDefinition:
        """Deserialize from dictionary."""
        fields = [
            FieldDefinition.from_dict(f) if isinstance(f, dict) else f
            for f in data.get("fields", [])
        ]

        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.utcnow()

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        elif updated_at is None:
            updated_at = datetime.utcnow()

        return cls(
            type_id=data["type_id"],
            display_name=data.get("display_name", data["type_id"]),
            description=data.get("description", ""),
            fields=fields,
            display_template=data.get("display_template", "{type_id}"),
            icon=data.get("icon", "file-text"),
            created_at=created_at,
            updated_at=updated_at,
        )

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> CustomTypeDefinition:
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)


# =============================================================================
# Example Type Definitions
# =============================================================================

EXAMPLE_TYPES: dict[str, CustomTypeDefinition] = {}


def _create_example_types() -> dict[str, CustomTypeDefinition]:
    """Create example type definitions."""
    examples = {}

    # Creative Project
    examples["creative_project"] = CustomTypeDefinition(
        type_id="creative_project",
        display_name="Creative Project",
        description="Track creative collaborations and artistic projects",
        fields=[
            FieldDefinition("project_name", "string", required=True, help_text="Name of the project"),
            FieldDefinition("medium", "string", required=True, help_text="Art form (music, visual, writing, etc.)"),
            FieldDefinition("collaborators", "list", required=False, help_text="People involved"),
            FieldDefinition("status", "string", required=False, default="in progress", help_text="Current status"),
            FieldDefinition("notes", "text", required=False, help_text="Additional notes"),
        ],
        display_template="{project_name} ({medium})",
        icon="palette",
    )

    # Book Note
    examples["book_note"] = CustomTypeDefinition(
        type_id="book_note",
        display_name="Book Note",
        description="Notes and thoughts from reading",
        fields=[
            FieldDefinition("title", "string", required=True, help_text="Book title"),
            FieldDefinition("author", "string", required=True, help_text="Author name"),
            FieldDefinition("quote", "text", required=False, help_text="Notable quote"),
            FieldDefinition("reflection", "text", required=True, help_text="Your thoughts"),
            FieldDefinition("page", "number", required=False, help_text="Page number"),
            FieldDefinition("tags", "list", required=False, help_text="Tags for organization"),
        ],
        display_template='"{title}" by {author}',
        icon="book-open",
    )

    # Dream Log
    examples["dream_log"] = CustomTypeDefinition(
        type_id="dream_log",
        display_name="Dream Log",
        description="Record and explore your dreams",
        fields=[
            FieldDefinition("title", "string", required=True, help_text="Brief title for the dream"),
            FieldDefinition("date", "date", required=True, help_text="When you had this dream"),
            FieldDefinition("narrative", "text", required=True, help_text="What happened in the dream"),
            FieldDefinition("symbols", "list", required=False, help_text="Recurring symbols or images"),
            FieldDefinition("feeling", "string", required=False, help_text="How you felt"),
            FieldDefinition("lucid", "string", required=False, default="no", help_text="Was it lucid?"),
        ],
        display_template="{title} ({date})",
        icon="moon",
    )

    # Location
    examples["location"] = CustomTypeDefinition(
        type_id="location",
        display_name="Location",
        description="Important places with emotional significance",
        fields=[
            FieldDefinition("name", "string", required=True, help_text="Place name"),
            FieldDefinition("description", "text", required=True, help_text="What makes this place special"),
            FieldDefinition("associated_people", "list", required=False, help_text="People connected to this place"),
            FieldDefinition("first_visit", "date", required=False, help_text="When you first visited"),
            FieldDefinition("feeling", "string", required=False, help_text="Emotional quality"),
        ],
        display_template="{name}",
        icon="map-pin",
    )

    return examples


EXAMPLE_TYPES = _create_example_types()


def get_example_type(type_id: str) -> Optional[CustomTypeDefinition]:
    """Get an example type definition by ID."""
    return EXAMPLE_TYPES.get(type_id)


def list_example_types() -> list[str]:
    """List all example type IDs."""
    return list(EXAMPLE_TYPES.keys())
