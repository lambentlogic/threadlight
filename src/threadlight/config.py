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
from dotenv import load_dotenv, set_key


def save_api_key_to_env(provider_id: str, api_key: str) -> Path:
    """Save an API key to the Threadlight .env file.

    The key is saved in the format: <PROVIDER_ID>_API_KEY=<key>
    This allows automatic loading via load_dotenv() on startup.

    After saving, the .env file is reloaded with override=True so the
    new value is immediately available to the running process without
    requiring a server restart.

    Args:
        provider_id: The provider identifier (e.g., "openai", "anthropic")
        api_key: The API key to save

    Returns:
        Path to the .env file
    """
    config_dir = Path(os.path.expanduser("~/.config/threadlight"))
    config_dir.mkdir(parents=True, exist_ok=True)
    env_path = config_dir / ".env"

    # Create the file with secure permissions if it doesn't exist
    if not env_path.exists():
        env_path.touch(mode=0o600)
    else:
        # Ensure existing file has secure permissions
        env_path.chmod(0o600)

    # Format the environment variable name
    env_var_name = f"{provider_id.upper()}_API_KEY"

    # Use python-dotenv's set_key to add/update the key
    # This preserves other variables in the file
    set_key(str(env_path), env_var_name, api_key)

    # Reload the .env file so the new value is immediately available
    # to the running process. override=True ensures the new value
    # replaces any existing environment variable.
    load_dotenv(env_path, override=True)

    return env_path


def get_env_file_path() -> Path:
    """Get the path to the Threadlight .env file.

    Returns:
        Path to ~/.config/threadlight/.env
    """
    return Path(os.path.expanduser("~/.config/threadlight/.env"))


