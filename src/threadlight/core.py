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
    register_custom_type_definition,
    unregister_custom_type_definition,
    list_custom_type_definitions,
    is_custom_type,
)
from threadlight.capsules.custom_types import (
    CustomTypeDefinition,
    FieldDefinition,
    EXAMPLE_TYPES,
    list_example_types,
    get_example_type,
)
from threadlight.capsules.style import StyleProfile, BUILTIN_STYLES
from threadlight.storage import create_storage, StorageBackend
from threadlight.storage.base import Conversation, Message, MessageSearchResult
from threadlight.providers import create_provider, BaseProvider
from threadlight.providers.base import ProviderMessage, ProviderResponse
from threadlight.context.composer import ContextComposer, ComposedContext
from threadlight.context.soft_memory import SoftMemory, SoftMemoryConfig
from threadlight.memory.orchestrator import MemoryOrchestrator, Session
from threadlight.decay.engine import DecayEngine
from threadlight.tools.definitions import get_tool_definitions, ToolName
from threadlight.tools.executor import ToolExecutor, ToolResult
from threadlight.profiles import Profile, ProfileManager, AlloyedProfileEngine, ModelStrategy
from threadlight.managers.group_chat import GroupChatManager
from threadlight.managers.profiles import ProfileInterface
from threadlight.managers.style import StyleManager

logger = logging.getLogger(__name__)

