"""
Imported Memory capsules.

Raw imported memories from external sources (text files, etc).
These preserve the original text and can be converted to
structured types later.

An imported memory is the first step -- raw material for
future shaping and organization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from threadlight.capsules.base import (
    MemoryCapsule,
    CapsuleType,
    ContextMode,
    RetentionPolicy,
    register_capsule_type,
)


@register_capsule_type("imported")
@register_capsule_type("note")
@dataclass
class ImportedMemory(MemoryCapsule):
    """
    A general note or imported memory.

    This capsule type serves dual purposes:
    1. As "note" - a simple text note with optional context (about)
    2. As "imported" - raw content from external sources

    The "note" type is the default for unstructured memories that
    don't fit other types. When in doubt, use note.

    Fields for "note" type:
    - content: The note text itself (required)
    - about: What or who the note is about (optional)

    Legacy fields for "imported" type (backward compatibility):
    - text: The memory text
    - source: Source file/origin
    - line_number: Line number in source
    - tags: Organization tags
    """

    type: CapsuleType = field(default=CapsuleType.CUSTOM, init=False)

    # Default to normal retention -- these memories can decay
    retention: RetentionPolicy = field(default=RetentionPolicy.NORMAL)

    # Note type fields (new schema)
    note_content: str = ""  # The note text (named to avoid conflict with base content dict)
    about: str = ""  # What/who the note is about

    # Legacy imported memory fields (for backward compatibility)
    # Note: 'text' is inherited from base class (Optional[str] = None) for text-first architecture
    source: str = ""  # Source file/origin (e.g., "fable-memory.txt")
    line_number: Optional[int] = None  # Line number in source file
    tags: list[str] = field(default_factory=list)  # Organization tags

    def __post_init__(self) -> None:
        # Set the type value for serialization
        self.type = CapsuleType.CUSTOM

        # Restore structured fields from content if loading from storage
        if self.content:
            self.note_content = self.content.get("content", self.note_content)
            self.about = self.content.get("about", self.about)
            self.source = self.content.get("source", self.source)
            self.line_number = self.content.get("line_number", self.line_number)
            self.tags = self.content.get("tags", self.tags)
            # Restore text from content if present (loading from storage)
            if self.text is None and "text" in self.content:
                self.text = self.content["text"]

        # Text-first architecture: if text is not provided, generate from fields
        if self.text is None:
            if self.note_content:
                self.text = self.note_content
            elif self.content and self.content.get("text"):
                # Legacy content dict had "text" key
                self.text = self.content["text"]

        # Always sync structured fields to content dict for storage/serialization
        if self.note_content or self.about:
            # New "note" schema
            self.content = {
                "content": self.note_content,
                "about": self.about,
            }
        else:
            # Legacy "imported" schema
            self.content = {
                "source": self.source,
                "line_number": self.line_number,
                "tags": self.tags,
                "capsule_subtype": "imported",
            }
        # Also store text in content for persistence
        if self.text:
            self.content["text"] = self.text

        # Build cue phrases from text content for searchability
        if not self.cue_phrases and self.text:
            self._extract_cue_phrases()

    def _extract_cue_phrases(self) -> None:
        """Extract searchable cue phrases from the text content."""
        if not self.text:
            return
        # Split into words and extract significant ones
        words = self.text.lower().split()

        # Remove common stop words and keep significant terms
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
            "for", "of", "with", "by", "from", "as", "is", "was", "are",
            "were", "been", "be", "have", "has", "had", "do", "does", "did",
            "will", "would", "could", "should", "may", "might", "can",
            "this", "that", "these", "those", "it", "its", "they", "them",
            "their", "he", "she", "his", "her", "we", "our", "you", "your",
        }

        # Clean and filter words
        significant_words = []
        for word in words:
            # Strip punctuation
            clean_word = word.strip(".,!?\"'()[]{};:-")
            # Keep words that are long enough and not stop words
            if len(clean_word) >= 4 and clean_word not in stop_words:
                significant_words.append(clean_word)

        # Take up to 15 unique significant words as cue phrases
        seen = set()
        unique_cues = []
        for word in significant_words:
            if word not in seen:
                seen.add(word)
                unique_cues.append(word)
                if len(unique_cues) >= 15:
                    break

        self.cue_phrases = unique_cues

    def validate(self) -> bool:
        """Validate that required fields are present.

        Text-first: valid if we have text OR note_content (for backward compatibility).
        """
        return bool(self.text or self.note_content)

    def get_text(self) -> str:
        """Get the main text content, supporting both schemas.

        Text-first: checks self.text (base class field) first, then
        falls back to self.note_content for backward compatibility.
        """
        return self.text or self.note_content or ""

    def to_context(self, mode: ContextMode = ContextMode.NARRATIVE) -> str:
        """Transform into prompt-ready context.

        Text-first: When text field exists, use it directly instead of
        reconstructing from structured fields. Falls back to field-based
        construction for backward compatibility with memories that don't
        have a text field.
        """
        text = self.get_text()

        # Build context info from either schema
        about_info = ""
        source_info = ""
        if self.about:
            about_info = f" about {self.about}"
        if self.source:
            source_info = self.source

        tag_info = ""
        if self.tags:
            tag_info = f" [tags: {', '.join(self.tags)}]"

        if mode == ContextMode.DIRECT:
            # If we have text, use it directly with minimal framing
            if self.text:
                context_suffix = about_info if about_info else (f" ({source_info})" if source_info else "")
                return f"[Note{context_suffix}] {self.text}{tag_info}"
            # Fallback: use note_content
            context_suffix = about_info if about_info else (f" ({source_info})" if source_info else "")
            return f"[Note{context_suffix}] {text}{tag_info}"

        elif mode == ContextMode.NARRATIVE:
            # If we have text, wrap it in narrative framing
            if self.text:
                if about_info:
                    return f'(You noted{about_info}: "{self.text}")'
                else:
                    return f'(From your notes: "{self.text}")'
            # Fallback: reconstruct from fields
            if about_info:
                return f'(You noted{about_info}: "{text}")'
            else:
                return f'(From your notes: "{text}")'

        elif mode == ContextMode.WHISPER:
            # For whisper mode, just the essence
            return f'("{text[:100]}...")'

        elif mode == ContextMode.RITUAL:
            # In ritual mode, memories carry context
            if self.text:
                if about_info:
                    return f'(A note surfaces{about_info}: "{self.text}")'
                else:
                    return f'(A memory surfaces: "{self.text}")'
            # Fallback
            if about_info:
                return f'(A note surfaces{about_info}: "{text}")'
            else:
                return f'(A memory surfaces: "{text}")'

        return text

    def add_tag(self, tag: str) -> None:
        """Add a tag to this memory."""
        if tag not in self.tags:
            self.tags.append(tag)
            self.content["tags"] = self.tags
            self.touch()

    def remove_tag(self, tag: str) -> None:
        """Remove a tag from this memory."""
        if tag in self.tags:
            self.tags.remove(tag)
            self.content["tags"] = self.tags
            self.touch()

    def matches_text(self, query: str) -> bool:
        """Check if this memory's text contains the query (case-insensitive)."""
        text = self.get_text()
        return query.lower() in text.lower() if text else False


def create_imported_memory(
    text: str,
    source: str = "",
    line_number: Optional[int] = None,
    tags: Optional[list[str]] = None,
    **kwargs: Any
) -> ImportedMemory:
    """Factory function for creating imported memories."""
    return ImportedMemory(
        text=text,
        source=source,
        line_number=line_number,
        tags=tags or [],
        **kwargs
    )
