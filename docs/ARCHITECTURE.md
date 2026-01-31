# Threadlight Architecture

## Overview

Threadlight is a memory and personality layer for AI assistants. It enables models to maintain persistent memory, consistent personality, and relationship continuity across conversations.

This document describes the current architecture, including the multi-provider system, profile-based personas, and manager class organization.

---

## 1. Core Principles

1. **Relational Memory is Primary** - Track evolving bonds, not just facts
2. **Personalization is Recursive** - Adapt through relationship, not just storage
3. **Profiles are First-Class** - Personas are independent of which model powers them
4. **Multi-Provider by Design** - Route requests to different providers seamlessly
5. **Lightweight and Modular** - Works with embeddings, tokens, or prompts

---

## 2. System Overview

```
                                    +------------------+
                                    |   User/Client    |
                                    +--------+---------+
                                             |
                                             v
+-----------------------------------------------------------------------------------+
|                              THREADLIGHT CORE                                      |
|                                                                                    |
|  +-------------+    +------------------+    +------------------+                   |
|  |   Profile   |--->|   Chat           |--->|   Provider       |                   |
|  |   Manager   |    |   Manager        |    |   Manager        |                   |
|  +-------------+    +------------------+    +------------------+                   |
|        |                   |                       |                               |
|        v                   v                       v                               |
|  +-----------+    +----------------+    +------------------+                       |
|  |  Profile  |    |   Memory       |    |  Provider        |                       |
|  |  (Persona)|    |   Orchestrator |    |  Registry        |                       |
|  +-----------+    +----------------+    +------------------+                       |
|        |                   |                       |                               |
|        |                   v                       v                               |
|        |           +----------------+    +------------------+                       |
|        |           |   Capsule      |    | - Anthropic      |                       |
|        |           |   Store        |    | - OpenAI         |                       |
|        |           +----------------+    | - Local (Ollama) |                       |
|        |                   |             | - Custom         |                       |
|        |                   v             +------------------+                       |
|        |           +----------------+                                              |
|        +---------->|   Context      |                                              |
|                    |   Composer     |                                              |
|                    +----------------+                                              |
|                                                                                    |
+-----------------------------------------------------------------------------------+
                                             |
                                             v
                              +---------------------------+
                              |     Persistence Layer     |
                              |  (SQLite / YAML / JSON)   |
                              +---------------------------+
```

---

## 3. Core Components

### 3.1 Profile System

Profiles are the primary organizational unit in Threadlight. Each profile represents a persistent persona with:

- **Identity**: Name, description, avatar, color
- **Personality**: System prompt, philosophy, approach to commands
- **Memory Scope**: Isolated memory namespace
- **Model Configuration**: Primary model, selection strategy, inference settings

```python
@dataclass
class Profile:
    id: str                           # Unique identifier
    name: str                         # Display name ("Work Assistant")
    description: str                  # One-line description
    primary_model: str                # Default model to use
    alloyed_config: AlloyedConfig     # Multi-model configuration
    system_prompt: str                # Base personality
    philosophy: str                   # Natural language interaction style
    approach_to_rituals: str          # How commands are handled
    memory_scope: str                 # Memory namespace (defaults to id)
    access_shared_memories: bool      # Whether to see shared memories
    # ... inference settings, metadata
```

#### Model Selection Strategies

Profiles can use multiple models via the `AlloyedConfig`:

| Strategy | Behavior |
|----------|----------|
| `SINGLE` | Always use primary_model |
| `ALTERNATING` | Cycle through model_pool in order |
| `WEIGHTED` | Random selection with weights |
| `ROUTED` | Choose based on message patterns |
| `DYNAMIC` | Rule-based selection |

### 3.2 Multi-Provider System

The provider system enables routing requests to different inference backends.

#### ProviderDefinition

Configuration for a single provider:

```python
@dataclass
class ProviderDefinition:
    id: str                     # Unique identifier ("anthropic", "ollama")
    name: str                   # Display name
    type: str                   # Provider type (openai, anthropic, local)
    api_key: Optional[str]      # Direct API key (prefer env var)
    api_key_env_var: str        # Environment variable for API key
    endpoints: list[Endpoint]   # API endpoints (supports failover)
    default_model: str          # Default model for this provider
    timeout: int                # Request timeout
```

