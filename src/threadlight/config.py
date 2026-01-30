"""
Configuration management for Threadlight.

Supports environment variables, configuration files, and programmatic configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

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
class MemoryConfig:
    """Configuration for memory system."""

    decay: DecayConfig = field(default_factory=DecayConfig)
    proposals: ProposalConfig = field(default_factory=ProposalConfig)
    conversation: ConversationConfig = field(default_factory=ConversationConfig)
    max_capsules_per_request: int = 5
    similarity_threshold: float = 0.7
    enable_embeddings: bool = False


@dataclass
class StyleConfig:
    """Configuration for style modulation."""

    default_profile: str = "default"
    profiles_path: str = "./styles"
    allow_silence: bool = True
    enforce_constraints: bool = True


@dataclass
class IdentityConfig:
    """Configuration for model identity."""

    name: Optional[str] = None
    seed_dream_path: Optional[str] = None
    system_prompt: Optional[str] = None


@dataclass
class ThreadlightConfig:
    """Main configuration for Threadlight."""

    provider: ProviderConfig = field(default_factory=ProviderConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    style: StyleConfig = field(default_factory=StyleConfig)
    identity: IdentityConfig = field(default_factory=IdentityConfig)

    @classmethod
    def from_env(cls) -> ThreadlightConfig:
        """Load configuration from environment variables."""
        load_dotenv()

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
                default_profile=os.getenv("THREADLIGHT_DEFAULT_STYLE", "default"),
                allow_silence=os.getenv("THREADLIGHT_ALLOW_SILENCE", "true").lower() == "true",
            ),
        )

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
            config.memory.max_capsules_per_request = m.get(
                "max_capsules", config.memory.max_capsules_per_request
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
                name=i.get("name"),
                seed_dream_path=i.get("seed_dream"),
                system_prompt=i.get("system_prompt"),
            )

        return config

    def to_dict(self) -> dict[str, Any]:
        """Export configuration as dictionary."""
        return {
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
                "max_capsules": self.memory.max_capsules_per_request,
            },
            "style": {
                "default_profile": self.style.default_profile,
                "allow_silence": self.style.allow_silence,
                "enforce_constraints": self.style.enforce_constraints,
            },
            "identity": {
                "name": self.identity.name,
                "seed_dream": self.identity.seed_dream_path,
            },
        }
