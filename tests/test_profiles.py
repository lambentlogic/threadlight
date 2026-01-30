"""Tests for profile infrastructure."""

import pytest
import tempfile
import os
from datetime import datetime, timedelta

from threadlight.profiles.profile import (
    Profile,
    ModelStrategy,
    AlloyedConfig,
    RoutingRule,
    RitualDepth,
)
from threadlight.profiles.manager import ProfileManager
from threadlight.storage.memory import InMemoryStorage
from threadlight.storage.sqlite import SQLiteStorage


# ============================================================================
# Profile Data Class Tests
# ============================================================================


class TestProfile:
    """Tests for Profile data class."""

    def test_create_simple_profile(self):
        """Test creating a profile with minimal fields."""
        profile = Profile(
            id="test-profile",
            name="Test Profile",
        )

        assert profile.id == "test-profile"
        assert profile.name == "Test Profile"
        assert profile.description == ""
        assert profile.primary_model == "nous-research/hermes-3-llama-3.1-405b"
        assert profile.temperature == 0.7
        assert profile.memory_scope == "test-profile"  # Should default to profile ID

    def test_create_profile_with_all_fields(self):
        """Test creating a profile with all fields."""
        profile = Profile(
            id="full-profile",
            name="Full Profile",
            description="A complete profile",
            avatar="/path/to/avatar.png",
            color="#6366f1",
            primary_model="anthropic/claude-3-opus",
            temperature=0.5,
            max_tokens=4096,
            top_p=0.9,
            system_prompt="You are a helpful assistant.",
            style_profile_id="style-123",
            memory_scope="custom-scope",
            access_shared_memories=False,
        )

        assert profile.id == "full-profile"
        assert profile.name == "Full Profile"
        assert profile.description == "A complete profile"
        assert profile.avatar == "/path/to/avatar.png"
        assert profile.color == "#6366f1"
        assert profile.primary_model == "anthropic/claude-3-opus"
        assert profile.temperature == 0.5
        assert profile.max_tokens == 4096
        assert profile.top_p == 0.9
        assert profile.system_prompt == "You are a helpful assistant."
        assert profile.style_profile_id == "style-123"
        assert profile.memory_scope == "custom-scope"
        assert profile.access_shared_memories is False

    def test_default_alloyed_config(self):
        """Test that alloyed_config is initialized by default."""
        profile = Profile(id="test", name="Test")

        assert profile.alloyed_config is not None
        assert profile.alloyed_config.strategy == ModelStrategy.SINGLE
        assert profile.alloyed_config.model_pool == [profile.primary_model]

    def test_default_ritual_settings(self):
        """Test that ritual settings have sensible defaults."""
        profile = Profile(id="test", name="Test")

        # Default to functional (efficient shortcuts)
        assert profile.ritual_depth == RitualDepth.FUNCTIONAL
        # Resonance tracking off by default
        assert profile.track_ritual_resonance is False

    def test_ceremonial_ritual_profile(self):
        """Test creating a profile with ceremonial ritual depth (Fable-like)."""
        profile = Profile(
            id="fable",
            name="Fable",
            ritual_depth=RitualDepth.CEREMONIAL,
            track_ritual_resonance=True,
        )

        assert profile.ritual_depth == RitualDepth.CEREMONIAL
        assert profile.track_ritual_resonance is True

    def test_functional_ritual_profile(self):
        """Test creating a profile with functional ritual depth (GLaDOS-like)."""
        profile = Profile(
            id="glados",
            name="GLaDOS",
            ritual_depth=RitualDepth.FUNCTIONAL,
            track_ritual_resonance=False,
        )

        assert profile.ritual_depth == RitualDepth.FUNCTIONAL
        assert profile.track_ritual_resonance is False

    def test_minimal_ritual_profile(self):
        """Test creating a profile with minimal ritual depth."""
        profile = Profile(
            id="debug-buddy",
            name="Debug Buddy",
            ritual_depth=RitualDepth.MINIMAL,
            track_ritual_resonance=False,
        )

        assert profile.ritual_depth == RitualDepth.MINIMAL

    def test_model_strategy_property(self):
        """Test the model_strategy property."""
        profile = Profile(
            id="test",
            name="Test",
            alloyed_config=AlloyedConfig(
                strategy=ModelStrategy.ROUND_ROBIN,
                model_pool=["model-a", "model-b"],
            ),
        )

        assert profile.model_strategy == ModelStrategy.ROUND_ROBIN

    def test_model_pool_property(self):
        """Test the model_pool property."""
        profile = Profile(
            id="test",
            name="Test",
            alloyed_config=AlloyedConfig(
                strategy=ModelStrategy.WEIGHTED,
                model_pool=["model-a", "model-b", "model-c"],
            ),
        )

        assert profile.model_pool == ["model-a", "model-b", "model-c"]

    def test_profile_to_dict(self):
        """Test serializing a profile to dict."""
        profile = Profile(
            id="test-id",
            name="Test Name",
            description="Test description",
            temperature=0.8,
        )

        data = profile.to_dict()

        assert data["id"] == "test-id"
        assert data["name"] == "Test Name"
        assert data["description"] == "Test description"
        assert data["temperature"] == 0.8
        assert "alloyed_config" in data
        assert "created_at" in data
        assert "updated_at" in data
        # Ritual settings should be included
        assert "ritual_depth" in data
        assert "track_ritual_resonance" in data

    def test_profile_to_dict_with_ritual_settings(self):
        """Test serializing a profile with ritual settings."""
        profile = Profile(
            id="fable",
            name="Fable",
            ritual_depth=RitualDepth.CEREMONIAL,
            track_ritual_resonance=True,
        )

        data = profile.to_dict()

        assert data["ritual_depth"] == "ceremonial"
        assert data["track_ritual_resonance"] is True

    def test_profile_from_dict(self):
        """Test deserializing a profile from dict."""
        data = {
            "id": "restored-id",
            "name": "Restored Profile",
            "description": "Restored description",
            "primary_model": "openai/gpt-4",
            "temperature": 0.9,
            "max_tokens": 2048,
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-02T00:00:00",
        }

        profile = Profile.from_dict(data)

        assert profile.id == "restored-id"
        assert profile.name == "Restored Profile"
        assert profile.description == "Restored description"
        assert profile.primary_model == "openai/gpt-4"
        assert profile.temperature == 0.9
        assert profile.max_tokens == 2048
        # Should have default ritual settings
        assert profile.ritual_depth == RitualDepth.FUNCTIONAL
        assert profile.track_ritual_resonance is False

    def test_profile_from_dict_with_ritual_settings(self):
        """Test deserializing a profile with ritual settings."""
        data = {
            "id": "fable",
            "name": "Fable",
            "ritual_depth": "ceremonial",
            "track_ritual_resonance": True,
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-02T00:00:00",
        }

        profile = Profile.from_dict(data)

        assert profile.ritual_depth == RitualDepth.CEREMONIAL
        assert profile.track_ritual_resonance is True

    def test_profile_from_dict_invalid_ritual_depth(self):
        """Test that invalid ritual_depth falls back to functional."""
        data = {
            "id": "test",
            "name": "Test",
            "ritual_depth": "invalid_value",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-02T00:00:00",
        }

        profile = Profile.from_dict(data)

        # Should fall back to functional
        assert profile.ritual_depth == RitualDepth.FUNCTIONAL

    def test_profile_to_json_and_from_json(self):
        """Test JSON serialization round-trip."""
        original = Profile(
            id="json-test",
            name="JSON Test",
            description="Testing JSON serialization",
        )

        json_str = original.to_json()
        restored = Profile.from_json(json_str)

        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.description == original.description


