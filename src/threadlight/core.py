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
from typing import Any, Iterator, Optional
import logging

from threadlight.config import ThreadlightConfig
from threadlight.capsules.base import ContextMode, CapsuleType, MemoryCapsule
from threadlight.capsules.style import StyleProfile, DEFAULT_STYLE
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
        )

    def _init_context(self) -> None:
        """Initialize context composer."""
        self.composer = ContextComposer(
            identity_name=self.config.identity.name,
            base_system_prompt=self.config.identity.system_prompt,
        )

        # Load style profile
        self.style_profile: Optional[StyleProfile] = None
        if self.config.style.default_profile == "fable-2026":
            self.style_profile = StyleProfile(**DEFAULT_STYLE)

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

        # Build messages
        messages = []

        # 1. System message with memory context
        context: Optional[ComposedContext] = None
        system_content = ""

        if use_memory:
            context = self._build_context(message, memory_filter, context_mode)
            if context.system_message:
                system_content = context.system_message
        elif self.config.identity.system_prompt:
            system_content = self.config.identity.system_prompt

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
        response = self._complete_with_tools(messages, tools, **kwargs)

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
        This method finds the matching ritual, activates its state,
        and returns an appropriate response.

        Args:
            ritual_name: The ritual trigger (e.g., "/snuggle", "/coil")

        Returns:
            An appropriate ritual response string

        Example:
            response = tl.invoke_ritual("/snuggle")
            # -> "*settles close, presence warm and unhurried*"
        """
        # Use orchestrator to invoke ritual (handles state tracking)
        result = self.memory.invoke_ritual(ritual_name)

        if result.matched and result.response_template:
            return result.response_template

        # Get valence for generic response
        valence = None
        if result.capsule and hasattr(result.capsule, 'valence'):
            valence = result.capsule.valence

        return self.composer.format_ritual_response(ritual_name, valence=valence)

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
            **kwargs: Additional capsule fields

        Returns:
            The created MemoryCapsule
        """
        return self.memory.create(
            type=type,
            content=content,
            cue_phrases=cue_phrases,
            consent_confirmed=confirm,
            **kwargs
        )

    def recall(
        self,
        cue: str,
        limit: int = 5,
    ) -> list[MemoryCapsule]:
        """
        Recall memories matching a cue phrase.

        Shortcut for self.memory.recall().
        """
        return self.memory.recall(cue, limit=limit)

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

    def set_style(self, style_id: str) -> None:
        """
        Set the active style profile.

        Args:
            style_id: Style identifier ("fable-2026", "minimal", etc.)
        """
        from threadlight.capsules.style import DEFAULT_STYLE, MINIMAL_STYLE

        if style_id == "fable-2026":
            self.style_profile = StyleProfile(**DEFAULT_STYLE)
        elif style_id == "minimal":
            self.style_profile = StyleProfile(**MINIMAL_STYLE)
        else:
            # Try to load from storage
            from threadlight.storage.base import CapsuleFilter
            filter = CapsuleFilter(type=CapsuleType.STYLE, limit=100)
            styles = self.storage.list_capsules(filter)
            for style in styles:
                if hasattr(style, 'style_id') and style.style_id == style_id:
                    self.style_profile = style
                    return
            logger.warning(f"Style profile not found: {style_id}")

    def get_style(self) -> Optional[StyleProfile]:
        """Get the current style profile."""
        return self.style_profile
