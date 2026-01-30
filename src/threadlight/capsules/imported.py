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
@dataclass
class ImportedMemory(MemoryCapsule):
    """
    A raw imported memory from an external source.

    ImportedMemory capsules preserve freeform text content from
    imports (text files, documents, etc). They are searchable
    by text content and can be converted to structured types
    (relational, myth_seed, etc) later.

    Examples:
    - Memories imported from fable-memory.txt
    - Notes imported from personal archives
    - Journal entries brought into the system
    """

    type: CapsuleType = field(default=CapsuleType.CUSTOM, init=False)

    # Default to normal retention -- imported memories can decay
    retention: RetentionPolicy = field(default=RetentionPolicy.NORMAL)

    # Imported memory specific fields
    text: str = ""  # The original memory text
    source: str = ""  # Source file/origin (e.g., "fable-memory.txt")
    line_number: Optional[int] = None  # Line number in source file
    tags: list[str] = field(default_factory=list)  # Organization tags

    def __post_init__(self) -> None:
        # Set the type value for serialization
        # We use CUSTOM since IMPORTED isn't in the enum yet
        self.type = CapsuleType.CUSTOM

        if not self.content:
            self.content = {
                "text": self.text,
                "source": self.source,
                "line_number": self.line_number,
                "tags": self.tags,
                "capsule_subtype": "imported",  # Mark as imported subtype
            }
        else:
            self.text = self.content.get("text", self.text)
            self.source = self.content.get("source", self.source)
            self.line_number = self.content.get("line_number", self.line_number)
            self.tags = self.content.get("tags", self.tags)

        # Build cue phrases from text content for searchability
        if not self.cue_phrases and self.text:
            self._extract_cue_phrases()

    def _extract_cue_phrases(self) -> None:
        """Extract searchable cue phrases from the text content."""
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
        """Validate that required fields are present."""
        return bool(self.text)

    def to_context(self, mode: ContextMode = ContextMode.NARRATIVE) -> str:
        """Transform into prompt-ready context."""
        source_info = ""
        if self.source:
            source_info = f" (from {self.source}"
            if self.line_number is not None:
                source_info += f", line {self.line_number}"
            source_info += ")"

        tag_info = ""
        if self.tags:
            tag_info = f" [tags: {', '.join(self.tags)}]"

        if mode == ContextMode.DIRECT:
            return f"[Memory{source_info}] {self.text}{tag_info}"

        elif mode == ContextMode.NARRATIVE:
            return f'(You remember{source_info}: "{self.text}")'

        elif mode == ContextMode.WHISPER:
            # For whisper mode, just the essence
            return f'("{self.text[:100]}...")'

        elif mode == ContextMode.RITUAL:
            # In ritual mode, memories carry context
            return f'(A memory surfaces{source_info}: "{self.text}")'

        return self.text

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
        return query.lower() in self.text.lower()


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
