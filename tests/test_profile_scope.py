"""Tests for profile_scope functionality (Phase 2 of profile-based architecture)."""

import pytest
from datetime import datetime

from threadlight.storage.memory import InMemoryStorage
from threadlight.storage.base import CapsuleFilter, Message
from threadlight.memory.orchestrator import MemoryOrchestrator
from threadlight.decay.engine import DecayEngine, LinearDecayStrategy
from threadlight.capsules.relational import create_relational
from threadlight.capsules.base import CapsuleType


@pytest.fixture
def storage():
    """Create in-memory storage."""
    s = InMemoryStorage()
    s.initialize()
    yield s
    s.close()


@pytest.fixture
def decay_engine(storage):
    """Create decay engine."""
    return DecayEngine(
        storage=storage,
        strategy=LinearDecayStrategy(),
        min_age_hours=0,
    )


@pytest.fixture
def orchestrator(storage, decay_engine):
    """Create memory orchestrator with profile isolation enabled."""
    return MemoryOrchestrator(
        storage=storage,
        decay_engine=decay_engine,
        per_profile_isolation=True,
        current_profile="test-profile-1",
    )


class TestCapsuleFilterProfileScope:
    """Tests for CapsuleFilter profile_scope field."""

    def test_profile_scope_filter_basic(self):
        """Test that profile_scope field exists."""
        filter = CapsuleFilter(profile_scope="test-profile")
        assert filter.profile_scope == "test-profile"

    def test_model_scope_backward_compat(self):
        """Test that model_scope falls back to profile_scope via __post_init__."""
        filter = CapsuleFilter(model_scope="old-model-id")
        # After __post_init__, profile_scope should be set from model_scope
        assert filter.profile_scope == "old-model-id"

    def test_profile_scope_takes_precedence(self):
        """Test that profile_scope takes precedence over model_scope."""
        filter = CapsuleFilter(
            profile_scope="new-profile",
            model_scope="old-model"
        )
        # profile_scope should not be overwritten by model_scope
        assert filter.profile_scope == "new-profile"

    def test_include_shared_default(self):
        """Test that include_shared defaults to True."""
        filter = CapsuleFilter(profile_scope="test")
        assert filter.include_shared is True


class TestStorageProfileScope:
    """Tests for storage profile_scope filtering."""

    def test_list_capsules_by_profile(self, storage):
        """Test listing capsules filtered by profile_scope."""
        # Create capsules with different profile scopes
        c1 = create_relational(entity="Profile1", summary="test")
        c1.profile_scope = "profile-a"

        c2 = create_relational(entity="Profile2", summary="test")
        c2.profile_scope = "profile-b"

        c3 = create_relational(entity="Shared", summary="test")
        c3.profile_scope = None  # Shared

        storage.save_capsule(c1)
        storage.save_capsule(c2)
        storage.save_capsule(c3)

        # Filter by profile-a (including shared)
        filter = CapsuleFilter(profile_scope="profile-a", include_shared=True)
        results = storage.list_capsules(filter)

        assert len(results) == 2
        entities = [getattr(c, 'entity', None) for c in results]
        assert "Profile1" in entities
        assert "Shared" in entities
        assert "Profile2" not in entities

    def test_list_capsules_profile_only(self, storage):
        """Test listing capsules with include_shared=False."""
        c1 = create_relational(entity="Profile1", summary="test")
        c1.profile_scope = "profile-a"

        c2 = create_relational(entity="Shared", summary="test")
        c2.profile_scope = None

        storage.save_capsule(c1)
        storage.save_capsule(c2)

        # Filter by profile-a only (excluding shared)
        filter = CapsuleFilter(profile_scope="profile-a", include_shared=False)
        results = storage.list_capsules(filter)

        assert len(results) == 1
        assert results[0].entity == "Profile1"

    def test_search_by_cue_with_profile(self, storage):
        """Test search_by_cue with profile_scope."""
        c1 = create_relational(entity="Alpha", summary="test")
        c1.profile_scope = "profile-a"
        c1.cue_phrases = ["alpha", "test"]

        c2 = create_relational(entity="Beta", summary="test")
        c2.profile_scope = "profile-b"
        c2.cue_phrases = ["beta", "test"]

        storage.save_capsule(c1)
        storage.save_capsule(c2)

        # Search with profile_scope filter
        results = storage.search_by_cue(
            "test",
            profile_scope="profile-a",
            include_shared=False
        )

        assert len(results) == 1
        assert results[0].entity == "Alpha"


