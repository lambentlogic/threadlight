"""Tests for per-model configuration and auto-persistence."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from threadlight.core import Threadlight
from threadlight.config import ThreadlightConfig, ModelConfig
from threadlight.providers.base import ProviderResponse


@pytest.fixture
def mock_provider():
    """Create a mock provider that returns canned responses."""
    with patch("threadlight.core.create_provider") as mock_create:
        mock_prov = MagicMock()
        mock_prov.complete.return_value = ProviderResponse(
            content="Hello! I'm a test AI.",
            finish_reason="stop",
            model="test-model",
            prompt_tokens=50,
            completion_tokens=20,
            total_tokens=70,
        )
        mock_prov.stream.return_value = iter(["Hello", " world"])
        mock_prov.health_check.return_value = True
        mock_prov.model = "test-model"
        mock_create.return_value = mock_prov
        yield mock_prov


@pytest.fixture
def threadlight(mock_provider):
    """Create a Threadlight instance with mock provider."""
    tl = Threadlight(
        storage_backend="memory",
        identity_name="Test",
        system_prompt="You are a test AI.",
        enable_memory=True,
        enable_decay=False,
    )
    yield tl
    tl.close()


class TestModelConfig:
    """Tests for ModelConfig dataclass."""

    def test_model_config_defaults(self):
        """Test ModelConfig default values."""
        config = ModelConfig(model_id="test-model")

        assert config.model_id == "test-model"
        assert config.system_prompt == "You are a helpful AI assistant."
        assert config.style_profile is None
        assert config.memory_enabled is True
        assert config.decay_enabled is False
        assert config.temperature == 0.7
        assert config.max_tokens is None
        assert config.top_p == 1.0

    def test_model_config_to_dict(self):
        """Test ModelConfig serialization."""
        config = ModelConfig(
            model_id="gpt-4o",
            system_prompt="You are helpful.",
            style_profile="minimal",
            temperature=0.8,
        )

        data = config.to_dict()

        assert data["model_id"] == "gpt-4o"
        assert data["system_prompt"] == "You are helpful."
        assert data["style_profile"] == "minimal"
        assert data["temperature"] == 0.8
        assert data["memory"]["enabled"] is True
        assert data["memory"]["decay_enabled"] is False

    def test_model_config_from_dict(self):
        """Test ModelConfig deserialization."""
        data = {
            "model_id": "claude-opus-4.5",
            "system_prompt": "You are Claude.",
            "style_profile": "professional",
            "memory": {"enabled": True, "decay_enabled": True},
            "temperature": 0.9,
        }

        config = ModelConfig.from_dict(data)

        assert config.model_id == "claude-opus-4.5"
        assert config.system_prompt == "You are Claude."
        assert config.style_profile == "professional"
        assert config.memory_enabled is True
        assert config.decay_enabled is True
        assert config.temperature == 0.9


class TestThreadlightConfigModelManagement:
    """Tests for model config management in ThreadlightConfig."""

    def test_get_model_config_existing(self):
        """Test getting an existing model config."""
        config = ThreadlightConfig()
        model_config = ModelConfig(
            model_id="test-model",
            system_prompt="Test prompt",
        )
        config.model_configs["test-model"] = model_config

        result = config.get_model_config("test-model")

        assert result.model_id == "test-model"
        assert result.system_prompt == "Test prompt"

    def test_get_model_config_new_uses_default(self):
        """Test getting a new model config uses default if available."""
        config = ThreadlightConfig()
        config.model_configs["default"] = ModelConfig(
            model_id="default",
            system_prompt="Default prompt",
            temperature=0.5,
        )

        result = config.get_model_config("new-model")

        assert result.model_id == "new-model"
        assert result.system_prompt == "Default prompt"
        assert result.temperature == 0.5

    def test_get_model_config_new_no_default(self):
        """Test getting a new model config without default."""
        config = ThreadlightConfig()
        config.identity.system_prompt = "Identity prompt"

        result = config.get_model_config("new-model")

        assert result.model_id == "new-model"
        assert result.system_prompt == "Identity prompt"

    def test_set_model_config(self):
        """Test setting a model config."""
        config = ThreadlightConfig()
        model_config = ModelConfig(model_id="test", system_prompt="Hello")

        config.set_model_config("test", model_config)

        assert "test" in config.model_configs
        assert config.model_configs["test"].system_prompt == "Hello"

    def test_update_model_config(self):
        """Test updating a model config."""
        config = ThreadlightConfig()
        config.model_configs["test"] = ModelConfig(
            model_id="test",
            temperature=0.7,
        )

        result = config.update_model_config("test", temperature=0.9)

        assert result.temperature == 0.9
        assert config.model_configs["test"].temperature == 0.9

    def test_copy_model_config(self):
        """Test copying model config."""
        config = ThreadlightConfig()
        config.model_configs["source"] = ModelConfig(
            model_id="source",
            system_prompt="Source prompt",
            temperature=0.8,
        )

        result = config.copy_model_config("source", "target")

        assert result.model_id == "target"
        assert result.system_prompt == "Source prompt"
        assert result.temperature == 0.8
        assert "target" in config.model_configs

    def test_delete_model_config(self):
        """Test deleting model config."""
        config = ThreadlightConfig()
        config.model_configs["test"] = ModelConfig(model_id="test")

        success = config.delete_model_config("test")

        assert success is True
        assert "test" not in config.model_configs

    def test_delete_model_config_not_found(self):
        """Test deleting non-existent model config."""
        config = ThreadlightConfig()

        success = config.delete_model_config("nonexistent")

        assert success is False

    def test_set_as_default(self):
        """Test setting model config as default."""
        config = ThreadlightConfig()
        config.model_configs["source"] = ModelConfig(
            model_id="source",
            system_prompt="Source prompt",
        )

        config.set_as_default("source")

        assert "default" in config.model_configs
        assert config.model_configs["default"].system_prompt == "Source prompt"


class TestThreadlightConfigPersistence:
    """Tests for config auto-persistence."""

    def test_config_to_dict_includes_models(self):
        """Test that to_dict includes model configs."""
        config = ThreadlightConfig()
        config.current_model = "test-model"
        config.model_configs["test-model"] = ModelConfig(
            model_id="test-model",
            system_prompt="Test prompt",
        )

        data = config.to_dict()

        assert "current_model" in data
        assert data["current_model"] == "test-model"
        assert "model_configs" in data
        assert "test-model" in data["model_configs"]

    def test_config_from_dict_loads_models(self):
        """Test that from_dict loads model configs."""
        data = {
            "current_model": "gpt-4o",
            "model_configs": {
                "gpt-4o": {
                    "model_id": "gpt-4o",
                    "system_prompt": "GPT prompt",
                    "temperature": 0.8,
                }
            },
        }

        config = ThreadlightConfig._from_dict(data)

        assert config.current_model == "gpt-4o"
        assert "gpt-4o" in config.model_configs
        assert config.model_configs["gpt-4o"].system_prompt == "GPT prompt"

    def test_save_and_load_with_models(self):
        """Test saving and loading config with model configs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"

            # Create and save config
            config = ThreadlightConfig()
            config.current_model = "hermes"
            config.model_configs["hermes"] = ModelConfig(
                model_id="hermes",
                system_prompt="Hermes prompt",
                temperature=0.7,
            )
            config.model_configs["gpt-4o"] = ModelConfig(
                model_id="gpt-4o",
                system_prompt="GPT prompt",
                temperature=0.8,
            )
            config.save_to_file(config_path)

            # Load config
            loaded = ThreadlightConfig.from_file(config_path)

            assert loaded.current_model == "hermes"
            assert "hermes" in loaded.model_configs
            assert "gpt-4o" in loaded.model_configs
            assert loaded.model_configs["hermes"].system_prompt == "Hermes prompt"
            assert loaded.model_configs["gpt-4o"].temperature == 0.8

    def test_auto_save_enabled(self):
        """Test auto-save can be enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"

            config = ThreadlightConfig()
            config.enable_auto_save(config_path, debounce_ms=10)

            assert config._auto_save is True
            assert config._config_path == config_path

            config.disable_auto_save()

    def test_migrate_to_model_configs(self):
        """Test migration helper."""
        config = ThreadlightConfig()
        config.current_model = "test-model"
        config.identity.system_prompt = "My custom prompt"

        config.migrate_to_model_configs()

        assert "test-model" in config.model_configs
        assert config.model_configs["test-model"].system_prompt == "My custom prompt"
        assert "default" in config.model_configs


class TestThreadlightModelSwitching:
    """Tests for model switching in Threadlight."""

    def test_switch_model(self, threadlight, mock_provider):
        """Test switching models."""
        # Create a config for a different model
        threadlight.config.model_configs["gpt-4o"] = ModelConfig(
            model_id="gpt-4o",
            system_prompt="You are GPT-4o.",
            temperature=0.8,
        )

        result = threadlight.switch_model("gpt-4o")

        assert result.model_id == "gpt-4o"
        assert threadlight.config.current_model == "gpt-4o"
        assert threadlight.config.identity.system_prompt == "You are GPT-4o."

    def test_get_current_model_config(self, threadlight):
        """Test getting current model config."""
        config = threadlight.get_current_model_config()

        assert config is not None
        assert isinstance(config, ModelConfig)

    def test_update_current_model_config(self, threadlight):
        """Test updating current model config."""
        result = threadlight.update_current_model_config(
            system_prompt="Updated prompt",
            temperature=0.9,
        )

        assert result.system_prompt == "Updated prompt"
        assert result.temperature == 0.9

    def test_list_available_models(self, threadlight):
        """Test listing available models."""
        threadlight.config.model_configs["gpt-4o"] = ModelConfig(
            model_id="gpt-4o",
            system_prompt="GPT",
        )

        models = threadlight.list_available_models()

        assert len(models) >= 1
        model_ids = [m["model_id"] for m in models]
        assert "gpt-4o" in model_ids

    def test_create_model_config(self, threadlight):
        """Test creating a new model config."""
        result = threadlight.create_model_config(
            model_id="new-model",
            system_prompt="New prompt",
            temperature=0.6,
        )

        assert result.model_id == "new-model"
        assert result.system_prompt == "New prompt"
        assert "new-model" in threadlight.config.model_configs

    def test_copy_model_settings(self, threadlight):
        """Test copying model settings."""
        threadlight.update_current_model_config(
            system_prompt="Source prompt",
            temperature=0.8,
        )

        result = threadlight.copy_model_settings(
            threadlight.config.current_model,
            "target-model",
        )

        assert result.model_id == "target-model"
        assert result.system_prompt == "Source prompt"
        assert result.temperature == 0.8

    def test_delete_model_config_not_current(self, threadlight):
        """Test deleting a non-current model config."""
        threadlight.config.model_configs["to-delete"] = ModelConfig(
            model_id="to-delete",
        )

        success = threadlight.delete_model_config("to-delete")

        assert success is True
        assert "to-delete" not in threadlight.config.model_configs

    def test_delete_model_config_current_fails(self, threadlight):
        """Test deleting current model config fails."""
        success = threadlight.delete_model_config(threadlight.config.current_model)

        assert success is False
