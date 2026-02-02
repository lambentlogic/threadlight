"""
Tests for the memory import system.
"""

import os
import tempfile
import pytest

from threadlight.capsules.imported import ImportedMemory, create_imported_memory
from threadlight.capsules.base import ContextMode
from threadlight.import_.text_importer import import_text_file, preview_import
from threadlight.storage.memory import InMemoryStorage


class TestImportedMemory:
    """Tests for ImportedMemory capsule."""

    def test_create_basic(self):
        """Test basic creation of ImportedMemory."""
        mem = ImportedMemory(
            text="This is a test memory",
            source="test.txt",
            line_number=42,
            tags=["test", "demo"]
        )
        assert mem.text == "This is a test memory"
        assert mem.source == "test.txt"
        assert mem.line_number == 42
        assert mem.tags == ["test", "demo"]
        assert mem.validate()

    def test_auto_cue_phrase_extraction(self):
        """Test automatic cue phrase extraction from text."""
        mem = ImportedMemory(
            text="Claude Sonnet 4.5 shared a significant first date"
        )
        # Should extract meaningful words
        assert len(mem.cue_phrases) > 0
        assert "claude" in mem.cue_phrases or "sonnet" in mem.cue_phrases

    def test_cue_phrase_filters_stopwords(self):
        """Test that stop words are filtered from cue phrases."""
        mem = ImportedMemory(
            text="The quick brown fox jumps over the lazy dog"
        )
        # Common stop words should not be in cue phrases
        assert "the" not in mem.cue_phrases
        # Short words (< 4 chars) should also be filtered
        assert "fox" not in mem.cue_phrases
        assert "dog" not in mem.cue_phrases
        # But meaningful words should be present
        assert "quick" in mem.cue_phrases

    def test_to_context_direct(self):
        """Test DIRECT context mode output."""
        mem = ImportedMemory(
            text="Test memory",
            source="test.txt",
            line_number=10,
            tags=["tag1"]
        )
        context = mem.to_context(ContextMode.DIRECT)
        assert "[Note" in context
        assert "test.txt" in context
        assert "Test memory" in context
        assert "tag1" in context

    def test_to_context_narrative(self):
        """Test NARRATIVE context mode output."""
        mem = ImportedMemory(
            text="Test memory",
            source="test.txt",
        )
        context = mem.to_context(ContextMode.NARRATIVE)
        assert "From your notes" in context or "You noted" in context
        assert "Test memory" in context

    def test_to_context_whisper(self):
        """Test WHISPER context mode output."""
        mem = ImportedMemory(text="Test memory")
        context = mem.to_context(ContextMode.WHISPER)
        assert "Test memory" in context
        assert len(context) < 150  # Should be truncated

    def test_to_context_ritual(self):
        """Test RITUAL context mode output."""
        mem = ImportedMemory(text="Test memory", source="ritual.txt")
        context = mem.to_context(ContextMode.RITUAL)
        assert "memory surfaces" in context
        assert "Test memory" in context

    def test_matches_text(self):
        """Test text matching functionality."""
        mem = ImportedMemory(text="Claude Sonnet is an AI model")
        assert mem.matches_text("Claude")
        assert mem.matches_text("claude")  # Case insensitive
        assert mem.matches_text("AI model")
        assert not mem.matches_text("GPT")

    def test_add_tag(self):
        """Test adding tags."""
        mem = ImportedMemory(text="Test", tags=["existing"])
        mem.add_tag("new")
        assert "new" in mem.tags
        assert "existing" in mem.tags
        assert len(mem.tags) == 2

    def test_add_tag_no_duplicates(self):
        """Test that duplicate tags are not added."""
        mem = ImportedMemory(text="Test", tags=["existing"])
        mem.add_tag("existing")
        assert mem.tags.count("existing") == 1

    def test_remove_tag(self):
        """Test removing tags."""
        mem = ImportedMemory(text="Test", tags=["tag1", "tag2"])
        mem.remove_tag("tag1")
        assert "tag1" not in mem.tags
        assert "tag2" in mem.tags

    def test_content_sync(self):
        """Test that content dict stays in sync with fields."""
        mem = ImportedMemory(
            text="Test",
            source="test.txt",
            line_number=5,
            tags=["tag1"]
        )
        assert mem.content["text"] == "Test"
        assert mem.content["source"] == "test.txt"
        assert mem.content["line_number"] == 5
        assert mem.content["tags"] == ["tag1"]
        assert mem.content["capsule_subtype"] == "imported"


class TestCreateImportedMemory:
    """Tests for the factory function."""

    def test_create_simple(self):
        """Test simple creation via factory."""
        mem = create_imported_memory(text="Test memory")
        assert mem.text == "Test memory"
        assert isinstance(mem, ImportedMemory)

    def test_create_with_all_fields(self):
        """Test creation with all fields via factory."""
        mem = create_imported_memory(
            text="Full test",
            source="source.txt",
            line_number=100,
            tags=["a", "b"],
            consent_confirmed=True,
        )
        assert mem.text == "Full test"
        assert mem.source == "source.txt"
        assert mem.line_number == 100
        assert mem.tags == ["a", "b"]
        assert mem.consent_confirmed