class TestMessageProfileFields:
    """Tests for Message profile_id and model_used fields."""

    def test_message_has_profile_id(self):
        """Test that Message has profile_id field."""
        msg = Message(
            id="test-msg-1",
            conversation_id="conv-1",
            role="assistant",
            content="Hello!",
            timestamp=datetime.utcnow(),
            profile_id="test-profile"
        )
        assert msg.profile_id == "test-profile"

    def test_message_has_model_used(self):
        """Test that Message has model_used field."""
        msg = Message(
            id="test-msg-1",
            conversation_id="conv-1",
            role="assistant",
            content="Hello!",
            timestamp=datetime.utcnow(),
            model_used="gpt-4"
        )
        assert msg.model_used == "gpt-4"

    def test_message_to_dict_includes_profile_fields(self):
        """Test that to_dict includes profile fields."""
        msg = Message(
            id="test-msg-1",
            conversation_id="conv-1",
            role="assistant",
            content="Hello!",
            timestamp=datetime.utcnow(),
            profile_id="test-profile",
            model_used="claude-3"
        )
        data = msg.to_dict()

        assert data["profile_id"] == "test-profile"
        assert data["model_used"] == "claude-3"

    def test_message_from_dict_includes_profile_fields(self):
        """Test that from_dict parses profile fields."""
        data = {
            "id": "test-msg-1",
            "conversation_id": "conv-1",
            "role": "assistant",
            "content": "Hello!",
            "timestamp": datetime.utcnow().isoformat(),
            "profile_id": "test-profile",
            "model_used": "claude-3"
        }
        msg = Message.from_dict(data)

        assert msg.profile_id == "test-profile"
        assert msg.model_used == "claude-3"


