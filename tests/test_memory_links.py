"""Tests for inter-memory links and trash/recycle bin."""

import json
import pytest
import tempfile
import os
from datetime import datetime, timedelta, timezone

from threadlight.storage.memory import InMemoryStorage
from threadlight.storage.sqlite import SQLiteStorage
from threadlight.storage.base import MemoryLink, DeletedItem, CapsuleFilter
from threadlight.capsules.relational import create_relational
from threadlight.capsules.myth_seed import create_myth_seed
from threadlight.capsules.base import CapsuleType


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def memory_storage():
    """In-memory storage for fast tests."""
    s = InMemoryStorage()
    s.initialize()
    yield s
    s.close()


@pytest.fixture
def sqlite_storage():
    """SQLite storage for integration tests."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    s = SQLiteStorage(path=db_path)
    s.initialize()
    yield s
    s.close()

    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def two_capsules(memory_storage):
    """Create two capsules for linking."""
    c1 = create_relational(entity="Alice", summary="A friend")
    c2 = create_relational(entity="Bob", summary="Another friend")
    memory_storage.save_capsule(c1)
    memory_storage.save_capsule(c2)
    return c1, c2


@pytest.fixture
def two_capsules_sqlite(sqlite_storage):
    """Create two capsules in SQLite for linking."""
    c1 = create_relational(entity="Alice", summary="A friend")
    c2 = create_relational(entity="Bob", summary="Another friend")
    sqlite_storage.save_capsule(c1)
    sqlite_storage.save_capsule(c2)
    return c1, c2


# ============================================================================
# MemoryLink Dataclass Tests
# ============================================================================


class TestMemoryLinkDataclass:
    def test_default_values(self):
        link = MemoryLink()
        assert link.id  # UUID generated
        assert link.link_type == "related"
        assert link.strength == 1.0
        assert link.bidirectional is False
        assert link.created_by == "user"

    def test_to_dict(self):
        link = MemoryLink(
            source_capsule_id="src-1",
            target_capsule_id="tgt-1",
            link_type="supports",
            strength=0.8,
            bidirectional=True,
            notes="Test note",
        )
        d = link.to_dict()
        assert d["source_capsule_id"] == "src-1"
        assert d["target_capsule_id"] == "tgt-1"
        assert d["link_type"] == "supports"
        assert d["strength"] == 0.8
        assert d["bidirectional"] is True
        assert d["notes"] == "Test note"
        assert "created_at" in d

    def test_from_dict(self):
        data = {
            "id": "link-1",
            "source_capsule_id": "src-1",
            "target_capsule_id": "tgt-1",
            "link_type": "contradicts",
            "strength": 0.5,
            "bidirectional": False,
            "notes": "They disagree",
            "created_at": "2025-01-01T00:00:00+00:00",
            "created_by": "system",
        }
        link = MemoryLink.from_dict(data)
        assert link.id == "link-1"
        assert link.link_type == "contradicts"
        assert link.strength == 0.5
        assert link.created_by == "system"

    def test_roundtrip(self):
        link = MemoryLink(
            source_capsule_id="a",
            target_capsule_id="b",
            link_type="supports",
            strength=0.7,
            bidirectional=True,
        )
        restored = MemoryLink.from_dict(link.to_dict())
        assert restored.id == link.id
        assert restored.link_type == link.link_type
        assert restored.strength == link.strength
        assert restored.bidirectional == link.bidirectional


# ============================================================================
# DeletedItem Dataclass Tests
# ============================================================================


class TestDeletedItemDataclass:
    def test_default_values(self):
        item = DeletedItem()
        assert item.id  # UUID generated
        assert item.auto_purge_at > item.deleted_at  # 30 days in the future

    def test_to_dict_from_dict_roundtrip(self):
        item = DeletedItem(
            item_type="memory_link",
            item_id="link-1",
            item_data='{"id": "link-1"}',
            deleted_by="user",
        )
        restored = DeletedItem.from_dict(item.to_dict())
        assert restored.item_type == "memory_link"
        assert restored.item_id == "link-1"
        assert restored.deleted_by == "user"


# ============================================================================
# InMemoryStorage Link Tests
# ============================================================================


class TestInMemoryStorageLinks:
    def test_create_link(self, memory_storage, two_capsules):
        c1, c2 = two_capsules
        link = MemoryLink(
            source_capsule_id=c1.id,
            target_capsule_id=c2.id,
            link_type="related",
        )
        link_id = memory_storage.create_link(link)
        assert link_id == link.id

    def test_create_link_missing_source(self, memory_storage, two_capsules):
        _, c2 = two_capsules
        link = MemoryLink(
            source_capsule_id="nonexistent",
            target_capsule_id=c2.id,
        )
        with pytest.raises(ValueError, match="Source capsule not found"):
            memory_storage.create_link(link)

    def test_create_link_missing_target(self, memory_storage, two_capsules):
        c1, _ = two_capsules
        link = MemoryLink(
            source_capsule_id=c1.id,
            target_capsule_id="nonexistent",
        )
        with pytest.raises(ValueError, match="Target capsule not found"):
            memory_storage.create_link(link)

    def test_duplicate_link_prevention(self, memory_storage, two_capsules):
        c1, c2 = two_capsules
        link1 = MemoryLink(
            source_capsule_id=c1.id,
            target_capsule_id=c2.id,
            link_type="related",
        )
        memory_storage.create_link(link1)

        link2 = MemoryLink(
            source_capsule_id=c1.id,
            target_capsule_id=c2.id,
            link_type="related",
        )
        with pytest.raises(ValueError, match="Duplicate link"):
            memory_storage.create_link(link2)

    def test_different_type_not_duplicate(self, memory_storage, two_capsules):
        c1, c2 = two_capsules
        link1 = MemoryLink(
            source_capsule_id=c1.id,
            target_capsule_id=c2.id,
            link_type="related",
        )
        memory_storage.create_link(link1)

        link2 = MemoryLink(
            source_capsule_id=c1.id,
            target_capsule_id=c2.id,
            link_type="supports",
        )
        # Should not raise
        memory_storage.create_link(link2)

    def test_get_link(self, memory_storage, two_capsules):
        c1, c2 = two_capsules
        link = MemoryLink(
            source_capsule_id=c1.id,
            target_capsule_id=c2.id,
        )
        memory_storage.create_link(link)

        retrieved = memory_storage.get_link(link.id)
        assert retrieved is not None
        assert retrieved.id == link.id
        assert retrieved.source_capsule_id == c1.id

    def test_get_link_not_found(self, memory_storage):
        assert memory_storage.get_link("nonexistent") is None

    def test_get_links_outgoing(self, memory_storage, two_capsules):
        c1, c2 = two_capsules
        link = MemoryLink(source_capsule_id=c1.id, target_capsule_id=c2.id)
        memory_storage.create_link(link)

        outgoing = memory_storage.get_links_for_capsule(c1.id, direction="outgoing")
        assert len(outgoing) == 1
        assert outgoing[0].target_capsule_id == c2.id

        # c2 has no outgoing links
        outgoing_c2 = memory_storage.get_links_for_capsule(c2.id, direction="outgoing")
        assert len(outgoing_c2) == 0

    def test_get_links_incoming(self, memory_storage, two_capsules):
        c1, c2 = two_capsules
        link = MemoryLink(source_capsule_id=c1.id, target_capsule_id=c2.id)
        memory_storage.create_link(link)

        incoming = memory_storage.get_links_for_capsule(c2.id, direction="incoming")
        assert len(incoming) == 1
        assert incoming[0].source_capsule_id == c1.id

    def test_get_links_both(self, memory_storage, two_capsules):
        c1, c2 = two_capsules
        link = MemoryLink(source_capsule_id=c1.id, target_capsule_id=c2.id)
        memory_storage.create_link(link)

        both_c1 = memory_storage.get_links_for_capsule(c1.id, direction="both")
        assert len(both_c1) == 1

        both_c2 = memory_storage.get_links_for_capsule(c2.id, direction="both")
        assert len(both_c2) == 1

    def test_get_links_filter_by_type(self, memory_storage, two_capsules):
        c1, c2 = two_capsules
        link1 = MemoryLink(
            source_capsule_id=c1.id, target_capsule_id=c2.id, link_type="related"
        )
        link2 = MemoryLink(
            source_capsule_id=c1.id, target_capsule_id=c2.id, link_type="supports"
        )
        memory_storage.create_link(link1)
        memory_storage.create_link(link2)

        related = memory_storage.get_links_for_capsule(
            c1.id, link_types=["related"]
        )
        assert len(related) == 1
        assert related[0].link_type == "related"

    def test_update_link(self, memory_storage, two_capsules):
        c1, c2 = two_capsules
        link = MemoryLink(
            source_capsule_id=c1.id,
            target_capsule_id=c2.id,
            strength=0.5,
        )
        memory_storage.create_link(link)

        link.strength = 0.9
        link.notes = "Updated note"
        assert memory_storage.update_link(link) is True

        retrieved = memory_storage.get_link(link.id)
        assert retrieved.strength == 0.9
        assert retrieved.notes == "Updated note"

    def test_update_link_not_found(self, memory_storage):
        link = MemoryLink(id="nonexistent")
        assert memory_storage.update_link(link) is False

    def test_delete_link_moves_to_trash(self, memory_storage, two_capsules):
        c1, c2 = two_capsules
        link = MemoryLink(source_capsule_id=c1.id, target_capsule_id=c2.id)
        memory_storage.create_link(link)

        assert memory_storage.delete_link(link.id) is True
        assert memory_storage.get_link(link.id) is None

        # Should be in trash
        trash = memory_storage.list_deleted_items(item_type="memory_link")
        assert len(trash) == 1
        assert trash[0].item_id == link.id

    def test_delete_link_not_found(self, memory_storage):
        assert memory_storage.delete_link("nonexistent") is False

    def test_list_link_types(self, memory_storage, two_capsules):
        c1, c2 = two_capsules
        memory_storage.create_link(MemoryLink(
            source_capsule_id=c1.id, target_capsule_id=c2.id, link_type="related"
        ))
        memory_storage.create_link(MemoryLink(
            source_capsule_id=c1.id, target_capsule_id=c2.id, link_type="supports"
        ))

        types = memory_storage.list_link_types()
        assert sorted(types) == ["related", "supports"]

    def test_list_link_types_empty(self, memory_storage):
        types = memory_storage.list_link_types()
        assert types == []

    def test_bidirectional_link_traversal(self, memory_storage, two_capsules):
        """Bidirectional links should be traversable from both directions."""
        c1, c2 = two_capsules
        link = MemoryLink(
            source_capsule_id=c1.id,
            target_capsule_id=c2.id,
            bidirectional=True,
        )
        memory_storage.create_link(link)

        # From c1's perspective (outgoing)
        linked = memory_storage.get_linked_capsules(c1.id, direction="both")
        assert len(linked) == 1
        capsule, _, depth = linked[0]
        assert capsule.id == c2.id
        assert depth == 1

        # From c2's perspective (can traverse back via bidirectional)
        linked_c2 = memory_storage.get_linked_capsules(c2.id, direction="both")
        assert len(linked_c2) == 1
        capsule2, _, depth2 = linked_c2[0]
        assert capsule2.id == c1.id
        assert depth2 == 1


# ============================================================================
# Linked Capsules (Graph Traversal) Tests
# ============================================================================


class TestLinkedCapsules:
    def test_direct_linked_capsules(self, memory_storage, two_capsules):
        c1, c2 = two_capsules
        link = MemoryLink(source_capsule_id=c1.id, target_capsule_id=c2.id)
        memory_storage.create_link(link)

        results = memory_storage.get_linked_capsules(c1.id)
        assert len(results) == 1
        capsule, link_obj, depth = results[0]
        assert capsule.id == c2.id
        assert depth == 1

    def test_multi_hop_traversal(self, memory_storage):
        """Test depth > 1 traversal: A -> B -> C."""
        c1 = create_relational(entity="A", summary="First")
        c2 = create_relational(entity="B", summary="Second")
        c3 = create_relational(entity="C", summary="Third")
        memory_storage.save_capsule(c1)
        memory_storage.save_capsule(c2)
        memory_storage.save_capsule(c3)

        memory_storage.create_link(MemoryLink(
            source_capsule_id=c1.id, target_capsule_id=c2.id
        ))
        memory_storage.create_link(MemoryLink(
            source_capsule_id=c2.id, target_capsule_id=c3.id
        ))

        # Depth 1: only B
        results_d1 = memory_storage.get_linked_capsules(c1.id, depth=1)
        assert len(results_d1) == 1
        assert results_d1[0][0].id == c2.id

        # Depth 2: B and C
        results_d2 = memory_storage.get_linked_capsules(c1.id, depth=2)
        assert len(results_d2) == 2
        ids = {r[0].id for r in results_d2}
        assert ids == {c2.id, c3.id}

        # Check depths are correct
        depths = {r[0].id: r[2] for r in results_d2}
        assert depths[c2.id] == 1
        assert depths[c3.id] == 2

    def test_cycle_detection(self, memory_storage):
        """Cycles should not cause infinite loops."""
        c1 = create_relational(entity="A", summary="First")
        c2 = create_relational(entity="B", summary="Second")
        c3 = create_relational(entity="C", summary="Third")
        memory_storage.save_capsule(c1)
        memory_storage.save_capsule(c2)
        memory_storage.save_capsule(c3)

        # Create cycle: A -> B -> C -> A
        memory_storage.create_link(MemoryLink(
            source_capsule_id=c1.id, target_capsule_id=c2.id
        ))
        memory_storage.create_link(MemoryLink(
            source_capsule_id=c2.id, target_capsule_id=c3.id
        ))
        memory_storage.create_link(MemoryLink(
            source_capsule_id=c3.id, target_capsule_id=c1.id
        ))

        # Should not loop forever, should return B and C
        results = memory_storage.get_linked_capsules(c1.id, depth=10)
        assert len(results) == 2
        ids = {r[0].id for r in results}
        assert ids == {c2.id, c3.id}

    def test_depth_zero(self, memory_storage, two_capsules):
        """Depth 0 should return empty."""
        c1, c2 = two_capsules
        memory_storage.create_link(MemoryLink(
            source_capsule_id=c1.id, target_capsule_id=c2.id
        ))
        results = memory_storage.get_linked_capsules(c1.id, depth=0)
        assert results == []

    def test_outgoing_direction_filter(self, memory_storage):
        """Outgoing direction should only follow source -> target direction."""
        c1 = create_relational(entity="A", summary="First")
        c2 = create_relational(entity="B", summary="Second")
        memory_storage.save_capsule(c1)
        memory_storage.save_capsule(c2)

        # Non-bidirectional link: A -> B
        memory_storage.create_link(MemoryLink(
            source_capsule_id=c1.id,
            target_capsule_id=c2.id,
            bidirectional=False,
        ))

        # From A, outgoing should find B
        results_a = memory_storage.get_linked_capsules(c1.id, direction="outgoing")
        assert len(results_a) == 1

        # From B, outgoing should find nothing (link is A -> B, not B -> A)
        results_b = memory_storage.get_linked_capsules(c2.id, direction="outgoing")
        assert len(results_b) == 0


# ============================================================================
# Trash / Deleted Items Tests
# ============================================================================


class TestTrashOperations:
    def test_delete_link_to_trash(self, memory_storage, two_capsules):
        c1, c2 = two_capsules
        link = MemoryLink(source_capsule_id=c1.id, target_capsule_id=c2.id)
        memory_storage.create_link(link)

        memory_storage.delete_link(link.id)

        trash = memory_storage.list_deleted_items()
        assert len(trash) == 1
        assert trash[0].item_type == "memory_link"
        assert trash[0].item_id == link.id

    def test_restore_link_from_trash(self, memory_storage, two_capsules):
        c1, c2 = two_capsules
        link = MemoryLink(source_capsule_id=c1.id, target_capsule_id=c2.id)
        memory_storage.create_link(link)
        link_id = link.id

        # Delete (to trash)
        memory_storage.delete_link(link_id)
        assert memory_storage.get_link(link_id) is None

        # Restore from trash
        trash = memory_storage.list_deleted_items()
        assert len(trash) == 1

        success = memory_storage.restore_deleted_item(trash[0].id)
        assert success is True

        # Link should be back
        restored = memory_storage.get_link(link_id)
        assert restored is not None
        assert restored.source_capsule_id == c1.id

        # Trash should be empty
        assert len(memory_storage.list_deleted_items()) == 0

    def test_move_capsule_to_trash(self, memory_storage, two_capsules):
        c1, c2 = two_capsules
        link = MemoryLink(source_capsule_id=c1.id, target_capsule_id=c2.id)
        memory_storage.create_link(link)

        # Move capsule to trash
        success = memory_storage.move_capsule_to_trash(c1.id)
        assert success is True

        trash = memory_storage.list_deleted_items(item_type="capsule")
        assert len(trash) == 1
        assert trash[0].item_id == c1.id
        # Related links should be stored
        assert trash[0].related_items != ""

    def test_restore_capsule_from_trash(self, memory_storage, two_capsules):
        """Restore a capsule and its links from trash."""
        c1, c2 = two_capsules
        link = MemoryLink(source_capsule_id=c1.id, target_capsule_id=c2.id)
        memory_storage.create_link(link)
        link_id = link.id

        # Move to trash and then delete capsule
        memory_storage.move_capsule_to_trash(c1.id)
        del memory_storage.capsules[c1.id]
        # Delete the link too (simulates cascade)
        if link_id in memory_storage.memory_links:
            del memory_storage.memory_links[link_id]

        # Restore
        trash = memory_storage.list_deleted_items(item_type="capsule")
        assert len(trash) == 1
        success = memory_storage.restore_deleted_item(trash[0].id)
        assert success is True

        # Capsule should be back
        restored_capsule = memory_storage.get_capsule(c1.id)
        assert restored_capsule is not None

        # Link should be restored too
        restored_link = memory_storage.get_link(link_id)
        assert restored_link is not None

    def test_restore_nonexistent(self, memory_storage):
        assert memory_storage.restore_deleted_item("nonexistent") is False

    def test_list_deleted_items_filter_by_type(self, memory_storage, two_capsules):
        c1, c2 = two_capsules
        link = MemoryLink(source_capsule_id=c1.id, target_capsule_id=c2.id)
        memory_storage.create_link(link)

        # Delete a link and a capsule
        memory_storage.delete_link(link.id)
        memory_storage.move_capsule_to_trash(c1.id)

        all_items = memory_storage.list_deleted_items()
        assert len(all_items) == 2

        links_only = memory_storage.list_deleted_items(item_type="memory_link")
        assert len(links_only) == 1
        assert links_only[0].item_type == "memory_link"

        capsules_only = memory_storage.list_deleted_items(item_type="capsule")
        assert len(capsules_only) == 1
        assert capsules_only[0].item_type == "capsule"

    def test_purge_old_deleted_items(self, memory_storage, two_capsules):
        c1, c2 = two_capsules
        link = MemoryLink(source_capsule_id=c1.id, target_capsule_id=c2.id)
        memory_storage.create_link(link)
        memory_storage.delete_link(link.id)

        # Set auto_purge_at to the past
        trash = memory_storage.list_deleted_items()
        assert len(trash) == 1
        trash[0].auto_purge_at = datetime.now(timezone.utc) - timedelta(days=1)

        # Purge items older than 0 days (all items with past auto_purge_at)
        purged = memory_storage.purge_old_deleted_items(older_than_days=0)
        assert purged == 1
        assert len(memory_storage.list_deleted_items()) == 0

    def test_permanently_delete_trash_item(self, memory_storage, two_capsules):
        c1, c2 = two_capsules
        link = MemoryLink(source_capsule_id=c1.id, target_capsule_id=c2.id)
        memory_storage.create_link(link)
        memory_storage.delete_link(link.id)

        trash = memory_storage.list_deleted_items()
        assert len(trash) == 1

        success = memory_storage.permanently_delete_trash_item(trash[0].id)
        assert success is True
        assert len(memory_storage.list_deleted_items()) == 0

    def test_permanently_delete_nonexistent(self, memory_storage):
        assert memory_storage.permanently_delete_trash_item("nonexistent") is False


# ============================================================================
# SQLite Storage Link Tests
# ============================================================================


class TestSQLiteStorageLinks:
    def test_create_and_get_link(self, sqlite_storage, two_capsules_sqlite):
        c1, c2 = two_capsules_sqlite
        link = MemoryLink(
            source_capsule_id=c1.id,
            target_capsule_id=c2.id,
            link_type="supports",
            strength=0.8,
            notes="Test note",
        )
        link_id = sqlite_storage.create_link(link)

        retrieved = sqlite_storage.get_link(link_id)
        assert retrieved is not None
        assert retrieved.source_capsule_id == c1.id
        assert retrieved.target_capsule_id == c2.id
        assert retrieved.link_type == "supports"
        assert retrieved.strength == 0.8
        assert retrieved.notes == "Test note"

    def test_duplicate_prevention(self, sqlite_storage, two_capsules_sqlite):
        c1, c2 = two_capsules_sqlite
        link1 = MemoryLink(
            source_capsule_id=c1.id,
            target_capsule_id=c2.id,
            link_type="related",
        )
        sqlite_storage.create_link(link1)

        link2 = MemoryLink(
            source_capsule_id=c1.id,
            target_capsule_id=c2.id,
            link_type="related",
        )
        with pytest.raises(ValueError, match="Duplicate link"):
            sqlite_storage.create_link(link2)

    def test_missing_capsule_validation(self, sqlite_storage, two_capsules_sqlite):
        c1, c2 = two_capsules_sqlite
        link = MemoryLink(
            source_capsule_id="nonexistent",
            target_capsule_id=c2.id,
        )
        with pytest.raises(ValueError, match="Source capsule not found"):
            sqlite_storage.create_link(link)

    def test_get_links_for_capsule_directions(self, sqlite_storage, two_capsules_sqlite):
        c1, c2 = two_capsules_sqlite
        link = MemoryLink(source_capsule_id=c1.id, target_capsule_id=c2.id)
        sqlite_storage.create_link(link)

        outgoing = sqlite_storage.get_links_for_capsule(c1.id, direction="outgoing")
        assert len(outgoing) == 1

        incoming = sqlite_storage.get_links_for_capsule(c2.id, direction="incoming")
        assert len(incoming) == 1

        both = sqlite_storage.get_links_for_capsule(c1.id, direction="both")
        assert len(both) == 1

    def test_update_link(self, sqlite_storage, two_capsules_sqlite):
        c1, c2 = two_capsules_sqlite
        link = MemoryLink(
            source_capsule_id=c1.id,
            target_capsule_id=c2.id,
            strength=0.5,
        )
        sqlite_storage.create_link(link)

        link.strength = 0.9
        link.notes = "Updated"
        assert sqlite_storage.update_link(link) is True

        retrieved = sqlite_storage.get_link(link.id)
        assert retrieved.strength == 0.9
        assert retrieved.notes == "Updated"

    def test_delete_link_to_trash(self, sqlite_storage, two_capsules_sqlite):
        c1, c2 = two_capsules_sqlite
        link = MemoryLink(source_capsule_id=c1.id, target_capsule_id=c2.id)
        sqlite_storage.create_link(link)

        assert sqlite_storage.delete_link(link.id) is True
        assert sqlite_storage.get_link(link.id) is None

        trash = sqlite_storage.list_deleted_items(item_type="memory_link")
        assert len(trash) == 1

    def test_restore_link_from_trash(self, sqlite_storage, two_capsules_sqlite):
        c1, c2 = two_capsules_sqlite
        link = MemoryLink(source_capsule_id=c1.id, target_capsule_id=c2.id)
        sqlite_storage.create_link(link)
        link_id = link.id

        sqlite_storage.delete_link(link_id)
        trash = sqlite_storage.list_deleted_items()
        assert len(trash) == 1

        success = sqlite_storage.restore_deleted_item(trash[0].id)
        assert success is True

        restored = sqlite_storage.get_link(link_id)
        assert restored is not None
        assert restored.source_capsule_id == c1.id

    def test_list_link_types(self, sqlite_storage, two_capsules_sqlite):
        c1, c2 = two_capsules_sqlite
        sqlite_storage.create_link(MemoryLink(
            source_capsule_id=c1.id, target_capsule_id=c2.id, link_type="related"
        ))
        sqlite_storage.create_link(MemoryLink(
            source_capsule_id=c1.id, target_capsule_id=c2.id, link_type="supports"
        ))

        types = sqlite_storage.list_link_types()
        assert sorted(types) == ["related", "supports"]

    def test_cascade_delete_on_capsule_removal(self, sqlite_storage, two_capsules_sqlite):
        """When a capsule is deleted, its links should be cascade-deleted by FK."""
        c1, c2 = two_capsules_sqlite
        link = MemoryLink(source_capsule_id=c1.id, target_capsule_id=c2.id)
        sqlite_storage.create_link(link)

        # Delete the source capsule
        sqlite_storage.delete_capsule(c1.id)

        # Link should be gone (cascade delete via FK)
        assert sqlite_storage.get_link(link.id) is None

    def test_linked_capsules_depth_traversal(self, sqlite_storage):
        """Test multi-hop traversal in SQLite."""
        c1 = create_relational(entity="A", summary="First")
        c2 = create_relational(entity="B", summary="Second")
        c3 = create_relational(entity="C", summary="Third")
        sqlite_storage.save_capsule(c1)
        sqlite_storage.save_capsule(c2)
        sqlite_storage.save_capsule(c3)

        sqlite_storage.create_link(MemoryLink(
            source_capsule_id=c1.id, target_capsule_id=c2.id
        ))
        sqlite_storage.create_link(MemoryLink(
            source_capsule_id=c2.id, target_capsule_id=c3.id
        ))

        # Depth 1
        results_d1 = sqlite_storage.get_linked_capsules(c1.id, depth=1)
        assert len(results_d1) == 1

        # Depth 2
        results_d2 = sqlite_storage.get_linked_capsules(c1.id, depth=2)
        assert len(results_d2) == 2

    def test_move_capsule_to_trash_with_links(self, sqlite_storage, two_capsules_sqlite):
        c1, c2 = two_capsules_sqlite
        link = MemoryLink(source_capsule_id=c1.id, target_capsule_id=c2.id)
        sqlite_storage.create_link(link)

        success = sqlite_storage.move_capsule_to_trash(c1.id)
        assert success is True

        trash = sqlite_storage.list_deleted_items(item_type="capsule")
        assert len(trash) == 1
        assert trash[0].item_id == c1.id

        # Verify related links are stored
        related = json.loads(trash[0].related_items) if trash[0].related_items else []
        assert len(related) == 1

    def test_permanently_delete_trash_item(self, sqlite_storage, two_capsules_sqlite):
        c1, c2 = two_capsules_sqlite
        link = MemoryLink(source_capsule_id=c1.id, target_capsule_id=c2.id)
        sqlite_storage.create_link(link)
        sqlite_storage.delete_link(link.id)

        trash = sqlite_storage.list_deleted_items()
        assert len(trash) == 1

        success = sqlite_storage.permanently_delete_trash_item(trash[0].id)
        assert success is True
        assert len(sqlite_storage.list_deleted_items()) == 0

    def test_bidirectional_link(self, sqlite_storage, two_capsules_sqlite):
        c1, c2 = two_capsules_sqlite
        link = MemoryLink(
            source_capsule_id=c1.id,
            target_capsule_id=c2.id,
            bidirectional=True,
        )
        sqlite_storage.create_link(link)

        retrieved = sqlite_storage.get_link(link.id)
        assert retrieved.bidirectional is True

        # Should be found from both sides
        results_c1 = sqlite_storage.get_linked_capsules(c1.id, direction="both")
        assert len(results_c1) == 1

        results_c2 = sqlite_storage.get_linked_capsules(c2.id, direction="both")
        assert len(results_c2) == 1
