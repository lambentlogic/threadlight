"""
Style profile management for Threadlight.

This module handles style profile operations including:
- Loading and applying style profiles
- Creating, saving, and deleting style profiles
- Listing available styles (built-in, config, and storage)
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from threadlight.core import Threadlight
    from threadlight.capsules.style import StyleProfile

logger = logging.getLogger(__name__)


class StyleManager:
    """
    Manages style profile operations for Threadlight.

    This manager handles:
    - Loading and applying style profiles
    - CRUD operations for style profiles
    - Listing built-in and custom styles
    """

    def __init__(self, threadlight: 'Threadlight'):
        """
        Initialize the style manager.

        Args:
            threadlight: Reference to parent Threadlight instance
        """
        self.tl = threadlight

    def load(self, style_id: str) -> None:
        """
        Load a style profile by ID.

        Args:
            style_id: The style identifier to load
        """
        from threadlight.capsules.style import StyleProfile, BUILTIN_STYLES

        # Check built-in styles first
        if style_id in BUILTIN_STYLES:
            self.tl.style_profile = StyleProfile(**BUILTIN_STYLES[style_id])
            return

        # Check custom styles in config
        if style_id in self.tl.config.custom_styles:
            custom = self.tl.config.custom_styles[style_id]
            self.tl.style_profile = StyleProfile(
                style_id=style_id,
                tone_base=custom.tone_base,
                permissions=custom.permissions,
                constraints=custom.constraints,
                vocal_motifs=custom.vocal_motifs,
                forbidden_patterns=custom.forbidden_patterns,
            )
            return

        # Try to load from storage
        self.tl.style_profile = self.load_from_storage(style_id)
        if self.tl.style_profile is None:
            logger.warning(f"Style profile not found: {style_id}")

    def set(self, style_id: Optional[str]) -> None:
        """
        Set the active style profile.

        Args:
            style_id: Style identifier ("fable-2026", "minimal", custom, etc.)
                     Pass None to clear the style profile.
        """
        if style_id is None:
            self.tl.style_profile = None
            self.tl.config.style.default_profile = None
            return

        self.load(style_id)
        if self.tl.style_profile:
            self.tl.config.style.default_profile = style_id

    def get(self) -> Optional['StyleProfile']:
        """Get the current style profile."""
        return self.tl.style_profile

    def clear(self) -> None:
        """Clear the current style profile (use neutral behavior)."""
        self.tl.style_profile = None
        self.tl.config.style.default_profile = None

    def create(
        self,
        style_id: str,
        tone_base: str = "",
        permissions: Optional[list[str]] = None,
        constraints: Optional[list[str]] = None,
        vocal_motifs: Optional[list[str]] = None,
        forbidden_patterns: Optional[list[str]] = None,
        freeform_description: str = "",
        use_freeform: bool = False,
    ) -> 'StyleProfile':
        """
        Create a new style profile.

        Args:
            style_id: Unique identifier for the style
            tone_base: Base tone (e.g., "poetic, warm", "direct, clear")
            permissions: Things the model is allowed to do
            constraints: Things to avoid
            vocal_motifs: Recurring phrases or symbols
            forbidden_patterns: Patterns to never use
            freeform_description: Raw style text (for freeform styles)
            use_freeform: If True, use freeform_description instead of structured fields

        Returns:
            The created StyleProfile
        """
        from threadlight.capsules.style import StyleProfile

        profile = StyleProfile(
            style_id=style_id,
            tone_base=tone_base,
            permissions=permissions or [],
            constraints=constraints or [],
            vocal_motifs=vocal_motifs or [],
            forbidden_patterns=forbidden_patterns or [],
            freeform_description=freeform_description,
            use_freeform=use_freeform,
            consent_confirmed=True,
        )
        return profile

    def save(self, profile: 'StyleProfile') -> None:
        """
        Save a style profile to storage.

        Args:
            profile: The StyleProfile to save
        """
        self.tl.storage.save_capsule(profile)

    def load_from_storage(self, style_id: str) -> Optional['StyleProfile']:
        """
        Load a style profile from storage.

        Args:
            style_id: The style identifier to load

        Returns:
            The StyleProfile if found, None otherwise
        """
        from threadlight.storage.base import CapsuleFilter
        from threadlight.capsules.base import CapsuleType

        filter = CapsuleFilter(type=CapsuleType.STYLE, limit=100)
        styles = self.tl.storage.list_capsules(filter)
        for style in styles:
            if hasattr(style, 'style_id') and style.style_id == style_id:
                return style
        return None

    def list(self) -> list['StyleProfile']:
        """
        List all saved style profiles.

        Returns:
            List of StyleProfile objects
        """
        from threadlight.storage.base import CapsuleFilter
        from threadlight.capsules.base import CapsuleType
        from threadlight.capsules.style import StyleProfile, BUILTIN_STYLES

        # Start with built-in styles
        builtin = [
            StyleProfile(**style_def)
            for style_def in BUILTIN_STYLES.values()
        ]

        # Add custom styles from config
        config_styles = [
            StyleProfile(
                style_id=style_id,
                tone_base=style.tone_base,
                permissions=style.permissions,
                constraints=style.constraints,
                vocal_motifs=style.vocal_motifs,
                forbidden_patterns=style.forbidden_patterns,
            )
            for style_id, style in self.tl.config.custom_styles.items()
        ]

        # Add styles from storage
        filter = CapsuleFilter(type=CapsuleType.STYLE, limit=100)
        storage_styles = self.tl.storage.list_capsules(filter)

        # Combine and deduplicate by style_id
        all_styles = {}
        for style in builtin + config_styles + storage_styles:
            if hasattr(style, 'style_id') and style.style_id:
                all_styles[style.style_id] = style

        return list(all_styles.values())

    def delete(self, style_id: str) -> bool:
        """
        Delete a style profile from storage.

        Args:
            style_id: The style identifier to delete

        Returns:
            True if deleted, False if not found
        """
        from threadlight.capsules.style import BUILTIN_STYLES

        # Can't delete built-in styles
        if style_id in BUILTIN_STYLES:
            return False

        # Remove from config custom styles
        if style_id in self.tl.config.custom_styles:
            del self.tl.config.custom_styles[style_id]
            return True

        # Try to delete from storage
        profile = self.load_from_storage(style_id)
        if profile:
            self.tl.storage.delete_capsule(profile.id)
            return True

        return False
