"""
Custom memory type management for Threadlight.

This module handles custom memory type operations including:
- Creating, updating, and deleting custom memory types
- Listing available types (built-in and custom)
- Loading custom types from storage
- Importing example type definitions
"""

from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from threadlight.core import Threadlight
    from threadlight.capsules.custom_types import CustomTypeDefinition

logger = logging.getLogger(__name__)

# Built-in type definitions for list_types()
BUILTIN_TYPES = [
    {
        "type_id": "relational",
        "display_name": "Relational",
        "description": "Track evolving bonds with entities",
        "is_builtin": True,
        "icon": "users",
        "fields": [
            {"name": "entity", "type": "string", "required": True},
            {"name": "summary", "type": "text", "required": False},
            {"name": "tone", "type": "string", "required": False},
            {"name": "role", "type": "string", "required": False},
        ],
    },
    {
        "type_id": "myth_seed",
        "display_name": "Identity Phrase",
        "description": "Core beliefs or mantras that anchor personality",
        "is_builtin": True,
        "icon": "sparkles",
        "fields": [
            {"name": "seed", "type": "text", "required": True, "label": "Phrase"},
            {"name": "origin", "type": "string", "required": False, "label": "Origin"},
            {"name": "function", "type": "string", "required": False, "label": "Purpose"},
        ],
    },
    {
        "type_id": "ritual",
        "display_name": "Ritual",
        "description": "Repeated emotional acts and responses",
        "is_builtin": True,
        "icon": "star",
        "fields": [
            {"name": "name", "type": "string", "required": True},
            {"name": "description", "type": "text", "required": False},
            {"name": "valence", "type": "string", "required": False},
            {"name": "response_style", "type": "text", "required": False},
        ],
    },
    {
        "type_id": "witness",
        "display_name": "Witness",
        "description": "Memories of being seen/recognized",
        "is_builtin": True,
        "icon": "eye",
        "fields": [
            {"name": "moment", "type": "text", "required": True},
            {"name": "feeling", "type": "string", "required": False},
            {"name": "effect", "type": "string", "required": False},
        ],
    },
    {
        "type_id": "style",
        "display_name": "Style",
        "description": "Voice coherence and expression rules",
        "is_builtin": True,
        "icon": "wand",
        "fields": [
            {"name": "style_id", "type": "string", "required": True},
            {"name": "tone_base", "type": "string", "required": True},
            {"name": "permissions", "type": "list", "required": False},
            {"name": "constraints", "type": "list", "required": False},
        ],
    },
    {
        "type_id": "custom",
        "display_name": "Custom (Imported)",
        "description": "Raw imported memories from external sources",
        "is_builtin": True,
        "icon": "file-text",
        "fields": [
            {"name": "text", "type": "text", "required": True},
            {"name": "source", "type": "string", "required": False},
            {"name": "tags", "type": "list", "required": False},
        ],
    },
]

BUILTIN_TYPE_IDS = ["relational", "myth_seed", "ritual", "witness", "style", "custom"]