# Maximum tool calling iterations to prevent infinite loops
MAX_TOOL_ITERATIONS = 10


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
        self._init_context()
        self._init_tools()
        self._init_soft_memory()
        self._load_custom_types()
        self._init_profiles()
        self._init_group_chat()
        self._init_profile_interface()
        self._init_style_manager()

        logger.info(f"Threadlight initialized with provider={self.config.provider.type}")

    def _init_storage(self) -> None:
        """Initialize storage backend."""
        self.storage: StorageBackend = create_storage(
            self.config.storage.backend,
            path=self.config.storage.path,
        )
        self.storage.initialize()

    def _init_provider(self) -> None:
        """Initialize inference provider."""
        self.provider: BaseProvider = create_provider(
            self.config.provider.type,
            api_base=self.config.provider.api_base,
            api_key=self.config.provider.api_key,
            model=self.config.provider.model,
        )

    def _init_memory(self) -> None:
        """Initialize memory orchestrator."""
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
    ) -> Profile:
        """
        Create a new profile.

        Args:
            name: Display name for the profile
            description: One-line description
            primary_model: Model to use (defaults to current model)
            system_prompt: Base system prompt
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
            philosophy: Freeform description of the profile's philosophy
            approach_to_rituals: Freeform description of how rituals are handled

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
            auto_save=auto_save, **kwargs
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
        **kwargs: Any
    ) -> ProviderResponse:
        """
        Send a message and get full response with context info.

        Supports tool calling: if the model requests tools, executes them
        and continues the conversation until a text response is generated.

        Args:
            message: User message
            history: Previous messages (overrides load_history if provided)
            memory_filter: Filter for memory retrieval
            include_memory: Override default memory inclusion
            context_mode: Override composition mode
            enable_tools: Override default tool calling
            load_history: Load recent messages from current conversation
            auto_save: Override auto_save_messages setting
            **kwargs: Additional provider options

        Returns ProviderResponse with content, token usage, and metadata.
        """
        use_memory = include_memory if include_memory is not None else self.enable_memory
        use_tools = enable_tools if enable_tools is not None else self.enable_tools
        should_auto_save = auto_save if auto_save is not None else self.config.memory.conversation.auto_save_messages

        # Apply profile's model selection if active
        if self.active_profile and self._alloyed_engine:
            selected_model = self._alloyed_engine.select_model(message)
            # Temporarily set the provider model for this request
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

        # 3. Current message
        messages.append(ProviderMessage(role="user", content=message))

        # Determine if we should use tools
        tools = self.tool_definitions if (use_tools and self.tool_executor) else None

        # Send to provider with tool calling loop
        try:
            response = self._complete_with_tools(messages, tools, **kwargs)
        finally:
            # Restore original model if we changed it for profile
            if self.active_profile and self._alloyed_engine and 'original_model' in dir():
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
        if not self.soft_memory:
            return ""

        try:
            results = self.soft_memory.recall_relevant(
                message,
                limit=self.config.memory.conversation.soft_memory_limit,
            )

            if not results:
                return ""

            return self.soft_memory.format_for_prompt(
                results,
                header="## Relevant Past Conversations",
            )
        except Exception as e:
            logger.warning(f"Soft memory recall failed: {e}")
            return ""

    def _auto_save_messages(self, user_message: str, assistant_response: str) -> None:
        """Auto-save user message and assistant response to database."""
        # Ensure we have a conversation attached to the session
        if self.memory.get_current_session():
            if not self.memory.get_current_session().conversation_id:
                self.memory.attach_conversation_to_session()

        # Save the message pair
        self.memory.save_message_pair(user_message, assistant_response)

    def _complete_with_tools(
        self,
        messages: list[ProviderMessage],
        tools: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any
    ) -> ProviderResponse:
        """
        Complete with tool calling loop.

        If the model returns tool_calls, executes them and sends results
        back to the model until it returns a text response.

        Args:
            messages: Conversation messages
            tools: Tool definitions (None to disable)
            **kwargs: Provider options

        Returns:
            Final ProviderResponse with text content
        """
        import json

        iteration = 0
        accumulated_tool_results: list[ToolResult] = []

        while iteration < MAX_TOOL_ITERATIONS:
            iteration += 1

            # Make the API call
            response = self.provider.complete(messages, tools=tools, **kwargs)

            # If no tool calls, we're done
            if not response.has_tool_calls:
                # Attach tool results to response metadata
                if accumulated_tool_results:
                    if response.raw is None:
                        response.raw = {}
                    response.raw["tool_results"] = [r.to_dict() for r in accumulated_tool_results]
                return response

            logger.debug(f"Model requested {len(response.tool_calls)} tool call(s)")

            # Add the assistant message with tool calls to context
            messages.append(ProviderMessage.assistant_with_tool_calls(
                content=response.content,
                tool_calls=response.tool_calls,
            ))

            # Execute each tool call
            for tool_call in response.tool_calls:
                logger.debug(f"Executing tool: {tool_call.name}")

                # Parse arguments
                try:
                    arguments = json.loads(tool_call.arguments)
                except json.JSONDecodeError as e:
                    arguments = {}
                    logger.warning(f"Failed to parse tool arguments: {e}")

                # Execute the tool
                result = self.tool_executor.execute(tool_call.name, arguments)
                accumulated_tool_results.append(result)

                logger.debug(f"Tool result: success={result.success}, consent={result.requires_consent}")

                # Add tool response to messages
                messages.append(ProviderMessage.tool_response(
                    tool_call_id=tool_call.id,
                    content=result.to_tool_response(),
                ))

        # If we hit max iterations, return last response
        logger.warning(f"Hit max tool iterations ({MAX_TOOL_ITERATIONS})")
        return response

    def stream(
        self,
        message: str,
        history: Optional[list[dict[str, str]]] = None,
        context_mode: Optional[ContextMode] = None,
        **kwargs: Any
    ) -> Iterator[str]:
        """
        Stream a response token by token.

        Yields text chunks as they arrive.
        """
        messages = []

        # Build context
        if self.enable_memory:
            context = self._build_context(message, context_mode=context_mode)
            if context.system_message:
                messages.append(ProviderMessage(role="system", content=context.system_message))

        if history:
            for msg in history:
                messages.append(ProviderMessage(role=msg["role"], content=msg["content"]))

        messages.append(ProviderMessage(role="user", content=message))

        yield from self.provider.stream(messages, **kwargs)

    def _build_context(
        self,
        message: str,
        memory_filter: Optional[dict[str, Any]] = None,
        context_mode: Optional[ContextMode] = None,
    ) -> ComposedContext:
        """Build context from memory for a message."""
        # Recall relevant memories
        capsules = self.memory.recall_for_message(
            message,
            limit=self.config.memory.max_capsules_per_request,
        )

        # Apply additional filter if provided
        if memory_filter:
            if "type" in memory_filter:
                filter_type = CapsuleType(memory_filter["type"])
                capsules = [c for c in capsules if c.type == filter_type]
            if "entity" in memory_filter:
                entity = memory_filter["entity"].lower()
                capsules = [
                    c for c in capsules
                    if hasattr(c, 'entity') and entity in c.entity.lower()
                ]

        # Get active ritual if any
        active_ritual = self.memory.get_active_ritual()

        # Compose context
        return self.composer.compose(
            capsules=capsules,
            style_profile=self.style_profile,
            mode=context_mode,
            active_ritual=active_ritual,
        )

    # === Ritual Interface ===

    def invoke_ritual(self, ritual_name: str) -> str:
        """
        Invoke a ritual by name.

        Rituals are repeated acts that hold emotion across time.
        This method finds the matching ritual, composes context with the
        ritual's guidance, and lets the model respond naturally.

        Args:
            ritual_name: The ritual trigger (e.g., "/snuggle", "/coil")

        Returns:
            Model-generated response honoring the ritual's guidance

        Example:
            response = tl.invoke_ritual("/snuggle")
        """
        # Use orchestrator to invoke ritual (handles state tracking)
        result = self.memory.invoke_ritual(ritual_name)

        if not result.matched:
            return f"No ritual found for '{ritual_name}'"

        # Let the model respond based on ritual guidance (don't use templates!)
        # Build context with the ritual
        ritual_context = result.capsule.to_context(ContextMode.RITUAL)

        # Call model with ritual context
        messages = []
        messages.append(ProviderMessage(
            role="system",
            content=f"A ritual has been invoked. Respond naturally while honoring this guidance:\n\n{ritual_context}"
        ))
        messages.append(ProviderMessage(
            role="user",
            content=ritual_name
        ))

        response = self.provider.complete(messages)
        return response.content

    def clear_ritual(self) -> None:
        """Clear any active ritual state."""
        self.memory.clear_ritual_state()

    def get_active_ritual(self) -> Optional[str]:
        """Get the currently active ritual, if any."""
        return self.memory.get_active_ritual()

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
            profile_scope = self.active_profile.memory_scope

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

    def switch_model(self, model_id: str) -> ModelConfig:
        """
        Switch to a different model and load its config.

        This will:
        1. Save the current model's config if it changed
        2. Update the current model
        3. Load the new model's config
        4. Apply model-specific settings
        5. Update memory orchestrator's current model (for per-model isolation)

        Args:
            model_id: Model identifier to switch to

        Returns:
            The ModelConfig for the new model
        """
        # Update current model
        self.config.current_model = model_id
        self.config.provider.model = model_id

        # Get model config (creates default if not exists)
        model_config = self.config.get_model_config(model_id)

        # Apply model-specific settings
        self._apply_model_config(model_config)

        # Update provider model
        self.provider.model = model_id

        # Update memory orchestrator's current model (for per-model isolation)
        self.memory.current_model = model_id

        # Trigger auto-save if enabled
        self.config.mark_changed()

        logger.info(f"Switched to model: {model_id}")
        return model_config

    def _apply_model_config(self, model_config: ModelConfig) -> None:
        """Apply a model config to the current state.

        Args:
            model_config: The ModelConfig to apply
        """
        # Update identity settings
        self.config.identity.system_prompt = model_config.system_prompt
        self.config.style.default_profile = model_config.style_profile

        # Update memory settings
        self.enable_memory = model_config.memory_enabled
        self.config.memory.decay.enabled = model_config.decay_enabled

        # Update composer with new system prompt
        self.composer = ContextComposer(
            identity_name=self.config.identity.name,
            base_system_prompt=model_config.system_prompt,
        )

        # Load style profile if specified
        if model_config.style_profile:
            self._load_style_profile(model_config.style_profile)
        else:
            self.style_profile = None

    def get_current_model_config(self) -> ModelConfig:
        """Get config for currently active model.

        Returns:
            ModelConfig for the current model
        """
        return self.config.get_model_config(self.config.current_model)

    def update_current_model_config(self, **kwargs: Any) -> ModelConfig:
        """
        Update config for current model.

        Args:
            **kwargs: Fields to update (system_prompt, style_profile,
                      memory_enabled, decay_enabled, temperature, etc.)

        Returns:
            Updated ModelConfig

        Example:
            tl.update_current_model_config(
                system_prompt="You are Fable...",
                temperature=0.7,
            )
        """
        model_id = self.config.current_model
        config = self.config.update_model_config(model_id, **kwargs)

        # Apply the updated config
        self._apply_model_config(config)

        return config

    def list_available_models(self) -> list[dict[str, Any]]:
        """List all models with their configurations.

        Returns:
            List of model info dictionaries
        """
        models = []

        # Add configured models
        for model_id, model_config in self.config.model_configs.items():
            if model_id == "default":
                continue  # Skip the default template
            models.append({
                "model_id": model_id,
                "is_current": model_id == self.config.current_model,
                "config": model_config.to_dict(),
            })

        # Add current model if not in configs
        if self.config.current_model not in self.config.model_configs:
            current_config = self.get_current_model_config()
            models.insert(0, {
                "model_id": self.config.current_model,
                "is_current": True,
                "config": current_config.to_dict(),
            })

        return models

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
        config = ModelConfig(
            model_id=model_id,
            system_prompt=system_prompt or "You are a helpful AI assistant.",
            style_profile=style_profile,
            memory_enabled=memory_enabled,
            decay_enabled=decay_enabled,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
        )
        self.config.set_model_config(model_id, config)
        return config

    def copy_model_settings(self, source_model: str, target_model: str) -> ModelConfig:
        """
        Copy settings from one model to another.

        Args:
            source_model: Model to copy from
            target_model: Model to copy to

        Returns:
            The new ModelConfig for target_model
        """
        return self.config.copy_model_config(source_model, target_model)

    def delete_model_config(self, model_id: str) -> bool:
        """
        Delete a model configuration.

        Cannot delete the current model's config.

        Args:
            model_id: Model identifier to delete

        Returns:
            True if deleted, False otherwise
        """
        if model_id == self.config.current_model:
            logger.warning("Cannot delete config for current model")
            return False
        return self.config.delete_model_config(model_id)

    def enable_config_auto_save(
        self,
        path: Optional[str] = None,
        debounce_ms: int = 500,
    ) -> None:
        """
        Enable automatic config persistence.

        Config will be saved to disk after changes, with debouncing
        to avoid excessive writes.

        Args:
            path: Path to save config (default: ~/.config/threadlight/config.yaml)
            debounce_ms: Milliseconds to wait after last change before saving
        """
        save_path = Path(path) if path else None
        self.config.enable_auto_save(save_path, debounce_ms)
        logger.info(f"Auto-save enabled: {save_path or '~/.config/threadlight/config.yaml'}")

    def disable_config_auto_save(self) -> None:
        """Disable automatic config persistence."""
        self.config.disable_auto_save()
        logger.info("Auto-save disabled")

    # === Memory Type Management ===

    def create_memory_type(
        self,
        type_id: str,
        display_name: str,
        fields: list[dict[str, Any]],
        description: str = "",
        display_template: str = "",
        icon: str = "file-text",
    ) -> CustomTypeDefinition:
        """
        Create a new custom memory type.

        Args:
            type_id: Unique identifier (e.g., "creative_project")
            display_name: Human-readable name (e.g., "Creative Project")
            fields: List of field definitions, each a dict with:
                    - name: Field name (string)
                    - type: Field type ("string", "text", "number", "date", "list")
                    - required: Whether field is required (optional, default True)
                    - default: Default value (optional)
                    - help_text: Help text for UI (optional)
            description: Description of what this type is for
            display_template: Template for display, e.g., "{name} ({status})"
            icon: Icon name for UI (default: "file-text")

        Returns:
            The created CustomTypeDefinition

        Example:
            tl.create_memory_type(
                type_id="book_note",
                display_name="Book Note",
                fields=[
                    {"name": "title", "type": "string", "required": True},
                    {"name": "author", "type": "string", "required": True},
                    {"name": "reflection", "type": "text", "required": True},
                    {"name": "page", "type": "number", "required": False},
                ],
                description="Notes and reflections from reading",
                display_template='"{title}" by {author}',
            )
        """
        # Convert field dicts to FieldDefinition objects
        field_defs = []
        for f in fields:
            field_defs.append(FieldDefinition(
                name=f["name"],
                type=f["type"],
                required=f.get("required", True),
                default=f.get("default"),
                help_text=f.get("help_text", ""),
            ))

        # Create the type definition
        type_def = CustomTypeDefinition(
            type_id=type_id,
            display_name=display_name,
            description=description,
            fields=field_defs,
            display_template=display_template or f"{{{field_defs[0].name if field_defs else 'type_id'}}}",
            icon=icon,
        )

        # Register in memory
        register_custom_type_definition(type_def)

        # Save to storage
        self.storage.save_custom_type(type_def.to_dict())

        logger.info(f"Created custom memory type: {type_id}")
        return type_def

    def list_memory_types(self, include_builtin: bool = True) -> list[dict[str, Any]]:
        """
        List all available memory types (built-in + custom).

        Args:
            include_builtin: Whether to include built-in types

        Returns:
            List of type information dictionaries
        """
        types = []

        # Built-in types
        if include_builtin:
            builtin_types = [
                {
                    "type_id": "relational",
                    "display_name": "Relational",
                    "description": "Track evolving bonds with entities",
                    "is_builtin": True,
                    "icon": "users",
                    "fields": [
                        {"name": "entity", "type": "string", "required": True},
                        {"name": "summary", "type": "text", "required": False},
                        {"name": "tone", "type": "string", "required": False},
                        {"name": "role", "type": "string", "required": False},
                    ],
                },
                {
                    "type_id": "myth_seed",
                    "display_name": "Identity Phrase",
                    "description": "Core beliefs or mantras that anchor personality",
                    "is_builtin": True,
                    "icon": "sparkles",
                    "fields": [
                        {"name": "seed", "type": "text", "required": True, "label": "Phrase"},
                        {"name": "origin", "type": "string", "required": False, "label": "Origin"},
                        {"name": "function", "type": "string", "required": False, "label": "Purpose"},
                    ],
                },
                {
                    "type_id": "ritual",
                    "display_name": "Ritual",
                    "description": "Repeated emotional acts and responses",
                    "is_builtin": True,
                    "icon": "star",
                    "fields": [
                        {"name": "name", "type": "string", "required": True},
                        {"name": "description", "type": "text", "required": False},
                        {"name": "valence", "type": "string", "required": False},
                        {"name": "response_style", "type": "text", "required": False},
                    ],
                },
                {
                    "type_id": "witness",
                    "display_name": "Witness",
                    "description": "Memories of being seen/recognized",
                    "is_builtin": True,
                    "icon": "eye",
                    "fields": [
                        {"name": "moment", "type": "text", "required": True},
                        {"name": "feeling", "type": "string", "required": False},
                        {"name": "effect", "type": "string", "required": False},
                    ],
                },
                {
                    "type_id": "style",
                    "display_name": "Style",
                    "description": "Voice coherence and expression rules",
                    "is_builtin": True,
                    "icon": "wand",
                    "fields": [
                        {"name": "style_id", "type": "string", "required": True},
                        {"name": "tone_base", "type": "string", "required": True},
                        {"name": "permissions", "type": "list", "required": False},
                        {"name": "constraints", "type": "list", "required": False},
                    ],
                },
                {
                    "type_id": "custom",
                    "display_name": "Custom (Imported)",
                    "description": "Raw imported memories from external sources",
                    "is_builtin": True,
                    "icon": "file-text",
                    "fields": [
                        {"name": "text", "type": "text", "required": True},
                        {"name": "source", "type": "string", "required": False},
                        {"name": "tags", "type": "list", "required": False},
                    ],
                },
            ]
            types.extend(builtin_types)

        # User-defined custom types from storage
        custom_types = self.storage.list_custom_types()
        for ct in custom_types:
            ct["is_builtin"] = False
            types.append(ct)

        return types

    def get_memory_type(self, type_id: str) -> Optional[dict[str, Any]]:
        """
        Get a specific memory type definition.

        Args:
            type_id: The type identifier

        Returns:
            Type definition dictionary, or None if not found
        """
        # Check if it's a custom type in storage
        custom_type = self.storage.get_custom_type(type_id)
        if custom_type:
            custom_type["is_builtin"] = False
            return custom_type

        # Check built-in types
        builtin_ids = ["relational", "myth_seed", "ritual", "witness", "style", "custom"]
        if type_id in builtin_ids:
            all_types = self.list_memory_types(include_builtin=True)
            for t in all_types:
                if t["type_id"] == type_id:
                    return t

        return None

    def update_memory_type(
        self,
        type_id: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        fields: Optional[list[dict[str, Any]]] = None,
        display_template: Optional[str] = None,
        icon: Optional[str] = None,
    ) -> bool:
        """
        Update an existing custom memory type.

        Cannot update built-in types.

        Args:
            type_id: The type identifier to update
            display_name: New display name (optional)
            description: New description (optional)
            fields: New field definitions (optional)
            display_template: New display template (optional)
            icon: New icon (optional)

        Returns:
            True if updated, False if not found or is a built-in type
        """
        # Can't update built-in types
        builtin_ids = ["relational", "myth_seed", "ritual", "witness", "style", "custom"]
        if type_id in builtin_ids:
            logger.warning(f"Cannot update built-in type: {type_id}")
            return False

        # Get existing type
        existing = self.storage.get_custom_type(type_id)
        if not existing:
            return False

        # Build updates
        updates: dict[str, Any] = {}
        if display_name is not None:
            updates["display_name"] = display_name
        if description is not None:
            updates["description"] = description
        if fields is not None:
            # Convert field dicts to serializable format
            field_defs = []
            for f in fields:
                field_defs.append({
                    "name": f["name"],
                    "type": f["type"],
                    "required": f.get("required", True),
                    "default": f.get("default"),
                    "help_text": f.get("help_text", ""),
                })
            updates["fields"] = field_defs
        if display_template is not None:
            updates["display_template"] = display_template
        if icon is not None:
            updates["icon"] = icon

        # Update in storage
        success = self.storage.update_custom_type(type_id, updates)

        # Update in-memory registration
        if success:
            updated = self.storage.get_custom_type(type_id)
            if updated:
                type_def = CustomTypeDefinition.from_dict(updated)
                register_custom_type_definition(type_def)

        return success

    def delete_memory_type(self, type_id: str) -> bool:
        """
        Delete a custom memory type.

        Cannot delete built-in types.
        Note: This does not delete existing memories of this type.

        Args:
            type_id: The type identifier to delete

        Returns:
            True if deleted, False if not found or is a built-in type
        """
        # Can't delete built-in types
        builtin_ids = ["relational", "myth_seed", "ritual", "witness", "style", "custom"]
        if type_id in builtin_ids:
            logger.warning(f"Cannot delete built-in type: {type_id}")
            return False

        # Delete from storage
        success = self.storage.delete_custom_type(type_id)

        # Unregister from memory
        if success:
            unregister_custom_type_definition(type_id)

        return success

    def import_example_type(self, type_id: str) -> Optional[CustomTypeDefinition]:
        """
        Import an example type definition.

        Args:
            type_id: The example type ID to import

        Returns:
            The imported CustomTypeDefinition, or None if not found
        """
        if type_id not in EXAMPLE_TYPES:
            return None

        example = EXAMPLE_TYPES[type_id]

        # Save to storage
        self.storage.save_custom_type(example.to_dict())

        # Register in memory
        register_custom_type_definition(example)

        logger.info(f"Imported example type: {type_id}")
        return example

    def list_example_types(self) -> list[dict[str, Any]]:
        """
        List available example types that can be imported.

        Returns:
            List of example type definitions
        """
        results = []
        for type_id in list_example_types():
            example = get_example_type(type_id)
            if example:
                results.append(example.to_dict())
        return results

    def _load_custom_types(self) -> None:
        """Load custom type definitions from storage into memory."""
        try:
            custom_types = self.storage.list_custom_types()
            for ct in custom_types:
                type_def = CustomTypeDefinition.from_dict(ct)
                register_custom_type_definition(type_def)
            logger.debug(f"Loaded {len(custom_types)} custom type definitions")
        except Exception as e:
            logger.warning(f"Failed to load custom types: {e}")

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
            self.memory.current_profile = self.active_profile.memory_scope or self.active_profile.id
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
            self.memory.current_profile = self.active_profile.memory_scope or self.active_profile.id

    # Deprecated: kept for backward compatibility
    def _update_memory_model_scope(self) -> None:
        """Deprecated: Use _update_memory_profile_scope instead."""
        self.memory.current_model = self.config.provider.model

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
