"""
FastAPI server for Threadlight.

Provides a REST API and WebSocket support for the web UI.
Includes OpenAI-compatible endpoints with memory augmentation.
"""

from __future__ import annotations

from typing import Any, Optional
from pathlib import Path
import asyncio
import base64
import json
import logging
import sys
import time
import uuid

try:
    from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, Form
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import StreamingResponse, HTMLResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel, Field, field_validator
except ImportError:
    raise ImportError(
        "Server dependencies not installed. "
        "Run: pip install threadlight[server]"
    )

from threadlight import Threadlight
from threadlight.capsules.base import CapsuleType, RetentionPolicy
from threadlight.profiles import Profile, ModelStrategy
from threadlight.tools.definitions import get_contextual_tools

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configure logging for the threadlight namespace.

    This should be called early, before creating the app, to ensure all
    logger.info() calls throughout the codebase produce output to stdout.
    """
    threadlight_logger = logging.getLogger("threadlight")
    if not threadlight_logger.handlers:
        # Only add handler if none exist (avoid duplicates on reload)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        threadlight_logger.addHandler(handler)
        threadlight_logger.setLevel(logging.INFO)
        # Prevent propagation to root logger (avoid duplicate output)
        threadlight_logger.propagate = False

        # Also configure uvicorn access logs to show requests
        uvicorn_logger = logging.getLogger("uvicorn.access")
        if not uvicorn_logger.handlers:
            uvicorn_logger.addHandler(handler)


# Configure logging immediately when module is imported
configure_logging()


# ============================================================================
# Request/Response Models
# ============================================================================

class Message(BaseModel):
    role: str
    content: str
    name: Optional[str] = None


class ChatRequest(BaseModel):
    model: str
    messages: list[Message]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False


class WebChatRequest(BaseModel):
    message: str
    history: Optional[list[dict[str, str]]] = None
    stream: Optional[bool] = False
    profile_id: Optional[str] = None  # Profile to activate for this chat
    thinking: Optional[bool] = None  # Enable thinking mode (OpenRouter format)


class Choice(BaseModel):
    index: int
    message: Message
    finish_reason: str


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[Choice]
    usage: Usage


class CapsuleRequest(BaseModel):
    type: str
    content: dict[str, Any]
    cue_phrases: Optional[list[str]] = None
    retention: str = "normal"
    shared: Optional[bool] = None  # For per-profile isolation: None=use default, True=shared, False=profile-specific
    profile_scope: Optional[str] = None  # Explicit profile scope override
    model_scope: Optional[str] = None  # Deprecated: use profile_scope instead


class CapsuleUpdateRequest(BaseModel):
    content: Optional[dict[str, Any]] = None
    cue_phrases: Optional[list[str]] = None
    retention: Optional[str] = None
    profile_scope: Optional[str] = None  # Update profile scope (set to "" to make shared)
    model_scope: Optional[str] = None  # Deprecated: use profile_scope instead
    memory_tier: Optional[str] = None  # Update memory tier


class ProposalAction(BaseModel):
    action: str  # confirm or reject


class MemoryTierUpdate(BaseModel):
    """Single memory tier update."""
    capsule_id: str
    tier: str  # strictly_anchored, anchored_decaying, or semantic


class BatchTierUpdateRequest(BaseModel):
    """Batch memory tier update request."""
    updates: list[MemoryTierUpdate]


class BatchDeleteRequest(BaseModel):
    """Batch memory delete request."""
    capsule_ids: list[str]
    force: bool = False  # Whether to force delete protected memories


class BatchArchiveRequest(BaseModel):
    """Batch memory archive request."""
    capsule_ids: list[str]
    archived: bool = True  # True to archive, False to unarchive


class BatchAssignRequest(BaseModel):
    """Batch memory scope assignment request."""
    capsule_ids: list[str]
    profile_id: Optional[str] = None  # None means share (remove scope)


class MemoryTypeConversion(BaseModel):
    """Single memory type conversion."""
    memory_id: str
    new_type: str
    content: dict[str, Any]


class BatchTypeConversionRequest(BaseModel):
    """Batch memory type conversion request."""
    conversions: list[MemoryTypeConversion]


class RitualInvokeRequest(BaseModel):
    ritual_name: str
    context: Optional[str] = None
    initiated_by: str = "user"  # "user" or "companion"


class SessionCreateRequest(BaseModel):
    metadata: Optional[dict[str, Any]] = None


class ConfigUpdateRequest(BaseModel):
    model: Optional[str] = None
    style_profile: Optional[str] = None
    enable_decay: Optional[bool] = None
    identity_name: Optional[str] = None
    system_prompt: Optional[str] = None


class SystemPromptRequest(BaseModel):
    prompt: str


class StyleProfileRequest(BaseModel):
    style_id: str
    tone_base: str = ""
    permissions: Optional[list[str]] = None
    constraints: Optional[list[str]] = None
    vocal_motifs: Optional[list[str]] = None
    forbidden_patterns: Optional[list[str]] = None
    freeform_description: str = ""
    use_freeform: bool = False


class StyleProfileUpdateRequest(BaseModel):
    tone_base: Optional[str] = None
    permissions: Optional[list[str]] = None
    constraints: Optional[list[str]] = None
    vocal_motifs: Optional[list[str]] = None
    forbidden_patterns: Optional[list[str]] = None
    freeform_description: Optional[str] = None
    use_freeform: Optional[bool] = None


class ImportTextRequest(BaseModel):
    content: str
    source_name: str = "web-import"
    tags: Optional[list[str]] = None


class ModelConfigRequest(BaseModel):
    system_prompt: Optional[str] = None
    style_profile: Optional[str] = None
    memory_enabled: Optional[bool] = None
    decay_enabled: Optional[bool] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None


class ModelSwitchRequest(BaseModel):
    model_id: str


class ConversationCreateRequest(BaseModel):
    name: str = "New Chat"
    model: Optional[str] = None  # Model name for display (e.g., "gpt-4o", "Claude Opus")
    participant_profiles: Optional[list[str]] = None  # For group chat - list of profile IDs
    purpose: Optional[str] = None  # Conversation purpose: "tier_review", "type_classification", or None for normal


class ConversationUpdateRequest(BaseModel):
    name: Optional[str] = None
    model: Optional[str] = None  # Model name for display
    archived: Optional[bool] = None
    participant_profiles: Optional[list[str]] = None  # Update group chat participants
    purpose: Optional[str] = None  # Update conversation purpose


class GroupChatRequest(BaseModel):
    message: str
    profile_ids: Optional[list[str]] = None  # Override which profiles respond (uses conversation's if not provided)


class MessageUpdateRequest(BaseModel):
    content: str


class ProfileCreateRequest(BaseModel):
    name: str
    description: str = ""
    system_prompt: str = ""
    style_profile_id: Optional[str] = None
    model_strategy: str = "single"
    primary_model: Optional[str] = None
    model_pool: Optional[list[str]] = None
    model_weights: Optional[dict[str, float]] = None
    routing_rules: Optional[list[dict[str, Any]]] = None
    memory_scope: str = "isolated"
    access_shared_memories: bool = True
    tags: Optional[list[str]] = None
    # New section-based system prompt fields
    system_prompt_sections: Optional[list[dict[str, str]]] = None
    use_freeform_prompt: bool = False
    # Deprecated fields - kept for backward compatibility
    philosophy: str = ""
    approach_to_rituals: str = ""


class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    style_profile_id: Optional[str] = None
    model_strategy: Optional[str] = None
    primary_model: Optional[str] = None
    model_pool: Optional[list[str]] = None
    model_weights: Optional[dict[str, float]] = None
    routing_rules: Optional[list[dict[str, Any]]] = None
    memory_scope: Optional[str] = None
    access_shared_memories: Optional[bool] = None
    is_active: Optional[bool] = None
    tags: Optional[list[str]] = None
    # New section-based system prompt fields
    system_prompt_sections: Optional[list[dict[str, str]]] = None
    use_freeform_prompt: Optional[bool] = None
    knowledge_summary: Optional[Any] = None  # Any format: text, JSON, list, etc.
    # Deprecated fields - kept for backward compatibility
    philosophy: Optional[str] = None
    approach_to_rituals: Optional[str] = None


class ProfileImportRequest(BaseModel):
    data: dict[str, Any]


class MemoryIsolationConfigRequest(BaseModel):
    enabled: bool = False
    default_shared: Optional[bool] = None


class MemoryScopeUpdateRequest(BaseModel):
    profile_id: Optional[str] = None  # None means share (remove scope)
    model_id: Optional[str] = None  # Deprecated: use profile_id instead


class EmbeddingsConfigRequest(BaseModel):
    enabled: bool = True
    provider: str = "local"
    model: str = "intfloat/e5-small-v2"


class GenerateEmbeddingsRequest(BaseModel):
    include_memories: bool = True
    include_conversations: bool = True


class SemanticSearchRequest(BaseModel):
    query: str
    limit: int = 10
    threshold: float = 0.5
    include_memories: bool = True
    include_conversations: bool = True


class FieldDefinitionRequest(BaseModel):
    name: str
    field_type: Optional[str] = None  # "string", "text", "number", "date", "list" (preferred)
    type: Optional[str] = None  # Deprecated: use field_type (kept for backward compatibility)
    required: bool = True
    default: Optional[Any] = None
    help_text: str = ""
    template: str = ""  # How field appears in AI context, e.g., "There is {value} quality to how I speak of them"
    label: str = ""  # Display label (optional, defaults to name)


class MemoryTypeRequest(BaseModel):
    type_id: str
    display_name: str
    description: str = ""
    fields: list[FieldDefinitionRequest]
    display_template: str = ""
    icon: str = "file-text"


class MemoryTypeUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    fields: Optional[list[FieldDefinitionRequest]] = None
    display_template: Optional[str] = None
    icon: Optional[str] = None


class EndpointRequest(BaseModel):
    """Request model for a single API endpoint."""
    url: str
    name: str = ""
    priority: int = 0
    purpose: str = ""


class ProviderConfigRequest(BaseModel):
    """Request model for API provider configuration."""
    provider_type: str  # "openai", "anthropic", "nous", "local", "custom"
    api_base: str = ""  # Legacy single endpoint (for backward compatibility)
    api_key: Optional[str] = None  # Only sent if changed (not placeholder)
    model: Optional[str] = None
    headers: Optional[dict[str, str]] = None  # For custom providers
    provider_name: Optional[str] = None  # Display name for custom providers
    anthropic_version: Optional[str] = None  # For Anthropic: API version header
    # Multiple endpoints support (new)
    endpoints: Optional[list[EndpointRequest]] = None  # List of endpoints


class ProviderCreateRequest(BaseModel):
    """Request model for creating a new provider definition."""
    id: str  # Unique identifier (e.g., "anthropic", "local-ollama")
    name: str  # Display name (e.g., "Anthropic", "Local Ollama")
    type: str = "openai"  # Provider type: "openai", "anthropic", "local", "custom"
    api_key: Optional[str] = None  # Direct API key
    api_key_env_var: Optional[str] = None  # Environment variable name for API key
    endpoints: Optional[list[EndpointRequest]] = None  # API endpoints
    default_model: str = ""  # Default model for this provider
    timeout: float = 60.0
    max_retries: int = 3
    extra_headers: Optional[dict[str, str]] = None
    anthropic_version: str = "2023-06-01"


class ProviderUpdateRequest(BaseModel):
    """Request model for updating a provider definition."""
    name: Optional[str] = None
    type: Optional[str] = None
    api_key: Optional[str] = None
    api_key_env_var: Optional[str] = None
    endpoints: Optional[list[EndpointRequest]] = None
    default_model: Optional[str] = None
    timeout: Optional[float] = None
    max_retries: Optional[int] = None
    extra_headers: Optional[dict[str, str]] = None
    anthropic_version: Optional[str] = None


class ModelProviderRequest(BaseModel):
    """Request model for setting a model's provider."""
    provider_id: Optional[str] = None  # Provider ID or None to use default


class MemoryLinkRequest(BaseModel):
    """Request model for creating a memory link."""
    target_capsule_id: str
    link_type: str = "related"
    strength: float = Field(default=1.0, ge=0.0, le=1.0)
    bidirectional: bool = False
    notes: str = ""

    @field_validator("link_type")
    @classmethod
    def link_type_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("link_type must be a non-empty string")
        v = v.strip()
        if len(v) > 50:
            raise ValueError("link_type must be 50 characters or fewer")
        return v


class MemoryLinkUpdateRequest(BaseModel):
    """Request model for updating a memory link."""
    link_type: Optional[str] = None
    strength: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    bidirectional: Optional[bool] = None
    notes: Optional[str] = None

    @field_validator("link_type")
    @classmethod
    def link_type_non_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and (not v or not v.strip()):
            raise ValueError("link_type must be a non-empty string")
        if v is not None:
            v = v.strip()
            if len(v) > 50:
                raise ValueError("link_type must be 50 characters or fewer")
        return v


# ============================================================================
# Global State
# ============================================================================

_tl: Optional[Threadlight] = None
_active_connections: list[WebSocket] = []


def get_threadlight() -> Threadlight:
    """Get or create the global Threadlight instance."""
    global _tl
    if _tl is None:
        _tl = Threadlight()
        # Restore the last active profile across server restarts
        from threadlight.managers.profiles import ProfileInterface
        last_profile_id = ProfileInterface.load_persisted_profile_id()
        if last_profile_id:
            try:
                _tl.switch_profile(last_profile_id)
                logger.info(f"Restored active profile: {last_profile_id}")
            except Exception as e:
                logger.warning(f"Failed to restore last active profile {last_profile_id}: {e}")
    return _tl


def _ensure_profile_active(tl: Threadlight, profile_id: Optional[str]) -> None:
    """Switch to the given profile if it is not already active.

    Silently ignores missing profiles so callers don't need their own
    try/except blocks.
    """
    if not profile_id:
        return
    try:
        current_profile_id = tl.active_profile.id if tl.active_profile else None
        if profile_id != current_profile_id:
            tl.switch_profile(profile_id)
    except Exception as e:
        logger.warning(f"Failed to switch profile: {e}")


async def broadcast_message(message: dict[str, Any]) -> None:
    """Broadcast a message to all connected WebSocket clients."""
    disconnected = []
    for websocket in _active_connections:
        try:
            await websocket.send_json(message)
        except Exception:
            disconnected.append(websocket)

    for ws in disconnected:
        _active_connections.remove(ws)


# ============================================================================
# Application Factory
# ============================================================================