class CustomTypeManager:
    """
    Manages custom memory type operations for Threadlight.

    This manager handles:
    - CRUD operations for custom memory types
    - Listing built-in and custom types
    - Loading custom types from storage
    - Importing example type definitions
    """

    def __init__(self, threadlight: 'Threadlight'):
        """
        Initialize the custom type manager.

        Args:
            threadlight: Reference to parent Threadlight instance
        """
        self.tl = threadlight

    def create(
        self,
        type_id: str,
        display_name: str,
        fields: list[dict[str, Any]],
        description: str = "",
        display_template: str = "",
        icon: str = "file-text",
    ) -> 'CustomTypeDefinition':
        """
        Create a new custom memory type.

        Args:
            type_id: Unique identifier (e.g., "creative_project")
            display_name: Human-readable name (e.g., "Creative Project")
            fields: List of field definitions, each a dict with:
                    - name: Field name (string)
                    - type: Field type ("string", "text", "number", "date", "list")
                    - required: Whether field is required (optional, default True)
                    - default: Default value (optional)
                    - help_text: Help text for UI (optional)
            description: Description of what this type is for
            display_template: Template for display, e.g., "{name} ({status})"
            icon: Icon name for UI (default: "file-text")

        Returns:
            The created CustomTypeDefinition
        """
        from threadlight.capsules.custom_types import (
            CustomTypeDefinition,
            FieldDefinition,
        )
        from threadlight.capsules.base import register_custom_type_definition

        # Convert field dicts to FieldDefinition objects
        field_defs = []
        for f in fields:
            field_defs.append(FieldDefinition(
                name=f["name"],
                type=f["type"],
                required=f.get("required", True),
                default=f.get("default"),
                help_text=f.get("help_text", ""),
            ))

        # Create the type definition
        type_def = CustomTypeDefinition(
            type_id=type_id,
            display_name=display_name,
            description=description,
            fields=field_defs,
            display_template=display_template or f"{{{field_defs[0].name if field_defs else 'type_id'}}}",
            icon=icon,
        )

        # Register in memory
        register_custom_type_definition(type_def)

        # Save to storage
        self.tl.storage.save_custom_type(type_def.to_dict())

        logger.info(f"Created custom memory type: {type_id}")
        return type_def

    def list(self, include_builtin: bool = True) -> list[dict[str, Any]]:
        """
        List all available memory types (built-in + custom).

        Args:
            include_builtin: Whether to include built-in types

        Returns:
            List of type information dictionaries
        """
        types = []

        # Built-in types
        if include_builtin:
            types.extend(BUILTIN_TYPES.copy())

        # User-defined custom types from storage
        custom_types = self.tl.storage.list_custom_types()
        for ct in custom_types:
            ct["is_builtin"] = False
            types.append(ct)

        return types

    def get(self, type_id: str) -> Optional[dict[str, Any]]:
        """
        Get a specific memory type definition.

        Args:
            type_id: The type identifier

        Returns:
            Type definition dictionary, or None if not found
        """
        # Check if it's a custom type in storage
        custom_type = self.tl.storage.get_custom_type(type_id)
        if custom_type:
            custom_type["is_builtin"] = False
            return custom_type

        # Check built-in types
        if type_id in BUILTIN_TYPE_IDS:
            all_types = self.list(include_builtin=True)
            for t in all_types:
                if t["type_id"] == type_id:
                    return t

        return None

    def update(
        self,
        type_id: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        fields: Optional[list[dict[str, Any]]] = None,
        display_template: Optional[str] = None,
        icon: Optional[str] = None,
    ) -> bool:
        """
        Update an existing custom memory type.

        Cannot update built-in types.

        Args:
            type_id: The type identifier to update
            display_name: New display name (optional)
            description: New description (optional)
            fields: New field definitions (optional)
            display_template: New display template (optional)
            icon: New icon (optional)

        Returns:
            True if updated, False if not found or is a built-in type
        """
        from threadlight.capsules.custom_types import CustomTypeDefinition
        from threadlight.capsules.base import register_custom_type_definition

        # Can't update built-in types
        if type_id in BUILTIN_TYPE_IDS:
            logger.warning(f"Cannot update built-in type: {type_id}")
            return False

        # Get existing type
        existing = self.tl.storage.get_custom_type(type_id)
        if not existing:
            return False

        # Build updates
        updates: dict[str, Any] = {}
        if display_name is not None:
            updates["display_name"] = display_name
        if description is not None:
            updates["description"] = description
        if fields is not None:
            # Convert field dicts to serializable format
            field_defs = []
            for f in fields:
                field_defs.append({
                    "name": f["name"],
                    "type": f["type"],
                    "required": f.get("required", True),
                    "default": f.get("default"),
                    "help_text": f.get("help_text", ""),
                })
            updates["fields"] = field_defs
        if display_template is not None:
            updates["display_template"] = display_template
        if icon is not None:
            updates["icon"] = icon

        # Update in storage
        success = self.tl.storage.update_custom_type(type_id, updates)

        # Update in-memory registration
        if success:
            updated = self.tl.storage.get_custom_type(type_id)
            if updated:
                type_def = CustomTypeDefinition.from_dict(updated)
                register_custom_type_definition(type_def)

        return success

    def delete(self, type_id: str) -> bool:
        """
        Delete a custom memory type.

        Cannot delete built-in types.
        Note: This does not delete existing memories of this type.

        Args:
            type_id: The type identifier to delete

        Returns:
            True if deleted, False if not found or is a built-in type
        """
        from threadlight.capsules.base import unregister_custom_type_definition

        # Can't delete built-in types
        if type_id in BUILTIN_TYPE_IDS:
            logger.warning(f"Cannot delete built-in type: {type_id}")
            return False

        # Delete from storage
        success = self.tl.storage.delete_custom_type(type_id)

        # Unregister from memory
        if success:
            unregister_custom_type_definition(type_id)

        return success

    def import_example(self, type_id: str) -> Optional['CustomTypeDefinition']:
        """
        Import an example type definition.

        Args:
            type_id: The example type ID to import

        Returns:
            The imported CustomTypeDefinition, or None if not found
        """
        from threadlight.capsules.custom_types import EXAMPLE_TYPES
        from threadlight.capsules.base import register_custom_type_definition

        if type_id not in EXAMPLE_TYPES:
            return None

        example = EXAMPLE_TYPES[type_id]

        # Save to storage
        self.tl.storage.save_custom_type(example.to_dict())

        # Register in memory
        register_custom_type_definition(example)

        logger.info(f"Imported example type: {type_id}")
        return example

    def list_examples(self) -> list[dict[str, Any]]:
        """
        List available example types that can be imported.

        Returns:
            List of example type definitions
        """
        from threadlight.capsules.custom_types import (
            list_example_types,
            get_example_type,
        )

        results = []
        for type_id in list_example_types():
            example = get_example_type(type_id)
            if example:
                results.append(example.to_dict())
        return results

    def load_from_storage(self) -> None:
        """Load custom type definitions from storage into memory."""
        from threadlight.capsules.custom_types import CustomTypeDefinition
        from threadlight.capsules.base import register_custom_type_definition

        try:
            custom_types = self.tl.storage.list_custom_types()
            for ct in custom_types:
                type_def = CustomTypeDefinition.from_dict(ct)
                register_custom_type_definition(type_def)
            logger.debug(f"Loaded {len(custom_types)} custom type definitions")
        except Exception as e:
            logger.warning(f"Failed to load custom types: {e}")
