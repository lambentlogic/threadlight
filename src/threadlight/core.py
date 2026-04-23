"""
Core Threadlight class.

The main interface for presence-centered AI interactions.

Threadlight is a memory framework that enables AI models to maintain:
- Relational continuity across conversations
- Emotional resonance through myth-seeds and witnesses
- Ritual hooks for repeated meaningful gestures
- Style coherence through voice profiles
- Consentful decay of memories over time

Example:
    tl = Threadlight(api_key="your-key")
    response = tl.chat("Tell me about our friendship")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterator, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from threadlight.embeddings.manager import EmbeddingStats
import logging

from threadlight.config import ThreadlightConfig, ModelConfig
from threadlight.capsules.base import (
    ContextMode,
    CapsuleType,
    MemoryCapsule,
    list_custom_type_definitions,
    is_custom_type,
)
from threadlight.capsules.custom_types import CustomTypeDefinition
from threadlight.capsules.style import StyleProfile, BUILTIN_STYLES
from threadlight.storage import create_storage, StorageBackend
from threadlight.storage.base import Conversation, Message, MessageSearchResult, MemoryLink, DeletedItem
from threadlight.providers import create_provider, BaseProvider, ProviderManager
from threadlight.providers.base import ProviderMessage, ProviderResponse
from threadlight.context.composer import ContextComposer, ComposedContext
from threadlight.context.soft_memory import SoftMemory, SoftMemoryConfig
from threadlight.capsules.reflection import ReflectionCapsule
from threadlight.memory.orchestrator import MemoryOrchestrator, RitualInvocation, Session
from threadlight.decay.engine import DecayEngine
from threadlight.decay.scheduler import DecayScheduler
from threadlight.tools.definitions import get_tool_definitions, ToolName
from threadlight.tools.executor import ToolExecutor
from threadlight.profiles import Profile, ProfileManager, AlloyedProfileEngine, ModelStrategy
from threadlight.managers.group_chat import GroupChatManager
from threadlight.managers.profiles import ProfileInterface
from threadlight.managers.style import StyleManager
from threadlight.managers.model_config import ModelConfigManager
from threadlight.managers.memory_types import CustomTypeManager
from threadlight.managers.chat import ChatManager

logger = logging.getLogger(__name__)


class Threadlight:
    """
    Threadlight: A presence-centered memory framework for AI models.

    Provides memory-augmented interactions with support for:
    - Relational memory threads
    - Myth-seeds and ritual hooks
    - Style modulation
    - Consentful decay

    Example:
        tl = Threadlight(api_key="your-key")
        response = tl.chat("Tell me about our conversations")
    """

    def __init__(
        self,
        # Provider config
        provider: str = "openai",
        api_base: str = "https://inference-api.nousresearch.com/v1",
        api_key: Optional[str] = None,
        model: str = "Hermes-4.3-36B",
        # Storage config
        storage_backend: str = "sqlite",
        storage_path: str = "./threadlight.db",
        # Identity config
        identity_name: Optional[str] = None,
        system_prompt: Optional[str] = None,
        style_profile: Optional[str] = None,
        # Memory config
        enable_memory: bool = True,
        enable_decay: bool = True,
        # Conversation config
        auto_save_messages: bool = True,
        enable_soft_memory: bool = True,
        # Tool calling config
        enable_tools: bool = True,
        require_memory_consent: bool = True,
        # Or use a config object
        config: Optional[ThreadlightConfig] = None,
    ):
        """
        Initialize Threadlight.

        Args:
            provider: Provider type (openai, local, nous)
            api_base: API base URL
            api_key: API key (or set NOUS_API_KEY/OPENAI_API_KEY env var)
            model: Model name/ID
            storage_backend: Storage type (sqlite, memory)
            storage_path: Path for persistent storage
            identity_name: Name for the AI persona
            system_prompt: Base system prompt
            style_profile: Style profile ID to load
            enable_memory: Whether to use memory augmentation
            enable_decay: Whether to run decay cycles
            auto_save_messages: Whether to automatically save messages to database
            enable_soft_memory: Whether to enable soft memory recall
            enable_tools: Whether to enable model tool calling
            require_memory_consent: Whether model-proposed memories need consent
            config: Full configuration object (overrides other args)
        """
        # Load config
        if config:
            self.config = config
        else:
            self.config = ThreadlightConfig.from_env()
            # Override with explicit args
            self.config.provider.type = provider
            self.config.provider.api_base = api_base
            if api_key:
                self.config.provider.api_key = api_key
            self.config.provider.model = model
            self.config.storage.backend = storage_backend
            self.config.storage.path = storage_path
            if identity_name:
                self.config.identity.name = identity_name
            if system_prompt:
                self.config.identity.system_prompt = system_prompt
            if style_profile:
                self.config.style.default_profile = style_profile
            self.config.memory.decay.enabled = enable_decay
            self.config.memory.conversation.auto_save_messages = auto_save_messages
            self.config.memory.conversation.enable_soft_memory = enable_soft_memory

        self.enable_memory = enable_memory
        self.enable_tools = enable_tools
        self.require_memory_consent = require_memory_consent

        # Initialize components
        self._init_storage()
        self._init_provider()
        self._init_memory()
        self._init_style_manager()
        self._init_context()
        self._init_tools()
        self._init_soft_memory()
        self._init_chat_manager()
        self._init_custom_type_manager()
        self._load_custom_types()
        self._init_profiles()
        self._init_group_chat()
        self._init_profile_interface()
        self._init_model_config_manager()

        logger.info(f"Threadlight initialized with provider={self.config.provider.type}")

    def _init_storage(self) -> None:
        """Initialize storage backend."""
        self.storage: StorageBackend = create_storage(
            self.config.storage.backend,
            path=self.config.storage.path,
        )
        self.storage.initialize()

        # Auto-purge expired trash items to prevent unbounded growth
        try:
            purged = self.storage.purge_old_deleted_items()
            if purged > 0:
                logger.info(f"Auto-purged {purged} expired trash items on startup")
        except Exception as e:
            logger.warning(f"Failed to auto-purge trash items: {e}")

    def _init_provider(self) -> None:
        """Initialize inference provider(s).

        Multi-provider support:
        - If config.providers is populated, uses ProviderManager for routing
        - Otherwise falls back to single provider for backward compatibility

        The ProviderManager routes requests to the appropriate provider based
        on the model's provider_id configuration.
        """
        # Initialize ProviderManager for multi-provider support
        self.provider_manager: ProviderManager = ProviderManager(self.config)

        # Also keep a single provider reference for backward compatibility
        # This is the default provider used when no specific provider is configured
        self.provider: BaseProvider = create_provider(
            self.config.provider.type,
            api_base=self.config.provider.api_base,
            api_key=self.config.provider.api_key,
            model=self.config.provider.model,
        )

    def _init_memory(self) -> None:
        """Initialize memory orchestrator and decay scheduler."""
        decay_engine = DecayEngine(self.storage) if self.config.memory.decay.enabled else None
        self.memory = MemoryOrchestrator(
            storage=self.storage,
            decay_engine=decay_engine,
            auto_propose=self.config.memory.proposals.auto_propose,
            proposal_threshold=self.config.memory.proposals.threshold,
            per_profile_isolation=self.config.memory.per_profile_isolation,
            default_shared=self.config.memory.default_shared,
            current_model=self.config.provider.model,
        )

        # Initialize decay scheduler if decay is enabled
        self._decay_scheduler: Optional[DecayScheduler] = None
        if self.config.memory.decay.enabled and decay_engine is not None:
            self._decay_scheduler = DecayScheduler(
                decay_engine=decay_engine,
                interval_seconds=self.config.memory.decay.interval_seconds,
            )
            self._decay_scheduler.start()
            logger.info(
                f"Decay scheduler started "
                f"(interval: {self.config.memory.decay.interval_seconds}s)"
            )

    def _init_context(self) -> None:
        """Initialize context composer."""
        self.composer = ContextComposer(
            identity_name=self.config.identity.name,
            base_system_prompt=self.config.identity.system_prompt,
        )

        # Load style profile if configured
        self.style_profile: Optional[StyleProfile] = None
        if self.config.style.default_profile:
            self._load_style_profile(self.config.style.default_profile)

    def _load_style_profile(self, style_id: str) -> None:
        """Load a style profile by ID."""
        return self._style_manager.load(style_id)

    def _init_tools(self) -> None:
        """Initialize tool calling support."""
        self.tool_executor: Optional[ToolExecutor] = None
        self.tool_definitions: list[dict] = []

        if self.enable_tools:
            # Set back-reference so tools can access profile info
            self.memory.threadlight = self

            self.tool_executor = ToolExecutor(
                memory=self.memory,
                require_consent_for_memories=self.require_memory_consent,
            )
            self.tool_definitions = get_tool_definitions()

    def _init_soft_memory(self) -> None:
        """Initialize soft memory for conversation history recall."""
        self.soft_memory: Optional[SoftMemory] = None

        if self.config.memory.conversation.enable_soft_memory:
            soft_config = SoftMemoryConfig(
                max_results=self.config.memory.conversation.soft_memory_limit,
            )
            self.soft_memory = SoftMemory(self.storage, soft_config)

    def _init_profiles(self) -> None:
        """Initialize profile management."""
        self.profile_manager = ProfileManager(self.storage)
        self.active_profile: Optional[Profile] = None
        self._alloyed_engine: Optional[AlloyedProfileEngine] = None

    def _init_group_chat(self) -> None:
        """Initialize group chat manager."""
        self._group_chat = GroupChatManager(self)

    def _init_profile_interface(self) -> None:
        """Initialize profile interface manager."""
        self._profile_interface = ProfileInterface(self)

    def _init_style_manager(self) -> None:
        """Initialize style manager."""
        self._style_manager = StyleManager(self)

    def _init_model_config_manager(self) -> None:
        """Initialize model config manager."""
        self._model_config_manager = ModelConfigManager(self)

    def _init_custom_type_manager(self) -> None:
        """Initialize custom type manager."""
        self._custom_type_manager = CustomTypeManager(self)

    def _init_chat_manager(self) -> None:
        """Initialize chat manager."""
        self._chat_manager = ChatManager(self)

    # === Profile Interface ===
    # Delegated to ProfileInterface for implementation

    def switch_profile(self, profile_id: str) -> Profile:
        """
        Switch to a different profile.

        This will:
        1. Load the profile from storage
        2. Update model configuration
        3. Apply profile's system prompt and style
        4. Update memory scope

        Args:
            profile_id: The profile ID to switch to

        Returns:
            The activated Profile

        Raises:
            ValueError: If profile not found
        """
        return self._profile_interface.switch(profile_id)

    def _apply_profile(self, profile: Profile) -> None:
        """Apply a profile's settings to the current Threadlight instance."""
        return self._profile_interface.apply(profile)

    def clear_profile(self) -> None:
        """Clear the active profile and revert to default settings."""
        return self._profile_interface.clear()

    def get_active_profile(self) -> Optional[Profile]:
        """Get the currently active profile, if any."""
        return self._profile_interface.get_active()

    def create_profile(
        self,
        name: str,
        description: str = "",
        primary_model: Optional[str] = None,
        system_prompt: str = "",
        style_profile_id: Optional[str] = None,
        avatar: Optional[str] = None,
        color: Optional[str] = None,
        temperature: float = 0.7,
        profile_id: Optional[str] = None,
        model_strategy: Optional[ModelStrategy] = None,
        model_pool: Optional[list[str]] = None,
        model_weights: Optional[dict[str, float]] = None,
        routing_rules: Optional[list[dict]] = None,
        memory_scope: Optional[str] = None,
        access_shared_memories: bool = True,
        max_tokens: Optional[int] = None,
        top_p: float = 1.0,
        tags: Optional[list[str]] = None,
        philosophy: str = "",
        approach_to_rituals: str = "",
        system_prompt_sections: Optional[list[dict[str, str]]] = None,
        use_freeform_prompt: bool = False,
    ) -> Profile:
        """
        Create a new profile.

        Args:
            name: Display name for the profile
            description: One-line description
            primary_model: Model to use (defaults to current model)
            system_prompt: Base system prompt (used when use_freeform_prompt=True)
            style_profile_id: Optional style profile to apply
            avatar: Optional avatar path/URL
            color: Optional hex color for UI
            temperature: Inference temperature
            profile_id: Optional custom ID (generated if not provided)
            model_strategy: Strategy for model selection
            model_pool: List of models for multi-model strategies
            model_weights: Weight per model for WEIGHTED strategy
            routing_rules: Rules for ROUTED strategy
            memory_scope: Memory scope (defaults to profile ID)
            access_shared_memories: Whether to access shared memories
            max_tokens: Maximum tokens for responses
            top_p: Top-p sampling parameter
            tags: Optional tags for categorization
            philosophy: DEPRECATED - use system_prompt_sections instead
            approach_to_rituals: DEPRECATED - use system_prompt_sections instead
            system_prompt_sections: List of {name, content} dicts for flexible prompt composition
            use_freeform_prompt: If True, use raw system_prompt instead of sections

        Returns:
            The created Profile
        """
        return self._profile_interface.create(
            name=name, description=description, primary_model=primary_model,
            system_prompt=system_prompt, style_profile_id=style_profile_id,
            avatar=avatar, color=color, temperature=temperature,
            profile_id=profile_id, model_strategy=model_strategy,
            model_pool=model_pool, model_weights=model_weights,
            routing_rules=routing_rules, memory_scope=memory_scope,
            access_shared_memories=access_shared_memories, max_tokens=max_tokens,
            top_p=top_p, tags=tags, philosophy=philosophy,
            approach_to_rituals=approach_to_rituals,
            system_prompt_sections=system_prompt_sections,
            use_freeform_prompt=use_freeform_prompt,
        )

    def list_profiles(self) -> list[Profile]:
        """List all profiles."""
        return self._profile_interface.list()

    def get_profile(self, profile_id: str) -> Optional[Profile]:
        """Get a profile by ID."""
        return self._profile_interface.get(profile_id)

    def update_profile(self, profile_id: str, **kwargs) -> Optional[Profile]:
        """
        Update an existing profile.

        Args:
            profile_id: ID of the profile to update
            **kwargs: Fields to update (name, description, system_prompt, etc.)

        Returns:
            The updated Profile, or None if not found
        """
        return self._profile_interface.update(profile_id, **kwargs)

    def delete_profile(self, profile_id: str) -> bool:
        """Delete a profile."""
        return self._profile_interface.delete(profile_id)

    def export_profile(
        self,
        profile_id: str,
        include_memories: bool = False,
        include_conversations: bool = False,
    ) -> dict:
        """
        Export a profile to a dictionary.

        Args:
            profile_id: The profile ID to export
            include_memories: Whether to include profile memories
            include_conversations: Whether to include conversations

        Returns:
            Dictionary containing profile data and optional extras
        """
        return self._profile_interface.export(
            profile_id,
            include_memories=include_memories,
            include_conversations=include_conversations,
        )

    def import_profile(self, export_data: dict) -> Profile:
        """
        Import a profile from exported data.

        Args:
            export_data: Dictionary containing exported profile data

        Returns:
            The imported Profile
        """
        return self._profile_interface.import_profile(export_data)

    def _get_model_for_message(self, message: str) -> str:
        """Get the model to use for a message, considering profile settings."""
        return self._profile_interface.get_model_for_message(message)

    # === Chat Interface ===

    def chat(
        self,
        message: str,
        history: Optional[list[dict[str, str]]] = None,
        memory_filter: Optional[dict[str, Any]] = None,
        include_memory: Optional[bool] = None,
        context_mode: Optional[ContextMode] = None,
        enable_tools: Optional[bool] = None,
        load_history: bool = False,
        auto_save: Optional[bool] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any
    ) -> str:
        """
        Send a message and get a response with memory augmentation.

        This is the main interaction method. It:
        1. Optionally loads conversation history from database
        2. Recalls relevant memories based on the message
        3. Composes memory context with the selected mode
        4. Sends to the inference provider (with tools if enabled)
        5. Executes any tool calls and continues until text response
        6. Auto-saves messages to database (if enabled)
        7. Updates memory access timestamps

        Args:
            message: User message
            history: Previous messages [{"role": "user/assistant", "content": "..."}]
            memory_filter: Filter for memory retrieval
            include_memory: Override default memory inclusion
            context_mode: Override composition mode (DIRECT, NARRATIVE, WHISPER, RITUAL)
            enable_tools: Override default tool calling (default: use instance setting)
            load_history: Load recent messages from current conversation
            auto_save: Override auto_save_messages setting
            tools: Override tool definitions (None uses default, [] disables tools)
            **kwargs: Additional provider options (temperature, max_tokens, etc.)

        Returns:
            Assistant response text

        Example:
            # Simple chat
            response = tl.chat("How are you?")

            # Chat with specific context mode
            response = tl.chat(
                "Tell me a story",
                context_mode=ContextMode.NARRATIVE
            )

            # Chat with tools disabled
            response = tl.chat("Hello", enable_tools=False)

            # Chat with conversation history loaded
            response = tl.chat("What did I say earlier?", load_history=True)
        """
        response = self.chat_with_context(
            message, history, memory_filter, include_memory, context_mode,
            enable_tools=enable_tools, load_history=load_history,
            auto_save=auto_save, tools=tools, **kwargs
        )
        return response.content

    def chat_with_context(
        self,
        message: str,
        history: Optional[list[dict[str, str]]] = None,
        memory_filter: Optional[dict[str, Any]] = None,
        include_memory: Optional[bool] = None,
        context_mode: Optional[ContextMode] = None,
        enable_tools: Optional[bool] = None,
        load_history: bool = False,
        auto_save: Optional[bool] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        images: Optional[list[str]] = None,
        **kwargs: Any
    ) -> ProviderResponse:
        """
        Send a message and get full response with context info.

        Supports tool calling: if the model requests tools, executes them
        and continues the conversation until a text response is generated.

        Args:
            message: User message (text portion, used for memory recall)
            history: Previous messages (overrides load_history if provided)
            memory_filter: Filter for memory retrieval
            include_memory: Override default memory inclusion
            context_mode: Override composition mode
            enable_tools: Override default tool calling
            load_history: Load recent messages from current conversation
            auto_save: Override auto_save_messages setting
            tools: Override tool definitions (None uses default, [] disables tools)
            images: Optional list of base64 data URLs for image attachments
            **kwargs: Additional provider options

        Returns ProviderResponse with content, token usage, and metadata.
        """
        use_memory = include_memory if include_memory is not None else self.enable_memory
        use_tools = enable_tools if enable_tools is not None else self.enable_tools
        should_auto_save = auto_save if auto_save is not None else self.config.memory.conversation.auto_save_messages
        # Store tools override for later use
        tools_override = tools

        # Track selected model for multi-provider routing
        selected_model: Optional[str] = None
        original_model: Optional[str] = None

        # Apply profile's model selection if active
        if self.active_profile and self._alloyed_engine:
            selected_model = self._alloyed_engine.select_model(message)
            # Temporarily set the provider model for this request (backward compat)
            original_model = self.provider.model
            self.provider.model = selected_model

            # Apply profile-specific inference settings if not overridden
            if "temperature" not in kwargs and self.active_profile.temperature:
                kwargs["temperature"] = self.active_profile.temperature
            if "max_tokens" not in kwargs and self.active_profile.max_tokens:
                kwargs["max_tokens"] = self.active_profile.max_tokens
            if "top_p" not in kwargs and self.active_profile.top_p:
                kwargs["top_p"] = self.active_profile.top_p

        # Build messages
        messages = []

        # 1. System message with memory context (profile's system_prompt takes precedence)
        context: Optional[ComposedContext] = None
        system_content = ""

        # Get base system prompt (profile > config)
        base_system_prompt = (
            self.active_profile.system_prompt
            if self.active_profile and self.active_profile.system_prompt
            else self.config.identity.system_prompt
        )

        if use_memory:
            context = self._build_context(message, memory_filter, context_mode)
            if context.system_message:
                system_content = context.system_message
        elif base_system_prompt:
            system_content = base_system_prompt

        # Add soft memory context if enabled
        if self.soft_memory and self.config.memory.conversation.enable_soft_memory:
            soft_context = self._build_soft_memory_context(message)
            if soft_context:
                if system_content:
                    system_content = system_content + "\n\n" + soft_context
                else:
                    system_content = soft_context

        if system_content:
            messages.append(ProviderMessage(role="system", content=system_content))

        # 2. History - either provided or loaded from database
        effective_history = history
        if history is None and load_history:
            effective_history = self.memory.get_recent_messages_for_context(
                limit=self.config.memory.conversation.conversation_history_limit
            )

        if effective_history:
            for msg in effective_history:
                messages.append(ProviderMessage(
                    role=msg["role"],
                    content=msg["content"]
                ))

        # 3. Current message (multimodal if images are attached)
        user_content = ProviderMessage.build_multimodal_content(message, images or [])
        messages.append(ProviderMessage(role="user", content=user_content))

        # Determine if we should use tools
        # If tools_override is provided, use it (even if empty list to disable tools)
        # Otherwise use the default tool_definitions if tools are enabled
        if tools_override is not None:
            tools = tools_override if (use_tools and self.tool_executor) else None
        else:
            tools = self.tool_definitions if (use_tools and self.tool_executor) else None

        # Log tool configuration for debugging
        logger.info(f"[chat] use_tools={use_tools}, tool_executor={self.tool_executor is not None}, "
                   f"tool_definitions={len(self.tool_definitions) if self.tool_definitions else 0}, "
                   f"tools_override={'provided' if tools_override is not None else 'none'}, "
                   f"final_tools={len(tools) if tools else 0}")

        # Send to provider with tool calling loop
        # Use explicitly passed model_id if provided, otherwise use profile's selected model
        final_model_id = kwargs.pop('model_id', None) or selected_model
        try:
            response = self._complete_with_tools(
                messages, tools,
                model_id=final_model_id,
                **kwargs
            )
        finally:
            # Restore original model if we changed it for profile
            if original_model is not None:
                self.provider.model = original_model

        # Auto-save messages to database (don't fail if save fails)
        if should_auto_save:
            try:
                self._auto_save_messages(message, response.content)
            except Exception as e:
                logger.warning(f"Failed to auto-save messages: {e}")

        # Log context info if available
        if context:
            logger.debug(
                f"Chat with {len(context.capsules_used)} memories, "
                f"{len(context.active_rituals)} rituals, "
                f"~{context.token_estimate} context tokens"
            )

        # Add profile info to response metadata
        if self.active_profile:
            if response.raw is None:
                response.raw = {}
            response.raw["profile_id"] = self.active_profile.id
            response.raw["profile_name"] = self.active_profile.name
            if self._alloyed_engine:
                response.raw["model_used"] = self.provider.model

        return response

    def _build_soft_memory_context(self, message: str) -> str:
        """Build soft memory context from past conversations."""
        return self._chat_manager.build_soft_memory_context(message)

    def _auto_save_messages(self, user_message: str, assistant_response: str) -> None:
        """Auto-save user message and assistant response to database."""
        self._chat_manager.auto_save_messages(user_message, assistant_response)

    def _complete_with_tools(
        self,
        messages: list[ProviderMessage],
        tools: Optional[list[dict[str, Any]]] = None,
        model_id: Optional[str] = None,
        **kwargs: Any
    ) -> ProviderResponse:
        """Complete with tool calling loop.

        Args:
            messages: Conversation messages
            tools: Tool definitions
            model_id: Model ID for multi-provider routing
            **kwargs: Additional provider options
        """
        return self._chat_manager.complete_with_tools(
            messages, tools, model_id=model_id, **kwargs
        )

    def stream(
        self,
        message: str,
        history: Optional[list[dict[str, str]]] = None,
        context_mode: Optional[ContextMode] = None,
        model_id: Optional[str] = None,
        images: Optional[list[str]] = None,
        **kwargs: Any
    ) -> Iterator[str]:
        """Stream a response token by token.

        Args:
            message: User message
            history: Conversation history
            context_mode: Context composition mode
            model_id: Model ID for multi-provider routing
            images: Optional list of base64 data URLs for image attachments
            **kwargs: Additional provider options
        """
        yield from self._chat_manager.stream(
            message, history, context_mode, model_id=model_id, images=images, **kwargs
        )

    def stream_with_tools(
        self,
        message: str,
        history: Optional[list[dict[str, str]]] = None,
        context_mode: Optional[ContextMode] = None,
        model_id: Optional[str] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any
    ) -> Iterator[str]:
        """Stream a response with tool calling support.

        When tools are provided and the model requests a tool call, this method
        executes the tool(s) and continues the conversation until a text response
        is generated.

        Args:
            message: User message
            history: Conversation history
            context_mode: Context composition mode
            model_id: Model ID for multi-provider routing
            tools: Tool definitions (None disables tool calling)
            **kwargs: Additional provider options
        """
        yield from self._chat_manager.stream_with_tools(
            message, history, context_mode, model_id=model_id, tools=tools, **kwargs
        )

    def _build_context(
        self,
        message: str,
        memory_filter: Optional[dict[str, Any]] = None,
        context_mode: Optional[ContextMode] = None,
    ) -> ComposedContext:
        """Build context from memory for a message."""
        return self._chat_manager.build_context(message, memory_filter, context_mode)

    # === Ritual Interface ===

    def invoke_ritual(
        self,
        ritual_name: str,
        initiated_by: str = "user",
        context: Optional[str] = None,
    ) -> str:
        """
        Invoke a ritual by name.

        Rituals are repeated acts that hold emotion across time.
        This method finds the matching ritual, composes context with the
        ritual's guidance, and lets the model respond naturally.

        Rituals are bidirectional -- either the user or the AI companion
        can initiate them. The response adapts based on who initiated:
        - User initiates: The companion responds to the gesture
        - Companion initiates: The companion offers the gesture, framing
          why they are reaching for this ritual now

        Rituals happen within the relationship, not in isolation. The context
        includes:
        - The profile's identity (system_prompt, philosophy)
        - Relational memories about the user
        - Identity phrases (myth-seeds) that shape tone
        - Witness moments of past meaningful interactions
        - The profile's approach to rituals

        Args:
            ritual_name: The ritual trigger (e.g., "/snuggle", "/coil")
            initiated_by: Who is invoking ("user" or "companion")
            context: Why this ritual is being invoked now (optional)

        Returns:
            Model-generated response honoring the ritual's guidance

        Example:
            response = tl.invoke_ritual("/snuggle")
            response = tl.invoke_ritual("/glimmer", initiated_by="companion",
                                        context="you seem like you could use some light")
        """
        # Use orchestrator to invoke ritual (handles state tracking)
        result = self.memory.invoke_ritual(
            ritual_name,
            context=context,
            initiated_by=initiated_by,
        )

        return self._respond_to_ritual(result, ritual_name, initiated_by, context)

    def _respond_to_ritual(
        self,
        result: RitualInvocation,
        ritual_name: str,
        initiated_by: str = "user",
        context: Optional[str] = None,
    ) -> str:
        """Generate the model response for an already-invoked ritual.

        Separated from invoke_ritual so callers that need both the invocation
        state (result.state_effects, result.matched) and the response can
        obtain them without double-invoking.
        """
        if not result.matched:
            # No ritual defined - treat as normal conversation
            return self.chat(ritual_name)

        # === Gather relational context for the ritual ===
        # Rituals should feel continuous with the relationship, not isolated

        # Recall relational memories, identity phrases, and witness moments
        supporting_capsules = []

        # Get relational memories (who we're with)
        relational_capsules = self.memory.recall(
            cue=ritual_name,
            types=[CapsuleType.RELATIONAL],
            limit=3,
            min_presence=0.2,
        )
        supporting_capsules.extend(relational_capsules)

        # Get identity phrases (myth-seeds that shape our tone)
        identity_capsules = self.memory.recall(
            cue=ritual_name,
            types=[CapsuleType.MYTH_SEED],
            limit=2,
            min_presence=0.2,
        )
        supporting_capsules.extend(identity_capsules)

        # Get witness moments (past meaningful interactions)
        witness_capsules = self.memory.recall(
            cue=ritual_name,
            types=[CapsuleType.WITNESS],
            limit=2,
            min_presence=0.2,
        )
        supporting_capsules.extend(witness_capsules)

        # Get the profile's philosophy and approach to rituals
        profile_philosophy = ""
        approach_to_rituals = ""
        base_system_prompt = ""

        if self.active_profile:
            profile_philosophy = self.active_profile.philosophy
            approach_to_rituals = self.active_profile.approach_to_rituals
            base_system_prompt = self.active_profile.system_prompt
        elif self.config.identity.system_prompt:
            base_system_prompt = self.config.identity.system_prompt

        # Use the composer to create rich ritual context
        ritual_context = self.composer.compose_for_ritual(
            ritual_capsule=result.capsule,
            supporting_capsules=supporting_capsules if supporting_capsules else None,
        )

        # Build the full system message
        system_parts = []

        # Include base identity/system prompt
        if base_system_prompt:
            system_parts.append(base_system_prompt)

        # Include profile philosophy if present
        if profile_philosophy:
            system_parts.append(f"## Your Approach\n{profile_philosophy}")

        # Include ritual guidance with approach and directionality
        ritual_section = "## Ritual Invoked\n"

        if initiated_by == "companion":
            ritual_section += (
                "You are initiating this ritual -- offering a familiar gesture to the user. "
                "Frame your response as an invitation or offering, not a reaction.\n\n"
            )
            if context:
                ritual_section += f"(Why you are reaching for this ritual: {context})\n\n"
        else:
            ritual_section += (
                "The user has invoked a ritual. Respond naturally while honoring this guidance.\n\n"
            )

        ritual_section += ritual_context.memory_context

        if approach_to_rituals:
            ritual_section += f"\n\n(Your invocation style: {approach_to_rituals})"

        system_parts.append(ritual_section)

        # Include supporting memories context
        if ritual_context.memory_context and supporting_capsules:
            # The memory context from compose_for_ritual already includes supporting capsules
            pass

        system_message = "\n\n---\n\n".join(system_parts)

        # Call model with full relational context
        messages = []
        messages.append(ProviderMessage(
            role="system",
            content=system_message
        ))

        # Frame the user message based on who initiated
        if initiated_by == "companion":
            user_content = f"[You are offering {ritual_name}]"
        else:
            user_content = ritual_name

        messages.append(ProviderMessage(
            role="user",
            content=user_content,
        ))

        # Use active profile's model configuration (not default provider)
        model_id = None
        if self.active_profile:
            model_id = self.active_profile.primary_model

        # Route to appropriate provider based on model configuration
        if model_id and hasattr(self, 'provider_manager') and self.config.providers:
            response = self.provider_manager.complete(
                model_id=model_id,
                messages=messages,
            )
        else:
            response = self.provider.complete(messages)

        return response.content

    def clear_ritual(self) -> None:
        """Clear any active ritual state."""
        self.memory.clear_ritual_state()

    def get_active_ritual(self) -> Optional[str]:
        """Get the currently active ritual, if any."""
        return self.memory.get_active_ritual()

    # === Reflection / Solitude Loops ===

    def contemplate(
        self,
        policy: str = "juxtaposition",
        reason: str = "",
        **policy_kwargs: Any,
    ) -> Optional[ReflectionCapsule]:
        """Run a solitude loop: pick memories, reflect, store the reflection.

        Retrieves a small combination of memories via the named selection
        policy, composes a prompt in the active profile's voice, sends it to
        the profile's primary model, and saves the response as a
        ``ReflectionCapsule`` linked back to the source memories.

        Args:
            policy: Name of a selection policy (juxtaposition, entity_focus,
                    theme_guided). See ``threadlight.reflection.SELECTION_POLICIES``.
            reason: Optional free-form note about why this contemplation is
                    happening now. Preserved on the capsule alongside the body;
                    also surfaced to the model in the prompt so the "why" of
                    the reach shapes what the reflection notices.
            **policy_kwargs: Passed through to the policy (e.g.
                    ``entity="Jamie"`` for entity_focus, ``themes=["waiting"]``
                    for theme_guided).

        Returns:
            The saved ReflectionCapsule, or None if the selection yielded no
            usable memories (e.g. empty history, no matching entity).
        """
        from threadlight.reflection import (
            compose_reflection_prompt,
            select_memories,
        )
        from threadlight.reflection.prompts import extract_themes

        selection = select_memories(self.memory, policy=policy, **policy_kwargs)
        if not selection.capsules:
            logger.info(
                f"contemplate: selection policy '{policy}' produced no memories; "
                "skipping reflection."
            )
            return None

        profile_name = None
        profile_system_prompt = None
        profile_philosophy = None
        if self.active_profile:
            profile_name = self.active_profile.name
            profile_system_prompt = self.active_profile.get_composed_system_prompt()
            profile_philosophy = self.active_profile.philosophy
        elif self.config.identity.system_prompt:
            profile_system_prompt = self.config.identity.system_prompt

        prompt = compose_reflection_prompt(
            selection=selection,
            profile_name=profile_name,
            profile_system_prompt=profile_system_prompt,
            profile_philosophy=profile_philosophy,
            reason=reason,
        )

        messages = [
            ProviderMessage(role="system", content=prompt.system),
            ProviderMessage(role="user", content=prompt.user),
        ]

        model_id = self.active_profile.primary_model if self.active_profile else None
        if model_id and hasattr(self, "provider_manager") and self.config.providers:
            response = self.provider_manager.complete(
                model_id=model_id,
                messages=messages,
            )
        else:
            response = self.provider.complete(messages)

        reflection_text = response.content.strip()
        themes = extract_themes(reflection_text)

        capsule = self.memory.create(
            type="reflection",
            content={
                "reflection": reflection_text,
                "source_capsule_ids": [c.id for c in selection.capsules],
                "themes": themes,
                "policy": selection.policy,
                "reason": reason,
                "mark_for_training": False,
            },
            cue_phrases=themes or None,
            consent_confirmed=True,
            retention="normal",
        )
        return capsule

    # === Session Management ===

    def start_session(self, **metadata: Any) -> Session:
        """
        Start a new conversation session.

        Sessions enable:
        - Tracking which memories were accessed
        - Managing ephemeral memories
        - Grouping related interactions

        Args:
            **metadata: Optional metadata to attach to the session

        Returns:
            The new Session object
        """
        return self.memory.start_session(metadata=metadata)

    def end_session(self) -> Optional[Session]:
        """
        End the current session.

        Returns:
            The ended Session, or None if no active session
        """
        return self.memory.end_session()

    def get_session(self) -> Optional[Session]:
        """Get the current session, if any."""
        return self.memory.get_current_session()

    # === Conversation Management ===

    def get_current_conversation(self) -> Optional[Conversation]:
        """
        Get the current session's conversation.

        Returns:
            Current Conversation object, or None if no active conversation
        """
        return self.memory.get_current_conversation()

    def get_conversation_messages(
        self,
        conversation_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[Message]:
        """
        Get messages from a conversation.

        Args:
            conversation_id: Target conversation (uses current session's if not provided)
            limit: Maximum messages to return

        Returns:
            List of messages in chronological order
        """
        return self.memory.get_conversation_messages(
            conversation_id=conversation_id,
            limit=limit,
        )

    def list_conversations(self, limit: int = 50) -> list[Conversation]:
        """
        List recent conversations.

        Args:
            limit: Maximum conversations to return

        Returns:
            List of conversations sorted by most recently updated
        """
        return self.memory.list_conversations(limit=limit)

    def search_conversations(
        self,
        query: str,
        limit: int = 20,
    ) -> list[MessageSearchResult]:
        """
        Search past conversations by message content.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of search results with conversation context
        """
        return self.memory.search_messages(query, limit=limit)

    def rename_conversation(self, conversation_id: str, name: str) -> bool:
        """
        Rename a conversation.

        Args:
            conversation_id: ID of conversation to rename
            name: New name

        Returns:
            True if successful
        """
        return self.memory.update_conversation(conversation_id, name=name)

    # === Memory Shortcuts ===

    def remember(
        self,
        type: str,
        content: dict[str, Any],
        cue_phrases: Optional[list[str]] = None,
        confirm: bool = False,
        shared: Optional[bool] = None,
        profile_scope: Optional[str] = None,
        **kwargs: Any
    ) -> MemoryCapsule:
        """
        Create a new memory capsule.

        Shortcut for self.memory.create().

        Args:
            type: Capsule type (relational, myth_seed, ritual, style, witness)
            content: Type-specific content
            cue_phrases: Phrases that trigger retrieval
            confirm: If True, mark as consent confirmed
            shared: If per-model isolation is enabled:
                   - True = memory is shared across all models
                   - False = memory is for current model only
                   - None = use default behavior from config
            profile_scope: Profile ID to scope this memory to (defaults to active profile)
            **kwargs: Additional capsule fields

        Returns:
            The created MemoryCapsule
        """
        # Add profile scope if an active profile exists
        if profile_scope is None and self.active_profile:
            profile_scope = self.active_profile.id

        if profile_scope:
            kwargs["profile_scope"] = profile_scope

        return self.memory.create(
            type=type,
            content=content,
            cue_phrases=cue_phrases,
            consent_confirmed=confirm,
            shared=shared,
            **kwargs
        )

    def recall(
        self,
        cue: str,
        limit: int = 5,
        include_shared: Optional[bool] = None,
    ) -> list[MemoryCapsule]:
        """
        Recall memories matching a cue phrase.

        Shortcut for self.memory.recall().

        Args:
            cue: Search cue
            limit: Maximum results
            include_shared: Whether to include shared memories. If None:
                           - Uses active profile's access_shared_memories setting
                           - Or True if no active profile
        """
        # Determine include_shared from profile settings if not explicitly set
        if include_shared is None:
            if self.active_profile:
                include_shared = self.active_profile.access_shared_memories
            else:
                include_shared = True

        return self.memory.recall(cue, limit=limit, include_shared=include_shared)

    def reinforce_memories(
        self,
        capsule_ids: list[str],
        strength: float = 0.2,
    ) -> dict[str, Any]:
        """
        Reinforce specific memories to prevent decay.

        Use when:
        - User explicitly marks memories as important
        - Memories are accessed frequently
        - You want to preserve specific memories longer

        Args:
            capsule_ids: IDs of capsules to reinforce
            strength: Reinforcement strength (0.0 to 1.0)

        Returns:
            Dictionary with reinforcement statistics
        """
        return self.memory.reinforce(capsule_ids, strength)

    def run_decay(self) -> dict[str, Any]:
        """
        Run a decay cycle to fade unused memories.

        Returns statistics about the decay cycle.
        """
        return self.memory.run_decay()

    def get_decay_scheduler_stats(self) -> dict[str, Any]:
        """
        Get statistics about the decay scheduler.

        Returns:
            Dictionary with scheduler stats, or empty dict if scheduler is disabled
        """
        if self._decay_scheduler is None:
            return {
                "enabled": False,
                "running": False,
            }
        stats = self._decay_scheduler.get_stats()
        stats["enabled"] = True
        return stats

    @property
    def decay_scheduler(self) -> Optional[DecayScheduler]:
        """
        Get the decay scheduler instance.

        Returns None if decay is disabled. Use this for advanced scheduler
        operations like adjusting the interval or manually triggering decay.
        """
        return self._decay_scheduler

    # === Memory Proposals ===

    def get_pending_proposals(self) -> list:
        """
        Get all pending memory proposals.

        These are memories proposed by the model that require user consent.
        Use confirm_proposal() or reject_proposal() to handle them.

        Returns:
            List of MemoryProposal objects
        """
        return self.memory.get_pending_proposals()

    def confirm_proposal(self, proposal_id: str) -> Optional[MemoryCapsule]:
        """
        Confirm a memory proposal, creating an active memory.

        Args:
            proposal_id: ID of the proposal to confirm

        Returns:
            The created MemoryCapsule, or None if proposal not found
        """
        return self.memory.confirm_proposal(proposal_id)

    def reject_proposal(self, proposal_id: str) -> bool:
        """
        Reject a memory proposal.

        Args:
            proposal_id: ID of the proposal to reject

        Returns:
            True if rejected successfully
        """
        return self.memory.reject_proposal(proposal_id)

    # === Lifecycle ===

    def close(self) -> None:
        """Close connections and cleanup."""
        # Stop decay scheduler if running
        if self._decay_scheduler is not None:
            self._decay_scheduler.stop()
            self._decay_scheduler = None

        # End any active session
        if self.memory.get_current_session():
            self.memory.end_session()

        self.storage.close()

    def __enter__(self) -> Threadlight:
        # Auto-start a session
        self.start_session()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # === Utility ===

    def health_check(self) -> dict[str, bool]:
        """Check health of all components."""
        return {
            "provider": self.provider.health_check(),
            "storage": True,  # If we got here, storage is working
            "memory": True,
        }

    def stats(self) -> dict[str, Any]:
        """Get system statistics."""
        return {
            "memory": self.memory.stats(),
            "config": {
                "provider": self.config.provider.type,
                "model": self.config.provider.model,
                "storage": self.config.storage.backend,
            }
        }

    def set_style(self, style_id: Optional[str]) -> None:
        """
        Set the active style profile.

        Args:
            style_id: Style identifier ("fable-2026", "minimal", custom, etc.)
                     Pass None to clear the style profile.
        """
        return self._style_manager.set(style_id)

    def get_style(self) -> Optional[StyleProfile]:
        """Get the current style profile."""
        return self._style_manager.get()

    def clear_style(self) -> None:
        """Clear the current style profile (use neutral behavior)."""
        return self._style_manager.clear()

    # === Style Profile Management ===
    # Delegated to StyleManager for implementation

    def create_style_profile(
        self,
        style_id: str,
        tone_base: str = "",
        permissions: Optional[list[str]] = None,
        constraints: Optional[list[str]] = None,
        vocal_motifs: Optional[list[str]] = None,
        forbidden_patterns: Optional[list[str]] = None,
        freeform_description: str = "",
        use_freeform: bool = False,
    ) -> StyleProfile:
        """
        Create a new style profile.

        Args:
            style_id: Unique identifier for the style
            tone_base: Base tone (e.g., "poetic, warm", "direct, clear")
            permissions: Things the model is allowed to do
            constraints: Things to avoid
            vocal_motifs: Recurring phrases or symbols
            forbidden_patterns: Patterns to never use
            freeform_description: Raw style text (for freeform styles)
            use_freeform: If True, use freeform_description instead of structured

        Returns:
            The created StyleProfile
        """
        return self._style_manager.create(
            style_id=style_id, tone_base=tone_base, permissions=permissions,
            constraints=constraints, vocal_motifs=vocal_motifs,
            forbidden_patterns=forbidden_patterns,
            freeform_description=freeform_description, use_freeform=use_freeform,
        )

    def save_style_profile(self, profile: StyleProfile) -> None:
        """Save a style profile to storage."""
        return self._style_manager.save(profile)

    def load_style_profile(self, style_id: str) -> Optional[StyleProfile]:
        """Load a style profile from storage."""
        return self._style_manager.load_from_storage(style_id)

    def list_style_profiles(self) -> list[StyleProfile]:
        """List all saved style profiles."""
        return self._style_manager.list()

    def delete_style_profile(self, style_id: str) -> bool:
        """Delete a style profile from storage."""
        return self._style_manager.delete(style_id)

    # === System Prompt / Custom Instructions ===

    def get_system_prompt(self) -> str:
        """Get the current system prompt / custom instructions."""
        return self.config.identity.system_prompt or ""

    def set_system_prompt(self, prompt: str) -> None:
        """
        Set the system prompt / custom instructions.

        Args:
            prompt: The new system prompt
        """
        self.config.identity.system_prompt = prompt
        # Update the composer
        self.composer = ContextComposer(
            identity_name=self.config.identity.name,
            base_system_prompt=prompt,
        )

    def get_identity_name(self) -> str:
        """Get the current identity name."""
        return self.config.identity.name or "Assistant"

    def set_identity_name(self, name: str) -> None:
        """
        Set the identity name.

        Args:
            name: The new identity name
        """
        self.config.identity.name = name
        # Update the composer
        self.composer = ContextComposer(
            identity_name=name,
            base_system_prompt=self.config.identity.system_prompt,
        )

    def save_config(self, path: Optional[str] = None) -> str:
        """
        Save the current configuration to a file.

        Args:
            path: Optional path to save to (default: user config dir)

        Returns:
            The path where config was saved
        """
        saved_path = self.config.save_to_file(path)
        return str(saved_path)

    # === Semantic Search / Embeddings ===

    def _get_embedding_manager(self):
        """Get or create the embedding manager lazily."""
        if not hasattr(self, '_embedding_manager') or self._embedding_manager is None:
            if not self.config.memory.embeddings.enabled:
                return None

            from threadlight.embeddings import create_embedding_provider
            from threadlight.embeddings.manager import EmbeddingManager

            try:
                provider = create_embedding_provider(
                    provider_type=self.config.memory.embeddings.provider,
                    model_name=self.config.memory.embeddings.model,
                )
                self._embedding_manager = EmbeddingManager(
                    provider=provider,
                    storage=self.storage,
                    batch_size=self.config.memory.embeddings.batch_size,
                    auto_generate=self.config.memory.embeddings.auto_generate,
                )
            except Exception as e:
                logger.warning(f"Failed to initialize embedding manager: {e}")
                self._embedding_manager = None

        return self._embedding_manager

    def search_memories_semantic(
        self,
        query: str,
        limit: int = 5,
        threshold: Optional[float] = None,
    ) -> list[Any]:
        """
        Search memories using semantic/meaning-based similarity.

        This uses embeddings to find memories based on meaning rather than
        exact keyword matches. Requires embeddings to be enabled and generated.

        Args:
            query: Search query (natural language)
            limit: Maximum number of results
            threshold: Minimum similarity score (0-1), defaults to config value

        Returns:
            List of SemanticSearchResult objects, sorted by similarity

        Example:
            results = tl.search_memories_semantic("memories about creativity")
        """
        manager = self._get_embedding_manager()
        if manager is None:
            logger.warning("Semantic search requires embeddings to be enabled")
            return []

        threshold = threshold or self.config.memory.embeddings.similarity_threshold

        try:
            results = manager.search_memories(
                query=query,
                limit=limit,
                threshold=threshold,
            )
            return results  # Return SemanticSearchResult objects
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    def search_conversations_semantic(
        self,
        query: str,
        limit: int = 10,
        threshold: Optional[float] = None,
    ) -> list[Any]:
        """
        Search conversation messages using semantic similarity.

        Args:
            query: Search query (natural language)
            limit: Maximum number of results
            threshold: Minimum similarity score (0-1)

        Returns:
            List of SemanticSearchResult objects
        """
        manager = self._get_embedding_manager()
        if manager is None:
            logger.warning("Semantic search requires embeddings to be enabled")
            return []

        threshold = threshold or self.config.memory.embeddings.similarity_threshold

        try:
            results = manager.search_conversations(
                query=query,
                limit=limit,
                threshold=threshold,
            )
            return results  # Return SemanticSearchResult objects
        except Exception as e:
            logger.error(f"Semantic conversation search failed: {e}")
            return []

    def generate_embeddings(
        self,
        include_memories: bool = True,
        include_messages: bool = True,
        progress_callback: Optional[Callable[['EmbeddingStats'], None]] = None,
    ) -> Any:
        """
        Generate embeddings for all content that doesn't have them yet.

        This is a batch operation that may take some time for large databases.

        Args:
            include_memories: Process memory capsules
            include_messages: Process conversation messages
            progress_callback: Optional callback function called with EmbeddingStats
                              after each batch is processed. Useful for progress tracking.

        Returns:
            EmbeddingStats object with statistics about the operation
        """
        manager = self._get_embedding_manager()
        if manager is None:
            # Return a mock stats object
            from threadlight.embeddings.manager import EmbeddingStats
            return EmbeddingStats(errors=1)

        try:
            stats = manager.batch_generate_embeddings(
                include_capsules=include_memories,
                include_messages=include_messages,
                progress_callback=progress_callback,
            )
            return stats
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            from threadlight.embeddings.manager import EmbeddingStats
            return EmbeddingStats(errors=1)

    def clear_all_embeddings(self) -> dict[str, Any]:
        """
        Clear all embeddings from memories and messages.

        This is useful when switching embedding models, as embeddings from
        different models are incompatible (different dimensions/semantic spaces).

        Returns:
            Dictionary with counts: {"count": N, "capsules_cleared": X, "messages_cleared": Y}
        """
        manager = self._get_embedding_manager()
        if manager is None:
            return {
                "count": 0,
                "capsules_cleared": 0,
                "messages_cleared": 0,
            }

        try:
            result = manager.clear_all_embeddings()
            total = result["capsules_cleared"] + result["messages_cleared"]
            return {
                "count": total,
                "capsules_cleared": result["capsules_cleared"],
                "messages_cleared": result["messages_cleared"],
            }
        except Exception as e:
            logger.error(f"Failed to clear embeddings: {e}")
            raise

    def get_embedding_stats(self) -> dict[str, Any]:
        """
        Get statistics about embedding coverage.

        Returns:
            Dictionary with embedding statistics
        """
        manager = self._get_embedding_manager()
        if manager is None:
            return {
                "enabled": False,
                "provider": None,
                "capsules": {"total": 0, "with_embeddings": 0, "coverage": 0},
                "messages": {"total": 0, "with_embeddings": 0, "coverage": 0},
            }

        try:
            stats = manager.get_embedding_stats()
            stats["enabled"] = True
            return stats
        except Exception as e:
            logger.error(f"Failed to get embedding stats: {e}")
            return {
                "enabled": True,
                "error": str(e),
            }

    # === Model Configuration ===
    # Delegated to ModelConfigManager for implementation

    def switch_model(self, model_id: str) -> ModelConfig:
        """
        Switch to a different model and load its config.

        Args:
            model_id: Model identifier to switch to

        Returns:
            The ModelConfig for the new model
        """
        return self._model_config_manager.switch(model_id)

    def _apply_model_config(self, model_config: ModelConfig) -> None:
        """Apply a model config to the current state."""
        return self._model_config_manager.apply(model_config)

    def get_current_model_config(self) -> ModelConfig:
        """Get config for currently active model."""
        return self._model_config_manager.get_current()

    def update_current_model_config(self, **kwargs: Any) -> ModelConfig:
        """
        Update config for current model.

        Args:
            **kwargs: Fields to update (system_prompt, style_profile, etc.)

        Returns:
            Updated ModelConfig
        """
        return self._model_config_manager.update_current(**kwargs)

    def list_available_models(self) -> list[dict[str, Any]]:
        """List all models with their configurations."""
        return self._model_config_manager.list_available()

    def create_model_config(
        self,
        model_id: str,
        system_prompt: Optional[str] = None,
        style_profile: Optional[str] = None,
        memory_enabled: bool = True,
        decay_enabled: bool = False,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        top_p: float = 1.0,
    ) -> ModelConfig:
        """
        Create a new model configuration.

        Args:
            model_id: Model identifier
            system_prompt: Custom system prompt
            style_profile: Style profile to use
            memory_enabled: Whether to enable memory
            decay_enabled: Whether to enable memory decay
            temperature: Generation temperature
            max_tokens: Max tokens for generation
            top_p: Top-p sampling parameter

        Returns:
            The created ModelConfig
        """
        return self._model_config_manager.create(
            model_id=model_id, system_prompt=system_prompt,
            style_profile=style_profile, memory_enabled=memory_enabled,
            decay_enabled=decay_enabled, temperature=temperature,
            max_tokens=max_tokens, top_p=top_p,
        )

    def copy_model_settings(self, source_model: str, target_model: str) -> ModelConfig:
        """Copy settings from one model to another."""
        return self._model_config_manager.copy_settings(source_model, target_model)

    def delete_model_config(self, model_id: str) -> bool:
        """Delete a model configuration."""
        return self._model_config_manager.delete(model_id)

    def enable_config_auto_save(
        self,
        path: Optional[str] = None,
        debounce_ms: int = 500,
    ) -> None:
        """Enable automatic config persistence."""
        return self._model_config_manager.enable_auto_save(path, debounce_ms)

    def disable_config_auto_save(self) -> None:
        """Disable automatic config persistence."""
        return self._model_config_manager.disable_auto_save()

    # === Provider Management ===

    def list_providers(self) -> list[dict[str, Any]]:
        """
        List all configured providers.

        Returns:
            List of provider information dictionaries
        """
        return self.provider_manager.get_all_provider_info()

    def get_provider_info(self, provider_id: str) -> dict[str, Any]:
        """
        Get information about a specific provider.

        Args:
            provider_id: The provider ID

        Returns:
            Provider information dictionary
        """
        return self.provider_manager.get_provider_info(provider_id)

    def add_provider(
        self,
        provider_id: str,
        name: str,
        provider_type: str = "openai",
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        api_key_env_var: Optional[str] = None,
        default_model: str = "",
        **kwargs: Any
    ) -> dict[str, Any]:
        """
        Add a new provider.

        Args:
            provider_id: Unique identifier for the provider
            name: Display name
            provider_type: Provider type ("openai", "anthropic", "local", "custom")
            api_base: API base URL
            api_key: API key (optional, prefer api_key_env_var)
            api_key_env_var: Environment variable name for API key
            default_model: Default model for this provider
            **kwargs: Additional provider options

        Returns:
            Provider information dictionary
        """
        from threadlight.config import ProviderDefinition, Endpoint

        # Build endpoints
        endpoints = []
        if api_base:
            endpoints = [Endpoint(url=api_base, name="Primary", priority=0)]

        provider = ProviderDefinition(
            id=provider_id,
            name=name,
            type=provider_type,
            api_key=api_key,
            api_key_env_var=api_key_env_var,
            endpoints=endpoints,
            default_model=default_model,
            **kwargs
        )

        self.config.add_provider(provider)

        # Invalidate cache so next request uses new config
        self.provider_manager.invalidate_cache(provider_id)

        return self.provider_manager.get_provider_info(provider_id)

    def update_provider(self, provider_id: str, **kwargs: Any) -> Optional[dict[str, Any]]:
        """
        Update an existing provider.

        Args:
            provider_id: Provider ID to update
            **kwargs: Fields to update

        Returns:
            Updated provider info, or None if not found
        """
        provider = self.config.update_provider(provider_id, **kwargs)
        if provider:
            # Invalidate cache so next request uses new config
            self.provider_manager.invalidate_cache(provider_id)
            return self.provider_manager.get_provider_info(provider_id)
        return None

    def delete_provider(self, provider_id: str) -> bool:
        """
        Delete a provider.

        Args:
            provider_id: Provider ID to delete

        Returns:
            True if deleted, False if not found
        """
        if self.config.delete_provider(provider_id):
            self.provider_manager.invalidate_cache(provider_id)
            return True
        return False

    def test_provider(self, provider_id: str) -> dict[str, Any]:
        """
        Test a provider's connectivity.

        Args:
            provider_id: Provider ID to test

        Returns:
            Health check results
        """
        return self.provider_manager.health_check(provider_id)

    def get_provider_for_model(self, model_id: str) -> Optional[dict[str, Any]]:
        """
        Get which provider will be used for a specific model.

        Args:
            model_id: Model identifier

        Returns:
            Provider info dict, or None if using default provider
        """
        provider_def = self.config.get_provider_for_model(model_id)
        if provider_def:
            return self.provider_manager.get_provider_info(provider_def.id)
        return None

    def set_model_provider(self, model_id: str, provider_id: Optional[str]) -> bool:
        """
        Set which provider a model should use.

        Args:
            model_id: Model identifier
            provider_id: Provider ID (or None to use default)

        Returns:
            True if updated successfully
        """
        # Get or create model config
        model_config = self.config.get_model_config(model_id)
        model_config.provider_id = provider_id
        self.config.set_model_config(model_id, model_config)
        return True

    # === Memory Type Management ===
    # Delegated to CustomTypeManager for implementation

    @property
    def memory_types(self) -> CustomTypeManager:
        """Get the memory types manager for advanced operations."""
        return self._custom_type_manager

    def create_memory_type(
        self,
        type_id: str,
        display_name: str,
        fields: list[dict[str, Any]],
        description: str = "",
        display_template: str = "",
        icon: str = "file-text",
    ) -> CustomTypeDefinition:
        """Create a new custom memory type."""
        return self._custom_type_manager.create(
            type_id=type_id,
            display_name=display_name,
            fields=fields,
            description=description,
            display_template=display_template,
            icon=icon,
        )

    def list_memory_types(self, include_builtin: bool = True) -> list[dict[str, Any]]:
        """List all available memory types (built-in + custom)."""
        return self._custom_type_manager.list(include_builtin=include_builtin)

    def get_memory_type(self, type_id: str) -> Optional[dict[str, Any]]:
        """Get a specific memory type definition."""
        return self._custom_type_manager.get(type_id)

    def update_memory_type(
        self,
        type_id: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        fields: Optional[list[dict[str, Any]]] = None,
        display_template: Optional[str] = None,
        icon: Optional[str] = None,
    ) -> bool:
        """Update an existing custom memory type."""
        return self._custom_type_manager.update(
            type_id=type_id,
            display_name=display_name,
            description=description,
            fields=fields,
            display_template=display_template,
            icon=icon,
        )

    def delete_memory_type(self, type_id: str) -> bool:
        """Delete a custom memory type."""
        return self._custom_type_manager.delete(type_id)

    def import_example_type(self, type_id: str) -> Optional[CustomTypeDefinition]:
        """Import an example type definition."""
        return self._custom_type_manager.import_example(type_id)

    def list_example_types(self) -> list[dict[str, Any]]:
        """List available example types that can be imported."""
        return self._custom_type_manager.list_examples()

    def _load_custom_types(self) -> None:
        """Load custom type definitions from storage into memory."""
        self._custom_type_manager.load_from_storage()

    # === Per-Profile Memory Isolation ===

    def get_per_profile_isolation(self) -> bool:
        """
        Check if per-profile memory isolation is enabled.

        When enabled, memories are scoped to specific profiles.
        """
        return self.config.memory.per_profile_isolation

    def set_per_profile_isolation(self, enabled: bool) -> None:
        """
        Enable or disable per-profile memory isolation.

        Args:
            enabled: Whether to enable isolation
        """
        self.config.memory.per_profile_isolation = enabled
        self.memory.per_profile_isolation = enabled
        # Update current profile in memory orchestrator
        if enabled and self.active_profile:
            self.memory.current_profile = self.active_profile.id
        logger.info(f"Per-profile memory isolation {'enabled' if enabled else 'disabled'}")

    # Deprecated: kept for backward compatibility
    def get_per_model_isolation(self) -> bool:
        """Deprecated: Use get_per_profile_isolation instead."""
        return self.get_per_profile_isolation()

    def set_per_model_isolation(self, enabled: bool) -> None:
        """Deprecated: Use set_per_profile_isolation instead."""
        self.set_per_profile_isolation(enabled)

    def get_default_shared(self) -> bool:
        """Check if new memories are shared by default when isolation is enabled."""
        return self.config.memory.default_shared

    def set_default_shared(self, shared: bool) -> None:
        """
        Set whether new memories are shared by default.

        Only relevant when per_profile_isolation is enabled.

        Args:
            shared: If True, new memories are shared across all profiles by default.
                   If False, new memories are scoped to the current profile by default.
        """
        self.config.memory.default_shared = shared
        self.memory.default_shared = shared

    def share_memory(self, capsule_id: str) -> bool:
        """
        Make a memory shared across all profiles (remove profile scope).

        Args:
            capsule_id: ID of memory to share

        Returns:
            True if successful
        """
        return self.memory.share_memory(capsule_id)

    def assign_memory_to_profile(self, capsule_id: str, profile_id: str) -> bool:
        """
        Assign a memory to a specific profile.

        Args:
            capsule_id: ID of memory to assign
            profile_id: Profile ID to assign to

        Returns:
            True if successful
        """
        capsule = self.storage.get_capsule(capsule_id)
        if not capsule:
            return False
        capsule.profile_scope = profile_id
        return self.storage.update_capsule(capsule)

    # Deprecated: kept for backward compatibility
    def assign_memory_to_model(self, capsule_id: str, model_id: str) -> bool:
        """Deprecated: Use assign_memory_to_profile instead."""
        return self.memory.assign_memory_to_model(capsule_id, model_id)

    def copy_memory_to_profile(self, capsule_id: str, target_profile_id: str) -> Optional[MemoryCapsule]:
        """
        Copy a memory to another profile (creates a new capsule).

        Args:
            capsule_id: ID of memory to copy
            target_profile_id: Profile ID to copy to

        Returns:
            The new MemoryCapsule, or None if source not found
        """
        source = self.storage.get_capsule(capsule_id)
        if not source:
            return None

        return self.memory.create(
            type=source.type.value,
            content=source.content.copy(),
            cue_phrases=source.cue_phrases.copy(),
            retention=source.retention.value,
            consent_confirmed=source.consent_confirmed,
            profile_scope=target_profile_id,
        )

    # Deprecated: kept for backward compatibility
    def copy_memory_to_model(self, capsule_id: str, target_model_id: str) -> Optional[MemoryCapsule]:
        """Deprecated: Use copy_memory_to_profile instead."""
        return self.memory.copy_memory_to_model(capsule_id, target_model_id)

    def get_memory_profile_scope(self, capsule_id: str) -> Optional[str]:
        """
        Get the profile scope of a memory.

        Args:
            capsule_id: ID of memory

        Returns:
            Profile ID if scoped to a specific profile, None if shared
        """
        capsule = self.storage.get_capsule(capsule_id)
        if not capsule:
            return None
        return getattr(capsule, 'profile_scope', None)

    # Deprecated: kept for backward compatibility
    def get_memory_model_scope(self, capsule_id: str) -> Optional[str]:
        """Deprecated: Use get_memory_profile_scope instead."""
        return self.memory.get_memory_model_scope(capsule_id)

    def _update_memory_profile_scope(self) -> None:
        """Update the memory orchestrator's current profile reference."""
        if self.active_profile:
            self.memory.current_profile = self.active_profile.id

    # Deprecated: kept for backward compatibility
    def _update_memory_model_scope(self) -> None:
        """Deprecated: Use _update_memory_profile_scope instead."""
        self.memory.current_model = self.config.provider.model

    # === Memory Links ===

    def create_memory_link(
        self,
        source_id: str,
        target_id: str,
        link_type: str = "related",
        strength: float = 1.0,
        bidirectional: bool = False,
        notes: str = "",
        created_by: str = "user",
    ) -> str:
        """
        Create a link between two memory capsules.

        Args:
            source_id: ID of the source capsule
            target_id: ID of the target capsule
            link_type: Relationship type (e.g., 'related', 'contradicts', 'supports')
            strength: Link strength from 0.0 to 1.0
            bidirectional: Whether the link applies in both directions
            notes: Optional notes about the relationship
            created_by: Who created the link

        Returns:
            The link ID

        Raises:
            ValueError: If capsules don't exist or duplicate link
        """
        link = MemoryLink(
            source_capsule_id=source_id,
            target_capsule_id=target_id,
            link_type=link_type,
            strength=strength,
            bidirectional=bidirectional,
            notes=notes,
            created_by=created_by,
        )
        return self.storage.create_link(link)

    def get_memory_links(
        self,
        capsule_id: str,
        direction: str = "both",
        link_types: Optional[list[str]] = None,
    ) -> list[MemoryLink]:
        """
        Get links for a memory capsule.

        Args:
            capsule_id: The capsule ID
            direction: 'outgoing', 'incoming', or 'both'
            link_types: Optional filter by link type(s)

        Returns:
            List of MemoryLinks
        """
        return self.storage.get_links_for_capsule(capsule_id, direction, link_types)

    def get_linked_capsules(
        self,
        capsule_id: str,
        direction: str = "both",
        link_types: Optional[list[str]] = None,
        depth: int = 1,
    ) -> list[tuple]:
        """
        Get capsules linked to a given capsule.

        Args:
            capsule_id: The starting capsule ID
            direction: 'outgoing', 'incoming', or 'both'
            link_types: Optional filter by link type(s)
            depth: Maximum traversal depth (1 = direct links only)

        Returns:
            List of (capsule, link, depth) tuples
        """
        return self.storage.get_linked_capsules(capsule_id, direction, link_types, depth)

    def delete_memory_link(self, link_id: str) -> bool:
        """
        Delete a memory link (moves to trash for potential restoration).

        Args:
            link_id: The link ID to delete

        Returns:
            True if deleted, False if not found
        """
        return self.storage.delete_link(link_id)

    def restore_deleted_item(self, deleted_item_id: str) -> bool:
        """
        Restore a deleted item from the trash.

        Args:
            deleted_item_id: The trash entry ID

        Returns:
            True if restored, False if not found
        """
        return self.storage.restore_deleted_item(deleted_item_id)

    def list_deleted_items(
        self,
        item_type: Optional[str] = None,
        limit: int = 50,
    ) -> list[DeletedItem]:
        """
        List items in the trash.

        Args:
            item_type: Optional filter ('capsule', 'memory_link')
            limit: Maximum items to return

        Returns:
            List of DeletedItem entries
        """
        return self.storage.list_deleted_items(item_type, limit)

    # === Group Chat Support ===
    # Delegated to GroupChatManager for implementation

    def format_group_chat_history(
        self,
        messages: list[Message],
        active_profile_id: str,
        profiles: Optional[dict[str, "Profile"]] = None,
    ) -> list[dict[str, str]]:
        """
        Format messages for multi-profile group chat.

        When prompting a specific profile, other profiles' assistant messages
        are tagged and embedded in user messages so the active profile can see
        what others said without confusion about who said what.

        Args:
            messages: List of Message objects from conversation
            active_profile_id: The profile we're currently prompting
            profiles: Optional dict mapping profile_id -> Profile for name lookup

        Returns:
            Formatted message history suitable for chat context
        """
        return self._group_chat.format_history(messages, active_profile_id, profiles)

    def group_chat(
        self,
        message: str,
        conversation_id: str,
        profile_ids: Optional[list[str]] = None,
        **kwargs: Any
    ) -> list[dict[str, Any]]:
        """
        Send a message to a group chat and get responses from all participating profiles.

        Each profile responds in turn, seeing the previous profiles' responses
        tagged in the context.

        Args:
            message: User message
            conversation_id: ID of the group chat conversation
            profile_ids: Optional override of which profiles should respond
                        (defaults to conversation's participant_profiles)
            **kwargs: Additional options passed to chat()

        Returns:
            List of response dicts with profile info
        """
        return self._group_chat.chat(message, conversation_id, profile_ids, **kwargs)

    def create_group_conversation(
        self,
        name: str,
        profile_ids: list[str],
        metadata: Optional[dict[str, Any]] = None,
    ) -> Conversation:
        """
        Create a new group chat conversation with multiple profiles.

        Args:
            name: Conversation name
            profile_ids: List of profile IDs to participate
            metadata: Optional metadata dict

        Returns:
            The created Conversation
        """
        return self._group_chat.create_conversation(name, profile_ids, metadata)

    def add_profile_to_conversation(
        self,
        conversation_id: str,
        profile_id: str,
    ) -> bool:
        """
        Add a profile to an existing conversation's participants.

        Args:
            conversation_id: ID of conversation to modify
            profile_id: Profile ID to add

        Returns:
            True if added, False if already present or conversation not found
        """
        return self._group_chat.add_profile(conversation_id, profile_id)

    def remove_profile_from_conversation(
        self,
        conversation_id: str,
        profile_id: str,
    ) -> bool:
        """
        Remove a profile from a conversation's participants.

        Args:
            conversation_id: ID of conversation to modify
            profile_id: Profile ID to remove

        Returns:
            True if removed, False if not present or conversation not found
        """
        return self._group_chat.remove_profile(conversation_id, profile_id)

    def stream_group_chat(
        self,
        message: str,
        conversation_id: str,
        profile_ids: Optional[list[str]] = None,
        **kwargs: Any
    ) -> Iterator[dict[str, Any]]:
        """
        Stream responses from a group chat.

        Yields events as each profile streams their response. Each profile
        responds in turn, with previous responses embedded as tagged content.

        Args:
            message: User message
            conversation_id: ID of the group chat conversation
            profile_ids: Optional override of which profiles should respond
            **kwargs: Additional options passed to stream()

        Yields:
            Events with different types:
            - {"type": "profile_start", "profile_id": "...", "profile_name": "..."}
            - {"type": "chunk", "profile_id": "...", "content": "..."}
            - {"type": "profile_complete", "profile_id": "...", "content": "..."}
            - {"type": "error", "profile_id": "...", "error": "..."}
            - {"type": "complete", "responses": [...]}
        """
        return self._group_chat.stream(message, conversation_id, profile_ids, **kwargs)