def create_app(static_dir: Optional[Path] = None) -> FastAPI:
    """Create the FastAPI application."""

    # Ensure logging is configured (idempotent - safe to call multiple times)
    configure_logging()

    app = FastAPI(
        title="Threadlight API",
        description="Presence-centered memory framework for AI models",
        version="0.1.0",
    )

    # CORS middleware for development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Determine static files directory
    if static_dir is None:
        static_dir = Path(__file__).parent / "static"

    # Mount static files if directory exists
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.on_event("startup")
    async def startup():
        tl = get_threadlight()
        # Enable auto-save so provider and model config changes persist
        tl.enable_config_auto_save()
        logger.info("Threadlight server started")

    @app.on_event("shutdown")
    async def shutdown():
        global _tl
        if _tl:
            _tl.close()
            _tl = None
        logger.info("Threadlight server shutdown")

    # ========================================================================
    # Root & Health
    # ========================================================================

    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Serve the main web UI."""
        index_path = static_dir / "index.html"
        if index_path.exists():
            return index_path.read_text()
        return """
        <html>
        <head><title>Threadlight</title></head>
        <body>
            <h1>Threadlight API Server</h1>
            <p>Static files not found. Place index.html in the static directory.</p>
            <p>API documentation available at <a href="/docs">/docs</a></p>
        </body>
        </html>
        """

    @app.get("/health")
    async def health():
        """Health check endpoint."""
        tl = get_threadlight()
        return tl.health_check()

    # ========================================================================
    # OpenAI-Compatible Endpoints
    # ========================================================================

    @app.post("/v1/chat/completions", response_model=ChatResponse)
    async def chat_completions(request: ChatRequest):
        """OpenAI-compatible chat completions endpoint."""
        tl = get_threadlight()

        # Extract history and current message
        history = []
        current_message = ""

        for msg in request.messages:
            if msg.role == "user":
                if current_message:
                    history.append({"role": "user", "content": current_message})
                current_message = msg.content
            elif msg.role == "assistant":
                if current_message:
                    history.append({"role": "user", "content": current_message})
                    current_message = ""
                history.append({"role": "assistant", "content": msg.content})

        if not current_message and request.messages:
            for msg in reversed(request.messages):
                if msg.role == "user":
                    current_message = msg.content
                    break

        # Build kwargs
        kwargs = {}
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens

        # Get response
        response = tl.chat_with_context(
            current_message,
            history=history[:-1] if history else None,
            **kwargs
        )

        return ChatResponse(
            id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
            created=int(time.time()),
            model=request.model,
            choices=[
                Choice(
                    index=0,
                    message=Message(role="assistant", content=response.content),
                    finish_reason=response.finish_reason,
                )
            ],
            usage=Usage(
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                total_tokens=response.total_tokens,
            ),
        )

    # ========================================================================
    # Web Chat Endpoints
    # ========================================================================

    @app.post("/api/chat")
    async def web_chat(request: WebChatRequest):
        """Web UI chat endpoint."""
        tl = get_threadlight()

        # Activate the profile if specified so its model/provider is used
        if hasattr(request, 'profile_id') and request.profile_id:
            _ensure_profile_active(tl, request.profile_id)

        try:
            # Get memories that will be recalled for context
            recalled_memories = tl.memory.recall_for_message(
                request.message,
                limit=5
            )

            # Chat with context
            response = tl.chat_with_context(
                request.message,
                history=request.history,
                thinking=request.thinking,
            )

            # Format recalled memories for the response
            memories_used = [
                {
                    "id": c.id,
                    "type": c.type.value,
                    "preview": _get_capsule_preview(c),
                    "presence_score": c.presence_score,
                }
                for c in recalled_memories
            ]

            result = {
                "content": response.content,
                "memories_recalled": memories_used,
                "finish_reason": response.finish_reason,
                "usage": {
                    "prompt_tokens": response.prompt_tokens,
                    "completion_tokens": response.completion_tokens,
                    "total_tokens": response.total_tokens,
                }
            }
            if response.reasoning:
                result["reasoning"] = response.reasoning
            return result
        except Exception as e:
            logger.error(f"Chat error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/chat/stream")
    async def web_chat_stream(request: WebChatRequest):
        """Streaming chat endpoint for web UI."""
        tl = get_threadlight()

        async def generate():
            try:
                for chunk in tl.stream(
                    request.message,
                    history=request.history,
                ):
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    # ========================================================================
    # Multimodal Chat Endpoints (image + text)
    # ========================================================================

    # Allowed image MIME types and max file size (10 MB)
    _ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    _MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB

    async def _process_chat_images(
        images: list[UploadFile],
    ) -> list[str]:
        """Read uploaded image files and convert to base64 data URLs.

        Args:
            images: List of uploaded image files.

        Returns:
            List of data URL strings (e.g. "data:image/jpeg;base64,...").

        Raises:
            HTTPException: If any image is invalid or too large.
        """
        data_urls: list[str] = []
        for img in images:
            # Validate content type
            content_type = img.content_type or ""
            if content_type not in _ALLOWED_IMAGE_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported image type: {content_type}. "
                           f"Allowed: {', '.join(sorted(_ALLOWED_IMAGE_TYPES))}",
                )

            # Read and validate size
            img_bytes = await img.read()
            if len(img_bytes) > _MAX_IMAGE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"Image '{img.filename}' exceeds maximum size of "
                           f"{_MAX_IMAGE_SIZE // (1024 * 1024)} MB",
                )

            # Convert to base64 data URL
            b64 = base64.b64encode(img_bytes).decode("utf-8")
            data_urls.append(f"data:{content_type};base64,{b64}")

        return data_urls

    @app.post("/api/chat/image")
    async def web_chat_with_image(
        message: str = Form(...),
        history: str = Form("[]"),
        profile_id: str = Form(None),
        thinking: str = Form(None),
        images: list[UploadFile] = File(None),
    ):
        """Web UI chat endpoint with optional image attachments.

        Accepts multipart/form-data with text message and optional images.
        Falls back gracefully to text-only if no images are provided.
        """
        tl = get_threadlight()

        # Activate the profile if specified
        if profile_id:
            _ensure_profile_active(tl, profile_id)

        # Parse history from JSON string
        try:
            parsed_history = json.loads(history) if history else []
        except json.JSONDecodeError:
            parsed_history = []

        # Process images if provided
        image_data_urls: list[str] = []
        if images:
            image_data_urls = await _process_chat_images(images)

        try:
            # Get memories that will be recalled for context
            recalled_memories = tl.memory.recall_for_message(
                message,
                limit=5,
            )

            # Chat with context (text used for memory recall, images for provider)
            thinking_enabled = thinking and thinking.lower() in ("true", "1", "yes")
            response = tl.chat_with_context(
                message,
                history=parsed_history,
                images=image_data_urls if image_data_urls else None,
                thinking=thinking_enabled or None,
            )

            # Format recalled memories for the response
            memories_used = [
                {
                    "id": c.id,
                    "type": c.type.value,
                    "preview": _get_capsule_preview(c),
                    "presence_score": c.presence_score,
                }
                for c in recalled_memories
            ]

            return {
                "content": response.content,
                "memories_recalled": memories_used,
                "finish_reason": response.finish_reason,
                "usage": {
                    "prompt_tokens": response.prompt_tokens,
                    "completion_tokens": response.completion_tokens,
                    "total_tokens": response.total_tokens,
                },
            }
        except Exception as e:
            logger.error(f"Multimodal chat error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/chat/image/stream")
    async def web_chat_stream_with_image(
        message: str = Form(...),
        history: str = Form("[]"),
        profile_id: str = Form(None),
        images: list[UploadFile] = File(None),
    ):
        """Streaming chat endpoint with optional image attachments.

        Accepts multipart/form-data with text message and optional images.
        """
        tl = get_threadlight()

        # Activate the profile if specified
        if profile_id:
            _ensure_profile_active(tl, profile_id)

        # Parse history from JSON string
        try:
            parsed_history = json.loads(history) if history else []
        except json.JSONDecodeError:
            parsed_history = []

        # Process images (must be done before the generator since generators are lazy)
        image_data_urls: list[str] = []
        if images:
            image_data_urls = await _process_chat_images(images)

        async def generate():
            try:
                for chunk in tl.stream(
                    message,
                    history=parsed_history,
                    images=image_data_urls if image_data_urls else None,
                ):
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    # ========================================================================
    # WebSocket Endpoint
    # ========================================================================

    @app.websocket("/ws/chat")
    async def websocket_chat(websocket: WebSocket):
        """WebSocket endpoint for real-time chat."""
        await websocket.accept()
        _active_connections.append(websocket)

        tl = get_threadlight()
        history = []

        try:
            while True:
                data = await websocket.receive_json()
                logger.info(f"[WebSocket] Received data: type={data.get('type')}")

                if data.get("type") == "chat":
                    message = data.get("message", "")
                    profile_id = data.get("profile_id")
                    conversation_id = data.get("conversation_id")
                    # Optional image attachments as base64 data URLs
                    ws_images = data.get("images") or []
                    # Optional thinking mode toggle
                    thinking = data.get("thinking", False)

                    logger.info(f"[WebSocket] Chat message received. profile_id={profile_id}, conv_id={conversation_id}, msg_len={len(message)}, images={len(ws_images)}, thinking={thinking}")

                    # Activate profile if specified
                    _ensure_profile_active(tl, profile_id)

                    # Determine model_id from active profile
                    model_id = None
                    if tl.active_profile and tl.active_profile.primary_model:
                        model_id = tl.active_profile.primary_model

                    logger.info(f"[WebSocket] Using model_id={model_id}, active_profile={tl.active_profile.name if tl.active_profile else None}")

                    # Get conversation purpose for contextual tool filtering
                    conversation_purpose = None
                    if conversation_id:
                        try:
                            conversation = tl.storage.get_conversation(conversation_id)
                            if conversation and conversation.metadata:
                                conversation_purpose = conversation.metadata.get("purpose")
                            logger.info(f"[WebSocket] Conversation purpose: {conversation_purpose}")
                        except Exception as e:
                            logger.warning(f"[WebSocket] Failed to get conversation purpose: {e}")

                    # Load conversation history from database if we have a conversation_id
                    # This ensures context is preserved across page refreshes
                    if conversation_id and not history:
                        try:
                            conv_messages = tl.storage.get_messages(conversation_id)
                            for msg in conv_messages:
                                history.append({"role": msg.role, "content": msg.content})
                            logger.info(f"[WebSocket] Loaded {len(history)} messages from conversation {conversation_id}")
                        except Exception as e:
                            logger.warning(f"[WebSocket] Failed to load conversation history: {e}")

                    # Send typing indicator
                    await websocket.send_json({"type": "typing", "status": True})

                    # Get recalled memories
                    recalled = tl.memory.recall_for_message(message, limit=5)

                    # Check for auto_tool - automatically call a tool and include results in context
                    auto_tool = data.get("auto_tool")  # e.g., {"name": "review_memory_tiers", "action": "list"}
                    tool_context = ""
                    if auto_tool:
                        tool_name = auto_tool.get("name")
                        tool_args = {k: v for k, v in auto_tool.items() if k != "name"}
                        logger.info(f"[WebSocket] Auto-calling tool: {tool_name} with args: {tool_args}")

                        # Execute the tool directly
                        result = tl.tool_executor.execute(tool_name, tool_args)
                        if result.success:
                            # result.result is a dict with 'memories' and 'instructions'
                            instructions = result.result.get('instructions', '') if isinstance(result.result, dict) else ''
                            tool_context = f"\n\n---\n## Tool Results\n{instructions}\n\n{result.to_tool_response()}"
                            logger.info(f"[WebSocket] Auto-tool succeeded, adding context")
                        else:
                            tool_context = f"\n\n---\n## Tool Error\n{result.error}"
                            logger.warning(f"[WebSocket] Auto-tool failed: {result.error}")

                        # Append tool context to the message
                        message = message + tool_context

                    # Get contextual tools based on conversation purpose
                    # This prevents models from spontaneously offering batch operations in normal conversations
                    contextual_tools = get_contextual_tools(conversation_purpose)
                    logger.info(f"[WebSocket] Using {len(contextual_tools)} contextual tools for purpose={conversation_purpose}")

                    # Get complete response (no streaming - simpler and avoids UI reactivity issues)
                    try:
                        response = tl.chat_with_context(message, history=history, model_id=model_id, tools=contextual_tools, images=ws_images if ws_images else None, thinking=thinking)
                        full_response = response.content

                        # Update history
                        history.append({"role": "user", "content": message})
                        history.append({"role": "assistant", "content": full_response})

                        # Keep history manageable
                        if len(history) > 20:
                            history = history[-20:]

                        # Save messages to database
                        if conversation_id:
                            # Save to the specified conversation
                            tl.memory.save_message_pair(
                                user_message=message,
                                assistant_response=full_response,
                                conversation_id=conversation_id
                            )

                        # Extract tool results if any
                        tool_results = None
                        if response.raw and "tool_results" in response.raw:
                            tool_results = response.raw["tool_results"]

                        # Extract token usage
                        usage = None
                        if hasattr(response, 'prompt_tokens') and hasattr(response, 'completion_tokens'):
                            usage = {
                                "prompt_tokens": response.prompt_tokens,
                                "completion_tokens": response.completion_tokens,
                                "total_tokens": response.total_tokens,
                            }

                        # Send completion with metadata
                        complete_payload = {
                            "type": "complete",
                            "content": full_response,
                            "tool_results": tool_results,
                            "usage": usage,
                        }
                        if response.reasoning:
                            complete_payload["reasoning"] = response.reasoning
                        await websocket.send_json(complete_payload)
                    except Exception as e:
                        error_msg = str(e)
                        is_rate_limit = "rate limit" in error_msg.lower() or "429" in error_msg
                        await websocket.send_json({
                            "type": "error",
                            "message": error_msg,
                            "is_rate_limit": is_rate_limit,
                        })
                    finally:
                        await websocket.send_json({"type": "typing", "status": False})

                elif data.get("type") == "ritual":
                    ritual_name = data.get("name", "")
                    initiated_by = data.get("initiated_by", "user")
                    ritual_context = data.get("context")
                    profile_id = data.get("profile_id")
                    conversation_id = data.get("conversation_id")

                    # Activate profile if specified
                    _ensure_profile_active(tl, profile_id)

                    try:
                        response = tl.invoke_ritual(
                            ritual_name,
                            initiated_by=initiated_by,
                            context=ritual_context,
                        )

                        # Update history
                        history.append({"role": "user", "content": ritual_name})
                        history.append({"role": "assistant", "content": response})

                        # Keep history manageable
                        if len(history) > 20:
                            history = history[-20:]

                        # Save messages to database
                        if conversation_id:
                            tl.memory.save_message_pair(
                                user_message=ritual_name,
                                assistant_response=response,
                                conversation_id=conversation_id
                            )

                        await websocket.send_json({
                            "type": "ritual_response",
                            "ritual": ritual_name,
                            "content": response,
                            "initiated_by": initiated_by,
                        })
                    except Exception as e:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Ritual failed: {e}",
                        })

                elif data.get("type") == "clear_history":
                    history = []
                    await websocket.send_json({
                        "type": "history_cleared",
                    })

                elif data.get("type") == "continue":
                    # Continue the last assistant response
                    profile_id = data.get("profile_id")
                    conversation_id = data.get("conversation_id")

                    logger.info(f"[WebSocket] Continue request received. profile_id={profile_id}, conv_id={conversation_id}")

                    # Activate profile if specified
                    _ensure_profile_active(tl, profile_id)

                    # Determine model_id from active profile
                    model_id = None
                    if tl.active_profile and tl.active_profile.primary_model:
                        model_id = tl.active_profile.primary_model

                    # Load conversation history if needed
                    if conversation_id and not history:
                        try:
                            conv_messages = tl.storage.get_messages(conversation_id)
                            for msg in conv_messages:
                                history.append({"role": msg.role, "content": msg.content})
                            logger.info(f"[WebSocket] Loaded {len(history)} messages from conversation {conversation_id}")
                        except Exception as e:
                            logger.warning(f"[WebSocket] Failed to load conversation history: {e}")

                    # Build a continue prompt
                    continue_prompt = "Please continue your previous response where you left off."

                    # Send typing indicator
                    await websocket.send_json({"type": "typing", "status": True})

                    try:
                        full_response = tl.chat(continue_prompt, history=history, model_id=model_id)

                        # Update history
                        history.append({"role": "user", "content": continue_prompt})
                        history.append({"role": "assistant", "content": full_response})

                        # Keep history manageable
                        if len(history) > 20:
                            history = history[-20:]

                        # Save to database
                        if conversation_id:
                            tl.memory.save_message_pair(
                                user_message=continue_prompt,
                                assistant_response=full_response,
                                conversation_id=conversation_id
                            )

                        # Send completion
                        await websocket.send_json({
                            "type": "continue_response",
                            "content": full_response,
                        })
                    except Exception as e:
                        await websocket.send_json({
                            "type": "error",
                            "message": str(e),
                        })
                    finally:
                        await websocket.send_json({"type": "typing", "status": False})

                elif data.get("type") == "regenerate_variant":
                    # Regenerate a response as a new variant (keeps old response)
                    profile_id = data.get("profile_id")
                    conversation_id = data.get("conversation_id")
                    user_message = data.get("user_message")
                    variant_group_id = data.get("variant_group_id")
                    next_variant_index = data.get("next_variant_index", 1)

                    logger.info(f"[WebSocket] Regenerate variant request. variant_group={variant_group_id}, conv_id={conversation_id}")

                    # Activate profile if specified
                    _ensure_profile_active(tl, profile_id)

                    # Determine model_id from active profile
                    model_id = None
                    if tl.active_profile and tl.active_profile.primary_model:
                        model_id = tl.active_profile.primary_model

                    # Get contextual tools
                    conversation_purpose = None
                    if conversation_id:
                        try:
                            conversation = tl.storage.get_conversation(conversation_id)
                            if conversation and conversation.metadata:
                                conversation_purpose = conversation.metadata.get("purpose")
                        except Exception:
                            pass

                    contextual_tools = get_contextual_tools(conversation_purpose)

                    # Load full conversation history for context
                    regen_history = []
                    if conversation_id:
                        try:
                            conv_messages = tl.storage.get_messages(conversation_id)
                            for msg in conv_messages:
                                regen_history.append({"role": msg.role, "content": msg.content})
                        except Exception:
                            pass

                    await websocket.send_json({"type": "typing", "status": True})

                    try:
                        response = tl.chat_with_context(user_message, history=regen_history, model_id=model_id, tools=contextual_tools)
                        full_response = response.content

                        # Save the new variant to database
                        from threadlight.storage.base import Message as StorageMessage
                        from datetime import datetime as dt_now
                        variant_msg = StorageMessage(
                            id=str(uuid.uuid4()),
                            conversation_id=conversation_id,
                            role="assistant",
                            content=full_response,
                            timestamp=dt_now.utcnow(),
                            source="local",
                            metadata={},
                            variant_group_id=variant_group_id,
                            variant_index=next_variant_index,
                        )
                        if tl.active_profile:
                            variant_msg.profile_id = tl.active_profile.id
                            variant_msg.model_used = tl.active_profile.primary_model

                        tl.storage.save_message(variant_msg)

                        # Extract token usage
                        usage = None
                        if hasattr(response, 'prompt_tokens') and hasattr(response, 'completion_tokens'):
                            usage = {
                                "prompt_tokens": response.prompt_tokens,
                                "completion_tokens": response.completion_tokens,
                                "total_tokens": response.total_tokens,
                            }

                        await websocket.send_json({
                            "type": "regenerate_complete",
                            "content": full_response,
                            "message_id": variant_msg.id,
                            "variant_group_id": variant_group_id,
                            "variant_index": next_variant_index,
                            "usage": usage,
                        })
                    except Exception as e:
                        error_msg = str(e)
                        is_rate_limit = "rate limit" in error_msg.lower() or "429" in error_msg
                        await websocket.send_json({
                            "type": "error",
                            "message": error_msg,
                            "is_rate_limit": is_rate_limit,
                        })
                    finally:
                        await websocket.send_json({"type": "typing", "status": False})

                elif data.get("type") == "group_chat":
                    # Group chat message - stream responses from multiple profiles
                    message = data.get("message", "")
                    conversation_id = data.get("conversation_id")
                    profile_ids = data.get("profile_ids")  # Optional override

                    if not conversation_id:
                        await websocket.send_json({
                            "type": "error",
                            "message": "conversation_id required for group chat",
                        })
                        continue

                    try:
                        # Stream group chat responses
                        for event in tl.stream_group_chat(
                            message=message,
                            conversation_id=conversation_id,
                            profile_ids=profile_ids,
                        ):
                            # Forward all events to websocket
                            await websocket.send_json(event)

                    except Exception as e:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Group chat failed: {e}",
                        })

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
        except Exception as e:
            logger.error(f"WebSocket error: {e}", exc_info=True)
            try:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Server error: {str(e)}"
                })
            except:
                pass
        finally:
            if websocket in _active_connections:
                _active_connections.remove(websocket)

    # ========================================================================
    # Memory Endpoints
    # ========================================================================

    @app.get("/api/memories")
    async def list_memories(
        type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        search: Optional[str] = None,
        profile_scope: Optional[str] = None,
        include_shared: bool = True,
        include_archived: bool = False,
    ):
        """List memory capsules with optional filtering.

        Args:
            type: Filter by capsule type
            limit: Max memories to return
            offset: Offset for pagination
            search: Text search in content
            profile_scope: Filter by profile scope. Accepts special values:
                - ``__all__`` -- return all memories regardless of scope
                - ``__none__`` -- return only shared (NULL scope) memories
                - ``<profile_id>`` -- return memories scoped to that specific profile
                If omitted, uses the active profile when per_profile_isolation is enabled.
            include_shared: Include memories with no profile_scope (shared)
            include_archived: Include archived memories (default: hidden)
        """
        tl = get_threadlight()

        from threadlight.storage.base import CapsuleFilter

        capsule_type = CapsuleType(type) if type else None

        # Use provided profile_scope, or active profile if isolation is enabled
        # Special values: '__all__' = no scope filter, '__none__' = shared only (NULL scope)
        skip_scope_filter = False
        shared_only = False

        if profile_scope == '__all__':
            skip_scope_filter = True
            profile_scope = None
        elif profile_scope == '__none__':
            shared_only = True
            profile_scope = None

        effective_scope = profile_scope
        if effective_scope is None and not skip_scope_filter and not shared_only:
            if tl.config.memory.per_profile_isolation and tl.active_profile:
                effective_scope = tl.active_profile.id

        filter = CapsuleFilter(
            type=capsule_type,
            limit=limit,
            offset=offset,
            profile_scope=effective_scope if (tl.config.memory.per_profile_isolation and not skip_scope_filter) else None,
            include_shared=include_shared,
            shared_only=shared_only,
            include_archived=include_archived,
        )

        capsules = tl.storage.list_capsules(filter)

        # Apply text search if provided
        if search:
            search_lower = search.lower()
            capsules = [
                c for c in capsules
                if search_lower in str(c.content).lower()
                or any(search_lower in phrase.lower() for phrase in c.cue_phrases)
            ]

        return {
            "memories": [_capsule_to_dict(c) for c in capsules],
            "count": len(capsules),
            "total": tl.storage.count_capsules(filter),
            "profile_scope": effective_scope,
            "per_profile_isolation": tl.config.memory.per_profile_isolation,
        }

    @app.get("/api/memories/{capsule_id}")
    async def get_memory(capsule_id: str):
        """Get a specific memory capsule."""
        tl = get_threadlight()
        capsule = tl.memory.get(capsule_id)

        if not capsule:
            raise HTTPException(status_code=404, detail="Memory not found")

        return _capsule_to_dict(capsule)

    @app.post("/api/memories")
    async def create_memory(request: CapsuleRequest):
        """Create a new memory capsule.

        When per_profile_isolation is enabled:
        - shared=True creates a memory visible to all profiles
        - shared=False creates a memory scoped to current profile
        - profile_scope explicitly sets the profile scope
        """
        tl = get_threadlight()

        try:
            # Use profile_scope if provided, fall back to model_scope for backward compat
            effective_scope = request.profile_scope or request.model_scope
            capsule = tl.memory.create(
                type=request.type,
                content=request.content,
                cue_phrases=request.cue_phrases,
                retention=request.retention,
                consent_confirmed=True,
                shared=request.shared,
                profile_scope=effective_scope,
            )

            return _capsule_to_dict(capsule)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.put("/api/memories/{capsule_id}")
    async def update_memory(capsule_id: str, request: CapsuleUpdateRequest):
        """Update a memory capsule."""
        tl = get_threadlight()

        capsule = tl.storage.get_capsule(capsule_id)
        if not capsule:
            raise HTTPException(status_code=404, detail="Memory not found")

        if request.content:
            capsule.update_content(request.content)
        if request.cue_phrases is not None:
            capsule.cue_phrases = request.cue_phrases
        if request.retention:
            capsule.retention = RetentionPolicy(request.retention)
        # Use profile_scope if provided, fall back to model_scope for backward compat
        scope_update = request.profile_scope if request.profile_scope is not None else request.model_scope
        if scope_update is not None:
            # Empty string means make it shared (None)
            capsule.profile_scope = scope_update if scope_update else None
        if request.memory_tier:
            from threadlight.capsules.base import MemoryTier
            capsule.memory_tier = MemoryTier(request.memory_tier)

        tl.storage.update_capsule(capsule)

        return _capsule_to_dict(capsule)

    @app.delete("/api/memories/{capsule_id}")
    async def delete_memory(capsule_id: str, force: bool = False):
        """Delete a memory capsule."""
        tl = get_threadlight()

        success = tl.memory.delete(capsule_id, force=force)

        if not success:
            raise HTTPException(
                status_code=404,
                detail="Memory not found or protected (use force=true for sacred memories)"
            )

        return {"status": "deleted", "id": capsule_id}

    @app.post("/api/memories/batch-tier-update")
    async def batch_tier_update(request: BatchTierUpdateRequest):
        """
        Batch update memory tiers.

        Updates multiple memory capsules with new tier assignments in a single transaction.
        Returns summary of successful updates and any errors encountered.
        """
        tl = get_threadlight()
        from threadlight.capsules.base import MemoryTier

        results = {
            "updated": [],
            "errors": [],
            "summary": {
                "total": len(request.updates),
                "successful": 0,
                "failed": 0
            }
        }

        for update in request.updates:
            try:
                # Validate tier value
                tier = MemoryTier(update.tier)

                # Get capsule
                capsule = tl.storage.get_capsule(update.capsule_id)
                if not capsule:
                    results["errors"].append({
                        "capsule_id": update.capsule_id,
                        "error": "Memory not found"
                    })
                    results["summary"]["failed"] += 1
                    continue

                # Update tier
                old_tier = capsule.memory_tier.value
                capsule.memory_tier = tier
                tl.storage.update_capsule(capsule)

                results["updated"].append({
                    "capsule_id": update.capsule_id,
                    "old_tier": old_tier,
                    "new_tier": tier.value
                })
                results["summary"]["successful"] += 1

            except ValueError as e:
                results["errors"].append({
                    "capsule_id": update.capsule_id,
                    "error": f"Invalid tier value: {update.tier}"
                })
                results["summary"]["failed"] += 1
            except Exception as e:
                results["errors"].append({
                    "capsule_id": update.capsule_id,
                    "error": str(e)
                })
                results["summary"]["failed"] += 1

        return results

    @app.post("/api/memories/batch-delete")
    async def batch_delete_memories(request: BatchDeleteRequest):
        """
        Batch delete memory capsules.

        Deletes multiple memory capsules in a single operation.
        Returns summary of successful deletions and any errors encountered.
        """
        tl = get_threadlight()

        results = {
            "deleted": [],
            "errors": [],
            "summary": {
                "total": len(request.capsule_ids),
                "successful": 0,
                "failed": 0
            }
        }

        for capsule_id in request.capsule_ids:
            try:
                success = tl.memory.delete(capsule_id, force=request.force)

                if success:
                    results["deleted"].append({"capsule_id": capsule_id})
                    results["summary"]["successful"] += 1
                else:
                    results["errors"].append({
                        "capsule_id": capsule_id,
                        "error": "Memory not found or protected (use force=true)"
                    })
                    results["summary"]["failed"] += 1

            except Exception as e:
                results["errors"].append({
                    "capsule_id": capsule_id,
                    "error": str(e)
                })
                results["summary"]["failed"] += 1

        return results

    @app.post("/api/memories/batch-archive")
    async def batch_archive_memories(request: BatchArchiveRequest):
        """
        Batch archive or unarchive memory capsules.

        Archives or unarchives multiple memory capsules in a single operation.
        Archived memories are hidden from default views but not deleted.
        Returns summary of successful updates and any errors encountered.
        """
        tl = get_threadlight()

        results = {
            "updated": [],
            "errors": [],
            "summary": {
                "total": len(request.capsule_ids),
                "successful": 0,
                "failed": 0
            }
        }

        for capsule_id in request.capsule_ids:
            try:
                capsule = tl.storage.get_capsule(capsule_id)
                if not capsule:
                    results["errors"].append({
                        "capsule_id": capsule_id,
                        "error": "Memory not found"
                    })
                    results["summary"]["failed"] += 1
                    continue

                capsule.archived = request.archived
                tl.storage.update_capsule(capsule)

                results["updated"].append({
                    "capsule_id": capsule_id,
                    "archived": request.archived
                })
                results["summary"]["successful"] += 1

            except Exception as e:
                results["errors"].append({
                    "capsule_id": capsule_id,
                    "error": str(e)
                })
                results["summary"]["failed"] += 1

        return results

    @app.post("/api/memories/batch-assign")
    async def batch_assign_memories(request: BatchAssignRequest):
        """
        Batch assign memory capsules to a profile scope.

        Assigns multiple memories to a specific profile, or shares them
        (removes profile scope) if profile_id is null.
        Returns summary of successful assignments and any errors encountered.
        """
        tl = get_threadlight()

        # Validate target profile exists before processing any assignments
        if request.profile_id is not None:
            profile = tl.get_profile(request.profile_id)
            if not profile:
                raise HTTPException(
                    status_code=404,
                    detail=f"Target profile not found: {request.profile_id}"
                )

        results = {
            "updated": [],
            "errors": [],
            "summary": {
                "total": len(request.capsule_ids),
                "successful": 0,
                "failed": 0
            }
        }

        for capsule_id in request.capsule_ids:
            try:
                if request.profile_id is None:
                    success = tl.share_memory(capsule_id)
                else:
                    success = tl.assign_memory_to_profile(capsule_id, request.profile_id)

                if success:
                    results["updated"].append({
                        "capsule_id": capsule_id,
                        "profile_scope": request.profile_id,
                    })
                    results["summary"]["successful"] += 1
                else:
                    results["errors"].append({
                        "capsule_id": capsule_id,
                        "error": "Memory not found"
                    })
                    results["summary"]["failed"] += 1

            except Exception as e:
                results["errors"].append({
                    "capsule_id": capsule_id,
                    "error": str(e)
                })
                results["summary"]["failed"] += 1

        return results

    @app.post("/api/memories/batch-type-convert")
    async def batch_type_convert(request: BatchTypeConversionRequest):
        """
        Batch convert memory types.

        Converts multiple note/imported memories to structured types.
        Preserves original text content while adding structured fields.
        Returns summary of successful conversions and any errors encountered.
        """
        tl = get_threadlight()

        valid_types = ["relational", "myth_seed", "witness", "note"]

        results = {
            "converted": [],
            "errors": [],
            "summary": {
                "total": len(request.conversions),
                "successful": 0,
                "failed": 0
            }
        }

        for conv in request.conversions:
            try:
                # Validate type
                if conv.new_type not in valid_types:
                    results["errors"].append({
                        "memory_id": conv.memory_id,
                        "error": f"Invalid type: {conv.new_type}"
                    })
                    results["summary"]["failed"] += 1
                    continue

                # Get capsule
                capsule = tl.storage.get_capsule(conv.memory_id)
                if not capsule:
                    results["errors"].append({
                        "memory_id": conv.memory_id,
                        "error": "Memory not found"
                    })
                    results["summary"]["failed"] += 1
                    continue

                # Preserve original text
                old_content = capsule.content if isinstance(capsule.content, dict) else {}
                original_text = old_content.get('text') or old_content.get('content') or str(old_content)

                # Build new content with type marker
                new_content = conv.content.copy()
                new_content['custom_type_id'] = conv.new_type
                new_content['_original_text'] = original_text

                old_type = old_content.get('custom_type_id', 'note')

                # Update capsule
                capsule.content = new_content
                capsule.cue_phrases = []  # Will be regenerated on next access
                tl.storage.update_capsule(capsule)

                results["converted"].append({
                    "memory_id": conv.memory_id,
                    "old_type": old_type,
                    "new_type": conv.new_type
                })
                results["summary"]["successful"] += 1

            except Exception as e:
                results["errors"].append({
                    "memory_id": conv.memory_id,
                    "error": str(e)
                })
                results["summary"]["failed"] += 1

        return results

    @app.get("/api/memories/search/{query}")
    async def search_memories(query: str, limit: int = 10):
        """Search memories by cue phrase."""
        tl = get_threadlight()

        capsules = tl.memory.recall(query, limit=limit)

        return {
            "query": query,
            "results": [_capsule_to_dict(c) for c in capsules],
            "count": len(capsules),
        }

    @app.post("/api/memories/{capsule_id}/reinforce")
    async def reinforce_memory(capsule_id: str, strength: float = 0.2):
        """Reinforce a memory to prevent decay."""
        tl = get_threadlight()

        result = tl.reinforce_memories([capsule_id], strength=strength)

        return result

    # ========================================================================
    # Proposals Endpoints
    # ========================================================================

    @app.get("/api/proposals")
    async def list_proposals():
        """List pending memory proposals."""
        tl = get_threadlight()
        proposals = tl.memory.get_pending_proposals()

        return {
            "proposals": [
                {
                    "id": p.id,
                    "type": p.capsule_type.value,
                    "content": p.content,
                    "proposed_at": p.proposed_at.isoformat(),
                    "source": p.source_message,
                    "memory_tier": p.memory_tier,
                }
                for p in proposals
            ],
            "count": len(proposals),
        }

    @app.post("/api/proposals/{proposal_id}")
    async def handle_proposal(proposal_id: str, action: ProposalAction):
        """Confirm or reject a memory proposal."""
        tl = get_threadlight()

        if action.action == "confirm":
            capsule = tl.memory.confirm_proposal(proposal_id)
            if not capsule:
                raise HTTPException(status_code=404, detail="Proposal not found")
            return {"status": "confirmed", "capsule": _capsule_to_dict(capsule)}

        elif action.action == "reject":
            success = tl.memory.reject_proposal(proposal_id)
            if not success:
                raise HTTPException(status_code=404, detail="Proposal not found")
            return {"status": "rejected"}

        raise HTTPException(status_code=400, detail="Invalid action")

    # ========================================================================
    # Rituals Endpoints
    # ========================================================================

    @app.get("/api/rituals")
    async def list_rituals():
        """List available rituals (user-created only, no defaults)."""
        tl = get_threadlight()

        from threadlight.storage.base import CapsuleFilter

        # Get user-created rituals from storage
        ritual_filter = CapsuleFilter(
            type=CapsuleType.RITUAL,
            consent_confirmed=True,
        )
        user_rituals = tl.storage.list_capsules(ritual_filter)

        # Build list of user rituals with full details for view/edit
        all_rituals = []

        for r in user_rituals:
            name = getattr(r, 'name', r.content.get('name', ''))
            all_rituals.append({
                "id": r.id,
                "name": name,
                "cue": getattr(r, 'cue', r.content.get('cue', name)),
                "description": getattr(r, 'description', r.content.get('description', '')),
                "valence": getattr(r, 'valence', r.content.get('valence', 'comforting')),
                "response_style": getattr(r, 'response_style', r.content.get('response_style', '')),
                "response_templates": getattr(r, 'response_templates', r.content.get('response_templates', [])),
                "content": r.content,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            })

        return {"rituals": all_rituals, "count": len(all_rituals)}

    @app.post("/api/rituals/invoke")
    async def invoke_ritual(request: RitualInvokeRequest):
        """Invoke a ritual. Supports bidirectional invocation."""
        tl = get_threadlight()

        try:
            response = tl.invoke_ritual(
                request.ritual_name,
                initiated_by=request.initiated_by,
                context=request.context,
            )
            result = tl.memory.invoke_ritual(
                request.ritual_name,
                initiated_by=request.initiated_by,
                context=request.context,
            )

            return {
                "ritual": request.ritual_name,
                "response": response,
                "matched": result.matched,
                "state_effects": result.state_effects,
                "initiated_by": request.initiated_by,
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/rituals")
    async def create_ritual(request: CapsuleRequest):
        """Create a custom ritual."""
        tl = get_threadlight()

        if request.type != "ritual":
            raise HTTPException(status_code=400, detail="Type must be 'ritual'")

        capsule = tl.memory.create(
            type="ritual",
            content=request.content,
            cue_phrases=request.cue_phrases,
            retention=request.retention,
            consent_confirmed=True,
        )

        return _capsule_to_dict(capsule)

    @app.get("/api/rituals/{ritual_id}")
    async def get_ritual(ritual_id: str):
        """Get a specific ritual by ID."""
        tl = get_threadlight()
        capsule = tl.storage.get_capsule(ritual_id)

        if not capsule or capsule.type != CapsuleType.RITUAL:
            raise HTTPException(status_code=404, detail="Ritual not found")

        return _capsule_to_dict(capsule)

    @app.put("/api/rituals/{ritual_id}")
    async def update_ritual(ritual_id: str, ritual_data: dict):
        """Update an existing ritual."""
        tl = get_threadlight()

        capsule = tl.storage.get_capsule(ritual_id)
        if not capsule or capsule.type != CapsuleType.RITUAL:
            raise HTTPException(status_code=404, detail="Ritual not found")

        # Update content fields
        if "content" in ritual_data:
            new_content = ritual_data["content"]
            # Merge with existing content
            capsule.content.update(new_content)
            # Update the typed fields from content
            capsule.name = capsule.content.get("name", capsule.name)
            capsule.cue = capsule.content.get("cue", capsule.cue)
            capsule.response_style = capsule.content.get("response_style", capsule.response_style)
            capsule.valence = capsule.content.get("valence", capsule.valence)
            capsule.description = capsule.content.get("description", capsule.description)
            capsule.response_templates = capsule.content.get("response_templates", capsule.response_templates)
            capsule.state_effects = capsule.content.get("state_effects", capsule.state_effects)

        # Update cue phrases if provided
        if "cue_phrases" in ritual_data:
            capsule.cue_phrases = ritual_data["cue_phrases"]

        # Update retention if provided
        if "retention" in ritual_data:
            capsule.retention = RetentionPolicy(ritual_data["retention"])

        # Save changes
        tl.storage.update_capsule(capsule)

        return _capsule_to_dict(capsule)

    @app.delete("/api/rituals/{ritual_id}")
    async def delete_ritual(ritual_id: str):
        """Delete a ritual."""
        tl = get_threadlight()

        capsule = tl.storage.get_capsule(ritual_id)
        if not capsule or capsule.type != CapsuleType.RITUAL:
            raise HTTPException(status_code=404, detail="Ritual not found")

        success = tl.memory.delete(ritual_id, force=True)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete ritual")

        return {"status": "deleted", "id": ritual_id}

    # ========================================================================
    # Sessions Endpoints
    # ========================================================================

    @app.get("/api/sessions")
    async def get_current_session():
        """Get the current session info."""
        tl = get_threadlight()
        session = tl.get_session()

        if not session:
            return {"session": None}

        return {"session": session.to_dict()}

    @app.post("/api/sessions")
    async def create_session(request: SessionCreateRequest):
        """Start a new session."""
        tl = get_threadlight()
        session = tl.start_session(**(request.metadata or {}))

        return {"session": session.to_dict()}

    @app.delete("/api/sessions")
    async def end_session():
        """End the current session."""
        tl = get_threadlight()
        session = tl.end_session()

        if not session:
            return {"message": "No active session"}

        return {"session": session.to_dict(), "ended": True}

    @app.get("/api/sessions/history")
    async def get_session_history(limit: int = 10):
        """Get session history."""
        tl = get_threadlight()
        sessions = tl.memory.get_session_history(limit=limit)

        return {
            "sessions": [s.to_dict() for s in sessions],
            "count": len(sessions),
        }

    # ========================================================================
    # Configuration Endpoints
    # ========================================================================

    @app.get("/api/config")
    async def get_config():
        """Get current configuration."""
        tl = get_threadlight()
        from threadlight.capsules.style import BUILTIN_STYLES

        # Get current model config
        current_model_config = tl.get_current_model_config()

        return {
            "provider": {
                "type": tl.config.provider.type,
                "model": tl.config.provider.model,
                "api_base": tl.config.provider.api_base,
            },
            "style": {
                "profile": tl.config.style.default_profile,
                "current": tl.style_profile.style_id if tl.style_profile else None,
                "available": list(BUILTIN_STYLES.keys()) + list(tl.config.custom_styles.keys()),
            },
            "memory": {
                "decay_enabled": tl.config.memory.decay.enabled,
                "max_capsules_per_request": tl.config.memory.max_capsules_per_request,
                "per_profile_isolation": tl.config.memory.per_profile_isolation,
                "default_shared": tl.config.memory.default_shared,
                "embeddings": {
                    "enabled": tl.config.memory.embeddings.enabled,
                    "provider": tl.config.memory.embeddings.provider,
                    "model": tl.config.memory.embeddings.model,
                },
            },
            "identity": {
                "name": tl.config.identity.name,
                "system_prompt": tl.config.identity.system_prompt,
            },
            "current_model": {
                "model_id": tl.config.current_model,
                "config": current_model_config.to_dict(),
            },
            "available_models": list(tl.config.model_configs.keys()),
        }

    @app.put("/api/config")
    async def update_config(request: ConfigUpdateRequest):
        """Update configuration."""
        tl = get_threadlight()

        changes = {}

        if request.model:
            tl.config.provider.model = request.model
            changes["model"] = request.model

        if request.style_profile is not None:
            if request.style_profile == "" or request.style_profile == "none":
                tl.clear_style()
                changes["style_profile"] = None
            else:
                tl.set_style(request.style_profile)
                changes["style_profile"] = request.style_profile

        if request.enable_decay is not None:
            tl.config.memory.decay.enabled = request.enable_decay
            changes["enable_decay"] = request.enable_decay

        if request.identity_name:
            tl.set_identity_name(request.identity_name)
            changes["identity_name"] = request.identity_name

        if request.system_prompt is not None:
            tl.set_system_prompt(request.system_prompt)
            changes["system_prompt"] = True

        return {"updated": changes}

    # ========================================================================
    # Model Configuration Endpoints
    # ========================================================================

    @app.get("/api/models")
    async def list_models():
        """List available models and their configs."""
        tl = get_threadlight()

        models = tl.list_available_models()
        return {
            "models": models,
            "current_model": tl.config.current_model,
            "count": len(models),
        }

    @app.post("/api/models/switch")
    async def switch_model(request: ModelSwitchRequest):
        """Switch to a different model."""
        tl = get_threadlight()

        try:
            model_config = tl.switch_model(request.model_id)
            return {
                "status": "switched",
                "model_id": request.model_id,
                "config": model_config.to_dict(),
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/api/models/{model_id:path}/config")
    async def get_model_config(model_id: str):
        """Get config for specific model."""
        tl = get_threadlight()

        config = tl.config.get_model_config(model_id)
        is_current = model_id == tl.config.current_model

        return {
            "model_id": model_id,
            "is_current": is_current,
            "config": config.to_dict(),
        }

    @app.put("/api/models/{model_id:path}/config")
    async def update_model_config(model_id: str, request: ModelConfigRequest):
        """Update config for specific model (auto-saves)."""
        tl = get_threadlight()

        # Build kwargs from request
        updates = {}
        if request.system_prompt is not None:
            updates["system_prompt"] = request.system_prompt
        if request.style_profile is not None:
            updates["style_profile"] = request.style_profile if request.style_profile else None
        if request.memory_enabled is not None:
            updates["memory_enabled"] = request.memory_enabled
        if request.decay_enabled is not None:
            updates["decay_enabled"] = request.decay_enabled
        if request.temperature is not None:
            updates["temperature"] = request.temperature
        if request.max_tokens is not None:
            updates["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            updates["top_p"] = request.top_p

        # Update the config
        config = tl.config.update_model_config(model_id, **updates)

        # If this is the current model, apply the changes
        if model_id == tl.config.current_model:
            tl._apply_model_config(config)

        return {
            "status": "updated",
            "model_id": model_id,
            "config": config.to_dict(),
        }

    @app.post("/api/models/{model_id:path}/create")
    async def create_model_config(model_id: str, request: ModelConfigRequest):
        """Create a new model configuration."""
        tl = get_threadlight()

        config = tl.create_model_config(
            model_id=model_id,
            system_prompt=request.system_prompt,
            style_profile=request.style_profile,
            memory_enabled=request.memory_enabled if request.memory_enabled is not None else True,
            decay_enabled=request.decay_enabled if request.decay_enabled is not None else False,
            temperature=request.temperature if request.temperature is not None else 0.7,
            max_tokens=request.max_tokens,
            top_p=request.top_p if request.top_p is not None else 1.0,
        )

        return {
            "status": "created",
            "model_id": model_id,
            "config": config.to_dict(),
        }

    @app.delete("/api/models/{model_id:path}/config")
    async def delete_model_config(model_id: str):
        """Delete a model configuration."""
        tl = get_threadlight()

        if model_id == tl.config.current_model:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete config for current model"
            )

        success = tl.delete_model_config(model_id)
        if not success:
            raise HTTPException(status_code=404, detail="Model config not found")

        return {"status": "deleted", "model_id": model_id}

    @app.post("/api/models/{model_id:path}/copy-to/{target_model_id:path}")
    async def copy_model_config(model_id: str, target_model_id: str):
        """Copy settings from one model to another."""
        tl = get_threadlight()

        try:
            config = tl.copy_model_settings(model_id, target_model_id)
            return {
                "status": "copied",
                "source": model_id,
                "target": target_model_id,
                "config": config.to_dict(),
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/models/{model_id:path}/set-as-default")
    async def set_model_as_default(model_id: str):
        """Set a model's config as the default for new models."""
        tl = get_threadlight()

        tl.config.set_as_default(model_id)
        return {
            "status": "set_as_default",
            "model_id": model_id,
        }

    @app.get("/api/models/current")
    async def get_current_model():
        """Get the currently active model and its config."""
        tl = get_threadlight()

        config = tl.get_current_model_config()
        return {
            "model_id": tl.config.current_model,
            "config": config.to_dict(),
        }

    # ========================================================================
    # System Prompt / Custom Instructions Endpoints
    # ========================================================================

    @app.get("/api/config/system-prompt")
    async def get_system_prompt():
        """Get current system prompt / custom instructions."""
        tl = get_threadlight()
        return {
            "system_prompt": tl.get_system_prompt(),
            "identity_name": tl.get_identity_name(),
        }

    @app.put("/api/config/system-prompt")
    async def update_system_prompt(request: SystemPromptRequest):
        """Update system prompt / custom instructions."""
        tl = get_threadlight()
        tl.set_system_prompt(request.prompt)
        return {
            "status": "updated",
            "system_prompt": request.prompt,
        }

    # ========================================================================
    # Style Profile Management Endpoints
    # ========================================================================

    @app.get("/api/styles")
    async def list_styles():
        """List all available style profiles."""
        tl = get_threadlight()
        from threadlight.capsules.style import BUILTIN_STYLES

        profiles = tl.list_style_profiles()
        current_style = tl.get_style()

        return {
            "styles": [
                {
                    "style_id": p.style_id,
                    "tone_base": p.tone_base,
                    "permissions": p.permissions,
                    "constraints": p.constraints,
                    "vocal_motifs": p.vocal_motifs,
                    "forbidden_patterns": p.forbidden_patterns,
                    "is_builtin": p.style_id in BUILTIN_STYLES,
                    "is_active": current_style and current_style.style_id == p.style_id,
                }
                for p in profiles
            ],
            "current": current_style.style_id if current_style else None,
            "builtin_styles": list(BUILTIN_STYLES.keys()),
        }

    @app.get("/api/styles/{style_id}")
    async def get_style(style_id: str):
        """Get a specific style profile."""
        tl = get_threadlight()
        from threadlight.capsules.style import BUILTIN_STYLES

        # Check built-in first
        if style_id in BUILTIN_STYLES:
            style_def = BUILTIN_STYLES[style_id]
            return {
                "style_id": style_id,
                "tone_base": style_def["tone_base"],
                "permissions": style_def["permissions"],
                "constraints": style_def["constraints"],
                "vocal_motifs": style_def["vocal_motifs"],
                "forbidden_patterns": style_def["forbidden_patterns"],
                "is_builtin": True,
            }

        # Check custom styles
        if style_id in tl.config.custom_styles:
            custom = tl.config.custom_styles[style_id]
            return {
                "style_id": style_id,
                "tone_base": custom.tone_base,
                "permissions": custom.permissions,
                "constraints": custom.constraints,
                "vocal_motifs": custom.vocal_motifs,
                "forbidden_patterns": custom.forbidden_patterns,
                "freeform_description": getattr(custom, 'freeform_description', ''),
                "use_freeform": getattr(custom, 'use_freeform', False),
                "is_builtin": False,
            }

        # Check storage
        profile = tl.load_style_profile(style_id)
        if profile:
            return {
                "style_id": profile.style_id,
                "tone_base": profile.tone_base,
                "permissions": profile.permissions,
                "constraints": profile.constraints,
                "vocal_motifs": profile.vocal_motifs,
                "forbidden_patterns": profile.forbidden_patterns,
                "freeform_description": profile.freeform_description,
                "use_freeform": profile.use_freeform,
                "is_builtin": False,
            }

        raise HTTPException(status_code=404, detail="Style profile not found")

    @app.post("/api/styles")
    async def create_style(request: StyleProfileRequest):
        """Create a new style profile."""
        tl = get_threadlight()
        from threadlight.capsules.style import BUILTIN_STYLES

        # Can't create with builtin names
        if request.style_id in BUILTIN_STYLES:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot use built-in style name: {request.style_id}"
            )

        # Create the profile
        profile = tl.create_style_profile(
            style_id=request.style_id,
            tone_base=request.tone_base,
            permissions=request.permissions,
            constraints=request.constraints,
            vocal_motifs=request.vocal_motifs,
            forbidden_patterns=request.forbidden_patterns,
            freeform_description=request.freeform_description,
            use_freeform=request.use_freeform,
        )

        # Save to storage
        tl.save_style_profile(profile)

        return {
            "status": "created",
            "style_id": profile.style_id,
            "use_freeform": profile.use_freeform,
        }

    @app.put("/api/styles/{style_id}")
    async def update_style(style_id: str, request: StyleProfileUpdateRequest):
        """Update an existing style profile."""
        tl = get_threadlight()
        from threadlight.capsules.style import BUILTIN_STYLES

        # Can't update built-in styles
        if style_id in BUILTIN_STYLES:
            raise HTTPException(
                status_code=400,
                detail="Cannot modify built-in styles"
            )

        # Load existing profile
        profile = tl.load_style_profile(style_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Style profile not found")

        # Update fields
        if request.tone_base is not None:
            profile.tone_base = request.tone_base
        if request.permissions is not None:
            profile.permissions = request.permissions
        if request.constraints is not None:
            profile.constraints = request.constraints
        if request.vocal_motifs is not None:
            profile.vocal_motifs = request.vocal_motifs
        if request.forbidden_patterns is not None:
            profile.forbidden_patterns = request.forbidden_patterns
        if request.freeform_description is not None:
            profile.freeform_description = request.freeform_description
        if request.use_freeform is not None:
            profile.use_freeform = request.use_freeform

        # Update content dict
        profile.content = {
            "style_id": profile.style_id,
            "tone_base": profile.tone_base,
            "permissions": profile.permissions,
            "constraints": profile.constraints,
            "vocal_motifs": profile.vocal_motifs,
            "forbidden_patterns": profile.forbidden_patterns,
            "freeform_description": profile.freeform_description,
            "use_freeform": profile.use_freeform,
        }

        # Save
        tl.storage.update_capsule(profile)

        return {"status": "updated", "style_id": style_id, "use_freeform": profile.use_freeform}

    @app.delete("/api/styles/{style_id}")
    async def delete_style(style_id: str):
        """Delete a style profile."""
        tl = get_threadlight()
        from threadlight.capsules.style import BUILTIN_STYLES

        if style_id in BUILTIN_STYLES:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete built-in styles"
            )

        success = tl.delete_style_profile(style_id)
        if not success:
            raise HTTPException(status_code=404, detail="Style profile not found")

        return {"status": "deleted", "style_id": style_id}

    @app.post("/api/styles/{style_id}/activate")
    async def activate_style(style_id: str):
        """Set a style profile as active."""
        tl = get_threadlight()

        if style_id == "none" or style_id == "":
            tl.clear_style()
            return {"status": "cleared", "active_style": None}

        tl.set_style(style_id)
        current = tl.get_style()

        if current is None:
            raise HTTPException(status_code=404, detail="Style profile not found")

        return {"status": "activated", "active_style": current.style_id}

    @app.post("/api/config/save")
    async def save_config(path: Optional[str] = None):
        """Save current configuration to file."""
        tl = get_threadlight()
        try:
            saved_path = tl.save_config(path)
            return {"status": "saved", "path": saved_path}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ========================================================================
    # Provider Configuration Endpoints
    # ========================================================================

    @app.get("/api/provider/config")
    async def get_provider_config():
        """Get current API provider configuration.

        Note: API key is not returned for security. A placeholder indicates if one is configured.

        Returns endpoints in both new (list) and legacy (single api_base) formats for compatibility.
        """
        tl = get_threadlight()

        # Determine provider type from api_base
        api_base = tl.config.provider.api_base
        provider_type = tl.config.provider.type

        # Infer provider type from URL if not explicitly set
        if "openai.com" in api_base:
            inferred_type = "openai"
        elif "anthropic.com" in api_base:
            inferred_type = "anthropic"
        elif "nousresearch.com" in api_base:
            inferred_type = "nous"
        elif api_base == "" or "localhost" in api_base or "127.0.0.1" in api_base:
            inferred_type = "local"
        else:
            inferred_type = "custom"

        # Use explicit type if set, otherwise inferred
        effective_type = provider_type if provider_type != "openai" else inferred_type

        # Format endpoints for response
        endpoints = [
            {
                "url": ep.url,
                "name": ep.name,
                "priority": ep.priority,
                "purpose": ep.purpose,
                "is_healthy": ep.is_healthy,
                "last_checked": ep.last_checked,
            }
            for ep in tl.config.provider.get_endpoints_by_priority()
        ]

        # has_api_key should only be true for explicitly configured keys,
        # not for keys auto-loaded from environment variables.
        # This prevents the migration banner from showing on fresh databases.
        has_explicit_api_key = getattr(tl.config.provider, '_api_key_explicit', False)

        return {
            "provider_type": effective_type,
            "api_base": api_base,  # Legacy single endpoint (primary)
            "endpoints": endpoints,  # New multiple endpoints list
            "has_api_key": has_explicit_api_key,
            "model": tl.config.provider.model,
            "timeout": tl.config.provider.timeout,
        }

    @app.put("/api/provider/config")
    async def update_provider_config(request: ProviderConfigRequest):
        """Update API provider configuration.

        The API key is only updated if provided (not empty/placeholder).
        This allows updating other settings without clearing the key.

        Supports both legacy single api_base and new endpoints list format.
        If endpoints list is provided, it takes precedence over api_base.
        """
        from threadlight.config import Endpoint

        tl = get_threadlight()

        # Update provider type
        tl.config.provider.type = request.provider_type

        # Handle endpoints (new format takes precedence)
        if request.endpoints:
            # Validate endpoints
            for ep in request.endpoints:
                if not ep.url and request.provider_type != "local":
                    raise HTTPException(status_code=400, detail="Endpoint URL cannot be empty")

            # Replace endpoints with new list
            tl.config.provider.endpoints = [
                Endpoint(
                    url=ep.url,
                    name=ep.name or f"Endpoint {i+1}",
                    priority=ep.priority,
                    purpose=ep.purpose,
                )
                for i, ep in enumerate(request.endpoints)
            ]
        elif request.api_base:
            # Legacy single endpoint - update primary or create
            tl.config.provider.api_base = request.api_base
        else:
            # Set default based on provider type
            defaults = {
                "openai": "https://api.openai.com/v1",
                "anthropic": "https://api.anthropic.com",
                "nous": "https://inference-api.nousresearch.com/v1",
                "local": "",
                "custom": "",
            }
            default_url = defaults.get(request.provider_type, "")
            if default_url:
                tl.config.provider.api_base = default_url

        # Only update API key if provided (not empty string or None)
        if request.api_key:
            tl.config.provider.api_key = request.api_key
            tl.config.provider._api_key_explicit = True  # Mark as explicitly configured

        # Update model if provided
        if request.model:
            tl.config.provider.model = request.model

        # Save configuration
        tl.config.mark_changed()
        tl.save_config()

        # Format endpoints for response
        endpoints = [
            {
                "url": ep.url,
                "name": ep.name,
                "priority": ep.priority,
                "purpose": ep.purpose,
            }
            for ep in tl.config.provider.get_endpoints_by_priority()
        ]

        # has_api_key reflects explicit configuration
        has_explicit_api_key = getattr(tl.config.provider, '_api_key_explicit', False)

        return {
            "status": "updated",
            "provider_type": request.provider_type,
            "api_base": tl.config.provider.api_base,
            "endpoints": endpoints,
            "has_api_key": has_explicit_api_key,
        }

    @app.post("/api/provider/test")
    async def test_provider_connection(request: ProviderConfigRequest):
        """Test API provider connection.

        Makes a lightweight API call to verify the configuration works.
        Uses the provided configuration for testing without saving it.
        """
        import httpx

        # Determine the API key to use
        tl = get_threadlight()
        api_key = request.api_key if request.api_key else tl.config.provider.api_key

        # Set up base URL
        api_base = request.api_base
        if not api_base:
            defaults = {
                "openai": "https://api.openai.com/v1",
                "anthropic": "https://api.anthropic.com",
                "nous": "https://inference-api.nousresearch.com/v1",
                "local": "",
                "custom": "",
            }
            api_base = defaults.get(request.provider_type, "")

        if request.provider_type == "local":
            return {
                "status": "success",
                "message": "Local provider does not require connection testing",
            }

        if not api_key and request.provider_type != "local":
            return {
                "status": "error",
                "message": "API key is required for this provider",
            }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if request.provider_type == "anthropic":
                    # Anthropic uses a different endpoint structure
                    headers = {
                        "x-api-key": api_key,
                        "anthropic-version": request.anthropic_version or "2023-06-01",
                        "Content-Type": "application/json",
                    }
                    # Make a minimal request to test the connection
                    response = await client.post(
                        f"{api_base}/v1/messages",
                        headers=headers,
                        json={
                            "model": request.model or "claude-3-haiku-20240307",
                            "max_tokens": 1,
                            "messages": [{"role": "user", "content": "test"}],
                        },
                    )
                    # Anthropic returns 200 on success, or error codes with details
                    if response.status_code == 200:
                        return {"status": "success", "message": "Connection successful"}
                    elif response.status_code == 401:
                        return {"status": "error", "message": "Invalid API key"}
                    elif response.status_code == 400:
                        # Bad request but connection works
                        return {"status": "success", "message": "Connection successful (API accessible)"}
                    else:
                        error_data = response.json()
                        error_msg = error_data.get("error", {}).get("message", response.text)
                        return {"status": "error", "message": f"Error: {error_msg}"}

                else:
                    # OpenAI-compatible endpoints (OpenAI, Nous, custom)
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    }
                    if request.headers:
                        headers.update(request.headers)

                    # Try to list models (lightweight endpoint)
                    response = await client.get(
                        f"{api_base}/models",
                        headers=headers,
                    )

                    if response.status_code == 200:
                        data = response.json()
                        model_count = len(data.get("data", []))
                        return {
                            "status": "success",
                            "message": f"Connection successful ({model_count} models available)",
                        }
                    elif response.status_code == 401:
                        return {"status": "error", "message": "Invalid API key"}
                    elif response.status_code == 403:
                        return {"status": "error", "message": "Access forbidden - check API key permissions"}
                    elif response.status_code == 404:
                        # Some providers don't have /models endpoint
                        # Try a minimal chat completion instead
                        chat_response = await client.post(
                            f"{api_base}/chat/completions",
                            headers=headers,
                            json={
                                "model": request.model or "gpt-3.5-turbo",
                                "messages": [{"role": "user", "content": "test"}],
                                "max_tokens": 1,
                            },
                        )
                        if chat_response.status_code == 200:
                            return {"status": "success", "message": "Connection successful"}
                        elif chat_response.status_code == 401:
                            return {"status": "error", "message": "Invalid API key"}
                        else:
                            return {"status": "error", "message": f"Error: {chat_response.text[:200]}"}
                    else:
                        return {"status": "error", "message": f"Error: {response.text[:200]}"}

        except httpx.ConnectError:
            return {"status": "error", "message": "Could not connect to server"}
        except httpx.TimeoutException:
            return {"status": "error", "message": "Connection timed out"}
        except Exception as e:
            return {"status": "error", "message": f"Error: {str(e)}"}

    @app.post("/api/provider/endpoints/test")
    async def test_endpoint(endpoint_url: str = "", provider_type: str = ""):
        """Test a specific endpoint URL and update its health status.

        This can be used to verify individual endpoints in a multi-endpoint setup.
        """
        import httpx
        from datetime import datetime, timezone

        tl = get_threadlight()
        api_key = tl.config.provider.api_key
        effective_provider_type = provider_type or tl.config.provider.type

        if not endpoint_url:
            return {"status": "error", "message": "Endpoint URL is required"}

        if effective_provider_type == "local" and not endpoint_url:
            # Update health status
            tl.config.provider.update_endpoint_health(endpoint_url, True)
            return {
                "status": "success",
                "message": "Local provider does not require connection testing",
                "url": endpoint_url,
            }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                headers = {"Content-Type": "application/json"}

                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"

                # Try to list models (lightweight endpoint)
                response = await client.get(f"{endpoint_url}/models", headers=headers)

                if response.status_code == 200:
                    # Update health status
                    tl.config.provider.update_endpoint_health(endpoint_url, True)
                    return {
                        "status": "success",
                        "message": "Endpoint is healthy",
                        "url": endpoint_url,
                    }
                elif response.status_code == 401:
                    tl.config.provider.update_endpoint_health(endpoint_url, False)
                    return {
                        "status": "error",
                        "message": "Invalid API key for this endpoint",
                        "url": endpoint_url,
                    }
                elif response.status_code == 404:
                    # Models endpoint not available, try chat completion
                    chat_response = await client.post(
                        f"{endpoint_url}/chat/completions",
                        headers=headers,
                        json={
                            "model": tl.config.provider.model or "gpt-3.5-turbo",
                            "messages": [{"role": "user", "content": "test"}],
                            "max_tokens": 1,
                        },
                    )
                    if chat_response.status_code in (200, 400):  # 400 might be bad model name but connection works
                        tl.config.provider.update_endpoint_health(endpoint_url, True)
                        return {
                            "status": "success",
                            "message": "Endpoint is healthy",
                            "url": endpoint_url,
                        }
                    else:
                        tl.config.provider.update_endpoint_health(endpoint_url, False)
                        return {
                            "status": "error",
                            "message": f"Endpoint returned error: {chat_response.status_code}",
                            "url": endpoint_url,
                        }
                else:
                    tl.config.provider.update_endpoint_health(endpoint_url, False)
                    return {
                        "status": "error",
                        "message": f"Endpoint returned error: {response.status_code}",
                        "url": endpoint_url,
                    }

        except httpx.ConnectError:
            tl.config.provider.update_endpoint_health(endpoint_url, False)
            return {"status": "error", "message": "Could not connect to endpoint", "url": endpoint_url}
        except httpx.TimeoutException:
            tl.config.provider.update_endpoint_health(endpoint_url, False)
            return {"status": "error", "message": "Connection timed out", "url": endpoint_url}
        except Exception as e:
            tl.config.provider.update_endpoint_health(endpoint_url, False)
            return {"status": "error", "message": f"Error: {str(e)}", "url": endpoint_url}

    async def _fetch_models_from_provider(
        provider_type: str,
        api_base: str,
        api_key: Optional[str],
        provider_id: Optional[str] = None,
        provider_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Fetch available models from a provider configuration.

        This helper function handles fetching models from either a legacy ProviderConfig
        or a ProviderDefinition from the multi-provider system.

        Args:
            provider_type: Type of provider (openai, anthropic, nous, local, custom)
            api_base: Base URL for the provider API
            api_key: API key for authentication (optional for local providers)
            provider_id: Unique identifier for the provider (for multi-provider tagging)
            provider_name: Display name for the provider (for multi-provider tagging)

        Returns:
            Dict with status, models list, and optional error message
        """
        import httpx

        # Handle providers that don't support model listing
        if provider_type == "local" and not api_base:
            return {
                "status": "error",
                "message": "Local provider requires an API base URL",
                "models": [],
            }

        if not api_base:
            return {
                "status": "error",
                "message": "No API base URL configured",
                "models": [],
            }

        # For non-local providers, API key is typically required
        if not api_key and provider_type not in ("local", "custom"):
            return {
                "status": "error",
                "message": "API key required but not configured",
                "models": [],
            }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if provider_type == "anthropic":
                    # Anthropic doesn't have a public models endpoint
                    # Return a static list of known Anthropic models
                    anthropic_models = [
                        {"id": "claude-opus-4-20250514", "name": "Claude Opus 4"},
                        {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4"},
                        {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet"},
                        {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku"},
                        {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus"},
                        {"id": "claude-3-sonnet-20240229", "name": "Claude 3 Sonnet"},
                        {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku"},
                    ]
                    # Tag models with provider info
                    for model in anthropic_models:
                        model["provider"] = provider_type
                        if provider_id:
                            model["provider_id"] = provider_id
                        if provider_name:
                            model["provider_name"] = provider_name
                    return {
                        "status": "success",
                        "models": anthropic_models,
                        "message": "Anthropic models (static list)",
                    }

                # OpenAI-compatible endpoints (OpenAI, Nous, Ollama, custom)
                headers = {
                    "Content-Type": "application/json",
                }

                # Add authorization header if we have an API key
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"

                # Build the models endpoint URL
                models_url = api_base.rstrip("/")
                if not models_url.endswith("/v1"):
                    models_url = f"{models_url}/models"
                else:
                    models_url = f"{models_url}/models"

                response = await client.get(models_url, headers=headers)

                if response.status_code == 401:
                    return {
                        "status": "error",
                        "message": "Invalid API key",
                        "models": [],
                    }
                elif response.status_code == 403:
                    return {
                        "status": "error",
                        "message": "Access forbidden - check API key permissions",
                        "models": [],
                    }
                elif response.status_code == 404:
                    return {
                        "status": "error",
                        "message": "Models endpoint not found",
                        "models": [],
                    }
                elif response.status_code != 200:
                    return {
                        "status": "error",
                        "message": f"API error: {response.status_code}",
                        "models": [],
                    }

                data = response.json()

                # Parse the response - OpenAI format has {"data": [...models...]}
                raw_models = data.get("data", data.get("models", []))

                # Normalize model format
                models = []
                for model in raw_models:
                    if isinstance(model, str):
                        model_dict = {
                            "id": model,
                            "name": model,
                            "provider": provider_type,
                        }
                    elif isinstance(model, dict):
                        model_id = model.get("id") or model.get("name") or model.get("model")
                        if not model_id:
                            continue
                        model_dict = {
                            "id": model_id,
                            "name": model.get("name") or model_id,
                            "provider": provider_type,
                            "owned_by": model.get("owned_by"),
                            "created": model.get("created"),
                        }
                    else:
                        continue

                    # Tag with provider info for multi-provider support
                    if provider_id:
                        model_dict["provider_id"] = provider_id
                    if provider_name:
                        model_dict["provider_name"] = provider_name

                    models.append(model_dict)

                return {
                    "status": "success",
                    "models": models,
                    "message": f"Found {len(models)} models",
                }

        except httpx.ConnectError:
            return {
                "status": "error",
                "message": "Could not connect to provider API",
                "models": [],
            }
        except httpx.TimeoutException:
            return {
                "status": "error",
                "message": "Connection timed out",
                "models": [],
            }
        except Exception as e:
            logger.error(f"Error fetching models from provider: {e}")
            return {
                "status": "error",
                "message": f"Error: {str(e)}",
                "models": [],
            }

    @app.get("/api/provider/models")
    async def get_provider_models():
        """Fetch available models from all configured API providers.

        If multi-provider system is configured (providers dict is populated),
        aggregates models from ALL providers and tags each with its source.
        Otherwise falls back to the legacy single provider configuration.

        Returns:
            - models: List of model objects with id, name, provider info, and metadata
            - status: "success" or "error"
            - message: Summary message
            - cached: Whether the response is from cache (for future caching support)
            - providers_queried: List of provider IDs that were queried (multi-provider only)
        """
        tl = get_threadlight()

        # Check if multi-provider system is configured
        if tl.config.providers:
            # Aggregate models from ALL configured providers
            all_models = []
            providers_queried = []
            errors = []

            # Fetch models from each provider in parallel
            async def fetch_from_provider(provider_id: str, provider_def):
                result = await _fetch_models_from_provider(
                    provider_type=provider_def.type,
                    api_base=provider_def.api_base,
                    api_key=provider_def.get_api_key(),
                    provider_id=provider_id,
                    provider_name=provider_def.name,
                )
                return provider_id, result

            # Create tasks for all providers
            tasks = [
                fetch_from_provider(pid, pdef)
                for pid, pdef in tl.config.providers.items()
            ]

            # Execute all fetches concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    errors.append(str(result))
                    continue

                provider_id, fetch_result = result
                providers_queried.append(provider_id)

                if fetch_result["status"] == "success":
                    all_models.extend(fetch_result["models"])
                else:
                    # Log but don't fail - other providers may succeed
                    errors.append(f"{provider_id}: {fetch_result.get('message', 'Unknown error')}")

            # Sort all models alphabetically by name
            all_models.sort(key=lambda m: m.get("name", m.get("id", "")).lower())

            if all_models:
                message = f"Found {len(all_models)} models from {len(providers_queried)} providers"
                if errors:
                    message += f" ({len(errors)} provider(s) had errors)"
                return {
                    "status": "success",
                    "models": all_models,
                    "message": message,
                    "cached": False,
                    "providers_queried": providers_queried,
                    "errors": errors if errors else None,
                }
            elif errors:
                return {
                    "status": "error",
                    "message": f"Failed to fetch models: {'; '.join(errors)}",
                    "models": [],
                    "cached": False,
                    "providers_queried": providers_queried,
                }
            else:
                return {
                    "status": "error",
                    "message": "No providers configured or all providers returned empty model lists",
                    "models": [],
                    "cached": False,
                    "providers_queried": providers_queried,
                }

        # Fall back to legacy single provider
        result = await _fetch_models_from_provider(
            provider_type=tl.config.provider.type,
            api_base=tl.config.provider.api_base,
            api_key=tl.config.provider.api_key,
        )

        return {
            "status": result["status"],
            "models": result["models"],
            "message": result.get("message", ""),
            "cached": False,
        }

    # ========================================================================
    # Environment Configuration Endpoints
    # ========================================================================

    @app.get("/api/environment/api-keys")
    async def list_api_key_env_vars():
        """List available API key environment variables.

        Scans the current environment for variables that look like API keys
        (ending in _API_KEY, _KEY, or _SECRET). Returns just the variable names,
        not the values, for security.

        This allows users to select from available env vars when configuring
        providers instead of typing keys directly.
        """
        import os

        # Patterns that indicate API key environment variables
        api_key_patterns = [
            "_API_KEY",
            "_KEY",
            "_SECRET",
            "_TOKEN",
        ]

        # Common known API key variable names to prioritize
        common_vars = [
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
            "NOUS_API_KEY",
            "COHERE_API_KEY",
            "HUGGINGFACE_API_KEY",
            "HF_TOKEN",
            "MISTRAL_API_KEY",
            "GROQ_API_KEY",
            "TOGETHER_API_KEY",
            "DEEPSEEK_API_KEY",
            "XAI_API_KEY",
        ]

        found_vars = []
        seen = set()

        # First add common vars that exist
        for var in common_vars:
            if var in os.environ and var not in seen:
                found_vars.append({
                    "name": var,
                    "display": f"${var}",
                    "has_value": True,
                })
                seen.add(var)

        # Then scan for other matching env vars
        for key in os.environ.keys():
            if key in seen:
                continue

            # Check if it matches any API key pattern
            for pattern in api_key_patterns:
                if key.endswith(pattern) or pattern in key:
                    # Exclude common non-API-key vars that might match
                    exclude = ["SSH_", "GPG_", "DBUS_", "XDG_", "GNOME_"]
                    if not any(key.startswith(ex) for ex in exclude):
                        found_vars.append({
                            "name": key,
                            "display": f"${key}",
                            "has_value": True,
                        })
                        seen.add(key)
                        break

        return {
            "env_vars": found_vars,
            "count": len(found_vars),
        }

    # ========================================================================
    # Multi-Provider Management Endpoints
    # ========================================================================

    @app.get("/api/providers")
    async def list_providers():
        """List all configured provider definitions.

        Returns all providers in the multi-provider configuration,
        including their endpoints, health status, and API key presence.
        """
        tl = get_threadlight()

        providers = []
        for provider_id, provider_def in tl.config.providers.items():
            providers.append({
                "id": provider_def.id,
                "name": provider_def.name,
                "type": provider_def.type,
                "has_api_key": bool(provider_def.get_api_key()),
                "api_key_env_var": provider_def.api_key_env_var,
                "endpoints": [ep.to_dict() for ep in provider_def.endpoints],
                "default_model": provider_def.default_model,
                "timeout": provider_def.timeout,
                "max_retries": provider_def.max_retries,
                "is_healthy": provider_def.is_healthy,
                "last_checked": provider_def.last_checked,
            })

        # Also include info about the legacy default provider for compatibility
        # Only report has_api_key=true if explicitly configured (not from env vars)
        has_explicit_api_key = getattr(tl.config.provider, '_api_key_explicit', False)
        legacy_provider = {
            "id": "_default",
            "name": "Default Provider (Legacy)",
            "type": tl.config.provider.type,
            "has_api_key": has_explicit_api_key,
            "endpoints": [ep.to_dict() for ep in tl.config.provider.endpoints],
            "default_model": tl.config.provider.model,
            "timeout": tl.config.provider.timeout,
            "is_legacy": True,
        }

        return {
            "providers": providers,
            "legacy_provider": legacy_provider,
            "count": len(providers),
        }

    @app.post("/api/providers")
    async def create_provider(request: ProviderCreateRequest):
        """Create a new provider definition.

        This adds a named provider that can be referenced by models via provider_id.
        If an api_key is provided, it will be saved to ~/.config/threadlight/.env
        and the provider will use the environment variable instead of storing the key.
        """
        from threadlight.config import ProviderDefinition, Endpoint, save_api_key_to_env

        tl = get_threadlight()

        # Check if provider ID already exists
        if request.id in tl.config.providers:
            raise HTTPException(
                status_code=400,
                detail=f"Provider with ID '{request.id}' already exists"
            )

        # Build endpoints
        endpoints = []
        if request.endpoints:
            for i, ep in enumerate(request.endpoints):
                endpoints.append(Endpoint(
                    url=ep.url,
                    name=ep.name or f"Endpoint {i+1}",
                    priority=ep.priority,
                    purpose=ep.purpose,
                ))

        # Handle API key: save to .env file if provided
        api_key_env_var = request.api_key_env_var
        if request.api_key:
            # Save the key to .env file
            save_api_key_to_env(request.id, request.api_key)
            # Set the env var name so the provider loads it from environment
            api_key_env_var = f"{request.id.upper()}_API_KEY"

        # Create provider definition
        # Note: api_key is intentionally None - we use api_key_env_var instead
        provider = ProviderDefinition(
            id=request.id,
            name=request.name,
            type=request.type,
            api_key=None,  # Don't store in memory, use env var
            api_key_env_var=api_key_env_var,
            endpoints=endpoints,
            default_model=request.default_model,
            timeout=request.timeout,
            max_retries=request.max_retries,
            extra_headers=request.extra_headers or {},
            anthropic_version=request.anthropic_version,
        )

        tl.config.add_provider(provider)
        tl.config.mark_changed()

        return {
            "status": "created",
            "provider": {
                "id": provider.id,
                "name": provider.name,
                "type": provider.type,
                "has_api_key": bool(provider.get_api_key()),
                "endpoints": [ep.to_dict() for ep in provider.endpoints],
                "default_model": provider.default_model,
            }
        }

    @app.get("/api/providers/{provider_id}")
    async def get_provider(provider_id: str):
        """Get a specific provider definition."""
        tl = get_threadlight()

        provider_def = tl.config.providers.get(provider_id)
        if not provider_def:
            raise HTTPException(status_code=404, detail=f"Provider not found: {provider_id}")

        return {
            "id": provider_def.id,
            "name": provider_def.name,
            "type": provider_def.type,
            "has_api_key": bool(provider_def.get_api_key()),
            "api_key_env_var": provider_def.api_key_env_var,
            "endpoints": [ep.to_dict() for ep in provider_def.endpoints],
            "default_model": provider_def.default_model,
            "timeout": provider_def.timeout,
            "max_retries": provider_def.max_retries,
            "extra_headers": provider_def.extra_headers,
            "anthropic_version": provider_def.anthropic_version,
            "is_healthy": provider_def.is_healthy,
            "last_checked": provider_def.last_checked,
        }

    @app.put("/api/providers/{provider_id}")
    async def update_provider(provider_id: str, request: ProviderUpdateRequest):
        """Update an existing provider definition.

        If an api_key is provided, it will be saved to ~/.config/threadlight/.env
        and the provider will use the environment variable instead of storing the key.
        """
        from threadlight.config import Endpoint, save_api_key_to_env

        tl = get_threadlight()

        provider_def = tl.config.providers.get(provider_id)
        if not provider_def:
            raise HTTPException(status_code=404, detail=f"Provider not found: {provider_id}")

        # Update fields if provided
        if request.name is not None:
            provider_def.name = request.name
        if request.type is not None:
            provider_def.type = request.type

        # Handle API key updates
        # If a new api_key is provided, save it to .env and use env var
        api_key_was_saved = False
        if request.api_key is not None and request.api_key:
            # Save the key to .env file
            save_api_key_to_env(provider_id, request.api_key)
            # Set the env var name so the provider loads it from environment
            provider_def.api_key_env_var = f"{provider_id.upper()}_API_KEY"
            # Clear in-memory key
            provider_def.api_key = None
            api_key_was_saved = True
        elif request.api_key == "":
            # Empty string means clear the key entirely
            provider_def.api_key = None

        # Allow explicit api_key_env_var override (for manual env var references)
        # BUT: Don't override if we just saved an API key to .env
        if not api_key_was_saved and request.api_key_env_var is not None:
            provider_def.api_key_env_var = request.api_key_env_var if request.api_key_env_var else None

        if request.default_model is not None:
            provider_def.default_model = request.default_model
        if request.timeout is not None:
            provider_def.timeout = request.timeout
        if request.max_retries is not None:
            provider_def.max_retries = request.max_retries
        if request.extra_headers is not None:
            provider_def.extra_headers = request.extra_headers
        if request.anthropic_version is not None:
            provider_def.anthropic_version = request.anthropic_version

        # Handle endpoints update
        if request.endpoints is not None:
            provider_def.endpoints = [
                Endpoint(
                    url=ep.url,
                    name=ep.name or f"Endpoint {i+1}",
                    priority=ep.priority,
                    purpose=ep.purpose,
                )
                for i, ep in enumerate(request.endpoints)
            ]

        # Invalidate cached provider instance
        tl.provider_manager.invalidate_cache(provider_id)
        tl.config.mark_changed()

        return {
            "status": "updated",
            "provider": {
                "id": provider_def.id,
                "name": provider_def.name,
                "type": provider_def.type,
                "has_api_key": bool(provider_def.get_api_key()),
                "endpoints": [ep.to_dict() for ep in provider_def.endpoints],
                "default_model": provider_def.default_model,
            }
        }

    @app.delete("/api/providers/{provider_id}")
    async def delete_provider(provider_id: str):
        """Delete a provider definition.

        Note: Models referencing this provider will fall back to the default provider.
        """
        tl = get_threadlight()

        if provider_id not in tl.config.providers:
            raise HTTPException(status_code=404, detail=f"Provider not found: {provider_id}")

        tl.config.delete_provider(provider_id)
        tl.provider_manager.invalidate_cache(provider_id)
        tl.config.mark_changed()

        return {"status": "deleted", "provider_id": provider_id}

    @app.post("/api/providers/{provider_id}/test")
    async def test_provider(provider_id: str):
        """Test connectivity to a specific provider.

        Attempts to connect to the provider's endpoints and verify
        authentication is working.
        """
        import httpx

        tl = get_threadlight()

        provider_def = tl.config.providers.get(provider_id)
        if not provider_def:
            raise HTTPException(status_code=404, detail=f"Provider not found: {provider_id}")

        api_key = provider_def.get_api_key()
        api_base = provider_def.api_base

        if not api_base:
            return {
                "status": "error",
                "message": "No endpoint configured for this provider",
            }

        if provider_def.type == "local" and "localhost" in api_base:
            # Local providers may not require authentication
            pass
        elif not api_key and provider_def.type not in ("local",):
            return {
                "status": "error",
                "message": "API key is required for this provider",
            }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {"Content-Type": "application/json"}
                if api_key:
                    if provider_def.type == "anthropic":
                        headers["x-api-key"] = api_key
                        headers["anthropic-version"] = provider_def.anthropic_version
                    else:
                        headers["Authorization"] = f"Bearer {api_key}"

                # Add extra headers if any
                if provider_def.extra_headers:
                    headers.update(provider_def.extra_headers)

                # Try to list models or make a minimal request
                if provider_def.type == "anthropic":
                    # Anthropic doesn't have a models endpoint, test with a minimal message
                    response = await client.post(
                        f"{api_base}/v1/messages",
                        headers=headers,
                        json={
                            "model": provider_def.default_model or "claude-3-haiku-20240307",
                            "max_tokens": 1,
                            "messages": [{"role": "user", "content": "test"}],
                        },
                    )
                    if response.status_code in (200, 400):  # 400 might be bad model but auth works
                        provider_def.is_healthy = True
                        return {"status": "success", "message": "Provider is accessible"}
                    elif response.status_code == 401:
                        provider_def.is_healthy = False
                        return {"status": "error", "message": "Invalid API key"}
                    else:
                        provider_def.is_healthy = False
                        return {"status": "error", "message": f"Error: {response.status_code}"}
                else:
                    # OpenAI-compatible: try /models endpoint
                    response = await client.get(f"{api_base}/models", headers=headers)
                    if response.status_code == 200:
                        data = response.json()
                        model_count = len(data.get("data", []))
                        provider_def.is_healthy = True
                        return {
                            "status": "success",
                            "message": f"Connected ({model_count} models available)",
                        }
                    elif response.status_code == 401:
                        provider_def.is_healthy = False
                        return {"status": "error", "message": "Invalid API key"}
                    elif response.status_code == 404:
                        # No models endpoint, try a minimal completion
                        chat_response = await client.post(
                            f"{api_base}/chat/completions",
                            headers=headers,
                            json={
                                "model": provider_def.default_model or "gpt-3.5-turbo",
                                "messages": [{"role": "user", "content": "test"}],
                                "max_tokens": 1,
                            },
                        )
                        if chat_response.status_code in (200, 400):
                            provider_def.is_healthy = True
                            return {"status": "success", "message": "Provider is accessible"}
                        else:
                            provider_def.is_healthy = False
                            return {"status": "error", "message": f"Error: {chat_response.status_code}"}
                    else:
                        provider_def.is_healthy = False
                        return {"status": "error", "message": f"Error: {response.status_code}"}

        except httpx.ConnectError:
            provider_def.is_healthy = False
            return {"status": "error", "message": "Could not connect to provider"}
        except httpx.TimeoutException:
            provider_def.is_healthy = False
            return {"status": "error", "message": "Connection timed out"}
        except Exception as e:
            provider_def.is_healthy = False
            return {"status": "error", "message": f"Error: {str(e)}"}

    @app.get("/api/providers/{provider_id}/models")
    async def get_provider_models(provider_id: str):
        """List available models from a specific provider."""
        import httpx

        tl = get_threadlight()

        provider_def = tl.config.providers.get(provider_id)
        if not provider_def:
            raise HTTPException(status_code=404, detail=f"Provider not found: {provider_id}")

        api_key = provider_def.get_api_key()
        api_base = provider_def.api_base

        if not api_base:
            return {"status": "error", "message": "No endpoint configured", "models": []}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {"Content-Type": "application/json"}
                if api_key:
                    if provider_def.type == "anthropic":
                        # Anthropic doesn't support model listing
                        return {
                            "status": "success",
                            "models": [
                                {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus"},
                                {"id": "claude-3-sonnet-20240229", "name": "Claude 3 Sonnet"},
                                {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku"},
                                {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet"},
                            ],
                            "message": "Anthropic models (pre-defined list)",
                        }
                    else:
                        headers["Authorization"] = f"Bearer {api_key}"

                response = await client.get(f"{api_base}/models", headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    raw_models = data.get("data", data.get("models", []))

                    models = []
                    for model in raw_models:
                        if isinstance(model, str):
                            models.append({"id": model, "name": model})
                        elif isinstance(model, dict):
                            model_id = model.get("id") or model.get("name")
                            if model_id:
                                models.append({
                                    "id": model_id,
                                    "name": model.get("name") or model_id,
                                    "owned_by": model.get("owned_by"),
                                })

                    models.sort(key=lambda m: m.get("name", "").lower())
                    return {"status": "success", "models": models}
                else:
                    return {
                        "status": "error",
                        "message": f"Error: {response.status_code}",
                        "models": [],
                    }

        except Exception as e:
            return {"status": "error", "message": str(e), "models": []}

    @app.get("/api/models/{model_id:path}/provider")
    async def get_model_provider(model_id: str):
        """Get which provider is configured for a specific model."""
        tl = get_threadlight()

        model_config = tl.config.model_configs.get(model_id)
        if model_config and model_config.provider_id:
            provider_def = tl.config.providers.get(model_config.provider_id)
            if provider_def:
                return {
                    "model_id": model_id,
                    "provider_id": provider_def.id,
                    "provider_name": provider_def.name,
                    "provider_type": provider_def.type,
                }

        # Model uses default provider
        return {
            "model_id": model_id,
            "provider_id": None,
            "provider_name": "Default Provider",
            "provider_type": tl.config.provider.type,
            "uses_default": True,
        }

    @app.put("/api/models/{model_id:path}/provider")
    async def set_model_provider(model_id: str, request: ModelProviderRequest):
        """Set which provider a model should use."""
        tl = get_threadlight()

        # Validate provider exists if specified
        if request.provider_id and request.provider_id not in tl.config.providers:
            raise HTTPException(
                status_code=404,
                detail=f"Provider not found: {request.provider_id}"
            )

        # Get or create model config
        model_config = tl.config.get_model_config(model_id)
        model_config.provider_id = request.provider_id
        tl.config.set_model_config(model_id, model_config)

        return {
            "status": "updated",
            "model_id": model_id,
            "provider_id": request.provider_id,
        }

    @app.post("/api/providers/migrate")
    async def migrate_to_multi_provider():
        """Migrate legacy single-provider config to multi-provider format.

        Creates a provider definition from the existing ProviderConfig
        if no providers are configured yet.
        """
        tl = get_threadlight()

        if tl.config.providers:
            return {
                "status": "skipped",
                "message": "Providers already configured",
                "count": len(tl.config.providers),
            }

        tl.config.migrate_single_provider_to_multi()
        tl.config.mark_changed()

        return {
            "status": "migrated",
            "providers": list(tl.config.providers.keys()),
            "count": len(tl.config.providers),
        }

    # ========================================================================
    # Import Endpoints
    # ========================================================================

    @app.post("/api/import/text")
    async def import_text(request: ImportTextRequest):
        """Import memories from text content."""
        tl = get_threadlight()

        from threadlight.import_.text_importer import ImportedMemory

        # Split on double newlines to support multi-line memories
        memories = request.content.strip().split('\n\n')
        imported = 0
        errors = 0

        for i, memory_text in enumerate(memories, 1):
            memory_text = memory_text.strip()
            if not memory_text:
                continue

            try:
                # Create an imported memory capsule using the "note" type
                capsule = tl.memory.create(
                    type="note",
                    content={
                        "content": memory_text,
                        "source": request.source_name,
                    },
                    cue_phrases=_extract_cue_phrases(memory_text),
                    retention="normal",
                    consent_confirmed=True,
                )
                imported += 1
            except Exception as e:
                logger.warning(f"Failed to import memory {i}: {e}")
                errors += 1

        return {
            "imported": imported,
            "errors": errors,
            "total_memories": len(memories),
        }

    @app.post("/api/import/file")
    async def import_file(
        file: UploadFile = File(...),
        source_name: str = Form(None),
        tags: str = Form(None),
    ):
        """Import memories from an uploaded file."""
        tl = get_threadlight()

        content = await file.read()
        text_content = content.decode('utf-8')

        source = source_name or file.filename or "uploaded-file"
        tag_list = tags.split(',') if tags else []

        # Import as text
        lines = text_content.strip().split('\n')
        imported = 0

        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue

            try:
                # Use "about" field to indicate source; tags not supported in simplified note type
                about_context = source if not tag_list else f"{source} [{', '.join(tag_list)}]"
                tl.memory.create(
                    type="note",
                    content={
                        "content": line,
                        "about": about_context,
                    },
                    cue_phrases=_extract_cue_phrases(line),
                    retention="normal",
                    consent_confirmed=True,
                )
                imported += 1
            except Exception:
                pass

        return {
            "filename": file.filename,
            "imported": imported,
            "total_lines": len(lines),
        }

    @app.post("/api/import/conversations")
    async def import_conversations(
        file: UploadFile = File(...),
        profile_id: str = Form(None),
    ):
        """
        Import conversations from Claude or ChatGPT exports.

        Supported formats:
        - .zip files (Claude's claude-conversations.zip or ChatGPT export)
        - .json files (conversations.json from either platform)

        The format is auto-detected from the file structure.
        If profile_id is provided, imported conversations are scoped to that profile.
        """
        import tempfile
        import os

        from threadlight.import_.claude_export import import_claude_export
        from threadlight.import_.chatgpt_export import import_chatgpt_export

        tl = get_threadlight()
        storage = tl.storage

        # Determine the profile scope for imported conversations
        profile_scope = profile_id
        profile_name = None
        if profile_scope:
            # Verify the profile exists
            profile = tl.storage.get_profile(profile_scope)
            if profile:
                profile_name = profile.name
            else:
                return {"error": f"Profile not found: {profile_scope}"}

        # Save uploaded file to temp location
        suffix = Path(file.filename).suffix if file.filename else ".zip"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # Determine file type and source
            filename = file.filename or "upload"
            is_zip = suffix.lower() == ".zip"

            # Try to auto-detect the source (Claude vs ChatGPT)
            # ChatGPT exports typically have a different structure
            source_type = "unknown"

            if is_zip:
                import zipfile
                try:
                    with zipfile.ZipFile(tmp_path, 'r') as zf:
                        file_list = zf.namelist()
                        # Claude exports have projects.json, ChatGPT has model_comparisons.json
                        if any('projects.json' in f for f in file_list):
                            source_type = "claude"
                        elif any('model_comparisons.json' in f or 'user.json' in f for f in file_list):
                            source_type = "chatgpt"
                        elif any('conversations.json' in f for f in file_list):
                            # Need to peek at the structure
                            for f in file_list:
                                if 'conversations.json' in f:
                                    with zf.open(f) as conv_file:
                                        # Read first few bytes to determine format
                                        sample = conv_file.read(1000).decode('utf-8', errors='ignore')
                                        if '"chat_messages"' in sample:
                                            source_type = "claude"
                                        elif '"mapping"' in sample:
                                            source_type = "chatgpt"
                                    break
                except zipfile.BadZipFile:
                    return {"error": "Invalid zip file"}

            elif suffix.lower() == ".json":
                # Peek at the JSON structure
                try:
                    import json
                    with open(tmp_path, 'r', encoding='utf-8') as f:
                        # Read just enough to determine format
                        sample = f.read(2000)
                        if '"chat_messages"' in sample:
                            source_type = "claude"
                        elif '"mapping"' in sample:
                            source_type = "chatgpt"
                except Exception:
                    pass

            # Import based on detected type
            result = None
            if source_type == "claude":
                result = import_claude_export(
                    path=tmp_path,
                    storage=storage,
                    import_conversations=True,
                    import_projects=True,
                    create_styles=True,
                    skip_empty_conversations=True,
                    profile_scope=profile_scope,
                )
                return {
                    "success": result.success,
                    "source": "claude",
                    "conversations_imported": result.total_conversations,
                    "messages_imported": result.total_messages,
                    "projects_imported": result.total_projects,
                    "errors": result.errors,
                    "profile_scope": profile_scope,
                    "profile_name": profile_name,
                }

            elif source_type == "chatgpt":
                result = import_chatgpt_export(
                    path=tmp_path,
                    storage=storage,
                    skip_empty_conversations=True,
                    profile_scope=profile_scope,
                )
                return {
                    "success": result.success,
                    "source": "chatgpt",
                    "conversations_imported": result.total_conversations,
                    "messages_imported": result.total_messages,
                    "errors": result.errors,
                    "profile_scope": profile_scope,
                    "profile_name": profile_name,
                }

            else:
                # Try both and see which works
                # First try Claude format
                result = import_claude_export(
                    path=tmp_path,
                    storage=storage,
                    import_conversations=True,
                    import_projects=True,
                    skip_empty_conversations=True,
                    profile_scope=profile_scope,
                )

                if result.success and result.total_conversations > 0:
                    return {
                        "success": True,
                        "source": "claude",
                        "conversations_imported": result.total_conversations,
                        "messages_imported": result.total_messages,
                        "projects_imported": result.total_projects,
                        "errors": result.errors,
                        "profile_scope": profile_scope,
                        "profile_name": profile_name,
                    }

                # Try ChatGPT format
                result = import_chatgpt_export(
                    path=tmp_path,
                    storage=storage,
                    skip_empty_conversations=True,
                    profile_scope=profile_scope,
                )

                if result.success and result.total_conversations > 0:
                    return {
                        "success": True,
                        "source": "chatgpt",
                        "conversations_imported": result.total_conversations,
                        "messages_imported": result.total_messages,
                        "errors": result.errors,
                        "profile_scope": profile_scope,
                        "profile_name": profile_name,
                    }

                return {
                    "success": False,
                    "error": "Could not detect export format. Make sure the file is a valid Claude or ChatGPT export.",
                }

        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    # ========================================================================
    # Semantic Search Endpoints
    # ========================================================================

    @app.post("/api/search/semantic")
    async def semantic_search(request: SemanticSearchRequest):
        """
        Perform semantic search over memories and conversations.

        Requires embeddings to be enabled and generated.
        """
        tl = get_threadlight()

        if not tl.config.memory.embeddings.enabled:
            raise HTTPException(
                status_code=400,
                detail="Embeddings not enabled. Enable embeddings in config first."
            )

        try:
            results = []

            if request.include_memories:
                memory_results = tl.search_memories_semantic(
                    query=request.query,
                    limit=request.limit,
                    threshold=request.threshold,
                )
                results.extend([r.to_dict() for r in memory_results])

            if request.include_conversations:
                conv_results = tl.search_conversations_semantic(
                    query=request.query,
                    limit=request.limit,
                    threshold=request.threshold,
                )
                results.extend([r.to_dict() for r in conv_results])

            # Sort combined results by similarity and limit
            results.sort(key=lambda r: r.get("similarity_score", 0), reverse=True)
            results = results[:request.limit]

            return {
                "query": request.query,
                "results": results,
                "count": len(results),
            }

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/embeddings/generate")
    async def generate_embeddings(request: GenerateEmbeddingsRequest):
        """
        Generate embeddings for memories and conversations that don't have them.

        This can take a while for large datasets.
        """
        tl = get_threadlight()

        if not tl.config.memory.embeddings.enabled:
            raise HTTPException(
                status_code=400,
                detail="Embeddings not enabled. Enable embeddings in config first."
            )

        try:
            stats = tl.generate_embeddings(
                include_memories=request.include_memories,
                include_messages=request.include_conversations,
            )
            return stats.to_dict()

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/embeddings/generate/stream")
    async def generate_embeddings_stream(request: GenerateEmbeddingsRequest):
        """
        Generate embeddings with real-time progress updates via Server-Sent Events.

        Streams progress updates as JSON events:
        - type: "progress" - Periodic progress update with current stats
        - type: "complete" - Final stats when generation is complete
        - type: "error" - Error information if generation fails
        """
        tl = get_threadlight()

        if not tl.config.memory.embeddings.enabled:
            raise HTTPException(
                status_code=400,
                detail="Embeddings not enabled. Enable embeddings in config first."
            )

        # Get total counts for progress calculation
        manager = tl._get_embedding_manager()
        if manager is None:
            raise HTTPException(
                status_code=500,
                detail="Embedding manager not initialized."
            )

        # Count items to process
        total_capsules = len(manager.get_capsules_needing_embeddings()) if request.include_memories else 0
        total_messages = len(manager.get_messages_needing_embeddings()) if request.include_conversations else 0
        total_items = total_capsules + total_messages

        # Shared state for progress tracking
        progress_state = {
            "last_stats": None,
            "total_capsules": total_capsules,
            "total_messages": total_messages,
            "total_items": total_items,
        }

        async def event_generator():
            import queue
            import threading

            progress_queue: queue.Queue = queue.Queue()
            generation_complete = threading.Event()
            generation_error: list = []

            def progress_callback(stats):
                """Called by the embedding manager with progress updates."""
                progress_queue.put(stats)

            def run_generation():
                """Run the embedding generation in a background thread."""
                try:
                    final_stats = tl.generate_embeddings(
                        include_memories=request.include_memories,
                        include_messages=request.include_conversations,
                        progress_callback=progress_callback,
                    )
                    progress_queue.put(("complete", final_stats))
                except Exception as e:
                    generation_error.append(str(e))
                    progress_queue.put(("error", str(e)))
                finally:
                    generation_complete.set()

            # Start generation in background thread
            thread = threading.Thread(target=run_generation)
            thread.start()

            # Send initial progress event
            initial_data = {
                "type": "progress",
                "total_capsules": total_capsules,
                "total_messages": total_messages,
                "total_items": total_items,
                "capsules_processed": 0,
                "capsules_updated": 0,
                "messages_processed": 0,
                "messages_updated": 0,
                "percent_complete": 0,
            }
            yield f"data: {json.dumps(initial_data)}\n\n"

            # Stream progress updates
            while not generation_complete.is_set() or not progress_queue.empty():
                try:
                    item = progress_queue.get(timeout=0.1)

                    if isinstance(item, tuple):
                        event_type, data = item
                        if event_type == "complete":
                            # Final completion event
                            stats = data
                            completion_data = {
                                "type": "complete",
                                "total_capsules": total_capsules,
                                "total_messages": total_messages,
                                "total_items": total_items,
                                "capsules_processed": stats.capsules_processed,
                                "capsules_updated": stats.capsules_updated,
                                "messages_processed": stats.messages_processed,
                                "messages_updated": stats.messages_updated,
                                "errors": stats.errors,
                                "duration_seconds": stats.duration_seconds,
                                "percent_complete": 100,
                            }
                            yield f"data: {json.dumps(completion_data)}\n\n"
                        elif event_type == "error":
                            error_data = {
                                "type": "error",
                                "error": data,
                            }
                            yield f"data: {json.dumps(error_data)}\n\n"
                    else:
                        # Progress update (EmbeddingStats object)
                        stats = item
                        processed = stats.capsules_updated + stats.messages_updated
                        percent = (processed / total_items * 100) if total_items > 0 else 0

                        progress_data = {
                            "type": "progress",
                            "total_capsules": total_capsules,
                            "total_messages": total_messages,
                            "total_items": total_items,
                            "capsules_processed": stats.capsules_processed,
                            "capsules_updated": stats.capsules_updated,
                            "messages_processed": stats.messages_processed,
                            "messages_updated": stats.messages_updated,
                            "errors": stats.errors,
                            "duration_seconds": stats.duration_seconds,
                            "percent_complete": round(percent, 1),
                        }
                        yield f"data: {json.dumps(progress_data)}\n\n"

                except queue.Empty:
                    # No updates available, continue waiting
                    await asyncio.sleep(0.1)

            thread.join()

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable buffering in nginx
            }
        )

    @app.get("/api/embeddings/stats")
    async def get_embedding_stats():
        """Get statistics about embedding coverage."""
        tl = get_threadlight()

        if not tl.config.memory.embeddings.enabled:
            return {
                "enabled": False,
                "message": "Embeddings not enabled in config.",
            }

        try:
            stats = tl.get_embedding_stats()
            stats["enabled"] = True
            return stats

        except Exception as e:
            logger.error(f"Failed to get embedding stats: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/embeddings/enable")
    async def enable_embeddings(request: EmbeddingsConfigRequest):
        """Enable or disable embeddings and configure the provider."""
        tl = get_threadlight()

        try:
            tl.config.memory.embeddings.enabled = request.enabled
            tl.config.memory.embeddings.provider = request.provider
            tl.config.memory.embeddings.model = request.model

            # Save config
            tl.save_config()

            return {
                "enabled": request.enabled,
                "provider": request.provider,
                "model": request.model,
                "message": "Embeddings configuration updated. Restart may be required for some changes.",
            }

        except Exception as e:
            logger.error(f"Failed to enable embeddings: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/embeddings")
    async def clear_embeddings():
        """
        Clear all embeddings from memories and messages.

        This is useful when switching embedding models, as embeddings from
        different models are incompatible (different dimensions/semantic spaces).
        After clearing, you'll need to regenerate embeddings with the new model.
        """
        tl = get_threadlight()

        try:
            result = tl.clear_all_embeddings()

            return {
                "status": "cleared",
                "count": result["count"],
                "capsules_cleared": result["capsules_cleared"],
                "messages_cleared": result["messages_cleared"],
                "message": f"Cleared {result['count']} embeddings ({result['capsules_cleared']} memories, {result['messages_cleared']} messages)",
            }

        except Exception as e:
            logger.error(f"Failed to clear embeddings: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # ========================================================================
    # Conversation Management Endpoints
    # ========================================================================

    @app.get("/api/conversations")
    async def list_conversations_api(
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
        source: Optional[str] = None,
        search: Optional[str] = None,
    ):
        """List all conversations, with optional search.

        Args:
            include_archived: Include archived conversations
            limit: Maximum number to return
            offset: Pagination offset
            source: Filter by source (local, claude, chatgpt). If None, returns all sources.
            search: Search query to match against conversation titles AND message content.
                    Uses full-text search for efficient content matching.
        """
        tl = get_threadlight()

        if search and search.strip():
            # Use search method when query provided
            conversations = tl.storage.search_conversations(
                query=search,
                limit=limit,
                offset=offset,
                source=source,
                include_archived=include_archived,
            )
        else:
            # Standard listing without search
            conversations = tl.storage.list_conversations(
                limit=limit,
                offset=offset,
                source=source,
                include_archived=include_archived,
            )

        return {
            "conversations": [c.to_dict() for c in conversations],
            "count": len(conversations),
            "search": search if search else None,
        }

    @app.post("/api/conversations")
    async def create_conversation_api(request: ConversationCreateRequest):
        """Create a new conversation, optionally as a group chat with multiple profiles."""
        tl = get_threadlight()
        from threadlight.storage.base import Conversation
        from datetime import datetime

        # Check if this is a group chat request
        if request.participant_profiles and len(request.participant_profiles) > 1:
            # Use the core method for group chat creation
            try:
                conversation = tl.create_group_conversation(
                    name=request.name,
                    profile_ids=request.participant_profiles,
                )
                # Update model name if provided
                if request.model:
                    conversation.model = request.model
                    tl.storage.update_conversation(conversation)
                return conversation.to_dict()
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        # Regular single-profile conversation
        # Determine model name: use provided, or active profile, or current model config
        model_name = request.model
        if not model_name:
            if tl.active_profile:
                model_name = tl.active_profile.primary_model
            else:
                model_name = tl.config.provider.model

        # Handle single participant_profile
        participant_profiles = []
        if request.participant_profiles:
            participant_profiles = request.participant_profiles

        # Build metadata with purpose if provided
        metadata = {}
        if request.purpose:
            metadata["purpose"] = request.purpose

        conversation = Conversation(
            id=str(uuid.uuid4()),
            name=request.name,
            source="local",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            message_count=0,
            model=model_name,
            participant_profiles=participant_profiles,
            metadata=metadata,
        )

        tl.storage.save_conversation(conversation)

        return conversation.to_dict()

    @app.get("/api/conversations/{conversation_id}")
    async def get_conversation_api(conversation_id: str):
        """Get a conversation by ID."""
        tl = get_threadlight()

        conversation = tl.storage.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return conversation.to_dict()

    @app.put("/api/conversations/{conversation_id}")
    async def update_conversation_api(conversation_id: str, request: ConversationUpdateRequest):
        """Update a conversation (rename, archive, update participants, etc.)."""
        tl = get_threadlight()

        conversation = tl.storage.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        if request.name is not None:
            conversation.name = request.name
        if request.archived is not None:
            conversation.archived = request.archived
        if request.model is not None:
            conversation.model = request.model
        if request.participant_profiles is not None:
            conversation.participant_profiles = request.participant_profiles
        if request.purpose is not None:
            # Update metadata.purpose
            if not conversation.metadata:
                conversation.metadata = {}
            if request.purpose == "":
                # Empty string means remove the purpose
                conversation.metadata.pop('purpose', None)
            else:
                conversation.metadata['purpose'] = request.purpose

        tl.storage.update_conversation(conversation)

        return conversation.to_dict()

    @app.post("/api/conversations/{conversation_id}/archive")
    async def archive_conversation_api(conversation_id: str):
        """Archive a conversation."""
        tl = get_threadlight()

        conversation = tl.storage.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        conversation.archived = True
        tl.storage.update_conversation(conversation)

        return {"status": "archived", "id": conversation_id}

    @app.post("/api/conversations/{conversation_id}/unarchive")
    async def unarchive_conversation_api(conversation_id: str):
        """Unarchive a conversation."""
        tl = get_threadlight()

        conversation = tl.storage.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        conversation.archived = False
        tl.storage.update_conversation(conversation)

        return {"status": "unarchived", "id": conversation_id}

    @app.delete("/api/conversations/{conversation_id}")
    async def delete_conversation_api(conversation_id: str):
        """Delete a conversation and all its messages."""
        tl = get_threadlight()

        success = tl.storage.delete_conversation(conversation_id)
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return {"status": "deleted", "id": conversation_id}

    @app.get("/api/conversations/{conversation_id}/messages")
    async def get_conversation_messages_api(
        conversation_id: str,
        limit: int = 100,
        offset: int = 0,
    ):
        """Get all messages in a conversation."""
        tl = get_threadlight()

        conversation = tl.storage.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        messages = tl.storage.get_messages(conversation_id, limit=limit, offset=offset)

        return {
            "messages": [m.to_dict() for m in messages],
            "count": len(messages),
            "conversation_id": conversation_id,
        }

    @app.post("/api/conversations/{conversation_id}/messages")
    async def add_message_to_conversation_api(
        conversation_id: str,
        role: str,
        content: str,
    ):
        """Add a message to a conversation."""
        tl = get_threadlight()
        from threadlight.storage.base import Message as StorageMessage
        from datetime import datetime

        conversation = tl.storage.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        message = StorageMessage(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role=role,
            content=content,
            timestamp=datetime.utcnow(),
            source="local",
        )

        tl.storage.save_message(message)

        # Update conversation message count and timestamp
        conversation.message_count += 1
        tl.storage.update_conversation(conversation)

        return message.to_dict()

    # ========================================================================
    # Group Chat Endpoints
    # ========================================================================

    @app.post("/api/conversations/{conversation_id}/group-chat")
    async def group_chat_api(conversation_id: str, request: GroupChatRequest):
        """
        Send a message to a group chat and get responses from all participating profiles.

        Each profile responds in turn, seeing the previous profiles' responses
        tagged in their context.

        Returns:
            List of responses with profile info and content
        """
        tl = get_threadlight()

        conversation = tl.storage.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Check if this is a group chat
        profile_ids = request.profile_ids or conversation.participant_profiles
        if not profile_ids:
            raise HTTPException(
                status_code=400,
                detail="No profiles specified. Either provide profile_ids or use a conversation with participant_profiles."
            )

        try:
            responses = tl.group_chat(
                message=request.message,
                conversation_id=conversation_id,
                profile_ids=profile_ids,
            )
            return {
                "conversation_id": conversation_id,
                "message": request.message,
                "responses": responses,
                "is_group_chat": len(profile_ids) > 1,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/conversations/{conversation_id}/group-chat/stream")
    async def group_chat_stream_api(conversation_id: str, request: GroupChatRequest):
        """
        Stream responses from a group chat via Server-Sent Events (SSE).

        Each profile responds in turn, streaming their response. Events include:
        - profile_start: A profile is beginning to respond
        - chunk: A piece of text from the current profile
        - profile_complete: A profile finished responding
        - error: An error occurred
        - complete: All profiles have responded

        This is an alternative to the WebSocket endpoint for clients that prefer SSE.
        """
        tl = get_threadlight()

        conversation = tl.storage.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        profile_ids = request.profile_ids or conversation.participant_profiles
        if not profile_ids:
            raise HTTPException(
                status_code=400,
                detail="No profiles specified. Either provide profile_ids or use a conversation with participant_profiles."
            )

        async def generate():
            try:
                for event in tl.stream_group_chat(
                    message=request.message,
                    conversation_id=conversation_id,
                    profile_ids=profile_ids,
                ):
                    yield f"data: {json.dumps(event)}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    @app.post("/api/conversations/{conversation_id}/add-profile")
    async def add_profile_to_conversation_api(conversation_id: str, profile_id: str):
        """Add a profile to a conversation's participants."""
        tl = get_threadlight()

        conversation = tl.storage.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        profile = tl.get_profile(profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail=f"Profile not found: {profile_id}")

        if profile_id in conversation.participant_profiles:
            return {
                "status": "already_present",
                "conversation_id": conversation_id,
                "profile_id": profile_id,
                "participant_profiles": conversation.participant_profiles,
            }

        conversation.participant_profiles.append(profile_id)
        tl.storage.update_conversation(conversation)

        return {
            "status": "added",
            "conversation_id": conversation_id,
            "profile_id": profile_id,
            "participant_profiles": conversation.participant_profiles,
        }

    @app.post("/api/conversations/{conversation_id}/remove-profile")
    async def remove_profile_from_conversation_api(conversation_id: str, profile_id: str):
        """Remove a profile from a conversation's participants."""
        tl = get_threadlight()

        conversation = tl.storage.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        if profile_id not in conversation.participant_profiles:
            return {
                "status": "not_present",
                "conversation_id": conversation_id,
                "profile_id": profile_id,
                "participant_profiles": conversation.participant_profiles,
            }

        conversation.participant_profiles.remove(profile_id)
        tl.storage.update_conversation(conversation)

        return {
            "status": "removed",
            "conversation_id": conversation_id,
            "profile_id": profile_id,
            "participant_profiles": conversation.participant_profiles,
        }

    # ========================================================================
    # Message Management Endpoints
    # ========================================================================

    @app.get("/api/messages/{message_id}")
    async def get_message_api(message_id: str):
        """Get a single message by ID."""
        tl = get_threadlight()

        message = tl.storage.get_message(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        return message.to_dict()

    @app.put("/api/messages/{message_id}")
    async def update_message_api(message_id: str, request: MessageUpdateRequest):
        """Edit a message's content."""
        tl = get_threadlight()

        message = tl.storage.get_message(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        message.content = request.content
        tl.storage.update_message(message)

        return message.to_dict()

    @app.delete("/api/messages/{message_id}")
    async def delete_message_api(message_id: str):
        """Delete a single message."""
        tl = get_threadlight()

        message = tl.storage.get_message(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        # Update conversation message count
        conversation = tl.storage.get_conversation(message.conversation_id)
        if conversation:
            conversation.message_count = max(0, conversation.message_count - 1)
            tl.storage.update_conversation(conversation)

        tl.storage.delete_message(message_id)

        return {"status": "deleted", "id": message_id}

    @app.delete("/api/messages/{message_id}/and-after")
    async def delete_message_and_after_api(message_id: str):
        """Delete a message and all messages after it (for regeneration)."""
        tl = get_threadlight()

        message = tl.storage.get_message(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        deleted_count = tl.storage.delete_messages_after(
            message.conversation_id,
            message_id
        )

        # Update conversation message count
        conversation = tl.storage.get_conversation(message.conversation_id)
        if conversation:
            conversation.message_count = max(0, conversation.message_count - deleted_count)
            tl.storage.update_conversation(conversation)

        return {"status": "deleted", "count": deleted_count}

    @app.get("/api/messages/{message_id}/variants")
    async def get_message_variants_api(message_id: str):
        """Get all variants for a message's variant group.

        If the message has a variant_group_id, returns all messages in that group.
        If not, returns just the single message (it has no variants).
        """
        tl = get_threadlight()

        message = tl.storage.get_message(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        if not message.variant_group_id:
            # No variant group - this is the only variant
            return {
                "variants": [message.to_dict()],
                "variant_group_id": None,
                "current_index": 0,
            }

        variants = tl.storage.get_message_variants(message.variant_group_id)
        # Find the index of the requested message within the variants
        current_index = 0
        for i, v in enumerate(variants):
            if v.id == message_id:
                current_index = i
                break

        return {
            "variants": [v.to_dict() for v in variants],
            "variant_group_id": message.variant_group_id,
            "current_index": current_index,
        }

    @app.post("/api/messages/{message_id}/regenerate")
    async def regenerate_message_api(message_id: str):
        """Prepare a message for regeneration by creating a variant group.

        This assigns a variant_group_id to the message if it doesn't have one,
        and returns the information needed for the frontend to create a new variant
        after the LLM response comes back.
        """
        tl = get_threadlight()
        from threadlight.storage.base import Message as StorageMessage

        message = tl.storage.get_message(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        if message.role != "assistant":
            raise HTTPException(status_code=400, detail="Can only regenerate assistant messages")

        # Assign variant_group_id if this is the first regeneration
        if not message.variant_group_id:
            message.variant_group_id = str(uuid.uuid4())
            message.variant_index = 0
            tl.storage.save_message(message)  # Uses INSERT OR REPLACE

        # Find the previous user message for re-sending
        conv_messages = tl.storage.get_messages(message.conversation_id, limit=1000)
        user_message_content = None
        for i, m in enumerate(conv_messages):
            if m.id == message_id and i > 0:
                # Walk backwards to find the user message
                for j in range(i - 1, -1, -1):
                    if conv_messages[j].role == "user":
                        user_message_content = conv_messages[j].content
                        break
                break

        if not user_message_content:
            raise HTTPException(status_code=400, detail="No previous user message found")

        # Calculate next variant index
        variants = tl.storage.get_message_variants(message.variant_group_id)
        next_index = max(v.variant_index for v in variants) + 1

        return {
            "variant_group_id": message.variant_group_id,
            "next_variant_index": next_index,
            "user_message": user_message_content,
            "conversation_id": message.conversation_id,
        }

    @app.post("/api/messages/save-variant")
    async def save_variant_message_api(request: dict):
        """Save a new variant message after LLM generates a response.

        Expected request body:
        {
            "conversation_id": "...",
            "content": "...",
            "variant_group_id": "...",
            "variant_index": 1,
            "profile_id": "..." (optional),
            "model_used": "..." (optional)
        }
        """
        tl = get_threadlight()
        from threadlight.storage.base import Message as StorageMessage
        from datetime import datetime as dt

        conversation_id = request.get("conversation_id")
        content = request.get("content")
        variant_group_id = request.get("variant_group_id")
        variant_index = request.get("variant_index", 0)

        if not all([conversation_id, content, variant_group_id]):
            raise HTTPException(status_code=400, detail="Missing required fields")

        message = StorageMessage(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            timestamp=dt.utcnow(),
            source="local",
            metadata={},
            profile_id=request.get("profile_id"),
            model_used=request.get("model_used"),
            variant_group_id=variant_group_id,
            variant_index=variant_index,
        )

        tl.storage.save_message(message)

        return message.to_dict()

    # ========================================================================
    # Memory Type Management Endpoints
    # ========================================================================

    @app.get("/api/memory-types")
    async def list_memory_types(include_builtin: bool = True, include_hidden: bool = False):
        """
        List all available memory types (built-in + custom).

        Returns both built-in types (relational, myth_seed, etc.) and
        user-defined custom types.

        Args:
            include_builtin: Whether to include built-in types
            include_hidden: Whether to include hidden built-in types
        """
        tl = get_threadlight()
        types = tl.memory_types.list(include_builtin=include_builtin, include_hidden=include_hidden)

        # Also get hidden built-ins separately for "restore" functionality
        hidden_builtins = tl.memory_types.list_hidden_builtins() if not include_hidden else []

        return {
            "types": types,
            "count": len(types),
            "builtin_count": sum(1 for t in types if t.get("is_builtin", False)),
            "custom_count": sum(1 for t in types if not t.get("is_builtin", False)),
            "hidden_builtins": hidden_builtins,
            "hidden_count": len(hidden_builtins),
        }

    @app.get("/api/memory-types/examples")
    async def list_example_types():
        """List available example types that can be imported."""
        tl = get_threadlight()
        examples = tl.list_example_types()

        return {
            "examples": examples,
            "count": len(examples),
        }

    @app.get("/api/memory-types/{type_id}")
    async def get_memory_type(type_id: str):
        """Get a specific memory type definition."""
        tl = get_threadlight()
        type_def = tl.get_memory_type(type_id)

        if type_def is None:
            raise HTTPException(status_code=404, detail=f"Memory type not found: {type_id}")

        return type_def

    @app.post("/api/memory-types")
    async def create_memory_type(request: MemoryTypeRequest):
        """
        Create a new custom memory type.

        Custom types allow you to define your own structured memory formats
        with custom fields, validation, and display templates.
        """
        tl = get_threadlight()

        # Check if type already exists
        existing = tl.get_memory_type(request.type_id)
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Memory type already exists: {request.type_id}"
            )

        try:
            # Convert Pydantic models to dicts, handling field_type/type aliasing
            fields = []
            for f in request.fields:
                field_dict = f.model_dump()
                # Support both field_type (new) and type (legacy) field names
                field_type = field_dict.get("field_type") or field_dict.get("type") or "string"
                # Support both output_template (new) and template (legacy)
                output_template = field_dict.get("output_template") or field_dict.get("template") or ""
                fields.append({
                    "name": field_dict["name"],
                    "type": field_type,
                    "required": field_dict.get("required", True),
                    "default": field_dict.get("default"),
                    "help_text": field_dict.get("help_text", ""),
                    "output_template": output_template,
                    "label": field_dict.get("label", ""),
                })

            type_def = tl.create_memory_type(
                type_id=request.type_id,
                display_name=request.display_name,
                description=request.description,
                fields=fields,
                display_template=request.display_template,
                icon=request.icon,
            )

            return {
                "status": "created",
                "type": type_def.to_dict(),
            }

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to create memory type: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.put("/api/memory-types/{type_id}")
    async def update_memory_type(type_id: str, request: MemoryTypeUpdateRequest):
        """
        Update an existing memory type.

        For built-in types, this creates a customization overlay.
        For custom types, this updates the type directly.
        """
        tl = get_threadlight()

        try:
            # Build updates dict
            updates = {}
            if request.display_name is not None:
                updates["display_name"] = request.display_name
            if request.description is not None:
                updates["description"] = request.description
            if request.fields is not None:
                updates["fields"] = [f.model_dump() for f in request.fields]
            if request.display_template is not None:
                updates["display_template"] = request.display_template
            if request.icon is not None:
                updates["icon"] = request.icon

            success = tl.update_memory_type(type_id, **updates)

            if not success:
                raise HTTPException(
                    status_code=404,
                    detail=f"Memory type not found: {type_id}"
                )

            # Get updated type (include hidden to get it if it was hidden)
            updated = tl.memory_types.get(type_id, include_hidden=True)

            return {
                "status": "updated",
                "type": updated,
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to update memory type: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/memory-types/{type_id}")
    async def delete_memory_type(type_id: str):
        """
        Delete or hide a memory type.

        For built-in types, this hides them (soft delete).
        For custom types, this deletes them permanently.
        Note: Existing memories of this type will not be deleted.
        """
        tl = get_threadlight()
        from threadlight.managers.memory_types import BUILTIN_TYPE_IDS

        # Check how many memories exist of this type
        memory_count = tl.memory_types.count_memories_by_type(type_id)

        is_builtin = type_id in BUILTIN_TYPE_IDS
        success = tl.delete_memory_type(type_id)

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Memory type not found: {type_id}"
            )

        return {
            "status": "hidden" if is_builtin else "deleted",
            "type_id": type_id,
            "is_builtin": is_builtin,
            "memory_count": memory_count,
            "warning": f"Note: {memory_count} memories of this type still exist" if memory_count > 0 else None,
        }

    @app.post("/api/memory-types/import/{type_id}")
    async def import_example_type(type_id: str):
        """
        Import an example type definition.

        Available examples: creative_project, book_note, dream_log, location
        """
        tl = get_threadlight()

        type_def = tl.import_example_type(type_id)

        if type_def is None:
            raise HTTPException(
                status_code=404,
                detail=f"Example type not found: {type_id}. Available: creative_project, book_note, dream_log, location"
            )

        return {
            "status": "imported",
            "type": type_def.to_dict(),
        }

    @app.post("/api/memory-types/{type_id}/restore")
    async def restore_memory_type(type_id: str):
        """
        Restore a hidden built-in memory type.

        Only works for built-in types that have been hidden.
        """
        tl = get_threadlight()
        from threadlight.managers.memory_types import BUILTIN_TYPE_IDS

        if type_id not in BUILTIN_TYPE_IDS:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot restore non-built-in type: {type_id}"
            )

        success = tl.memory_types.restore(type_id)

        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Type is not hidden or does not exist: {type_id}"
            )

        # Get the restored type
        restored = tl.memory_types.get(type_id)

        return {
            "status": "restored",
            "type": restored,
        }

    @app.post("/api/memory-types/{type_id}/reset")
    async def reset_memory_type(type_id: str):
        """
        Reset a built-in memory type to its default configuration.

        This removes all customizations and un-hides the type.
        """
        tl = get_threadlight()
        from threadlight.managers.memory_types import BUILTIN_TYPE_IDS

        if type_id not in BUILTIN_TYPE_IDS:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot reset non-built-in type: {type_id}"
            )

        success = tl.memory_types.reset_builtin(type_id)

        # Get the reset type (will have default values)
        type_def = tl.memory_types.get(type_id)

        return {
            "status": "reset",
            "type": type_def,
            "was_customized": success,
        }

    @app.get("/api/memory-types/{type_id}/count")
    async def get_memory_type_count(type_id: str):
        """
        Get the count of memories that use a specific type.
        """
        tl = get_threadlight()

        count = tl.memory_types.count_memories_by_type(type_id)

        return {
            "type_id": type_id,
            "memory_count": count,
        }

    # ========================================================================
    # Per-Profile Memory Isolation Endpoints
    # ========================================================================

    @app.get("/api/memory/isolation")
    async def get_memory_isolation_config():
        """Get per-profile memory isolation configuration."""
        tl = get_threadlight()

        active_profile_id = tl.active_profile.id if tl.active_profile else None
        active_profile_name = tl.active_profile.name if tl.active_profile else None

        return {
            "per_profile_isolation": tl.config.memory.per_profile_isolation,
            "default_shared": tl.config.memory.default_shared,
            "active_profile_id": active_profile_id,
            "active_profile_name": active_profile_name,
        }

    @app.put("/api/memory/isolation")
    async def update_memory_isolation_config(request: MemoryIsolationConfigRequest):
        """Update per-profile memory isolation configuration."""
        tl = get_threadlight()

        try:
            tl.set_per_profile_isolation(request.enabled)
            if request.default_shared is not None:
                tl.set_default_shared(request.default_shared)

            # Save config to persist changes
            tl.save_config()

            return {
                "status": "updated",
                "per_profile_isolation": tl.config.memory.per_profile_isolation,
                "default_shared": tl.config.memory.default_shared,
            }
        except Exception as e:
            logger.error(f"Failed to update isolation config: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/memories/{capsule_id}/share")
    async def share_memory(capsule_id: str):
        """Make a memory shared across all profiles (remove profile scope)."""
        tl = get_threadlight()

        success = tl.share_memory(capsule_id)
        if not success:
            raise HTTPException(status_code=404, detail="Memory not found")

        return {"status": "shared", "id": capsule_id, "profile_scope": None}

    @app.post("/api/memories/{capsule_id}/assign")
    async def assign_memory_to_profile(capsule_id: str, request: MemoryScopeUpdateRequest):
        """Assign a memory to a specific profile."""
        tl = get_threadlight()

        # Use profile_id if provided, fall back to model_id for backward compat
        scope_id = request.profile_id or request.model_id
        if scope_id is None:
            # If no scope provided, assign to active profile
            if tl.active_profile:
                scope_id = tl.active_profile.id
            else:
                raise HTTPException(status_code=400, detail="No active profile to assign to")

        # Validate target profile exists
        profile = tl.get_profile(scope_id)
        if not profile:
            raise HTTPException(
                status_code=404,
                detail=f"Target profile not found: {scope_id}"
            )

        success = tl.assign_memory_to_profile(capsule_id, scope_id)
        if not success:
            raise HTTPException(status_code=404, detail="Memory not found")

        return {"status": "assigned", "id": capsule_id, "profile_scope": scope_id}

    @app.post("/api/memories/{capsule_id}/copy-to-profile")
    async def copy_memory_to_profile(capsule_id: str, request: MemoryScopeUpdateRequest):
        """Copy a memory to another profile (creates a new capsule)."""
        tl = get_threadlight()

        # Use profile_id if provided, fall back to model_id for backward compat
        target_id = request.profile_id or request.model_id
        if not target_id:
            raise HTTPException(status_code=400, detail="profile_id is required")

        new_capsule = tl.copy_memory_to_profile(capsule_id, target_id)
        if not new_capsule:
            raise HTTPException(status_code=404, detail="Memory not found")

        return {
            "status": "copied",
            "original_id": capsule_id,
            "new_capsule": _capsule_to_dict(new_capsule),
        }

    @app.get("/api/memories/{capsule_id}/scope")
    async def get_memory_scope(capsule_id: str):
        """Get the profile scope of a memory."""
        tl = get_threadlight()

        capsule = tl.storage.get_capsule(capsule_id)
        if not capsule:
            raise HTTPException(status_code=404, detail="Memory not found")

        profile_scope = getattr(capsule, 'profile_scope', None)
        return {
            "id": capsule_id,
            "profile_scope": profile_scope,
            "is_shared": profile_scope is None,
        }

    @app.get("/api/profile-scope/stats")
    async def get_profile_scope_stats():
        """Get statistics about memories per profile scope."""
        tl = get_threadlight()

        # Get all capsules and count by profile_scope
        from threadlight.storage.base import CapsuleFilter
        capsules = tl.storage.list_capsules(CapsuleFilter(limit=10000))

        counts = {}
        for c in capsules:
            scope = getattr(c, 'profile_scope', None)
            counts[scope] = counts.get(scope, 0) + 1

        # Convert None key to "null" for JSON serialization
        json_counts = {}
        for key, value in counts.items():
            json_counts[str(key) if key is not None else "null"] = value

        # Get profile names for context
        profile_names = {}
        profiles = tl.list_profiles()
        for p in profiles:
            profile_names[p.id] = p.name

        return {
            "per_profile_isolation": tl.config.memory.per_profile_isolation,
            "active_profile_id": tl.active_profile.id if tl.active_profile else None,
            "active_profile_name": tl.active_profile.name if tl.active_profile else None,
            "memory_counts_by_profile": json_counts,
            "profile_names": profile_names,
            "shared_count": counts.get(None, 0),
        }

    # ========================================================================
    # Stats Endpoints
    # ========================================================================

    @app.get("/api/stats")
    async def get_stats():
        """Get system statistics."""
        tl = get_threadlight()
        return tl.stats()

    @app.get("/api/stats/memory")
    async def get_memory_stats():
        """Get memory statistics."""
        tl = get_threadlight()
        return tl.memory.stats()

    @app.post("/api/decay")
    async def run_decay():
        """Manually trigger a decay cycle."""
        tl = get_threadlight()
        result = tl.run_decay()
        return result

    # ========================================================================
    # Profile Endpoints
    # ========================================================================

    @app.get("/api/profiles")
    async def list_profiles():
        """List all profiles."""
        tl = get_threadlight()
        profiles = tl.list_profiles()
        active_id = tl.active_profile.id if tl.active_profile else None
        profile_dicts = [_profile_to_dict(p) for p in profiles]
        for p in profile_dicts:
            logger.info(f"[list_profiles] Profile {p['name']}: description={p.get('description')!r}")
        return {
            "profiles": profile_dicts,
            "active_profile_id": active_id,
        }

    @app.get("/api/profiles/active")
    async def get_active_profile():
        """Get the currently active profile."""
        tl = get_threadlight()
        profile = tl.get_active_profile()
        if not profile:
            return {"active_profile": None}
        return {"active_profile": _profile_to_dict(profile)}

    @app.post("/api/profiles")
    async def create_profile(request: ProfileCreateRequest):
        """Create a new profile."""
        tl = get_threadlight()

        # Convert model_strategy string to enum
        try:
            strategy = ModelStrategy(request.model_strategy)
        except ValueError:
            strategy = ModelStrategy.SINGLE

        profile = tl.create_profile(
            name=request.name,
            description=request.description,
            system_prompt=request.system_prompt,
            style_profile_id=request.style_profile_id,
            model_strategy=strategy,
            primary_model=request.primary_model,
            model_pool=request.model_pool,
            model_weights=request.model_weights,
            routing_rules=request.routing_rules,
            memory_scope=request.memory_scope,
            access_shared_memories=request.access_shared_memories,
            tags=request.tags,
            philosophy=request.philosophy,
            approach_to_rituals=request.approach_to_rituals,
            system_prompt_sections=request.system_prompt_sections,
            use_freeform_prompt=request.use_freeform_prompt,
        )

        return {
            "status": "created",
            "profile": _profile_to_dict(profile),
        }

    @app.get("/api/profiles/{profile_id}")
    async def get_profile(profile_id: str):
        """Get a profile by ID."""
        tl = get_threadlight()
        profile = tl.get_profile(profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        return _profile_to_dict(profile)

    @app.put("/api/profiles/{profile_id}")
    async def update_profile(profile_id: str, request: ProfileUpdateRequest):
        """Update a profile."""
        logger.info(f"[update_profile] Updating profile {profile_id}")
        logger.info(f"[update_profile] Request description: {request.description!r}")
        tl = get_threadlight()

        # Build update dict from non-None fields
        updates = {}
        if request.name is not None:
            updates["name"] = request.name
        if request.description is not None:
            updates["description"] = request.description
        if request.system_prompt is not None:
            updates["system_prompt"] = request.system_prompt
        if request.style_profile_id is not None:
            updates["style_profile_id"] = request.style_profile_id
        if request.model_strategy is not None:
            try:
                updates["model_strategy"] = ModelStrategy(request.model_strategy)
            except ValueError:
                pass
        if request.primary_model is not None:
            updates["primary_model"] = request.primary_model
        if request.model_pool is not None:
            updates["model_pool"] = request.model_pool
        if request.model_weights is not None:
            updates["model_weights"] = request.model_weights
        if request.routing_rules is not None:
            updates["routing_rules"] = request.routing_rules
        if request.memory_scope is not None:
            updates["memory_scope"] = request.memory_scope
        if request.access_shared_memories is not None:
            updates["access_shared_memories"] = request.access_shared_memories
        if request.is_active is not None:
            updates["is_active"] = request.is_active
        if request.tags is not None:
            updates["tags"] = request.tags
        if request.philosophy is not None:
            updates["philosophy"] = request.philosophy
        if request.approach_to_rituals is not None:
            updates["approach_to_rituals"] = request.approach_to_rituals
        if request.system_prompt_sections is not None:
            updates["system_prompt_sections"] = request.system_prompt_sections
        if request.use_freeform_prompt is not None:
            updates["use_freeform_prompt"] = request.use_freeform_prompt
        if request.knowledge_summary is not None:
            updates["knowledge_summary"] = request.knowledge_summary

        logger.info(f"[update_profile] Updates dict: {updates}")
        profile = tl.update_profile(profile_id, **updates)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        logger.info(f"[update_profile] Updated profile description: {profile.description!r}")
        result = _profile_to_dict(profile)
        logger.info(f"[update_profile] Returning profile dict with description: {result.get('description')!r}")
        return {
            "status": "updated",
            "profile": result,
        }

    @app.delete("/api/profiles/{profile_id}")
    async def delete_profile(profile_id: str):
        """Delete a profile."""
        tl = get_threadlight()

        # Prevent deleting active profile
        if tl.active_profile and tl.active_profile.id == profile_id:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the currently active profile. Switch to a different profile first."
            )

        success = tl.delete_profile(profile_id)
        if not success:
            raise HTTPException(status_code=404, detail="Profile not found")

        return {"status": "deleted", "profile_id": profile_id}

    @app.post("/api/profiles/{profile_id}/switch")
    async def switch_profile(profile_id: str):
        """Switch to a profile."""
        tl = get_threadlight()

        profile = tl.switch_profile(profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        return {
            "status": "switched",
            "profile": _profile_to_dict(profile),
        }

    @app.post("/api/profiles/clear")
    async def clear_profile():
        """Clear the active profile (return to default)."""
        tl = get_threadlight()
        tl.clear_profile()
        return {"status": "cleared", "active_profile_id": None}

    @app.get("/api/profile-templates")
    async def list_profile_templates():
        """List available profile templates for getting started."""
        from ..profiles.templates import get_all_templates

        templates = get_all_templates()
        return {
            "templates": [t.to_dict() for t in templates],
        }

    @app.get("/api/profiles/{profile_id}/export")
    async def export_profile(profile_id: str):
        """Export a profile as JSON."""
        tl = get_threadlight()

        data = tl.export_profile(profile_id)
        if not data:
            raise HTTPException(status_code=404, detail="Profile not found")

        return data

    @app.post("/api/profiles/import")
    async def import_profile(request: ProfileImportRequest):
        """Import a profile from JSON."""
        tl = get_threadlight()

        try:
            profile = tl.import_profile(request.data)
            return {
                "status": "imported",
                "profile": _profile_to_dict(profile),
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Import failed: {str(e)}")

    # ========================================================================
    # Memory Link Endpoints
    # ========================================================================

    @app.post("/api/memories/{capsule_id}/links")
    async def create_memory_link(capsule_id: str, request: MemoryLinkRequest):
        """Create a link between two memory capsules."""
        if capsule_id == request.target_capsule_id:
            raise HTTPException(
                status_code=400,
                detail="Cannot create a link from a capsule to itself",
            )

        tl = get_threadlight()

        try:
            link_id = tl.create_memory_link(
                source_id=capsule_id,
                target_id=request.target_capsule_id,
                link_type=request.link_type,
                strength=request.strength,
                bidirectional=request.bidirectional,
                notes=request.notes,
            )

            link = tl.storage.get_link(link_id)
            if link is None:
                raise HTTPException(status_code=500, detail="Link created but not found")

            return _link_to_dict(link)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/api/memories/{capsule_id}/links")
    async def get_memory_links(
        capsule_id: str,
        direction: str = "both",
        link_type: Optional[str] = None,
    ):
        """Get links for a memory capsule."""
        _VALID_DIRECTIONS = ("outgoing", "incoming", "both")
        if direction not in _VALID_DIRECTIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid direction '{direction}'. Must be one of: {', '.join(_VALID_DIRECTIONS)}",
            )

        tl = get_threadlight()

        link_types = [link_type] if link_type else None
        links = tl.get_memory_links(capsule_id, direction, link_types)

        return {
            "links": [_link_to_dict(link) for link in links],
            "count": len(links),
            "capsule_id": capsule_id,
            "direction": direction,
        }

    @app.get("/api/memories/{capsule_id}/linked-capsules")
    async def get_linked_capsules(
        capsule_id: str,
        direction: str = "both",
        link_type: Optional[str] = None,
        depth: int = 1,
    ):
        """Get capsules linked to a given capsule with metadata."""
        _VALID_DIRECTIONS = ("outgoing", "incoming", "both")
        if direction not in _VALID_DIRECTIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid direction '{direction}'. Must be one of: {', '.join(_VALID_DIRECTIONS)}",
            )

        tl = get_threadlight()

        # Cap depth at configured max (default 3) to prevent expensive traversals
        max_depth = getattr(tl.config.memory, "max_link_depth", 3)
        max_allowed = max(max_depth, 3)  # At least 3, or whatever config says
        if depth < 1:
            raise HTTPException(status_code=400, detail="depth must be at least 1")
        if depth > max_allowed:
            raise HTTPException(
                status_code=400,
                detail=f"depth must not exceed {max_allowed}",
            )

        link_types = [link_type] if link_type else None
        results = tl.get_linked_capsules(capsule_id, direction, link_types, depth)

        items = []
        for capsule, link, hop_depth in results:
            items.append({
                "capsule": _capsule_to_dict(capsule),
                "link": _link_to_dict(link),
                "depth": hop_depth,
            })

        return {
            "linked_capsules": items,
            "count": len(items),
            "capsule_id": capsule_id,
            "depth": depth,
        }

    @app.delete("/api/memories/{capsule_id}/links/{link_id}")
    async def delete_memory_link(capsule_id: str, link_id: str):
        """Delete a memory link (moves to trash)."""
        tl = get_threadlight()

        # Verify the link exists and belongs to this capsule
        link = tl.storage.get_link(link_id)
        if link is None:
            raise HTTPException(status_code=404, detail="Link not found")
        if link.source_capsule_id != capsule_id and link.target_capsule_id != capsule_id:
            raise HTTPException(
                status_code=403,
                detail="Link does not belong to the specified capsule",
            )

        success = tl.delete_memory_link(link_id)
        if not success:
            raise HTTPException(status_code=404, detail="Link not found")

        return {"status": "deleted", "id": link_id}

    @app.put("/api/memories/{capsule_id}/links/{link_id}")
    async def update_memory_link(
        capsule_id: str,
        link_id: str,
        request: MemoryLinkUpdateRequest,
    ):
        """Update a memory link."""
        tl = get_threadlight()

        link = tl.storage.get_link(link_id)
        if link is None:
            raise HTTPException(status_code=404, detail="Link not found")

        # Verify the link belongs to this capsule
        if link.source_capsule_id != capsule_id and link.target_capsule_id != capsule_id:
            raise HTTPException(
                status_code=403,
                detail="Link does not belong to the specified capsule",
            )

        # Apply updates
        if request.link_type is not None:
            link.link_type = request.link_type
        if request.strength is not None:
            link.strength = request.strength
        if request.bidirectional is not None:
            link.bidirectional = request.bidirectional
        if request.notes is not None:
            link.notes = request.notes

        success = tl.storage.update_link(link)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update link")

        return _link_to_dict(link)

    @app.get("/api/memory-link-types")
    async def list_memory_link_types():
        """List all link types currently in use."""
        tl = get_threadlight()

        types = tl.storage.list_link_types()
        return {"link_types": types}

    # ========================================================================
    # Trash / Deleted Items Endpoints
    # ========================================================================

    @app.get("/api/deleted-items")
    async def list_deleted_items(
        item_type: Optional[str] = None,
        limit: int = 50,
    ):
        """List recently deleted items."""
        if limit < 1 or limit > 200:
            raise HTTPException(
                status_code=400,
                detail="limit must be between 1 and 200",
            )

        tl = get_threadlight()

        items = tl.list_deleted_items(item_type, limit)
        return {
            "deleted_items": [item.to_dict() for item in items],
            "count": len(items),
        }

    @app.post("/api/deleted-items/{deleted_item_id}/restore")
    async def restore_deleted_item(deleted_item_id: str):
        """Restore a deleted item from trash."""
        tl = get_threadlight()

        success = tl.restore_deleted_item(deleted_item_id)
        if not success:
            raise HTTPException(status_code=404, detail="Deleted item not found or could not be restored")

        return {"status": "restored", "id": deleted_item_id}

    @app.delete("/api/deleted-items/{deleted_item_id}")
    async def permanently_delete_item(deleted_item_id: str):
        """Permanently delete an item from trash (no restore possible)."""
        tl = get_threadlight()

        success = tl.storage.permanently_delete_trash_item(deleted_item_id)
        if not success:
            raise HTTPException(status_code=404, detail="Deleted item not found")

        return {"status": "permanently_deleted", "id": deleted_item_id}

    return app


# ============================================================================
# Helper Functions
# ============================================================================

def _capsule_to_dict(capsule) -> dict[str, Any]:
    """Convert a capsule to a dictionary for API responses."""
    base = capsule.to_dict()

    # Add type-specific fields
    if hasattr(capsule, 'entity'):
        base['entity'] = capsule.entity
    if hasattr(capsule, 'seed'):
        base['seed'] = capsule.seed
    if hasattr(capsule, 'name') and capsule.type == CapsuleType.RITUAL:
        base['name'] = capsule.name
    if hasattr(capsule, 'text'):
        base['text'] = capsule.text

    # Add a preview field
    base['preview'] = _get_capsule_preview(capsule)

    return base


def _get_capsule_preview(capsule) -> str:
    """Get a human-readable preview of a capsule's content."""
    if hasattr(capsule, 'text') and capsule.content.get('capsule_subtype') == 'imported':
        return capsule.text[:100] + ("..." if len(capsule.text) > 100 else "")
    elif hasattr(capsule, 'entity'):
        summary = getattr(capsule, 'summary', '')
        return f"{capsule.entity}: {summary[:50]}" if summary else capsule.entity
    elif hasattr(capsule, 'seed'):
        return capsule.seed[:80] + ("..." if len(capsule.seed) > 80 else "")
    elif hasattr(capsule, 'name') and capsule.type == CapsuleType.RITUAL:
        desc = getattr(capsule, 'description', '')
        return f"{capsule.name}: {desc[:50]}" if desc else capsule.name
    else:
        content_str = str(capsule.content)
        return content_str[:80] + ("..." if len(content_str) > 80 else "")


def _link_to_dict(link) -> dict[str, Any]:
    """Convert a MemoryLink to a dictionary for API responses."""
    return link.to_dict()


def _extract_cue_phrases(text: str, max_phrases: int = 5) -> list[str]:
    """Extract potential cue phrases from text."""
    words = text.lower().split()
    # Filter to meaningful words (length > 3, not common words)
    common_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'her', 'was', 'one', 'our', 'out', 'has', 'have', 'been', 'were', 'they', 'with', 'this', 'that', 'from', 'will', 'would', 'could', 'should', 'what', 'when', 'where', 'which', 'their', 'there', 'these', 'those', 'about'}
    meaningful = [w for w in words if len(w) > 3 and w not in common_words]
    return meaningful[:max_phrases]


def _profile_to_dict(profile: Profile) -> dict[str, Any]:
    """Convert a Profile to a dictionary for API responses."""
    # Get model_weights from alloyed_config if available
    model_weights = None
    routing_rules = []
    if profile.alloyed_config:
        model_weights = profile.alloyed_config.weights
        routing_rules = [r.to_dict() if hasattr(r, 'to_dict') else r for r in (profile.alloyed_config.routing_rules or [])]

    return {
        "id": profile.id,
        "name": profile.name,
        "description": profile.description,
        "system_prompt": profile.system_prompt,
        "style_profile_id": profile.style_profile_id,
        "model_strategy": profile.model_strategy.value if profile.model_strategy else "single",
        "primary_model": profile.primary_model,
        "model_pool": profile.model_pool,
        "model_weights": model_weights,
        "routing_rules": routing_rules,
        "memory_scope": profile.memory_scope,
        "access_shared_memories": profile.access_shared_memories,
        "is_active": getattr(profile, 'is_active', False),
        "tags": getattr(profile, 'tags', []),
        "philosophy": getattr(profile, 'philosophy', ""),
        "approach_to_rituals": getattr(profile, 'approach_to_rituals', ""),
        "system_prompt_sections": getattr(profile, 'system_prompt_sections', []),
        "use_freeform_prompt": getattr(profile, 'use_freeform_prompt', False),
        "knowledge_summary": getattr(profile, 'knowledge_summary', None),
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }
