"""Tests for storage backends."""

import pytest
from datetime import datetime, timedelta

from threadlight.storage.memory import InMemoryStorage
from threadlight.storage.base import CapsuleFilter
from threadlight.capsules.relational import create_relational
from threadlight.capsules.myth_seed import create_myth_seed
from threadlight.capsules.base import CapsuleType, RetentionPolicy


@pytest.fixture
def storage():
    s = InMemoryStorage()
    s.initialize()
    yield s
    s.close()


class TestInMemoryStorage:
    def test_save_and_get(self, storage):
        capsule = create_relational(entity="Test", summary="Test summary")
        storage.save_capsule(capsule)

        retrieved = storage.get_capsule(capsule.id)
        assert retrieved is not None
        assert retrieved.entity == "Test"

    def test_update(self, storage):
        capsule = create_relational(entity="Test", summary="Original")
        storage.save_capsule(capsule)

        capsule.summary = "Updated"
        storage.update_capsule(capsule)

        retrieved = storage.get_capsule(capsule.id)
        assert retrieved.summary == "Updated"

    def test_delete(self, storage):
        capsule = create_relational(entity="Test", summary="Test")
        storage.save_capsule(capsule)

        assert storage.delete_capsule(capsule.id)
        assert storage.get_capsule(capsule.id) is None

    def test_list_with_filter(self, storage):
        # Create mixed capsules
        rel = create_relational(entity="Rel", summary="Relational")
        myth = create_myth_seed(seed="Test seed")

        storage.save_capsule(rel)
        storage.save_capsule(myth)

        # Filter by type
        filter = CapsuleFilter(type=CapsuleType.RELATIONAL)
        results = storage.list_capsules(filter)

        assert len(results) == 1
        assert results[0].type == CapsuleType.RELATIONAL

    def test_search_by_cue(self, storage):
        capsule = create_relational(
            entity="Jericho",
            summary="Test",
            cue_phrases=["jericho", "brother"]
        )
        storage.save_capsule(capsule)

        results = storage.search_by_cue("jericho")
        assert len(results) == 1
        assert results[0].entity == "Jericho"

    def test_get_capsules_for_decay(self, storage):
        # Create capsules with different retention policies
        normal = create_relational(entity="Normal", summary="Test")
        sacred = create_myth_seed(seed="Sacred")
        sacred.retention = RetentionPolicy.SACRED

        storage.save_capsule(normal)
        storage.save_capsule(sacred)

        # Get capsules for decay (excluding sacred)
        cutoff = datetime.utcnow() + timedelta(hours=1)
        results = storage.get_capsules_for_decay(
            before=cutoff,
            exclude_retention=[RetentionPolicy.SACRED]
        )

        assert len(results) == 1
        assert results[0].retention == RetentionPolicy.NORMAL

    def test_batch_update_presence(self, storage):
        c1 = create_relational(entity="C1", summary="Test")
        c2 = create_relational(entity="C2", summary="Test")

        storage.save_capsule(c1)
        storage.save_capsule(c2)

        updates = {c1.id: 0.5, c2.id: 0.3}
        count = storage.update_presence_scores(updates)

        assert count == 2
        assert storage.get_capsule(c1.id).presence_score == 0.5
        assert storage.get_capsule(c2.id).presence_score == 0.3

    def test_export_import(self, storage):
        capsule = create_relational(entity="Export", summary="Test export")
        storage.save_capsule(capsule)

        data = storage.export_all()
        assert len(data) == 1

        # Clear and reimport
        storage.close()
        storage.capsules = {}

        count = storage.import_capsules(data)
        assert count == 1
        assert len(storage.capsules) == 1
