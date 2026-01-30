"""
Configuration management for Threadlight.

Supports environment variables, configuration files, and programmatic configuration.
Includes per-model configuration profiles and automatic config persistence.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import yaml
from dotenv import load_dotenv


@dataclass
class ProviderConfig:
    """Configuration for inference providers."""

    type: str = "openai"
    api_base: str = "https://inference-api.nousresearch.com/v1"
    api_key: Optional[str] = None
    model: str = "Hermes-4.3-36B"
    timeout: float = 60.0
    max_retries: int = 3

    def __post_init__(self) -> None:
        # Try to load API key from environment if not provided
        if self.api_key is None:
            self.api_key = os.getenv("NOUS_API_KEY") or os.getenv("OPENAI_API_KEY")


@dataclass
class StorageConfig:
    """Configuration for memory storage."""

    backend: str = "sqlite"
    path: str = "./threadlight.db"
    # For future backends
    connection_string: Optional[str] = None


@dataclass
class DecayConfig:
    """Configuration for memory decay."""

    enabled: bool = True
    interval_seconds: int = 3600  # 1 hour
    default_rate: float = 0.1
    minimum_presence: float = 0.1  # Below this, capsule becomes dormant


@dataclass
class ProposalConfig:
    """Configuration for memory proposals."""

    enabled: bool = True
    auto_propose: bool = True
    threshold: int = 3  # Interactions before auto-proposing
    max_pending: int = 50  # Maximum pending proposals


@dataclass
class ConversationConfig:
    """Configuration for conversation history."""

    auto_save_messages: bool = True  # Automatically save messages to database
    conversation_history_limit: int = 20  # Max messages to load from history
    enable_soft_memory: bool = True  # Enable soft memory recall from past conversations
    soft_memory_limit: int = 5  # Max soft memory results
    current_session_weight: float = 2.0  # Weight boost for current session messages


@dataclass
class EmbeddingsConfig:
    """Configuration for semantic search embeddings.

    Recommended embedding models (2024-2025):
    - intfloat/e5-small-v2 (default): Fast, modern, 100MB
    - google/embedding-gemma-300m: Best quality <500M, 250MB
    - nomic-ai/nomic-embed-text-v1.5: Best long-context, 400MB
    - all-MiniLM-L6-v2: Legacy (2020), consider upgrading
    """

    enabled: bool = False  # Whether embeddings are enabled
    provider: str = "local"  # "local", "openai", or "nous"
    model: str = "intfloat/e5-small-v2"  # Modern default (2024), upgrade from all-MiniLM-L6-v2
    auto_generate: bool = True  # Generate embeddings automatically on save
    batch_size: int = 100  # Batch size for bulk operations
    similarity_threshold: float = 0.5  # Minimum similarity for search results


@dataclass
class MemoryConfig:
    """Configuration for memory system."""

    decay: DecayConfig = field(default_factory=DecayConfig)
    proposals: ProposalConfig = field(default_factory=ProposalConfig)
    conversation: ConversationConfig = field(default_factory=ConversationConfig)
    embeddings: EmbeddingsConfig = field(default_factory=EmbeddingsConfig)
    max_capsules_per_request: int = 5
    similarity_threshold: float = 0.7
    enable_embeddings: bool = False  # Deprecated: use embeddings.enabled instead
    # Per-profile memory isolation (profiles are the primary organizational unit)
    per_profile_isolation: bool = False  # When true, memories are scoped to specific profiles
    default_shared: bool = False  # When per_profile_isolation is true, whether new memories are shared by default
    # Deprecated: kept for backward compatibility, mapped to per_profile_isolation
    per_model_isolation: bool = False

    def __post_init__(self) -> None:
        # Migrate per_model_isolation to per_profile_isolation for backward compatibility
        if self.per_model_isolation and not self.per_profile_isolation:
            self.per_profile_isolation = self.per_model_isolation


@dataclass
class StyleConfig:
    """Configuration for style modulation."""

    default_profile: Optional[str] = None  # None = no default style (neutral)
    profiles_path: str = "./styles"
    allow_silence: bool = True
    enforce_constraints: bool = True


@dataclass
class CustomStyleConfig:
    """Configuration for a custom style profile."""

    tone_base: str = "helpful, clear"
    permissions: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    vocal_motifs: list[str] = field(default_factory=list)
    forbidden_patterns: list[str] = field(default_factory=list)


@dataclass
class IdentityConfig:
    """Configuration for model identity."""

    name: str = "Assistant"  # Neutral default
    seed_dream_path: Optional[str] = None
    system_prompt: str = "You are a helpful AI assistant."  # Minimal neutral default


@dataclass
class ModelConfig:
    """Configuration for a specific model."""

    model_id: str
    system_prompt: str = "You are a helpful AI assistant."
    style_profile: Optional[str] = None
    memory_enabled: bool = True
    decay_enabled: bool = False
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """Export model config as dictionary."""
        return {
            "model_id": self.model_id,
            "system_prompt": self.system_prompt,
            "style_profile": self.style_profile,
            "memory": {
                "enabled": self.memory_enabled,
                "decay_enabled": self.decay_enabled,
            },
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelConfig":
        """Create ModelConfig from dictionary."""
        memory_data = data.get("memory", {})
        return cls(
            model_id=data.get("model_id", "unknown"),
            system_prompt=data.get("system_prompt", "You are a helpful AI assistant."),
            style_profile=data.get("style_profile"),
            memory_enabled=memory_data.get("enabled", True) if isinstance(memory_data, dict) else True,
            decay_enabled=memory_data.get("decay_enabled", False) if isinstance(memory_data, dict) else False,
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("max_tokens"),
            top_p=data.get("top_p", 1.0),
        )


@dataclass
class ThreadlightConfig:
    """Main configuration for Threadlight.

    Supports per-model configuration profiles and automatic persistence.
    """

    provider: ProviderConfig = field(default_factory=ProviderConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    style: StyleConfig = field(default_factory=StyleConfig)
    identity: IdentityConfig = field(default_factory=IdentityConfig)
    custom_styles: dict[str, CustomStyleConfig] = field(default_factory=dict)

    # Model-specific configurations
    current_model: str = "Hermes-4.3-36B"
    model_configs: dict[str, ModelConfig] = field(default_factory=dict)

    # Auto-save configuration (not persisted)
    _auto_save: bool = field(default=False, repr=False)
    _config_path: Optional[Path] = field(default=None, repr=False)
    _save_timer: Optional[threading.Timer] = field(default=None, repr=False)
    _save_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _save_debounce_ms: int = field(default=500, repr=False)
    _on_save_callback: Optional[Callable[[], None]] = field(default=None, repr=False)

    @classmethod
    def from_env(cls) -> ThreadlightConfig:
        """Load configuration from environment variables."""
        load_dotenv()

        # Check for user config file first
        config_path = cls._get_config_path()
        if config_path and config_path.exists():
            return cls.from_file(config_path)

        # Default style is None (neutral) unless explicitly set
        default_style_env = os.getenv("THREADLIGHT_DEFAULT_STYLE")
        default_style = default_style_env if default_style_env else None

        return cls(
            provider=ProviderConfig(
                type=os.getenv("THREADLIGHT_PROVIDER", "openai"),
                api_base=os.getenv(
                    "THREADLIGHT_API_BASE",
                    "https://inference-api.nousresearch.com/v1"
                ),
                api_key=os.getenv("NOUS_API_KEY") or os.getenv("OPENAI_API_KEY"),
                model=os.getenv("THREADLIGHT_MODEL", "Hermes-4.3-36B"),
            ),
            storage=StorageConfig(
                backend=os.getenv("THREADLIGHT_STORAGE_BACKEND", "sqlite"),
                path=os.getenv("THREADLIGHT_STORAGE_PATH", "./threadlight.db"),
            ),
            memory=MemoryConfig(
                decay=DecayConfig(
                    enabled=os.getenv("THREADLIGHT_DECAY_ENABLED", "true").lower() == "true",
                    interval_seconds=int(os.getenv("THREADLIGHT_DECAY_INTERVAL", "3600")),
                ),
                max_capsules_per_request=int(
                    os.getenv("THREADLIGHT_MAX_CONTEXT_CAPSULES", "5")
                ),
            ),
            style=StyleConfig(
                default_profile=default_style,
                allow_silence=os.getenv("THREADLIGHT_ALLOW_SILENCE", "true").lower() == "true",
            ),
            identity=IdentityConfig(
                name=os.getenv("THREADLIGHT_IDENTITY_NAME", "Assistant"),
                system_prompt=os.getenv("THREADLIGHT_SYSTEM_PROMPT", "You are a helpful AI assistant."),
            ),
        )

    @staticmethod
    def _get_config_path() -> Optional[Path]:
        """Get the user config file path if it exists."""
        # Check in order: current directory, XDG config, home directory
        candidates = [
            Path("threadlight.yaml"),
            Path("threadlight.yml"),
            Path(os.path.expanduser("~/.config/threadlight/config.yaml")),
            Path(os.path.expanduser("~/.config/threadlight/config.yml")),
            Path(os.path.expanduser("~/.threadlight.yaml")),
            Path(os.path.expanduser("~/.threadlight.yml")),
        ]
        for path in candidates:
            if path.exists():
                return path
        return None

    @classmethod
    def get_user_config_dir(cls) -> Path:
        """Get the user configuration directory, creating it if needed."""
        config_dir = Path(os.path.expanduser("~/.config/threadlight"))
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir

    @classmethod
    def get_styles_dir(cls) -> Path:
        """Get the user styles directory, creating it if needed."""
        styles_dir = cls.get_user_config_dir() / "styles"
        styles_dir.mkdir(parents=True, exist_ok=True)
        return styles_dir

    @classmethod
    def from_file(cls, path: str | Path) -> ThreadlightConfig:
        """Load configuration from a YAML file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(path) as f:
            data = yaml.safe_load(f)

        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> ThreadlightConfig:
        """Create configuration from dictionary."""
        config = cls()

        if "provider" in data:
            p = data["provider"]
            config.provider = ProviderConfig(
                type=p.get("type", config.provider.type),
                api_base=p.get("api_base", config.provider.api_base),
                api_key=p.get("api_key", config.provider.api_key),
                model=p.get("model", config.provider.model),
            )

        if "storage" in data:
            s = data["storage"]
            config.storage = StorageConfig(
                backend=s.get("backend", config.storage.backend),
                path=s.get("path", config.storage.path),
            )

        if "memory" in data:
            m = data["memory"]
            if "decay" in m:
                d = m["decay"]
                config.memory.decay = DecayConfig(
                    enabled=d.get("enabled", config.memory.decay.enabled),
                    interval_seconds=d.get(
                        "interval_seconds", config.memory.decay.interval_seconds
                    ),
                    default_rate=d.get("default_rate", config.memory.decay.default_rate),
                )
            if "proposals" in m:
                pr = m["proposals"]
                config.memory.proposals = ProposalConfig(
                    enabled=pr.get("enabled", config.memory.proposals.enabled),
                    auto_propose=pr.get("auto_propose", config.memory.proposals.auto_propose),
                    threshold=pr.get("threshold", config.memory.proposals.threshold),
                )
            if "conversation" in m:
                cv = m["conversation"]
                config.memory.conversation = ConversationConfig(
                    auto_save_messages=cv.get("auto_save_messages", config.memory.conversation.auto_save_messages),
                    conversation_history_limit=cv.get("conversation_history_limit", config.memory.conversation.conversation_history_limit),
                    enable_soft_memory=cv.get("enable_soft_memory", config.memory.conversation.enable_soft_memory),
                    soft_memory_limit=cv.get("soft_memory_limit", config.memory.conversation.soft_memory_limit),
                    current_session_weight=cv.get("current_session_weight", config.memory.conversation.current_session_weight),
                )
            if "embeddings" in m:
                em = m["embeddings"]
                config.memory.embeddings = EmbeddingsConfig(
                    enabled=em.get("enabled", config.memory.embeddings.enabled),
                    provider=em.get("provider", config.memory.embeddings.provider),
                    model=em.get("model", config.memory.embeddings.model),
                    auto_generate=em.get("auto_generate", config.memory.embeddings.auto_generate),
                    batch_size=em.get("batch_size", config.memory.embeddings.batch_size),
                    similarity_threshold=em.get("similarity_threshold", config.memory.embeddings.similarity_threshold),
                )
            config.memory.max_capsules_per_request = m.get(
                "max_capsules", config.memory.max_capsules_per_request
            )
            # Per-profile memory isolation settings (preferred)
            config.memory.per_profile_isolation = m.get(
                "per_profile_isolation", config.memory.per_profile_isolation
            )
            # Backward compatibility: migrate per_model_isolation to per_profile_isolation
            if m.get("per_model_isolation") and not config.memory.per_profile_isolation:
                config.memory.per_profile_isolation = m.get("per_model_isolation")
            config.memory.default_shared = m.get(
                "default_shared", config.memory.default_shared
            )

        if "style" in data:
            st = data["style"]
            config.style = StyleConfig(
                default_profile=st.get("default_profile", config.style.default_profile),
                allow_silence=st.get("allow_silence", config.style.allow_silence),
                enforce_constraints=st.get(
                    "enforce_constraints", config.style.enforce_constraints
                ),
            )

        if "identity" in data:
            i = data["identity"]
            config.identity = IdentityConfig(
                name=i.get("name", config.identity.name),
                seed_dream_path=i.get("seed_dream"),
                system_prompt=i.get("system_prompt", config.identity.system_prompt),
            )

        # Parse custom styles
        if "custom_styles" in data:
            for style_id, style_data in data["custom_styles"].items():
                config.custom_styles[style_id] = CustomStyleConfig(
                    tone_base=style_data.get("tone_base", "helpful, clear"),
                    permissions=style_data.get("permissions", []),
                    constraints=style_data.get("constraints", []),
                    vocal_motifs=style_data.get("vocal_motifs", []),
                    forbidden_patterns=style_data.get("forbidden_patterns", []),
                )

        # Parse current model
        if "current_model" in data:
            config.current_model = data["current_model"]

        # Parse model configs
        if "model_configs" in data:
            for model_id, model_data in data["model_configs"].items():
                model_data["model_id"] = model_id
                config.model_configs[model_id] = ModelConfig.from_dict(model_data)

        return config

    def to_dict(self) -> dict[str, Any]:
        """Export configuration as dictionary."""
        result = {
            "provider": {
                "type": self.provider.type,
                "api_base": self.provider.api_base,
                "model": self.provider.model,
                # Note: api_key intentionally omitted for security
            },
            "storage": {
                "backend": self.storage.backend,
                "path": self.storage.path,
            },
            "memory": {
                "decay": {
                    "enabled": self.memory.decay.enabled,
                    "interval_seconds": self.memory.decay.interval_seconds,
                    "default_rate": self.memory.decay.default_rate,
                },
                "proposals": {
                    "enabled": self.memory.proposals.enabled,
                    "auto_propose": self.memory.proposals.auto_propose,
                    "threshold": self.memory.proposals.threshold,
                },
                "conversation": {
                    "auto_save_messages": self.memory.conversation.auto_save_messages,
                    "conversation_history_limit": self.memory.conversation.conversation_history_limit,
                    "enable_soft_memory": self.memory.conversation.enable_soft_memory,
                    "soft_memory_limit": self.memory.conversation.soft_memory_limit,
                    "current_session_weight": self.memory.conversation.current_session_weight,
                },
                "embeddings": {
                    "enabled": self.memory.embeddings.enabled,
                    "provider": self.memory.embeddings.provider,
                    "model": self.memory.embeddings.model,
                    "auto_generate": self.memory.embeddings.auto_generate,
                    "batch_size": self.memory.embeddings.batch_size,
                    "similarity_threshold": self.memory.embeddings.similarity_threshold,
                },
                "max_capsules": self.memory.max_capsules_per_request,
                "per_profile_isolation": self.memory.per_profile_isolation,
                "default_shared": self.memory.default_shared,
            },
            "style": {
                "default_profile": self.style.default_profile,
                "allow_silence": self.style.allow_silence,
                "enforce_constraints": self.style.enforce_constraints,
            },
            "identity": {
                "name": self.identity.name,
                "seed_dream": self.identity.seed_dream_path,
                "system_prompt": self.identity.system_prompt,
            },
            "custom_styles": {
                style_id: {
                    "tone_base": style.tone_base,
                    "permissions": style.permissions,
                    "constraints": style.constraints,
                    "vocal_motifs": style.vocal_motifs,
                    "forbidden_patterns": style.forbidden_patterns,
                }
                for style_id, style in self.custom_styles.items()
            },
            "current_model": self.current_model,
            "model_configs": {
                model_id: model_config.to_dict()
                for model_id, model_config in self.model_configs.items()
            },
        }
        return result

    def save_to_file(self, path: Optional[str | Path] = None) -> Path:
        """Save configuration to a YAML file."""
        if path is None:
            path = self._config_path or self.get_user_config_dir() / "config.yaml"
        else:
            path = Path(path)

        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)

        return path

    # === Model Configuration Management ===

    def get_model_config(self, model_id: Optional[str] = None) -> ModelConfig:
        """Get config for specific model, or default if not found.

        Args:
            model_id: Model identifier. If None, uses current_model.

        Returns:
            ModelConfig for the specified model
        """
        model_id = model_id or self.current_model

        if model_id in self.model_configs:
            return self.model_configs[model_id]

        # Check for a default config
        if "default" in self.model_configs:
            default_config = self.model_configs["default"]
            # Create a copy with the new model_id
            return ModelConfig(
                model_id=model_id,
                system_prompt=default_config.system_prompt,
                style_profile=default_config.style_profile,
                memory_enabled=default_config.memory_enabled,
                decay_enabled=default_config.decay_enabled,
                temperature=default_config.temperature,
                max_tokens=default_config.max_tokens,
                top_p=default_config.top_p,
            )

        # Return a new default config
        return ModelConfig(
            model_id=model_id,
            system_prompt=self.identity.system_prompt,
            style_profile=self.style.default_profile,
            memory_enabled=True,
            decay_enabled=self.memory.decay.enabled,
            temperature=0.7,
        )

    def set_model_config(self, model_id: str, config: ModelConfig) -> None:
        """Set config for specific model.

        Args:
            model_id: Model identifier
            config: ModelConfig to set
        """
        self.model_configs[model_id] = config
        self._trigger_auto_save()

    def update_model_config(self, model_id: str, **kwargs: Any) -> ModelConfig:
        """Update specific fields of a model config.

        Args:
            model_id: Model identifier
            **kwargs: Fields to update

        Returns:
            Updated ModelConfig
        """
        config = self.get_model_config(model_id)

        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)

        self.model_configs[model_id] = config
        self._trigger_auto_save()
        return config

    def list_model_configs(self) -> list[str]:
        """List all configured model IDs.

        Returns:
            List of model identifiers
        """
        return list(self.model_configs.keys())

    def delete_model_config(self, model_id: str) -> bool:
        """Delete a model config.

        Args:
            model_id: Model identifier to delete

        Returns:
            True if deleted, False if not found
        """
        if model_id in self.model_configs:
            del self.model_configs[model_id]
            self._trigger_auto_save()
            return True
        return False

    def copy_model_config(self, source_model_id: str, target_model_id: str) -> ModelConfig:
        """Copy settings from one model to another.

        Args:
            source_model_id: Model to copy from
            target_model_id: Model to copy to

        Returns:
            The new ModelConfig
        """
        source = self.get_model_config(source_model_id)
        new_config = ModelConfig(
            model_id=target_model_id,
            system_prompt=source.system_prompt,
            style_profile=source.style_profile,
            memory_enabled=source.memory_enabled,
            decay_enabled=source.decay_enabled,
            temperature=source.temperature,
            max_tokens=source.max_tokens,
            top_p=source.top_p,
        )
        self.model_configs[target_model_id] = new_config
        self._trigger_auto_save()
        return new_config

    def set_as_default(self, model_id: str) -> None:
        """Set a model's config as the default for new models.

        Args:
            model_id: Model whose config to use as default
        """
        source = self.get_model_config(model_id)
        self.model_configs["default"] = ModelConfig(
            model_id="default",
            system_prompt=source.system_prompt,
            style_profile=source.style_profile,
            memory_enabled=source.memory_enabled,
            decay_enabled=source.decay_enabled,
            temperature=source.temperature,
            max_tokens=source.max_tokens,
            top_p=source.top_p,
        )
        self._trigger_auto_save()

    # === Auto-Save Functionality ===

    def enable_auto_save(
        self,
        path: Optional[Path] = None,
        debounce_ms: int = 500,
        on_save: Optional[Callable[[], None]] = None,
    ) -> None:
        """Enable automatic saving when config changes.

        Args:
            path: Path to save to. Defaults to ~/.config/threadlight/config.yaml
            debounce_ms: Milliseconds to wait after last change before saving
            on_save: Optional callback to invoke after saving
        """
        self._auto_save = True
        self._config_path = path or Path(os.path.expanduser("~/.config/threadlight/config.yaml"))
        self._save_debounce_ms = debounce_ms
        self._on_save_callback = on_save

    def disable_auto_save(self) -> None:
        """Disable automatic saving."""
        self._auto_save = False
        with self._save_lock:
            if self._save_timer:
                self._save_timer.cancel()
                self._save_timer = None

    def _trigger_auto_save(self) -> None:
        """Trigger a debounced auto-save if enabled."""
        if not self._auto_save:
            return

        with self._save_lock:
            # Cancel any pending save
            if self._save_timer:
                self._save_timer.cancel()

            # Schedule a new save
            self._save_timer = threading.Timer(
                self._save_debounce_ms / 1000.0,
                self._do_auto_save,
            )
            self._save_timer.daemon = True
            self._save_timer.start()

    def _do_auto_save(self) -> None:
        """Perform the actual auto-save."""
        try:
            self.save_to_file(self._config_path)
            if self._on_save_callback:
                self._on_save_callback()
        except Exception:
            # Silently fail auto-save to not interrupt the application
            pass

    def mark_changed(self) -> None:
        """Manually trigger an auto-save.

        Call this after making direct changes to nested config objects.
        """
        self._trigger_auto_save()

    @classmethod
    def load(
        cls,
        path: Optional[Path] = None,
        auto_save: bool = True,
        debounce_ms: int = 500,
    ) -> "ThreadlightConfig":
        """Load config from file and optionally enable auto-save.

        Args:
            path: Path to load from. Auto-detects if not provided.
            auto_save: Whether to enable auto-saving
            debounce_ms: Milliseconds to wait before saving

        Returns:
            ThreadlightConfig instance
        """
        # Determine path
        if path is None:
            path = cls._get_config_path()

        # Load or create config
        if path and path.exists():
            config = cls.from_file(path)
            config._config_path = path
        else:
            config = cls.from_env()
            config._config_path = path or Path(os.path.expanduser("~/.config/threadlight/config.yaml"))

        # Enable auto-save if requested
        if auto_save:
            config.enable_auto_save(config._config_path, debounce_ms)

        return config

    # === Migration Helper ===

    def migrate_to_model_configs(self) -> None:
        """Migrate existing config to per-model configuration.

        Creates a model config for the current model based on existing settings.
        This is useful for existing users upgrading to the new config format.
        """
        if self.current_model not in self.model_configs:
            self.model_configs[self.current_model] = ModelConfig(
                model_id=self.current_model,
                system_prompt=self.identity.system_prompt,
                style_profile=self.style.default_profile,
                memory_enabled=True,
                decay_enabled=self.memory.decay.enabled,
                temperature=0.7,
            )

        # Also create a default config
        if "default" not in self.model_configs:
            self.model_configs["default"] = ModelConfig(
                model_id="default",
                system_prompt="You are a helpful AI assistant.",
                style_profile=None,
                memory_enabled=True,
                decay_enabled=False,
                temperature=0.7,
            )

        self._trigger_auto_save()