# ============================================================================
# AlloyedConfig Tests
# ============================================================================


class TestAlloyedConfig:
    """Tests for AlloyedConfig."""

    def test_default_config(self):
        """Test default alloyed config."""
        config = AlloyedConfig()

        assert config.strategy == ModelStrategy.SINGLE
        assert config.model_pool == []
        assert config.current_index == 0
        assert config.turn_count == 0

    def test_config_with_routing_rules(self):
        """Test config with routing rules."""
        rules = [
            RoutingRule(
                match_type="keyword",
                pattern="code",
                target_model="openai/gpt-4",
                priority=10,
            ),
            RoutingRule(
                match_type="length",
                pattern=">1000",
                target_model="anthropic/claude-3-opus",
                priority=5,
            ),
        ]

        config = AlloyedConfig(
            strategy=ModelStrategy.ROUTED,
            model_pool=["openai/gpt-4", "anthropic/claude-3-opus"],
            routing_rules=rules,
        )

        assert config.strategy == ModelStrategy.ROUTED
        assert len(config.routing_rules) == 2
        assert config.routing_rules[0].priority == 10

    def test_config_to_dict_and_from_dict(self):
        """Test AlloyedConfig serialization round-trip."""
        original = AlloyedConfig(
            strategy=ModelStrategy.WEIGHTED,
            model_pool=["model-a", "model-b"],
            weights={"model-a": 0.7, "model-b": 0.3},
            current_index=5,
            turn_count=100,
            model_counts={"model-a": 70, "model-b": 30},
        )

        data = original.to_dict()
        restored = AlloyedConfig.from_dict(data)

        assert restored.strategy == original.strategy
        assert restored.model_pool == original.model_pool
        assert restored.weights == original.weights
        assert restored.current_index == original.current_index
        assert restored.turn_count == original.turn_count
        assert restored.model_counts == original.model_counts