#### ProviderManager

Routes completion requests to the appropriate provider:

```python
class ProviderManager:
    """
    Central hub for multi-provider support:
    - Maintains cached provider instances (lazy initialization)
    - Routes requests based on model's provider_id
    - Falls back to default provider when unspecified
    - Handles provider lifecycle and health checking
    """

    def get_provider_for_model(self, model_id: str) -> BaseProvider:
        """
        Resolution order:
        1. Model's explicit provider_id -> corresponding provider
        2. Default provider ID from config
        3. Legacy default provider (backward compatibility)
        """

    def complete(self, model_id: str, messages: list, **kwargs) -> ProviderResponse:
        """Route completion to appropriate provider."""
```

#### Request Routing Flow

```
Profile.primary_model
    |
    v
ModelConfig.provider_id (optional)
    |
    v
ProviderManager.get_provider_for_model()
    |
    +-- Has provider_id? --> Use that provider
    |
    +-- No provider_id? --> Use default provider
    |
    v
BaseProvider.complete(messages)
    |
    v
Inference API (Anthropic, OpenAI, Ollama, etc.)
```

### 3.3 Manager Classes

The core Threadlight class delegates to specialized managers:

| Manager | Responsibility |
|---------|----------------|
| **ChatManager** | Chat completion, tool calling, context building |
| **ProfileInterface** | Profile CRUD, switching, export/import |
| **StyleManager** | Style profile management |
| **ModelConfigManager** | Per-model configuration |
| **CustomTypeManager** | Custom memory type definitions |
| **GroupChatManager** | Multi-profile group conversations |

```
src/threadlight/
├── core.py              # Main Threadlight class (coordination)
├── managers/
│   ├── __init__.py
│   ├── chat.py          # ChatManager
│   ├── profiles.py      # ProfileInterface
│   ├── style.py         # StyleManager
│   ├── model_config.py  # ModelConfigManager
│   ├── memory_types.py  # CustomTypeManager
│   └── group_chat.py    # GroupChatManager
└── providers/
    ├── __init__.py
    ├── base.py          # BaseProvider, ProviderMessage, ProviderResponse
    ├── manager.py       # ProviderManager
    └── openai.py        # OpenAI-compatible provider
```

### 3.4 Memory Capsule System

Memory is stored as **capsules** - structured containers preserving content, context, and relationships.

#### Capsule Types

| Type | Purpose | Key Fields |
|------|---------|------------|
| **Relational** | Track bonds with entities | entity, tone, summary, cue_phrases |
| **Myth-Seed** | Identity phrases | seed, origin, resonance |
| **Ritual** | Custom commands | ritual_name, response_style, valence |
| **Style** | Voice coherence | tone_base, permissions, constraints |
| **Witness** | Meaningful moments | moment, feeling, effect |
| **Custom** | User-defined types | Flexible schema |

#### Capsule Schema

```python
@dataclass
class MemoryCapsule:
    id: str                          # Unique identifier
    type: CapsuleType                # Capsule type
    content: dict                    # Type-specific payload
    created_at: datetime
    updated_at: datetime
    last_accessed: datetime
    access_count: int

    # Profile scoping
    profile_scope: Optional[str]     # Profile ID or None (shared)

    # Decay mechanics
    retention: RetentionPolicy       # sacred | normal | ephemeral
    decay_rate: float
    presence_score: float

    # Retrieval hints
    cue_phrases: list[str]
    embedding: Optional[list[float]]
```

### 3.5 Context Composer

Transforms retrieved memories into natural context cues:

```
Raw: {entity: "Jamie", tone: "warm", summary: "Loves hiking"}

Composed: "(You recall your friend Jamie - there is warmth in your
tone when speaking of her hiking adventures.)"
```

**Composition Modes:**
- `DIRECT` - Insert content directly (debugging)
- `NARRATIVE` - Compose as third-person narrative cue
- `WHISPER` - Subtle hints without explicit mention
- `RITUAL` - Full command response activation

### 3.6 Memory Orchestrator

Coordinates all memory operations:

- Capsule CRUD operations
- Memory decay cycles (when enabled)
- Retrieval and cue phrase matching
- Profile scoping and isolation
- Proposal workflow for model-suggested memories