@dataclass
class Endpoint:
    """A single API endpoint configuration."""

    url: str
    name: str = ""  # Display name (e.g., "Primary", "Backup")
    priority: int = 0  # Lower = higher priority (0 is primary)
    purpose: str = ""  # Purpose description (e.g., "main", "fallback", "fast")
    is_healthy: Optional[bool] = None  # Last known health status
    last_checked: Optional[str] = None  # ISO timestamp of last health check

    def to_dict(self) -> dict[str, Any]:
        """Export endpoint as dictionary."""
        return {
            "url": self.url,
            "name": self.name,
            "priority": self.priority,
            "purpose": self.purpose,
            "is_healthy": self.is_healthy,
            "last_checked": self.last_checked,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Endpoint":
        """Create Endpoint from dictionary."""
        return cls(
            url=data.get("url", ""),
            name=data.get("name", ""),
            priority=data.get("priority", 0),
            purpose=data.get("purpose", ""),
            is_healthy=data.get("is_healthy"),
            last_checked=data.get("last_checked"),
        )


@dataclass
class ProviderDefinition:
    """A named provider configuration for multi-provider support.

    Each provider definition represents a distinct inference backend that can
    be used by one or more models. This allows users to configure multiple
    providers (e.g., Anthropic, local Ollama, OpenAI) and have different
    models route to appropriate providers.

    Example providers:
        - "anthropic": Anthropic API for Claude models
        - "local-ollama": Local Ollama instance for Hermes/Llama models
        - "openai-prod": OpenAI API for GPT models
    """

    id: str  # Unique identifier (e.g., "anthropic", "local-ollama", "openai-prod")
    name: str  # Display name (e.g., "Anthropic", "Local Ollama")
    type: str = "openai"  # Provider type: "openai", "anthropic", "local", "custom"

    # Authentication - exactly one of api_key or api_key_env_var should be set
    api_key: Optional[str] = None  # Direct API key (stored securely)
    api_key_env_var: Optional[str] = None  # Environment variable name for API key

    # Endpoints (supports multiple for fallback)
    endpoints: list[Endpoint] = field(default_factory=list)

    # Default model for this provider (used if model doesn't specify)
    default_model: str = ""

    # Provider-specific settings
    timeout: float = 60.0
    max_retries: int = 3
    extra_headers: dict[str, str] = field(default_factory=dict)

    # Anthropic-specific
    anthropic_version: str = "2023-06-01"

    # Health tracking
    is_healthy: Optional[bool] = None
    last_checked: Optional[str] = None

    def __post_init__(self) -> None:
        """Initialize provider with defaults."""
        # Resolve API key from environment if using env var
        # Use 'not self.api_key' to treat empty strings as missing (same as None)
        if not self.api_key and self.api_key_env_var:
            self.api_key = os.getenv(self.api_key_env_var)

        # Ensure at least one endpoint based on provider type
        if not self.endpoints:
            default_endpoints = {
                "openai": "https://api.openai.com/v1",
                "anthropic": "https://api.anthropic.com",
                "nous": "https://inference-api.nousresearch.com/v1",
                "local": "http://localhost:11434/v1",  # Ollama default
            }
            default_url = default_endpoints.get(self.type, "")
            if default_url:
                self.endpoints = [Endpoint(url=default_url, name="Primary", priority=0)]

    @property
    def api_base(self) -> str:
        """Get the primary API base URL for backward compatibility."""
        if not self.endpoints:
            return ""
        sorted_endpoints = sorted(self.endpoints, key=lambda e: e.priority)
        return sorted_endpoints[0].url

    def get_api_key(self) -> Optional[str]:
        """Get the resolved API key (from direct value or environment)."""
        if self.api_key:
            return self.api_key
        if self.api_key_env_var:
            return os.getenv(self.api_key_env_var)
        return None

    def to_dict(self) -> dict[str, Any]:
        """Export provider definition as dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "api_key_env_var": self.api_key_env_var,  # Don't serialize actual key
            "endpoints": [ep.to_dict() for ep in self.endpoints],
            "default_model": self.default_model,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "extra_headers": self.extra_headers,
            "anthropic_version": self.anthropic_version,
            "is_healthy": self.is_healthy,
            "last_checked": self.last_checked,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderDefinition":
        """Create ProviderDefinition from dictionary."""
        endpoints = [
            Endpoint.from_dict(ep) for ep in data.get("endpoints", [])
        ]
        return cls(
            id=data.get("id", "default"),
            name=data.get("name", "Default Provider"),
            type=data.get("type", "openai"),
            api_key=data.get("api_key"),  # May be loaded if present
            api_key_env_var=data.get("api_key_env_var"),
            endpoints=endpoints,
            default_model=data.get("default_model", ""),
            timeout=data.get("timeout", 60.0),
            max_retries=data.get("max_retries", 3),
            extra_headers=data.get("extra_headers", {}),
            anthropic_version=data.get("anthropic_version", "2023-06-01"),
            is_healthy=data.get("is_healthy"),
            last_checked=data.get("last_checked"),
        )


@dataclass
class ProviderConfig:
    """Configuration for inference providers."""

    type: str = "openai"
    api_key: Optional[str] = None
    model: str = "Hermes-4.3-36B"
    timeout: float = 60.0
    max_retries: int = 3

    # Multiple endpoints support
    endpoints: list[Endpoint] = field(default_factory=list)

    # Deprecated: single api_base (kept for backward compatibility)
    # When loaded from old config, this will be migrated to endpoints
    _api_base: Optional[str] = field(default=None, repr=False)

    # Track whether API key was explicitly configured (vs auto-loaded from env)
    # This is used to determine if there's legacy config worth migrating
    _api_key_explicit: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        # Track if API key was explicitly set before loading from env
        # Use truthiness to exclude empty strings (which are not real keys)
        if self.api_key:
            self._api_key_explicit = True

        # Try to load API key from environment if not provided
        # Use 'not self.api_key' to treat empty strings as missing (same as None)
        if not self.api_key:
            self.api_key = os.getenv("NOUS_API_KEY") or os.getenv("OPENAI_API_KEY")

        # Migrate legacy api_base to endpoints if needed
        if self._api_base and not self.endpoints:
            self.endpoints = [Endpoint(url=self._api_base, name="Primary", priority=0)]
            self._api_base = None

        # Ensure at least one default endpoint
        if not self.endpoints:
            self.endpoints = [
                Endpoint(
                    url="https://inference-api.nousresearch.com/v1",
                    name="Primary",
                    priority=0,
                )
            ]

    @property
    def api_base(self) -> str:
        """Get the primary API base URL (highest priority endpoint).

        This property maintains backward compatibility with code that expects
        a single api_base value.
        """
        if not self.endpoints:
            return ""
        # Return the endpoint with lowest priority number (highest priority)
        sorted_endpoints = sorted(self.endpoints, key=lambda e: e.priority)
        return sorted_endpoints[0].url

    @api_base.setter
    def api_base(self, value: str) -> None:
        """Set the primary API base URL.

        This setter maintains backward compatibility. It updates the primary
        endpoint or creates one if no endpoints exist.
        """
        if not self.endpoints:
            self.endpoints = [Endpoint(url=value, name="Primary", priority=0)]
        else:
            # Find and update the primary endpoint (lowest priority number)
            sorted_endpoints = sorted(self.endpoints, key=lambda e: e.priority)
            sorted_endpoints[0].url = value

    def get_endpoints_by_priority(self) -> list[Endpoint]:
        """Get all endpoints sorted by priority (lowest number first)."""
        return sorted(self.endpoints, key=lambda e: e.priority)

    def get_healthy_endpoints(self) -> list[Endpoint]:
        """Get only healthy endpoints, sorted by priority."""
        return [
            e for e in self.get_endpoints_by_priority()
            if e.is_healthy is None or e.is_healthy
        ]

    def add_endpoint(
        self,
        url: str,
        name: str = "",
        priority: Optional[int] = None,
        purpose: str = "",
    ) -> Endpoint:
        """Add a new endpoint.

        Args:
            url: The endpoint URL
            name: Display name for the endpoint
            priority: Priority (lower = higher priority). Auto-assigns if not provided.
            purpose: Purpose description

        Returns:
            The created Endpoint
        """
        if priority is None:
            # Auto-assign priority as one higher than current max
            priority = max((e.priority for e in self.endpoints), default=-1) + 1

        endpoint = Endpoint(url=url, name=name, priority=priority, purpose=purpose)
        self.endpoints.append(endpoint)
        return endpoint

    def remove_endpoint(self, url: str) -> bool:
        """Remove an endpoint by URL.

        Args:
            url: The URL of the endpoint to remove

        Returns:
            True if removed, False if not found
        """
        for i, e in enumerate(self.endpoints):
            if e.url == url:
                self.endpoints.pop(i)
                return True
        return False

    def update_endpoint_health(
        self,
        url: str,
        is_healthy: bool,
        timestamp: Optional[str] = None,
    ) -> None:
        """Update the health status of an endpoint.

        Args:
            url: The endpoint URL
            is_healthy: Whether the endpoint is healthy
            timestamp: ISO timestamp (auto-generated if not provided)
        """
        from datetime import datetime, timezone

        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()

        for e in self.endpoints:
            if e.url == url:
                e.is_healthy = is_healthy
                e.last_checked = timestamp
                break


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

    # Anchored memory settings
    # max_anchored_memories: Maximum number of anchored memories to include per request
    max_anchored_memories: int = 10
    # anchored_demotion_threshold: Presence score below which anchored_decaying memories can be demoted to semantic
    anchored_demotion_threshold: float = 0.3
    # anchored_demotion_days: Days of inactivity (with low access count) before demotion consideration
    anchored_demotion_days: int = 90

    # Inter-memory threads (linked memory recall)
    include_linked_in_recall: bool = False  # Whether to include linked memories during recall
    max_link_depth: int = 1  # How many hops to traverse (1 = direct links only)
    max_links_per_capsule: int = 2  # Maximum linked capsules per recalled memory

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
    system_prompt: str = ""  # Minimal neutral default


@dataclass
class ModelConfig:
    """Configuration for a specific model.

    Each model config now includes a provider_id that specifies which
    ProviderDefinition to use for inference. This enables multi-provider
    support where different models can use different providers.
    """

    model_id: str
    system_prompt: str = ""
    style_profile: Optional[str] = None
    memory_enabled: bool = True
    decay_enabled: bool = False
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: float = 1.0

    # Multi-provider support: which provider to use for this model
    # If None, uses the default provider from ThreadlightConfig.provider
    provider_id: Optional[str] = None

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
            "provider_id": self.provider_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelConfig":
        """Create ModelConfig from dictionary."""
        memory_data = data.get("memory", {})
        return cls(
            model_id=data.get("model_id", "unknown"),
            system_prompt=data.get("system_prompt", ""),
            style_profile=data.get("style_profile"),
            memory_enabled=memory_data.get("enabled", True) if isinstance(memory_data, dict) else True,
            decay_enabled=memory_data.get("decay_enabled", False) if isinstance(memory_data, dict) else False,
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("max_tokens"),
            top_p=data.get("top_p", 1.0),
            provider_id=data.get("provider_id"),
        )


@dataclass
class ThreadlightConfig:
    """Main configuration for Threadlight.

    Supports per-model configuration profiles, multi-provider support,
    and automatic persistence.

    Multi-provider Architecture:
        The 'providers' dict contains named ProviderDefinition objects that
        configure different inference backends (Anthropic, OpenAI, local Ollama, etc.).
        Each ModelConfig can reference a specific provider via provider_id.

        The legacy 'provider' field is maintained for backward compatibility
        and serves as the default provider when a model doesn't specify one.
    """

    # Legacy single provider (kept for backward compatibility)
    # When no providers dict exists, this is used as the default
    provider: ProviderConfig = field(default_factory=ProviderConfig)

    # Multi-provider support: named provider definitions
    # Keys are provider IDs (e.g., "anthropic", "local-ollama")
    providers: dict[str, ProviderDefinition] = field(default_factory=dict)

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
        # Load from standard .env files first
        load_dotenv()

        # Also load from Threadlight-specific .env file
        # Use override=False to not overwrite system env vars or already-loaded vars
        threadlight_env = get_env_file_path()
        if threadlight_env.exists():
            load_dotenv(threadlight_env, override=False)

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
                _api_base=os.getenv(
                    "THREADLIGHT_API_BASE",
                    "https://inference-api.nousresearch.com/v1"
                ),
                # Don't pass api_key here - let ProviderConfig load from env
                # This ensures _api_key_explicit remains False for env-loaded keys
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
                system_prompt=os.getenv("THREADLIGHT_SYSTEM_PROMPT", ""),
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
            # Parse endpoints if present (new format)
            endpoints = []
            if "endpoints" in p:
                for ep_data in p["endpoints"]:
                    endpoints.append(Endpoint.from_dict(ep_data))

            # Handle legacy api_base (old format) - migrate to endpoints
            legacy_api_base = p.get("api_base")
            if legacy_api_base and not endpoints:
                endpoints = [Endpoint(url=legacy_api_base, name="Primary", priority=0)]

            # Track if API key was explicitly set in config file
            explicit_api_key = p.get("api_key")
            config.provider = ProviderConfig(
                type=p.get("type", config.provider.type),
                api_key=explicit_api_key if explicit_api_key else config.provider.api_key,
                model=p.get("model", config.provider.model),
                endpoints=endpoints if endpoints else config.provider.endpoints,
            )
            # Mark as explicit if loaded from config file
            if explicit_api_key:
                config.provider._api_key_explicit = True

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
            # Anchored memory settings
            config.memory.max_anchored_memories = m.get(
                "max_anchored_memories", config.memory.max_anchored_memories
            )
            config.memory.anchored_demotion_threshold = m.get(
                "anchored_demotion_threshold", config.memory.anchored_demotion_threshold
            )
            config.memory.anchored_demotion_days = m.get(
                "anchored_demotion_days", config.memory.anchored_demotion_days
            )
            # Inter-memory threads
            config.memory.include_linked_in_recall = m.get(
                "include_linked_in_recall", config.memory.include_linked_in_recall
            )
            config.memory.max_link_depth = m.get(
                "max_link_depth", config.memory.max_link_depth
            )
            config.memory.max_links_per_capsule = m.get(
                "max_links_per_capsule", config.memory.max_links_per_capsule
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

        # Parse providers (multi-provider support)
        if "providers" in data:
            for provider_id, provider_data in data["providers"].items():
                provider_data["id"] = provider_id
                config.providers[provider_id] = ProviderDefinition.from_dict(provider_data)

        return config

    def to_dict(self) -> dict[str, Any]:
        """Export configuration as dictionary."""
        result = {
            "provider": {
                "type": self.provider.type,
                "model": self.provider.model,
                # Store endpoints in new format
                "endpoints": [ep.to_dict() for ep in self.provider.endpoints],
                # Also keep api_base for backward compatibility with older readers
                "api_base": self.provider.api_base,
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
                # Anchored memory settings
                "max_anchored_memories": self.memory.max_anchored_memories,
                "anchored_demotion_threshold": self.memory.anchored_demotion_threshold,
                "anchored_demotion_days": self.memory.anchored_demotion_days,
                # Inter-memory threads
                "include_linked_in_recall": self.memory.include_linked_in_recall,
                "max_link_depth": self.memory.max_link_depth,
                "max_links_per_capsule": self.memory.max_links_per_capsule,
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
            # Multi-provider support
            "providers": {
                provider_id: provider_def.to_dict()
                for provider_id, provider_def in self.providers.items()
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
                provider_id=default_config.provider_id,  # Inherit provider from default
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
            provider_id=source.provider_id,
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
            provider_id=source.provider_id,
        )
        self._trigger_auto_save()

    # === Provider Management ===

    def get_provider(self, provider_id: str) -> Optional[ProviderDefinition]:
        """Get a provider definition by ID.

        Args:
            provider_id: Provider identifier

        Returns:
            ProviderDefinition if found, None otherwise
        """
        return self.providers.get(provider_id)

    def get_provider_for_model(self, model_id: str) -> Optional[ProviderDefinition]:
        """Get the provider definition for a specific model.

        Looks up the model's config to find its provider_id, then returns
        the corresponding provider definition.

        Args:
            model_id: Model identifier

        Returns:
            ProviderDefinition if found, None if model uses default provider
        """
        model_config = self.model_configs.get(model_id)
        if model_config and model_config.provider_id:
            return self.providers.get(model_config.provider_id)
        return None

    def add_provider(self, provider: ProviderDefinition) -> None:
        """Add a new provider definition.

        Args:
            provider: ProviderDefinition to add
        """
        self.providers[provider.id] = provider
        self._trigger_auto_save()

    def update_provider(self, provider_id: str, **kwargs: Any) -> Optional[ProviderDefinition]:
        """Update a provider definition.

        Args:
            provider_id: Provider identifier
            **kwargs: Fields to update

        Returns:
            Updated ProviderDefinition, or None if not found
        """
        provider = self.providers.get(provider_id)
        if not provider:
            return None

        for key, value in kwargs.items():
            if hasattr(provider, key):
                setattr(provider, key, value)

        self._trigger_auto_save()
        return provider

    def delete_provider(self, provider_id: str) -> bool:
        """Delete a provider definition.

        Note: This will not automatically update models that reference this provider.
        Those models will fall back to the default provider.

        Args:
            provider_id: Provider identifier to delete

        Returns:
            True if deleted, False if not found
        """
        if provider_id in self.providers:
            del self.providers[provider_id]
            self._trigger_auto_save()
            return True
        return False

    def list_providers(self) -> list[str]:
        """List all configured provider IDs.

        Returns:
            List of provider identifiers
        """
        return list(self.providers.keys())

    def get_default_provider_id(self) -> Optional[str]:
        """Get the default provider ID.

        Returns the first provider marked as default, or the first provider
        if none is marked as default, or None if no providers are configured.

        Returns:
            Default provider ID, or None
        """
        if not self.providers:
            return None
        # Return the first provider ID as default
        return next(iter(self.providers.keys()))

    def migrate_single_provider_to_multi(self) -> None:
        """Migrate legacy single-provider config to multi-provider format.

        This creates a provider definition from the existing ProviderConfig
        and adds it to the providers dict. Safe to call multiple times.
        """
        if self.providers:
            # Already have providers defined, no migration needed
            return

        # Create a default provider from the legacy config
        provider_id = "default"

        # Infer a better ID from the provider type/URL
        if "anthropic" in self.provider.api_base.lower():
            provider_id = "anthropic"
        elif "openai" in self.provider.api_base.lower():
            provider_id = "openai"
        elif "nousresearch" in self.provider.api_base.lower():
            provider_id = "nous"
        elif "localhost" in self.provider.api_base.lower() or "127.0.0.1" in self.provider.api_base:
            provider_id = "local"

        # Create provider definition from legacy config
        provider = ProviderDefinition(
            id=provider_id,
            name=provider_id.title(),
            type=self.provider.type,
            api_key=self.provider.api_key,
            endpoints=self.provider.endpoints.copy(),
            default_model=self.provider.model,
            timeout=self.provider.timeout,
            max_retries=self.provider.max_retries,
        )

        self.providers[provider_id] = provider

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
                system_prompt="",
                style_profile=None,
                memory_enabled=True,
                decay_enabled=False,
                temperature=0.7,
            )

        self._trigger_auto_save()