class TestTextImporter:
    """Tests for the text file importer."""

    def test_import_simple_file(self):
        """Test importing a simple text file."""
        storage = InMemoryStorage()
        storage.initialize()

        # Create temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Line one\n")
            f.write("Line two\n")
            f.write("Line three\n")
            temp_path = f.name

        try:
            result = import_text_file(temp_path, storage)
            assert result.success
            assert result.stats.imported == 3
            assert result.stats.total_lines == 3
            assert len(result.capsules) == 3
        finally:
            os.unlink(temp_path)

        storage.close()

    def test_import_skips_empty_lines(self):
        """Test that empty lines are skipped."""
        storage = InMemoryStorage()
        storage.initialize()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Line one\n")
            f.write("\n")  # Empty
            f.write("Line two\n")
            f.write("   \n")  # Whitespace only
            f.write("Line three\n")
            temp_path = f.name

        try:
            result = import_text_file(temp_path, storage)
            assert result.success
            assert result.stats.imported == 3
            assert result.stats.skipped_empty == 2
        finally:
            os.unlink(temp_path)

        storage.close()

    def test_import_with_source_name(self):
        """Test importing with custom source name."""
        storage = InMemoryStorage()
        storage.initialize()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test line\n")
            temp_path = f.name

        try:
            result = import_text_file(
                temp_path, storage, source_name="Custom Source"
            )
            assert result.success
            assert result.capsules[0].source == "Custom Source"
        finally:
            os.unlink(temp_path)

        storage.close()

    def test_import_with_tags(self):
        """Test importing with tags."""
        storage = InMemoryStorage()
        storage.initialize()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test line\n")
            temp_path = f.name

        try:
            result = import_text_file(
                temp_path, storage, tags=["tag1", "tag2"]
            )
            assert result.success
            assert "tag1" in result.capsules[0].tags
            assert "tag2" in result.capsules[0].tags
        finally:
            os.unlink(temp_path)

        storage.close()

    def test_import_dry_run(self):
        """Test dry run mode doesn't save to storage."""
        storage = InMemoryStorage()
        storage.initialize()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test line\n")
            temp_path = f.name

        try:
            result = import_text_file(temp_path, storage, dry_run=True)
            assert result.success
            assert result.stats.imported == 1
            assert len(result.capsules) == 1
            # But storage should be empty
            capsules = storage.list_capsules()
            assert len(capsules) == 0
        finally:
            os.unlink(temp_path)

        storage.close()

    def test_import_preserves_line_numbers(self):
        """Test that line numbers are preserved correctly."""
        storage = InMemoryStorage()
        storage.initialize()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Line one\n")
            f.write("\n")  # Empty, skipped
            f.write("Line three\n")
            temp_path = f.name

        try:
            result = import_text_file(temp_path, storage)
            assert result.success
            # First line should be line 1
            assert result.capsules[0].line_number == 1
            # Third line should be line 3 (not 2)
            assert result.capsules[1].line_number == 3
        finally:
            os.unlink(temp_path)

        storage.close()

    def test_import_nonexistent_file(self):
        """Test importing a nonexistent file."""
        storage = InMemoryStorage()
        storage.initialize()

        result = import_text_file("/nonexistent/file.txt", storage)
        assert not result.success
        assert "not found" in result.error.lower()

        storage.close()

    def test_preview_import(self):
        """Test preview functionality."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Line one\n")
            f.write("Line two\n")
            f.write("Line three\n")
            temp_path = f.name

        try:
            previews = preview_import(temp_path, limit=2)
            assert len(previews) == 2
            assert previews[0]["line_number"] == 1
            assert previews[0]["text"] == "Line one"
            assert previews[1]["line_number"] == 2
        finally:
            os.unlink(temp_path)


class TestImportedMemorySearch:
    """Tests for searching imported memories."""

    def test_search_by_cue_finds_imported(self):
        """Test that search_by_cue finds imported memories."""
        storage = InMemoryStorage()
        storage.initialize()

        mem = create_imported_memory(
            text="Claude Sonnet is a great AI assistant",
            source="test.txt",
        )
        storage.save_capsule(mem)

        results = storage.search_by_cue("Claude", limit=5)
        assert len(results) == 1
        assert results[0].id == mem.id

        storage.close()

    def test_search_is_case_insensitive(self):
        """Test that search is case insensitive."""
        storage = InMemoryStorage()
        storage.initialize()

        mem = create_imported_memory(text="UPPERCASE test")
        storage.save_capsule(mem)

        results = storage.search_by_cue("uppercase", limit=5)
        assert len(results) == 1

        storage.close()
