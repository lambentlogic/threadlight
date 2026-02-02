"""
Chat orchestration for Threadlight.

This module handles core chat operations including:
- Message completion with tool calling
- Context building from memory
- Soft memory integration
- Auto-saving of conversation messages
"""

from __future__ import annotations

from typing import Any, Iterator, Optional, TYPE_CHECKING
import logging
import json

if TYPE_CHECKING:
    from threadlight.core import Threadlight
    from threadlight.capsules.base import ContextMode, MemoryCapsule, CapsuleType
    from threadlight.context.composer import ComposedContext
    from threadlight.providers.base import ProviderMessage, ProviderResponse
    from threadlight.tools.executor import ToolResult

logger = logging.getLogger(__name__)

# Maximum tool calling iterations to prevent infinite loops
MAX_TOOL_ITERATIONS = 10


class ChatManager:
    """
    Manages chat operations for Threadlight.

    This manager handles:
    - Tool calling loops
    - Context building from memory
    - Soft memory integration
    - Message auto-saving
    """

    def __init__(self, threadlight: 'Threadlight'):
        """
        Initialize the chat manager.

        Args:
            threadlight: Reference to parent Threadlight instance
        """
        self.tl = threadlight

    def complete_with_tools(
        self,
        messages: list['ProviderMessage'],
        tools: Optional[list[dict[str, Any]]] = None,
        model_id: Optional[str] = None,
        **kwargs: Any
    ) -> 'ProviderResponse':
        """
        Complete with tool calling loop.

        If the model returns tool_calls, executes them and sends results
        back to the model until it returns a text response.

        Supports multi-provider routing: if model_id is specified and the model
        has a provider_id configured, the request is routed to that provider.

        Args:
            messages: Conversation messages
            tools: Tool definitions (None to disable)
            model_id: Model to use (for multi-provider routing)
            **kwargs: Provider options

        Returns:
            Final ProviderResponse with text content
        """
        from threadlight.providers.base import ProviderMessage

        iteration = 0
        accumulated_tool_results: list['ToolResult'] = []

        # Determine which provider to use
        # If model_id specified and multi-provider is configured, use ProviderManager
        use_provider_manager = (
            model_id is not None and
            hasattr(self.tl, 'provider_manager') and
            self.tl.config.providers
        )

        # Structured logging for model routing
        tool_count = len(tools) if tools else 0
        tool_names = [t['function']['name'] for t in tools] if tools else []
        logger.info(f"[model_routing] model_id={model_id}, use_provider_manager={use_provider_manager}, tool_count={tool_count}, tools={tool_names}")

        while iteration < MAX_TOOL_ITERATIONS:
            iteration += 1

            # Make the API call - route to appropriate provider
            if use_provider_manager:
                logger.info(f"[model_routing] routing to ProviderManager model={model_id}")
                response = self.tl.provider_manager.complete(
                    model_id=model_id,
                    messages=messages,
                    tools=tools,
                    **kwargs
                )
            else:
                logger.info(f"[model_routing] routing to default provider model={self.tl.provider.model}")
                response = self.tl.provider.complete(messages, tools=tools, **kwargs)

            # If no tool calls, we're done
            if not response.has_tool_calls:
                logger.info(f"[tool_calls] iteration={iteration} - no tool_calls in response, returning. "
                           f"finish_reason={response.finish_reason}, content_preview={response.content[:100] if response.content else 'empty'}...")
                # Attach tool results to response metadata
                if accumulated_tool_results:
                    if response.raw is None:
                        response.raw = {}
                    response.raw["tool_results"] = [r.to_dict() for r in accumulated_tool_results]
                return response

            logger.info(f"[tool_calls] model requested {len(response.tool_calls)} tool(s): {[tc.name for tc in response.tool_calls]}")

            # Add the assistant message with tool calls to context
            messages.append(ProviderMessage.assistant_with_tool_calls(
                content=response.content,
                tool_calls=response.tool_calls,
            ))

            # Execute each tool call
            for tool_call in response.tool_calls:
                logger.info(f"[tool_calls] executing tool={tool_call.name}")

                # Parse arguments
                try:
                    arguments = json.loads(tool_call.arguments)
                except json.JSONDecodeError as e:
                    arguments = {}
                    logger.warning(f"Failed to parse tool arguments: {e}")

                # Execute the tool
                result = self.tl.tool_executor.execute(tool_call.name, arguments)
                accumulated_tool_results.append(result)

                logger.info(f"[tool_calls] result tool={tool_call.name} success={result.success} consent_required={result.requires_consent}")

                # Add tool response to messages
                messages.append(ProviderMessage.tool_response(
                    tool_call_id=tool_call.id,
                    content=result.to_tool_response(),
                ))

        # If we hit max iterations, return last response
        logger.warning(f"Hit max tool iterations ({MAX_TOOL_ITERATIONS})")
        return response

    def build_context(
        self,
        message: str,
        memory_filter: Optional[dict[str, Any]] = None,
        context_mode: Optional['ContextMode'] = None,
    ) -> 'ComposedContext':
        """Build context from memory for a message."""
        from threadlight.capsules.base import CapsuleType

        # Determine include_shared from active profile's access_shared_memories setting
        include_shared = True
        if self.tl.active_profile:
            include_shared = self.tl.active_profile.access_shared_memories

        # Recall relevant memories
        capsules = self.tl.memory.recall_for_message(
            message,
            limit=self.tl.config.memory.max_capsules_per_request,
            include_shared=include_shared,
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
        active_ritual = self.tl.memory.get_active_ritual()

        # Get profile-specific prompt settings
        profile = self.tl.active_profile
        system_prompt_sections = None
        use_freeform_prompt = False
        freeform_system_prompt = None
        profile_philosophy = None
        approach_to_rituals = None

        knowledge_summary = None
        if profile:
            system_prompt_sections = profile.system_prompt_sections
            use_freeform_prompt = profile.use_freeform_prompt
            freeform_system_prompt = profile.system_prompt  # Profile uses system_prompt for freeform
            profile_philosophy = profile.philosophy
            approach_to_rituals = profile.approach_to_rituals
            knowledge_summary = profile.knowledge_summary

        # Compose context
        return self.tl.composer.compose(
            capsules=capsules,
            style_profile=self.tl.style_profile,
            mode=context_mode,
            active_ritual=active_ritual,
            system_prompt_sections=system_prompt_sections,
            use_freeform_prompt=use_freeform_prompt,
            freeform_system_prompt=freeform_system_prompt,
            profile_philosophy=profile_philosophy,
            approach_to_rituals=approach_to_rituals,
            knowledge_summary=knowledge_summary,
        )

    def build_soft_memory_context(
        self,
        message: str,
        use_integrated_recall: bool = True,
    ) -> str:
        """
        Build soft memory context from past conversations.

        When integrated recall is enabled, this weaves together soft memory
        (past conversations) with hard memory (capsules). If a past conversation
        mentions someone, the relational thread about them is surfaced alongside.

        Args:
            message: Current user message to find context for
            use_integrated_recall: If True, cross-reference with capsules

        Returns:
            Formatted context string for prompt injection
        """
        if not self.tl.soft_memory:
            return ""

        try:
            if use_integrated_recall:
                # Use integrated recall to weave soft and hard memory
                return self._build_woven_context(message)
            else:
                # Fallback to simple soft memory recall
                return self._build_simple_soft_context(message)
        except Exception as e:
            logger.warning(f"Soft memory recall failed: {e}")
            return ""

    def _build_woven_context(self, message: str) -> str:
        """
        Build woven context combining soft memory with related capsules.

        This is the "threads" vision - when a conversation mentions someone,
        surface both the conversation and who that person is to the companion.
        """
        try:
            woven = self.tl.soft_memory.recall_with_context(
                message=message,
                orchestrator=self.tl.memory,
                soft_memory_limit=self.tl.config.memory.conversation.soft_memory_limit,
                capsules_per_entity=2,
            )

            if not woven.soft_memory_results and not woven.related_capsules:
                return ""

            # If we have woven context (both soft memory and capsules),
            # use the integrated format
            if woven.has_woven_context():
                return woven.format_for_prompt(
                    max_soft_memory=self.tl.config.memory.conversation.soft_memory_limit,
                    max_capsules_per_entity=2,
                    header="## Relevant Context",
                )

            # If we only have soft memory, format just that
            if woven.soft_memory_results:
                return self.tl.soft_memory.format_for_prompt(
                    woven.soft_memory_results,
                    header="## Relevant Past Conversations",
                )

            return ""

        except Exception as e:
            logger.debug(f"Woven context failed, falling back to simple: {e}")
            return self._build_simple_soft_context(message)

    def _build_simple_soft_context(self, message: str) -> str:
        """Build simple soft memory context without capsule cross-referencing."""
        results = self.tl.soft_memory.recall_relevant(
            message,
            limit=self.tl.config.memory.conversation.soft_memory_limit,
        )

        if not results:
            return ""

        return self.tl.soft_memory.format_for_prompt(
            results,
            header="## Relevant Past Conversations",
        )

    def auto_save_messages(self, user_message: str, assistant_response: str) -> None:
        """Auto-save user message and assistant response to database."""
        # Ensure we have a conversation attached to the session
        if self.tl.memory.get_current_session():
            if not self.tl.memory.get_current_session().conversation_id:
                self.tl.memory.attach_conversation_to_session()

        # Save the message pair
        self.tl.memory.save_message_pair(user_message, assistant_response)

    def stream(
        self,
        message: str,
        history: Optional[list[dict[str, str]]] = None,
        context_mode: Optional['ContextMode'] = None,
        model_id: Optional[str] = None,
        **kwargs: Any
    ) -> Iterator[str]:
        """
        Stream a response token by token.

        Supports multi-provider routing: if model_id is specified and the model
        has a provider_id configured, the request is routed to that provider.

        Args:
            message: User message
            history: Conversation history
            context_mode: Context composition mode
            model_id: Model to use (for multi-provider routing)
            **kwargs: Additional provider options

        Yields:
            Text chunks as they arrive.
        """
        from threadlight.providers.base import ProviderMessage

        messages = []

        # Build context
        if self.tl.enable_memory:
            context = self.build_context(message, context_mode=context_mode)
            if context.system_message:
                messages.append(ProviderMessage(role="system", content=context.system_message))

        if history:
            for msg in history:
                messages.append(ProviderMessage(role=msg["role"], content=msg["content"]))

        messages.append(ProviderMessage(role="user", content=message))

        # Determine which provider to use
        use_provider_manager = (
            model_id is not None and
            hasattr(self.tl, 'provider_manager') and
            self.tl.config.providers
        )

        if use_provider_manager:
            yield from self.tl.provider_manager.stream(model_id=model_id, messages=messages, **kwargs)
        else:
            yield from self.tl.provider.stream(messages, **kwargs)

    def stream_with_tools(
        self,
        message: str,
        history: Optional[list[dict[str, str]]] = None,
        context_mode: Optional['ContextMode'] = None,
        model_id: Optional[str] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any
    ) -> Iterator[str]:
        """
        Stream a response with tool calling support.

        When tools are provided and the model requests a tool call, this method
        executes the tool(s) and continues the conversation until a text response
        is generated. Tool execution results are yielded as status messages.

        Args:
            message: User message
            history: Conversation history
            context_mode: Context composition mode
            model_id: Model to use (for multi-provider routing)
            tools: Tool definitions (None disables tool calling)
            **kwargs: Additional provider options

        Yields:
            Text chunks as they arrive, including tool execution status.
        """
        from threadlight.providers.base import ProviderMessage

        # If no tools provided, fall back to regular streaming
        if not tools:
            yield from self.stream(message, history, context_mode, model_id, **kwargs)
            return

        messages = []

        # Build context
        if self.tl.enable_memory:
            context = self.build_context(message, context_mode=context_mode)
            if context.system_message:
                messages.append(ProviderMessage(role="system", content=context.system_message))

        if history:
            for msg in history:
                messages.append(ProviderMessage(role=msg["role"], content=msg["content"]))

        messages.append(ProviderMessage(role="user", content=message))

        # Determine which provider to use
        use_provider_manager = (
            model_id is not None and
            hasattr(self.tl, 'provider_manager') and
            self.tl.config.providers
        )

        iteration = 0
        while iteration < MAX_TOOL_ITERATIONS:
            iteration += 1

            # Make the API call with tools (non-streaming to detect tool calls)
            if use_provider_manager:
                response = self.tl.provider_manager.complete(
                    model_id=model_id,
                    messages=messages,
                    tools=tools,
                    **kwargs
                )
            else:
                response = self.tl.provider.complete(messages, tools=tools, **kwargs)

            # If no tool calls, yield the response content and we're done
            if not response.has_tool_calls:
                if response.content:
                    yield response.content
                return

            # Handle tool calls
            logger.info(f"[stream_with_tools] Model requested {len(response.tool_calls)} tool call(s)")

            # Add the assistant message with tool calls to context
            messages.append(ProviderMessage.assistant_with_tool_calls(
                content=response.content,
                tool_calls=response.tool_calls,
            ))

            # Execute each tool call
            for tool_call in response.tool_calls:
                logger.info(f"[stream_with_tools] Executing tool: {tool_call.name}")

                # Yield status message so user sees progress
                yield f"\n[Executing {tool_call.name}...]\n"

                # Parse arguments
                try:
                    arguments = json.loads(tool_call.arguments)
                except json.JSONDecodeError as e:
                    arguments = {}
                    logger.warning(f"Failed to parse tool arguments: {e}")

                # Execute the tool
                result = self.tl.tool_executor.execute(tool_call.name, arguments)

                logger.info(f"[stream_with_tools] Tool result: success={result.success}")

                # Add tool response to messages
                messages.append(ProviderMessage.tool_response(
                    tool_call_id=tool_call.id,
                    content=result.to_tool_response(),
                ))

        # If we hit max iterations, yield warning
        logger.warning(f"Hit max tool iterations ({MAX_TOOL_ITERATIONS})")
        yield "\n[Warning: Maximum tool iterations reached]\n"