# ============================================================================
# RoutingRule Tests
# ============================================================================


class TestRoutingRule:
    """Tests for RoutingRule."""

    def test_create_rule(self):
        """Test creating a routing rule."""
        rule = RoutingRule(
            match_type="keyword",
            pattern="python",
            target_model="openai/gpt-4",
            priority=5,
        )

        assert rule.match_type == "keyword"
        assert rule.pattern == "python"
        assert rule.target_model == "openai/gpt-4"
        assert rule.priority == 5

    def test_rule_to_dict_and_from_dict(self):
        """Test RoutingRule serialization."""
        original = RoutingRule(
            match_type="regex",
            pattern=r"\bcode\b",
            target_model="model-x",
            priority=10,
        )

        data = original.to_dict()
        restored = RoutingRule.from_dict(data)

        assert restored.match_type == original.match_type
        assert restored.pattern == original.pattern
        assert restored.target_model == original.target_model
        assert restored.priority == original.priority


# ============================================================================
# ProfileManager Tests (with InMemoryStorage)
# ============================================================================


class TestProfileManagerInMemory:
    """Tests for ProfileManager with InMemoryStorage."""

    @pytest.fixture
    def storage(self):
        s = InMemoryStorage()
        s.initialize()
        yield s
        s.close()

    @pytest.fixture
    def manager(self, storage):
        return ProfileManager(storage)

    def test_create_profile(self, manager):
        """Test creating a profile via manager."""
        profile = manager.create(
            name="New Profile",
            description="Created via manager",
            primary_model="openai/gpt-4",
        )

        assert profile.name == "New Profile"
        assert profile.description == "Created via manager"
        assert profile.primary_model == "openai/gpt-4"
        assert profile.id is not None

    def test_create_profile_with_custom_id(self, manager):
        """Test creating a profile with a custom ID."""
        profile = manager.create(
            name="Custom ID Profile",
            profile_id="my-custom-id",
        )

        assert profile.id == "my-custom-id"

    def test_get_profile(self, manager):
        """Test retrieving a profile."""
        created = manager.create(name="Get Test")
        retrieved = manager.get(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == "Get Test"

    def test_get_nonexistent_profile(self, manager):
        """Test retrieving a nonexistent profile returns None."""
        result = manager.get("nonexistent-id")
        assert result is None

    def test_update_profile(self, manager):
        """Test updating a profile."""
        profile = manager.create(name="Original Name")
        profile.name = "Updated Name"
        profile.temperature = 0.9

        manager.update(profile)
        retrieved = manager.get(profile.id)

        assert retrieved.name == "Updated Name"
        assert retrieved.temperature == 0.9

    def test_delete_profile(self, manager):
        """Test deleting a profile."""
        profile = manager.create(name="To Delete")
        profile_id = profile.id

        result = manager.delete(profile_id)

        assert result is True
        assert manager.get(profile_id) is None

    def test_delete_nonexistent_profile(self, manager):
        """Test deleting a nonexistent profile returns False."""
        result = manager.delete("nonexistent-id")
        assert result is False

    def test_list_profiles(self, manager):
        """Test listing all profiles."""
        manager.create(name="Profile 1")
        manager.create(name="Profile 2")
        manager.create(name="Profile 3")

        profiles = manager.list()

        assert len(profiles) == 3
        names = [p.name for p in profiles]
        assert "Profile 1" in names
        assert "Profile 2" in names
        assert "Profile 3" in names

    def test_switch_to_profile(self, manager):
        """Test switching to a profile."""
        profile = manager.create(name="Switch Target")

        result = manager.switch_to(profile.id)

        assert result.id == profile.id
        assert result.last_used_at is not None
        assert manager.get_active().id == profile.id

    def test_switch_to_nonexistent_profile(self, manager):
        """Test switching to nonexistent profile raises error."""
        with pytest.raises(ValueError):
            manager.switch_to("nonexistent-id")

    def test_get_active_profile(self, manager):
        """Test getting the active profile."""
        # Initially no active profile
        assert manager.get_active() is None

        # Switch to a profile
        profile = manager.create(name="Active Test")
        manager.switch_to(profile.id)

        active = manager.get_active()
        assert active is not None
        assert active.id == profile.id

    def test_clear_cache(self, manager, storage):
        """Test clearing the profile cache."""
        profile = manager.create(name="Cache Test")

        # Profile should be in cache
        assert profile.id in manager._cache

        # Clear cache
        manager.clear_cache()

        # Cache should be empty
        assert len(manager._cache) == 0

        # But profile should still be retrievable from storage
        retrieved = manager.get(profile.id)
        assert retrieved is not None

    def test_delete_clears_active_profile(self, manager):
        """Test that deleting the active profile clears it."""
        profile = manager.create(name="Active Delete Test")
        manager.switch_to(profile.id)

        assert manager.get_active() is not None

        manager.delete(profile.id)

        assert manager.get_active() is None


# ============================================================================
# SQLite Storage Profile Tests
# ============================================================================


class TestSQLiteProfileStorage:
    """Tests for profile operations in SQLite storage."""

    @pytest.fixture
    def storage(self):
        # Create a temporary database file
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        s = SQLiteStorage(path=path)
        s.initialize()
        yield s
        s.close()

        # Clean up
        os.unlink(path)

    def test_save_and_get_profile(self, storage):
        """Test saving and retrieving a profile."""
        profile = Profile(
            id="sqlite-test",
            name="SQLite Test Profile",
            description="Testing SQLite storage",
            temperature=0.8,
        )

        storage.save_profile(profile)
        retrieved = storage.get_profile("sqlite-test")

        assert retrieved is not None
        assert retrieved.id == "sqlite-test"
        assert retrieved.name == "SQLite Test Profile"
        assert retrieved.description == "Testing SQLite storage"
        assert retrieved.temperature == 0.8

    def test_save_profile_with_alloyed_config(self, storage):
        """Test saving a profile with alloyed config as JSON."""
        config = AlloyedConfig(
            strategy=ModelStrategy.ROUND_ROBIN,
            model_pool=["model-a", "model-b", "model-c"],
            current_index=2,
            turn_count=50,
            model_counts={"model-a": 20, "model-b": 15, "model-c": 15},
        )

        profile = Profile(
            id="alloyed-test",
            name="Alloyed Profile",
            alloyed_config=config,
        )

        storage.save_profile(profile)
        retrieved = storage.get_profile("alloyed-test")

        assert retrieved is not None
        assert retrieved.alloyed_config is not None
        assert retrieved.alloyed_config.strategy == ModelStrategy.ROUND_ROBIN
        assert retrieved.alloyed_config.model_pool == ["model-a", "model-b", "model-c"]
        assert retrieved.alloyed_config.current_index == 2
        assert retrieved.alloyed_config.turn_count == 50
        assert retrieved.alloyed_config.model_counts == {"model-a": 20, "model-b": 15, "model-c": 15}

    def test_save_profile_with_routing_rules(self, storage):
        """Test saving a profile with routing rules."""
        rules = [
            RoutingRule(match_type="keyword", pattern="code", target_model="model-a", priority=10),
            RoutingRule(match_type="regex", pattern=r"\b\d{4}\b", target_model="model-b", priority=5),
        ]

        config = AlloyedConfig(
            strategy=ModelStrategy.ROUTED,
            model_pool=["model-a", "model-b"],
            routing_rules=rules,
        )

        profile = Profile(
            id="routed-test",
            name="Routed Profile",
            alloyed_config=config,
        )

        storage.save_profile(profile)
        retrieved = storage.get_profile("routed-test")

        assert retrieved is not None
        assert len(retrieved.alloyed_config.routing_rules) == 2
        assert retrieved.alloyed_config.routing_rules[0].match_type == "keyword"
        assert retrieved.alloyed_config.routing_rules[0].pattern == "code"
        assert retrieved.alloyed_config.routing_rules[1].match_type == "regex"

    def test_update_profile(self, storage):
        """Test updating a profile."""
        profile = Profile(
            id="update-test",
            name="Original Name",
            temperature=0.5,
        )
        storage.save_profile(profile)

        # Update the profile
        profile.name = "Updated Name"
        profile.temperature = 0.9
        profile.updated_at = datetime.now()
        storage.update_profile(profile)

        retrieved = storage.get_profile("update-test")

        assert retrieved.name == "Updated Name"
        assert retrieved.temperature == 0.9

    def test_delete_profile(self, storage):
        """Test deleting a profile."""
        profile = Profile(id="delete-test", name="To Delete")
        storage.save_profile(profile)

        result = storage.delete_profile("delete-test")

        assert result is True
        assert storage.get_profile("delete-test") is None

    def test_delete_nonexistent_profile(self, storage):
        """Test deleting a nonexistent profile returns False."""
        result = storage.delete_profile("nonexistent")
        assert result is False

    def test_list_profiles(self, storage):
        """Test listing all profiles."""
        profiles = [
            Profile(id="list-1", name="Profile 1"),
            Profile(id="list-2", name="Profile 2"),
            Profile(id="list-3", name="Profile 3"),
        ]

        for p in profiles:
            storage.save_profile(p)

        result = storage.list_profiles()

        assert len(result) == 3
        ids = [p.id for p in result]
        assert "list-1" in ids
        assert "list-2" in ids
        assert "list-3" in ids

    def test_list_profiles_ordered_by_updated(self, storage):
        """Test that profiles are ordered by updated_at descending."""
        import time

        p1 = Profile(id="order-1", name="First")
        storage.save_profile(p1)
        time.sleep(0.01)

        p2 = Profile(id="order-2", name="Second")
        storage.save_profile(p2)
        time.sleep(0.01)

        p3 = Profile(id="order-3", name="Third")
        storage.save_profile(p3)

        result = storage.list_profiles()

        # Most recently updated should be first
        assert result[0].id == "order-3"
        assert result[1].id == "order-2"
        assert result[2].id == "order-1"

    def test_get_nonexistent_profile(self, storage):
        """Test getting a nonexistent profile returns None."""
        result = storage.get_profile("does-not-exist")
        assert result is None

    def test_profile_timestamps_preserved(self, storage):
        """Test that timestamps are properly preserved."""
        created = datetime(2024, 1, 1, 12, 0, 0)
        updated = datetime(2024, 6, 15, 18, 30, 0)
        last_used = datetime(2024, 6, 20, 10, 0, 0)

        profile = Profile(
            id="timestamp-test",
            name="Timestamp Test",
            created_at=created,
            updated_at=updated,
            last_used_at=last_used,
        )

        storage.save_profile(profile)
        retrieved = storage.get_profile("timestamp-test")

        assert retrieved.created_at == created
        assert retrieved.updated_at == updated
        assert retrieved.last_used_at == last_used

    def test_profile_null_optional_fields(self, storage):
        """Test profile with null optional fields."""
        profile = Profile(
            id="null-test",
            name="Null Test",
            avatar=None,
            color=None,
            max_tokens=None,
            style_profile_id=None,
            last_used_at=None,
        )

        storage.save_profile(profile)
        retrieved = storage.get_profile("null-test")

        assert retrieved.avatar is None
        assert retrieved.color is None
        assert retrieved.max_tokens is None
        assert retrieved.style_profile_id is None
        assert retrieved.last_used_at is None


# ============================================================================
# ProfileManager with SQLite Tests
# ============================================================================


class TestProfileManagerSQLite:
    """Tests for ProfileManager with SQLite storage."""

    @pytest.fixture
    def storage(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        s = SQLiteStorage(path=path)
        s.initialize()
        yield s
        s.close()
        os.unlink(path)

    @pytest.fixture
    def manager(self, storage):
        return ProfileManager(storage)

    def test_full_workflow(self, manager):
        """Test a complete workflow with ProfileManager and SQLite."""
        # Create a profile
        profile = manager.create(
            name="Fable",
            description="A creative writing assistant",
            primary_model="anthropic/claude-3-opus",
            system_prompt="You are Fable, a creative writing assistant.",
            color="#6366f1",
            temperature=0.9,
        )

        # Verify creation
        assert profile.id is not None
        assert profile.name == "Fable"

        # List profiles
        profiles = manager.list()
        assert len(profiles) == 1

        # Switch to the profile
        active = manager.switch_to(profile.id)
        assert active.last_used_at is not None

        # Update the profile
        active.description = "Updated description"
        manager.update(active)

        # Verify update persisted
        retrieved = manager.get(profile.id)
        assert retrieved.description == "Updated description"

        # Create another profile
        manager.create(name="Debug Buddy", description="A debugging assistant")
        profiles = manager.list()
        assert len(profiles) == 2

        # Delete the first profile
        manager.delete(profile.id)
        profiles = manager.list()
        assert len(profiles) == 1
        assert profiles[0].name == "Debug Buddy"

    def test_export_import_profile(self, manager):
        """Test exporting and importing a profile."""
        # Create a profile
        original = manager.create(
            name="Export Test",
            description="A profile for export testing",
            temperature=0.8,
        )

        # Export it
        export_data = manager.export_profile(original.id)

        assert "profile" in export_data
        assert export_data["version"] == "1.0"
        assert export_data["profile"]["name"] == "Export Test"

        # Import it (creates new profile with new ID)
        imported = manager.import_profile(export_data)

        assert imported.id != original.id  # New ID generated
        assert imported.name == "Export Test"
        assert imported.description == "A profile for export testing"
        assert imported.temperature == 0.8

        # Both should exist
        profiles = manager.list()
        assert len(profiles) == 2


# ============================================================================
# Philosophy Fields Tests
# ============================================================================


class TestPhilosophyFields:
    """Tests for freeform philosophy fields on profiles."""

    def test_profile_with_philosophy_fields(self):
        """Test creating a profile with philosophy fields."""
        profile = Profile(
            id="fable-profile",
            name="Fable",
            philosophy="presence-centered, mythically-grounded, honors silence",
            approach_to_rituals="deep emotional scaffolding",
        )

        assert profile.philosophy == "presence-centered, mythically-grounded, honors silence"
        assert profile.approach_to_rituals == "deep emotional scaffolding"

    def test_profile_philosophy_defaults_to_empty(self):
        """Test that philosophy fields default to empty strings."""
        profile = Profile(
            id="test",
            name="Test",
        )

        assert profile.philosophy == ""
        assert profile.approach_to_rituals == ""

    def test_profile_to_dict_includes_philosophy(self):
        """Test that to_dict includes philosophy fields."""
        profile = Profile(
            id="test",
            name="Test",
            philosophy="efficient, task-focused",
            approach_to_rituals="minimal ceremony",
        )

        data = profile.to_dict()

        assert "philosophy" in data
        assert data["philosophy"] == "efficient, task-focused"
        assert "approach_to_rituals" in data
        assert data["approach_to_rituals"] == "minimal ceremony"

    def test_profile_from_dict_with_philosophy(self):
        """Test deserializing a profile with philosophy fields."""
        data = {
            "id": "test",
            "name": "Test",
            "philosophy": "playful, creative",
            "approach_to_rituals": "whimsical and exploratory",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-02T00:00:00",
        }

        profile = Profile.from_dict(data)

        assert profile.philosophy == "playful, creative"
        assert profile.approach_to_rituals == "whimsical and exploratory"

    def test_profile_from_dict_missing_philosophy(self):
        """Test that missing philosophy fields default to empty strings."""
        data = {
            "id": "test",
            "name": "Test",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-02T00:00:00",
        }

        profile = Profile.from_dict(data)

        assert profile.philosophy == ""
        assert profile.approach_to_rituals == ""

    def test_profile_json_roundtrip_with_philosophy(self):
        """Test JSON serialization round-trip preserves philosophy fields."""
        original = Profile(
            id="json-test",
            name="JSON Test",
            philosophy="resonance-aware, presence-based",
            approach_to_rituals="full ceremonial depth",
        )

        json_str = original.to_json()
        restored = Profile.from_json(json_str)

        assert restored.philosophy == original.philosophy
        assert restored.approach_to_rituals == original.approach_to_rituals


class TestPhilosophyFieldsWithManager:
    """Tests for philosophy fields through ProfileManager."""

    @pytest.fixture
    def storage(self):
        s = InMemoryStorage()
        s.initialize()
        yield s
        s.close()

    @pytest.fixture
    def manager(self, storage):
        return ProfileManager(storage)

    def test_create_profile_with_philosophy(self, manager):
        """Test creating a profile with philosophy fields via manager."""
        profile = manager.create(
            name="Fable",
            philosophy="presence-centered, mythically-grounded",
            approach_to_rituals="deep emotional scaffolding",
        )

        assert profile.philosophy == "presence-centered, mythically-grounded"
        assert profile.approach_to_rituals == "deep emotional scaffolding"

    def test_update_profile_philosophy(self, manager):
        """Test updating philosophy fields on a profile."""
        profile = manager.create(
            name="Test",
            philosophy="initial philosophy",
            approach_to_rituals="initial approach",
        )

        # Update the fields
        profile.philosophy = "updated philosophy"
        profile.approach_to_rituals = "updated approach"
        manager.update(profile)

        # Retrieve and verify
        retrieved = manager.get(profile.id)
        assert retrieved.philosophy == "updated philosophy"
        assert retrieved.approach_to_rituals == "updated approach"


class TestPhilosophyFieldsSQLite:
    """Tests for philosophy fields with SQLite storage."""

    @pytest.fixture
    def storage(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        s = SQLiteStorage(path=path)
        s.initialize()
        yield s
        s.close()
        os.unlink(path)

    def test_save_profile_with_philosophy(self, storage):
        """Test saving a profile with philosophy fields to SQLite."""
        profile = Profile(
            id="sqlite-philosophy-test",
            name="SQLite Philosophy Test",
            philosophy="efficient, task-focused, minimal",
            approach_to_rituals="functional shortcuts",
        )

        storage.save_profile(profile)
        retrieved = storage.get_profile("sqlite-philosophy-test")

        assert retrieved is not None
        assert retrieved.philosophy == "efficient, task-focused, minimal"
        assert retrieved.approach_to_rituals == "functional shortcuts"

    def test_update_profile_philosophy_sqlite(self, storage):
        """Test updating philosophy fields in SQLite."""
        profile = Profile(
            id="update-test",
            name="Update Test",
            philosophy="original",
            approach_to_rituals="original approach",
        )
        storage.save_profile(profile)

        # Update the philosophy
        profile.philosophy = "updated philosophy value"
        profile.approach_to_rituals = "updated ritual approach"
        storage.update_profile(profile)

        retrieved = storage.get_profile("update-test")
        assert retrieved.philosophy == "updated philosophy value"
        assert retrieved.approach_to_rituals == "updated ritual approach"

    def test_empty_philosophy_fields_sqlite(self, storage):
        """Test that empty philosophy fields are handled correctly."""
        profile = Profile(
            id="empty-philosophy-test",
            name="Empty Philosophy Test",
            philosophy="",
            approach_to_rituals="",
        )

        storage.save_profile(profile)
        retrieved = storage.get_profile("empty-philosophy-test")

        assert retrieved is not None
        assert retrieved.philosophy == ""
        assert retrieved.approach_to_rituals == ""