class TestOrchestratorProfileIsolation:
    """Tests for MemoryOrchestrator profile isolation."""

    def test_orchestrator_has_profile_settings(self, orchestrator):
        """Test that orchestrator has profile-related properties."""
        assert orchestrator.per_profile_isolation is True
        assert orchestrator.current_profile == "test-profile-1"

    def test_create_capsule_with_profile(self, orchestrator):
        """Test creating a capsule with profile scope."""
        capsule = orchestrator.create(
            type="relational",
            content={"entity": "Test", "summary": "test"},
            consent_confirmed=True
        )

        # Should have profile_scope set to current_profile
        assert capsule.profile_scope == "test-profile-1"

    def test_create_shared_capsule(self, orchestrator):
        """Test creating a shared capsule."""
        capsule = orchestrator.create(
            type="relational",
            content={"entity": "Shared", "summary": "test"},
            consent_confirmed=True,
            shared=True
        )

        # Should have profile_scope = None (shared)
        assert capsule.profile_scope is None

    def test_create_capsule_explicit_profile(self, orchestrator):
        """Test creating a capsule with explicit profile scope."""
        capsule = orchestrator.create(
            type="relational",
            content={"entity": "Explicit", "summary": "test"},
            consent_confirmed=True,
            profile_scope="other-profile"
        )

        # Should have the explicit profile_scope
        assert capsule.profile_scope == "other-profile"

    def test_recall_respects_profile(self, orchestrator, storage):
        """Test that recall respects profile scope."""
        # Create capsules for different profiles
        c1 = orchestrator.create(
            type="relational",
            content={"entity": "Mine", "summary": "test"},
            cue_phrases=["keyword"],
            consent_confirmed=True
        )

        # Manually create a capsule for another profile
        c2 = create_relational(entity="Others", summary="test")
        c2.profile_scope = "other-profile"
        c2.cue_phrases = ["keyword"]
        c2.consent_confirmed = True
        storage.save_capsule(c2)

        # Recall should only find capsules for current profile
        results = orchestrator.recall("keyword")

        entities = [getattr(c, 'entity', None) for c in results]
        assert "Mine" in entities
        assert "Others" not in entities

    def test_list_respects_profile(self, orchestrator, storage):
        """Test that list respects profile scope."""
        orchestrator.create(
            type="relational",
            content={"entity": "Mine1"},
            consent_confirmed=True
        )
        orchestrator.create(
            type="relational",
            content={"entity": "Mine2"},
            consent_confirmed=True
        )

        # Create capsule for another profile
        c3 = create_relational(entity="Others", summary="test")
        c3.profile_scope = "other-profile"
        c3.consent_confirmed = True
        storage.save_capsule(c3)

        # List should only show current profile capsules
        results = orchestrator.list(include_shared=False)

        entities = [getattr(c, 'entity', None) for c in results]
        assert "Mine1" in entities
        assert "Mine2" in entities
        assert "Others" not in entities

    def test_switch_profile(self, orchestrator, storage):
        """Test switching profile changes what capsules are visible."""
        # Create capsule for profile-1
        orchestrator.create(
            type="relational",
            content={"entity": "ForProfile1"},
            cue_phrases=["test"],
            consent_confirmed=True
        )

        # Switch to profile-2
        orchestrator.current_profile = "test-profile-2"

        # Create capsule for profile-2
        orchestrator.create(
            type="relational",
            content={"entity": "ForProfile2"},
            cue_phrases=["test"],
            consent_confirmed=True
        )

        # Recall should only find profile-2 capsules
        results = orchestrator.recall("test", include_shared=False)
        entities = [getattr(c, 'entity', None) for c in results]

        assert "ForProfile2" in entities
        assert "ForProfile1" not in entities


class TestBackwardCompatibility:
    """Tests for backward compatibility with model_scope."""

    def test_model_scope_still_works(self, storage, decay_engine):
        """Test that using model_scope still works."""
        orch = MemoryOrchestrator(
            storage=storage,
            decay_engine=decay_engine,
            per_model_isolation=True,
            current_model="old-model-id"
        )

        capsule = orch.create(
            type="relational",
            content={"entity": "ModelScoped"},
            consent_confirmed=True
        )

        # Should set profile_scope from model scope
        assert capsule.profile_scope == "old-model-id"

    def test_capsule_filter_model_scope_fallback(self):
        """Test CapsuleFilter model_scope -> profile_scope fallback."""
        filter = CapsuleFilter(model_scope="old-model")

        # profile_scope should be set from model_scope
        assert filter.profile_scope == "old-model"

    def test_create_with_model_scope_param(self, orchestrator):
        """Test create() with model_scope parameter still works."""
        capsule = orchestrator.create(
            type="relational",
            content={"entity": "Test"},
            model_scope="explicit-model",
            consent_confirmed=True
        )

        # Should set profile_scope from model_scope param
        assert capsule.profile_scope == "explicit-model"


class TestCapsuleBaseClassProfileScope:
    """Tests for MemoryCapsule base class profile_scope field."""

    def test_capsule_has_profile_scope(self):
        """Test that capsules have profile_scope field."""
        c = create_relational(entity="Test", summary="test")
        assert hasattr(c, 'profile_scope')
        assert c.profile_scope is None  # Default

    def test_capsule_to_dict_includes_profile_scope(self):
        """Test that to_dict includes profile_scope."""
        c = create_relational(entity="Test", summary="test")
        c.profile_scope = "my-profile"

        data = c.to_dict()
        assert data["profile_scope"] == "my-profile"

    def test_capsule_still_has_model_scope(self):
        """Test that capsules still have model_scope for backward compat."""
        c = create_relational(entity="Test", summary="test")
        assert hasattr(c, 'model_scope')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
