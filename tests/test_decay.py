"""Tests for the decay engine."""

import pytest
from datetime import datetime, timedelta

from threadlight.storage.memory import InMemoryStorage
from threadlight.decay.engine import (
    DecayEngine,
    LinearDecayStrategy,
    ExponentialDecayStrategy,
)
from threadlight.capsules.relational import create_relational
from threadlight.capsules.myth_seed import create_myth_seed
from threadlight.capsules.base import RetentionPolicy


@pytest.fixture
def storage():
    s = InMemoryStorage()
    s.initialize()
    yield s
    s.close()


@pytest.fixture
def decay_engine(storage):
    return DecayEngine(
        storage=storage,
        strategy=LinearDecayStrategy(),
        min_age_hours=0,  # Allow immediate decay for testing
    )


class TestLinearDecayStrategy:
    def test_sacred_never_decays(self):
        strategy = LinearDecayStrategy()
        capsule = create_myth_seed(seed="Sacred")
        capsule.retention = RetentionPolicy.SACRED
        capsule.presence_score = 1.0
        capsule.last_accessed = datetime.utcnow() - timedelta(days=365)

        new_score = strategy.calculate_decay(capsule, datetime.utcnow())
        assert new_score == 1.0  # Unchanged

    def test_normal_decay(self):
        strategy = LinearDecayStrategy(base_period_days=30)
        capsule = create_relational(entity="Test", summary="Test")
        capsule.decay_rate = 0.5
        capsule.presence_score = 1.0
        capsule.last_accessed = datetime.utcnow() - timedelta(days=30)

        new_score = strategy.calculate_decay(capsule, datetime.utcnow())
        assert new_score < 1.0

    def test_ephemeral_decays_faster(self):
        strategy = LinearDecayStrategy(base_period_days=30)

        normal = create_relational(entity="Normal", summary="Test")
        normal.retention = RetentionPolicy.NORMAL
        normal.decay_rate = 0.5
        normal.presence_score = 1.0
        normal.last_accessed = datetime.utcnow() - timedelta(days=10)

        ephemeral = create_relational(entity="Ephemeral", summary="Test")
        ephemeral.retention = RetentionPolicy.EPHEMERAL
        ephemeral.decay_rate = 0.5
        ephemeral.presence_score = 1.0
        ephemeral.last_accessed = datetime.utcnow() - timedelta(days=10)

        normal_score = strategy.calculate_decay(normal, datetime.utcnow())
        ephemeral_score = strategy.calculate_decay(ephemeral, datetime.utcnow())

        assert ephemeral_score < normal_score

    def test_access_reinforcement(self):
        strategy = LinearDecayStrategy(access_bonus_factor=0.1)

        accessed = create_relational(entity="Accessed", summary="Test")
        accessed.access_count = 10
        accessed.decay_rate = 0.5
        accessed.presence_score = 0.5
        accessed.last_accessed = datetime.utcnow() - timedelta(days=30)

        not_accessed = create_relational(entity="NotAccessed", summary="Test")
        not_accessed.access_count = 0
        not_accessed.decay_rate = 0.5
        not_accessed.presence_score = 0.5
        not_accessed.last_accessed = datetime.utcnow() - timedelta(days=30)

        accessed_score = strategy.calculate_decay(accessed, datetime.utcnow())
        not_accessed_score = strategy.calculate_decay(not_accessed, datetime.utcnow())

        assert accessed_score > not_accessed_score


class TestDecayEngine:
    def test_run_cycle(self, storage, decay_engine):
        # Create capsules
        c1 = create_relational(entity="C1", summary="Test")
        c1.last_accessed = datetime.utcnow() - timedelta(days=60)
        storage.save_capsule(c1)

        c2 = create_relational(entity="C2", summary="Test")
        c2.last_accessed = datetime.utcnow() - timedelta(days=60)
        storage.save_capsule(c2)

        # Run decay
        result = decay_engine.run_cycle()

        assert result.capsules_processed == 2
        assert result.capsules_decayed == 2
        assert len(result.updates) == 2

    def test_touch_refreshes_capsule(self, storage, decay_engine):
        capsule = create_relational(entity="Test", summary="Test")
        capsule.last_accessed = datetime.utcnow() - timedelta(days=30)
        storage.save_capsule(capsule)

        old_accessed = capsule.last_accessed
        decay_engine.touch_capsule(capsule.id)

        refreshed = storage.get_capsule(capsule.id)
        assert refreshed.last_accessed > old_accessed

    def test_revive_dormant(self, storage, decay_engine):
        capsule = create_relational(entity="Dormant", summary="Test")
        capsule.presence_score = 0.05
        storage.save_capsule(capsule)

        revived = decay_engine.revive_capsule(capsule.id, new_score=1.0)

        assert revived.presence_score == 1.0

    def test_get_dormant_capsules(self, storage, decay_engine):
        alive = create_relational(entity="Alive", summary="Test")
        alive.presence_score = 0.8
        alive.consent_confirmed = True
        storage.save_capsule(alive)

        dormant = create_relational(entity="Dormant", summary="Test")
        dormant.presence_score = 0.05
        dormant.consent_confirmed = True
        storage.save_capsule(dormant)

        result = decay_engine.get_dormant_capsules()

        assert len(result) == 1
        assert result[0].entity == "Dormant"