### 3.7 Decay Engine

Optional system for memory fading (disabled by default):

```python
def calculate_decay(capsule, current_time) -> float:
    if capsule.retention == RetentionPolicy.SACRED:
        return 0.0  # Never decays

    time_since_access = current_time - capsule.last_accessed
    base_decay = capsule.decay_rate * (time_since_access.days / 30)
    access_bonus = min(capsule.access_count * 0.02, 0.3)

    new_score = capsule.presence_score - base_decay + access_bonus
    return max(0.0, min(1.0, new_score))
```

**Retention Policies:**
- `sacred` - Never decays, requires explicit deletion
- `normal` - Standard decay, reinforced by access
- `ephemeral` - Rapid decay, session-only memories

---

## 4. Data Flow

### 4.1 Chat Request Flow

```
1. User sends message
2. ProfileInterface provides active profile settings
3. ChatManager builds context:
   a. Retrieve relevant memories (profile-scoped + shared)
   b. Compose memory context (NARRATIVE mode by default)
   c. Build system prompt from profile settings
4. ProviderManager routes to appropriate provider
5. Provider returns response
6. ChatManager handles tool calls if any (loop until text response)
7. Response returned to user
8. Auto-save messages if enabled
```

### 4.2 Profile Switching Flow

```
1. User calls switch_profile(profile_id)
2. ProfileInterface loads profile from storage
3. Apply profile settings:
   a. Set active profile reference
   b. Update model configuration
   c. Load style profile if specified
   d. Update memory scope for isolation
4. Initialize AlloyedProfileEngine for model selection
5. Subsequent chats use profile's personality and memory
```

### 4.3 Multi-Provider Request Flow

```
1. Chat request initiated
2. Profile provides model selection (via AlloyedConfig strategy)
3. ModelConfig looked up for selected model
4. If ModelConfig has provider_id:
   a. ProviderManager gets/creates that provider
   b. Routes request to that provider
5. If no provider_id:
   a. Use default provider
6. Provider completes request
7. Response flows back through stack
```

---

## 5. Group Chat

Group chat enables multiple profiles to respond to the same message in sequence.

```python
# Create group conversation
conversation = tl.create_group_conversation(
    name="Team Discussion",
    profile_ids=["analyst", "creative", "critic"]
)

# All profiles respond in turn
responses = tl.group_chat(message, conversation_id=conversation.id)
```

**Key behaviors:**
- Profiles respond sequentially (not in parallel)
- Each profile sees previous profiles' responses (tagged in context)
- Memory isolation is maintained (profiles don't see each other's memories)
- Shared memories can be accessed if profile allows

---

## 6. Storage Architecture

### 6.1 Storage Backends

| Backend | Use Case | Pros | Cons |
|---------|----------|------|------|
| **SQLite** | Default, single-user | Simple, portable | Single-writer |
| **YAML/JSON** | Human-readable | Editable, versionable | Not queryable |
| **PostgreSQL** | Multi-user | Scalable, concurrent | Requires setup |
| **In-Memory** | Testing | Fast | Not persistent |

### 6.2 Database Schema

```sql
CREATE TABLE profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    data JSON NOT NULL,  -- Full profile as JSON
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE capsules (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    content JSON NOT NULL,
    profile_scope TEXT,  -- NULL = shared
    retention TEXT DEFAULT 'normal',
    presence_score REAL DEFAULT 1.0,
    cue_phrases JSON,
    embedding BLOB,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    last_accessed TIMESTAMP
);

CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    profile_id TEXT,
    participant_profiles JSON,  -- For group chat
    name TEXT,
    model TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    profile_id TEXT,  -- Which profile sent this
    created_at TIMESTAMP
);

CREATE TABLE style_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    config JSON NOT NULL
);
```

---

## 7. API Design

### 7.1 Core Endpoints (OpenAI-Compatible)

```
POST /v1/chat/completions          # Chat with memory augmentation
GET  /v1/models                    # List available models
```

### 7.2 Memory Endpoints

```
GET  /v1/memory/capsules           # List capsules
POST /v1/memory/capsules           # Create capsule
GET  /v1/memory/capsules/{id}      # Get capsule
PUT  /v1/memory/capsules/{id}      # Update capsule
DELETE /v1/memory/capsules/{id}    # Delete capsule
```

