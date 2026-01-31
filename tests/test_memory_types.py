"""
Tests for memory type management including built-in type editing and hiding.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from threadlight import Threadlight
from threadlight.managers.memory_types import BUILTIN_TYPE_IDS, BUILTIN_TYPES


@pytest.fixture
def mock_provider():
    """Mock the OpenAI provider to avoid API calls."""
    with patch("threadlight.providers.openai.OpenAIProvider") as mock:
        instance = MagicMock()
        instance.chat.return_value = MagicMock(
            content="Test response",
            finish_reason="stop",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )
        mock.return_value = instance
        yield mock


class TestMemoryTypeManager:
    """Tests for CustomTypeManager operations."""

    @pytest.fixture
    def tl(self, mock_provider):
        """Create a Threadlight instance with in-memory storage."""
        tl = Threadlight(storage_backend="memory")
        yield tl
        tl.close()

    def test_list_memory_types_includes_builtins(self, tl):
        """Test that list() includes built-in types by default."""
        types = tl.memory_types.list()
        type_ids = [t["type_id"] for t in types]

        for builtin_id in BUILTIN_TYPE_IDS:
            assert builtin_id in type_ids

    def test_list_memory_types_excludes_builtins(self, tl):
        """Test that list() can exclude built-in types."""
        types = tl.memory_types.list(include_builtin=False)
        type_ids = [t["type_id"] for t in types]

        for builtin_id in BUILTIN_TYPE_IDS:
            assert builtin_id not in type_ids

    def test_get_builtin_type(self, tl):
        """Test getting a built-in type."""
        type_def = tl.memory_types.get("relational")
        assert type_def is not None
        assert type_def["type_id"] == "relational"
        assert type_def["is_builtin"] is True

    def test_create_custom_type(self, tl):
        """Test creating a custom memory type."""
        type_def = tl.create_memory_type(
            type_id="test_type",
            display_name="Test Type",
            description="A test type",
            fields=[
                {"name": "field1", "type": "string", "required": True},
                {"name": "field2", "type": "text", "required": False},
            ],
        )

        assert type_def.type_id == "test_type"
        assert type_def.display_name == "Test Type"
        assert len(type_def.fields) == 2

        # Verify it's in the list
        types = tl.memory_types.list()
        type_ids = [t["type_id"] for t in types]
        assert "test_type" in type_ids

    def test_update_custom_type(self, tl):
        """Test updating a custom memory type."""
        # Create a type first
        tl.create_memory_type(
            type_id="update_test",
            display_name="Original Name",
            description="Original desc",
            fields=[{"name": "field1", "type": "string", "required": True}],
        )

        # Update it
        success = tl.update_memory_type(
            "update_test",
            display_name="Updated Name",
            description="Updated desc",
        )
        assert success is True

        # Verify the update
        updated = tl.memory_types.get("update_test")
        assert updated["display_name"] == "Updated Name"
        assert updated["description"] == "Updated desc"

    def test_delete_custom_type(self, tl):
        """Test deleting a custom memory type."""
        # Create a type first
        tl.create_memory_type(
            type_id="delete_test",
            display_name="Delete Me",
            fields=[{"name": "field1", "type": "string", "required": True}],
        )

        # Verify it exists
        assert tl.memory_types.get("delete_test") is not None

        # Delete it
        success = tl.delete_memory_type("delete_test")
        assert success is True

        # Verify it's gone
        assert tl.memory_types.get("delete_test") is None


class TestBuiltinTypeCustomization:
    """Tests for built-in type editing and hiding."""

    @pytest.fixture
    def tl(self, mock_provider):
        """Create a Threadlight instance with in-memory storage."""
        tl = Threadlight(storage_backend="memory")
        yield tl
        tl.close()

    def test_update_builtin_type_creates_customization(self, tl):
        """Test that updating a built-in type creates a customization overlay."""
        # Update a built-in type
        success = tl.update_memory_type(
            "relational",
            display_name="Custom Relational",
            description="My custom description",
        )
        assert success is True

        # Get the type and verify customization is applied
        type_def = tl.memory_types.get("relational")
        assert type_def["display_name"] == "Custom Relational"
        assert type_def["description"] == "My custom description"
        assert type_def["is_builtin"] is True
        assert type_def.get("is_customized") is True

    def test_update_builtin_type_preserves_fields(self, tl):
        """Test that updating a built-in type with fields works."""
        # Get original field count
        original = tl.memory_types.get("relational")
        original_field_count = len(original["fields"])

        # Update with modified fields
        new_fields = [
            {"name": "entity", "type": "string", "required": True, "help_text": "Custom help"},
            {"name": "summary", "type": "text", "required": True},
        ]
        success = tl.update_memory_type("relational", fields=new_fields)
        assert success is True

        # Verify fields were updated
        updated = tl.memory_types.get("relational")
        assert len(updated["fields"]) == 2
        assert updated["fields"][0]["help_text"] == "Custom help"

    def test_hide_builtin_type(self, tl):
        """Test hiding a built-in type."""
        # Verify type is visible
        types = tl.memory_types.list()
        type_ids = [t["type_id"] for t in types]
        assert "witness" in type_ids

        # Hide it
        success = tl.delete_memory_type("witness")
        assert success is True

        # Verify it's not in regular list
        types = tl.memory_types.list()
        type_ids = [t["type_id"] for t in types]
        assert "witness" not in type_ids

        # Verify it's in hidden list
        hidden = tl.memory_types.list_hidden_builtins()
        hidden_ids = [t["type_id"] for t in hidden]
        assert "witness" in hidden_ids

    def test_restore_hidden_builtin_type(self, tl):
        """Test restoring a hidden built-in type."""
        # Hide and then restore
        tl.delete_memory_type("ritual")
        success = tl.memory_types.restore("ritual")
        assert success is True

        # Verify it's back in the list
        types = tl.memory_types.list()
        type_ids = [t["type_id"] for t in types]
        assert "ritual" in type_ids

        # Verify it's not in hidden list
        hidden = tl.memory_types.list_hidden_builtins()
        hidden_ids = [t["type_id"] for t in hidden]
        assert "ritual" not in hidden_ids

    def test_reset_builtin_type_removes_customizations(self, tl):
        """Test that resetting a built-in type removes customizations."""
        # Apply customization
        tl.update_memory_type(
            "myth_seed",
            display_name="Custom Myth Seed",
        )

        # Verify customization is applied
        customized = tl.memory_types.get("myth_seed")
        assert customized["display_name"] == "Custom Myth Seed"
        assert customized.get("is_customized") is True

        # Reset
        success = tl.memory_types.reset_builtin("myth_seed")
        assert success is True

        # Verify customization is removed
        reset = tl.memory_types.get("myth_seed")
        # Should have original display name from BUILTIN_TYPES
        original = next(t for t in BUILTIN_TYPES if t["type_id"] == "myth_seed")
        assert reset["display_name"] == original["display_name"]
        assert reset.get("is_customized") is not True

    def test_hidden_builtin_with_customization(self, tl):
        """Test that hiding a customized built-in preserves customization."""
        # Customize
        tl.update_memory_type("style", display_name="Custom Style")

        # Hide
        tl.delete_memory_type("style")

        # Restore
        tl.memory_types.restore("style")

        # Verify customization is preserved
        restored = tl.memory_types.get("style")
        assert restored["display_name"] == "Custom Style"

    def test_cannot_restore_non_builtin(self, tl):
        """Test that restoring a non-built-in type fails."""
        # Create and delete a custom type
        tl.create_memory_type(
            type_id="custom_test",
            display_name="Custom",
            fields=[{"name": "f", "type": "string", "required": True}],
        )
        tl.delete_memory_type("custom_test")

        # Try to restore it (should fail)
        success = tl.memory_types.restore("custom_test")
        assert success is False

    def test_cannot_reset_non_builtin(self, tl):
        """Test that resetting a non-built-in type fails."""
        tl.create_memory_type(
            type_id="custom_reset",
            display_name="Custom",
            fields=[{"name": "f", "type": "string", "required": True}],
        )

        success = tl.memory_types.reset_builtin("custom_reset")
        assert success is False

    def test_count_memories_by_type(self, tl):
        """Test counting memories of a specific type."""
        from threadlight.capsules.relational import RelationalThread

        # Initially should be 0
        count = tl.memory_types.count_memories_by_type("relational")
        assert count == 0

        # Create some memories directly through the storage
        capsule1 = RelationalThread(
            entity="Test1",
            summary="A test",
        )
        tl.storage.save_capsule(capsule1)

        capsule2 = RelationalThread(
            entity="Test2",
            summary="Another",
        )
        tl.storage.save_capsule(capsule2)

        # Verify counts
        assert tl.memory_types.count_memories_by_type("relational") == 2
        assert tl.memory_types.count_memories_by_type("note") == 0
        assert tl.memory_types.count_memories_by_type("myth_seed") == 0


class TestMemoryTypePersistence:
    """Tests for memory type persistence across restarts."""

    def test_customizations_persist_across_restart(self, mock_provider):
        """Test that built-in type customizations persist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")

            # First session: apply customization
            tl1 = Threadlight(storage_path=db_path)
            tl1.update_memory_type("relational", display_name="My Relational")
            tl1.close()

            # Second session: verify customization persists
            tl2 = Threadlight(storage_path=db_path)
            type_def = tl2.memory_types.get("relational")
            assert type_def["display_name"] == "My Relational"
            tl2.close()

    def test_hidden_types_persist_across_restart(self, mock_provider):
        """Test that hidden built-in types persist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")

            # First session: hide a type
            tl1 = Threadlight(storage_path=db_path)
            tl1.delete_memory_type("witness")
            tl1.close()

            # Second session: verify it's still hidden
            tl2 = Threadlight(storage_path=db_path)
            types = tl2.memory_types.list()
            type_ids = [t["type_id"] for t in types]
            assert "witness" not in type_ids

            hidden = tl2.memory_types.list_hidden_builtins()
            hidden_ids = [t["type_id"] for t in hidden]
            assert "witness" in hidden_ids
            tl2.close()

    def test_custom_types_persist_across_restart(self, mock_provider):
        """Test that custom types persist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")

            # First session: create custom type
            tl1 = Threadlight(storage_path=db_path)
            tl1.create_memory_type(
                type_id="persist_test",
                display_name="Persist Test",
                fields=[{"name": "data", "type": "string", "required": True}],
            )
            tl1.close()

            # Second session: verify it exists
            tl2 = Threadlight(storage_path=db_path)
            type_def = tl2.memory_types.get("persist_test")
            assert type_def is not None
            assert type_def["display_name"] == "Persist Test"
            tl2.close()