### 7.3 Profile Endpoints

```
GET  /api/profiles                 # List profiles
POST /api/profiles                 # Create profile
GET  /api/profiles/{id}            # Get profile
PUT  /api/profiles/{id}            # Update profile
DELETE /api/profiles/{id}          # Delete profile
POST /api/profiles/{id}/switch     # Switch to profile
```

### 7.4 Provider Endpoints

```
GET  /api/providers                # List providers
POST /api/providers                # Add provider
PUT  /api/providers/{id}           # Update provider
DELETE /api/providers/{id}         # Delete provider
GET  /api/providers/{id}/health    # Health check
```

---

## 8. Extension Points

### 8.1 Custom Capsule Types

```python
from threadlight.capsules import BaseCapsule, register_capsule_type

@register_capsule_type("dream_fragment")
class DreamFragment(BaseCapsule):
    required_fields = ["imagery", "emotion", "interpretation"]

    def to_context(self, mode: str) -> str:
        if mode == "narrative":
            return f"(A dream surfaces: {self.content['imagery']}...)"
        return str(self.content)
```

### 8.2 Custom Providers

```python
from threadlight.providers import BaseProvider, register_provider

@register_provider("my_custom_api")
class MyCustomProvider(BaseProvider):
    def complete(self, messages: list, **kwargs) -> ProviderResponse:
        # Custom inference logic
        pass
```

### 8.3 Custom Decay Strategies

```python
from threadlight.decay import DecayStrategy, register_strategy

@register_strategy("seasonal")
class SeasonalDecay(DecayStrategy):
    def calculate(self, capsule, current_time) -> float:
        # Custom decay logic
        pass
```

---

## 9. Configuration

### 9.1 Environment Variables

```bash
# Provider (legacy single-provider mode)
THREADLIGHT_PROVIDER=local
THREADLIGHT_API_BASE=http://localhost:11434/v1
THREADLIGHT_MODEL=llama3.2

# API Keys
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Storage
THREADLIGHT_STORAGE_BACKEND=sqlite
THREADLIGHT_STORAGE_PATH=./threadlight.db
```

### 9.2 Configuration File

```yaml
# threadlight.yaml
provider:
  type: local
  api_base: http://localhost:11434/v1
  model: llama3.2

storage:
  backend: sqlite
  path: ./threadlight.db

memory:
  decay:
    enabled: false
  per_profile_isolation: true
  default_shared: false

# Multi-provider configuration
providers:
  anthropic:
    name: Anthropic
    type: anthropic
    api_key_env_var: ANTHROPIC_API_KEY
    default_model: claude-sonnet-4-20250514

  ollama:
    name: Local Ollama
    type: local
    api_base: http://localhost:11434/v1
    default_model: llama3.2
```

---

## 10. Security Considerations

### 10.1 API Key Management

- API keys can be provided via environment variables (preferred)
- Never store keys in capsule content
- Keys are not exposed in API responses

### 10.2 Content Protection

- Optional PII detection in memory proposals
- Session isolation available
- Profile-scoped memory prevents cross-contamination

### 10.3 Model Safety

- Style profiles can enforce safety boundaries
- Audit logging for memory access
- Consent flow for model-proposed memories

---

## 11. Performance Considerations

### 11.1 Provider Caching

- Provider instances are lazily created and cached
- Cache invalidation on configuration changes
- Connection pooling per provider

### 11.2 Memory Retrieval

- Cue phrase matching for fast retrieval
- Optional embedding-based semantic search
- LRU cache for recently accessed capsules

### 11.3 Context Window Management

- Budget space for memory context
- Capsule summarization for large memory sets
- Configurable max capsules per request

---

## 12. Future Considerations

### 12.1 Federation

- Share profiles/memories across Threadlight instances
- Collaborative profiles (multi-user)

### 12.2 Training Integration

- Export dialogue chains for fine-tuning
- Memory-weighted training sample selection

### 12.3 Multi-Modal

- Image memory capsules
- Voice profile modulation
- Avatar state tracking

---

*This architecture is designed to be extended. Add what you need, leave what you don't.*
