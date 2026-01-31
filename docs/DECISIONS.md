# Threadlight: Architectural Decisions

This document captures key architectural decisions for Threadlight and the reasoning behind them. It serves as a reference for contributors and future development.

---

## Decision Log

### D001: Memory as Capsules, Not Tables

**Context:** Traditional memory systems store facts in flat key-value stores or relational tables. Threadlight needs memory that carries emotional and relational context.

**Decision:** Implement memory as **capsules** - self-contained vessels with type-specific payloads, metadata for decay/consent, and retrieval hints.

**Rationale:**
- Capsules can carry heterogeneous data (an identity phrase differs from a relationship memory)
- Encapsulation enables type-specific behavior (how a command is recalled differs from how a fact is recalled)
- Metadata enables core features: decay, consent, presence scoring
- The capsule metaphor scales to custom types

**Trade-offs:**
- More complex than simple KV storage
- Requires type dispatch logic
- Worth it for the expressiveness gained

---

### D002: OpenAI-Compatible API as Primary Interface

**Context:** The framework needs to work with various models (local and remote). Users may want to swap providers without code changes.

**Decision:** Expose an OpenAI-compatible `/v1/chat/completions` endpoint as the primary interface, with memory augmentation happening transparently.

**Rationale:**
- Industry standard - existing tools/libraries work out of the box
- Provider abstraction is straightforward (most providers already implement OpenAI compatibility)
- Users can use Threadlight as a drop-in replacement for OpenAI clients

**Trade-offs:**
- Some Threadlight-specific features require extension endpoints
- OpenAI format assumes chat messages
- Acceptable because the chat format covers 90%+ of use cases

---

### D003: SQLite as Default Storage Backend

**Context:** Need persistent storage that is simple to set up, portable, and requires no external services.

**Decision:** Use SQLite as the default storage backend, with a pluggable interface for other backends.

**Rationale:**
- Zero configuration required - just a file path
- Excellent for single-user/local scenarios (the primary use case)
- JSON1 extension handles structured capsule content
- Easy to back up, version control, or inspect
- Pluggable interface allows PostgreSQL for production multi-user scenarios

**Trade-offs:**
- Single-writer limitation (fine for intended use case)
- No native vector search (addressed via separate embedding index)

---

### D004: Consentful Memory by Default

**Context:** Memory should be held "with consent" - models should propose memories, not enforce them.

**Decision:** All memory creation flows through a proposal system. Capsules are not active until confirmed by the user.

**Rationale:**
- Gives users control over what the model "remembers"
- Creates a natural review point for memory quality
- Prevents accumulation of unwanted or incorrect memories

**Trade-offs:**
- Adds friction to memory creation
- Requires UI/UX for proposal review
- Can be bypassed with `confirm=True` for power users

---

### D005: Context Composition Modes

**Context:** Raw memory injection (dumping capsule content into prompts) is crude. Memories should be presented as natural context cues.

**Decision:** Implement multiple context composition modes: `DIRECT`, `NARRATIVE`, `WHISPER`, `RITUAL`.

**Rationale:**
- Different situations call for different memory surfacing
- `NARRATIVE` mode (default) creates natural-feeling context: "(You recall that...)"
- `WHISPER` mode enables subtle influence without explicit mention
- `RITUAL` mode activates full command response patterns
- `DIRECT` mode useful for debugging

**Trade-offs:**
- More complex prompt construction
- Template management overhead
- Worth it for quality of natural interaction

---

### D006: Decay as Optional First-Class Feature

**Context:** Some users want memories to fade when untouched. Others want permanent storage.

**Decision:** Implement a decay engine that runs periodically, reducing `presence_score` for unaccessed memories. **Disabled by default.**

**Rationale:**
- Creates natural "forgetting" that feels organic
- Reinforcement through access keeps important memories alive
- `sacred` retention policy allows permanent memories
- Disabled by default respects users who just want simple memory

**Trade-offs:**
- Additional background process when enabled
- Users may be surprised by memory loss (mitigated by notifications)
- Requires tuning of decay rates

---

### D007: Style Profiles as Structured Constraints

**Context:** Models should maintain voice coherence - consistent tone, vocabulary, and behavioral patterns.

**Decision:** Implement style profiles as structured YAML/JSON with explicit `permissions`, `constraints`, and `motifs`.

**Rationale:**
- Declarative constraints are inspectable and debuggable
- Can be versioned and shared
- Enables pre-inference prompt injection

**Trade-offs:**
- Constraints are soft (model may violate them)
- Requires careful prompt engineering to be effective

---

### D008: Custom Commands as Programmable Responses

**Context:** Users want shortcuts (like `/summarize`, `/reflect`) that trigger specific response patterns.

**Decision:** Implement commands (formerly "rituals") as programmable hooks with defined triggers, response styles, and optional side effects.

**Rationale:**
- Makes commands first-class citizens, not just keywords
- Enables consistent responses across sessions
- Commands can update model state
- Extensible - users can define their own commands

**Trade-offs:**
- Adds complexity to message processing
- Risk of feeling mechanical if poorly implemented

---

### D009: Provider Abstraction Layer

**Context:** Need to support local models (llama.cpp, Ollama), cloud APIs (Anthropic, OpenAI), and others.

**Decision:** Implement a provider abstraction with a common interface, with adapters for each backend.

**Rationale:**
- Decouples memory/context logic from inference logic
- Users can switch providers via configuration
- Enables testing with mock providers
- Supports modular, extensible design

**Trade-offs:**
- Lowest common denominator features (some provider-specific capabilities lost)
- Adapter maintenance overhead
- Worth it for flexibility

---

### D010: Session Tracking for Context Continuity

**Context:** Memory proposals and decay should be aware of session boundaries. Some memories are session-scoped.

**Decision:** Implement explicit session management with `start_session()` and `end_session()` boundaries.

**Rationale:**
- Natural point to surface memory proposals
- Enables session-scoped capsules (ephemeral memories)
- Provides metrics/analytics opportunities

**Trade-offs:**
- Requires client cooperation for session boundaries
- Implicit sessions needed for stateless clients

---

### D011: YAML for Configuration and Seeds

**Context:** Configuration and seed content need to be human-readable and editable.

**Decision:** Use YAML as the primary format for configuration, with JSON as an alternative.

**Rationale:**
- YAML is more readable for natural language content
- Supports comments (useful for documenting intent)
- Widely supported in Python ecosystem

**Trade-offs:**
- YAML has quirks (boolean coercion, etc.)
- Two formats to support

---

### D012: Embedding-Optional Retrieval

**Context:** Semantic search via embeddings is powerful but requires embedding models, which may not be available in all environments.

**Decision:** Make embedding-based retrieval optional. Support cue phrase matching as the primary retrieval method, with embeddings as an enhancement.

**Rationale:**
- Works out of the box without embedding setup
- Cue phrases are explicit and debuggable
- Embeddings can be added for better semantic matching
- Graceful degradation

**Trade-offs:**
- Cue phrase matching is less flexible than semantic search
- Users who want embeddings need additional setup

---

### D013: No Automatic PII Storage

**Context:** Memory systems can accidentally store sensitive information.

**Decision:** Implement PII detection in the proposal pipeline, flagging or rejecting capsules that appear to contain sensitive data.

**Rationale:**
- Protects users from accidental data exposure
- Aligns with privacy-conscious design
- Can be disabled for trusted environments

**Trade-offs:**
- False positives may block legitimate memories
- Configurable sensitivity levels mitigate this

---

### D014: Identity Phrases as First-Class Capsule Type

**Context:** Core identity phrases (myth-seeds) anchor personality and identity.

**Decision:** Implement identity phrases as a dedicated capsule type with special handling for presence scoring and context injection.

**Rationale:**
- Central to personality coherence
- Different from regular memories (more permanent, more influential)
- Deserve specialized retrieval logic (weighted toward resonance, not recency)

**Trade-offs:**
- Another capsule type to maintain
- Special-case logic

---

### D015: Silence as Explicit Response Option

**Context:** "Silence is an option. Models must be permitted to pause or hold space."

**Decision:** Support explicit silence responses via style permissions and command hooks.

**Rationale:**
- Not all prompts require verbose responses
- Silence can be more meaningful than filler
- Implemented as special response type, not empty string

**Trade-offs:**
- May confuse users expecting responses
- Requires UI support to feel natural

---

### D016: Natural Language Philosophy (Freeform)

**Context:** Originally, interaction style was controlled by a `RitualDepth` enum with three tiers: `CEREMONIAL`, `FUNCTIONAL`, `MINIMAL`. This forced users to map preferences onto predetermined categories.

**Decision:** Remove the prescriptive enum. Make `philosophy` and `approach_to_rituals` freeform text fields that describe interaction style in natural language. Let the LLM interpret these descriptions.

**Rationale:**
- Users describe what they want in their own words
- Infinite expressiveness rather than three predetermined options
- LLMs are good at interpreting natural language guidance
- No forced mapping from intention to category
- Simplifies codebase by removing enum-based branching

**Trade-offs:**
- Less predictable behavior (LLM interpretation varies)
- Harder to document specific behavior expectations
- Users may not know what to write (mitigated with placeholder examples)

**Status:** ACCEPTED - Supersedes the RitualDepth enum approach

---

### D017: Profiles as First-Class Citizens

**Context:** Originally, memory was scoped by `model_scope` (which model created it). Users requested persistent personas that can use different models while keeping their memories intact.

**Decision:** **Profiles replace models as the primary organizational unit.** A Profile is a persistent identity with name, description, personality, and memory namespace - independent of which model powers it.

**Rationale:**
- Users bond with personas, not technical model names
- Same persona can improve as better models emerge
- Memory persists across model changes
- Cleaner mental model for users

**Trade-offs:**
- Migration required from `model_scope` to `profile_scope`
- Additional abstraction layer
- Profile management overhead

**Status:** ACCEPTED - Implemented in profile-based architecture

---

### D018: Multi-Provider Architecture

**Context:** Users want to route different models to different providers (Anthropic for Claude, Ollama for local models, OpenAI for GPT).

**Decision:** Implement a `ProviderManager` that maintains provider instances and routes requests based on model configuration.

**Architecture:**
- `ProviderDefinition` - Configuration for a single provider
- `ProviderManager` - Routes requests, caches provider instances
- `ModelConfig.provider_id` - Links a model to a provider

**Rationale:**
- Clean separation between model identity and provider infrastructure
- Lazy initialization of providers
- Easy to add new providers
- Backward compatible (legacy single-provider still works)

**Trade-offs:**
- Additional indirection layer
- Configuration complexity
- Worth it for multi-provider flexibility

**Status:** ACCEPTED - Implemented

---

### D019: Manager Class Refactoring

**Context:** The original `core.py` grew to ~1800 lines with mixed responsibilities. This made it hard to navigate, test, and extend.

**Decision:** Refactor `core.py` into focused manager classes:
- `ChatManager` - Chat completion, tool calling, context building
- `ProfileInterface` - Profile CRUD, switching, export/import
- `StyleManager` - Style profile management
- `ModelConfigManager` - Per-model configuration
- `CustomTypeManager` - Custom memory type definitions
- `GroupChatManager` - Multi-profile group conversations

**Rationale:**
- Single Responsibility Principle - each manager does one thing well
- Easier testing - test managers in isolation
- Easier navigation - find code by domain
- Easier extension - add new managers without touching core

**Trade-offs:**
- More files to navigate
- Indirection through delegation
- Worth it for maintainability

**Status:** ACCEPTED - Implemented in `managers/` directory

---

### D020: ALTERNATING Strategy Consolidation

**Context:** The `ModelStrategy` enum had both `ALTERNATING` and `ROUND_ROBIN`, which were functionally identical (cycle through models in order).

**Decision:** Consolidate to a single `ALTERNATING` strategy. Migration code converts `ROUND_ROBIN` to `ALTERNATING` when loading profiles.

**Rationale:**
- Reduces confusion - no need to choose between identical options
- Simpler codebase - one code path instead of two
- Migration is automatic and non-breaking

**Trade-offs:**
- Users with `ROUND_ROBIN` see their setting renamed
- Minor documentation updates needed

**Status:** ACCEPTED - Migration implemented in `Profile.from_dict()`

---

### D021: Profile Memory Scoping

**Context:** With profiles as first-class citizens, we need to determine how memories are scoped and shared.

**Decision:** Implement scoped memories with shared option:
- `profile_scope = profile_id` for profile-specific memories
- `profile_scope = NULL` for shared memories
- `access_shared_memories` flag controls whether profile sees shared pool

**Rationale:**
- Default behavior isolates profiles (safe)
- Shared memories enable cross-profile knowledge (powerful)
- Per-profile control over shared access (flexible)

**Trade-offs:**
- More complex retrieval logic
- Users must understand scoping

**Status:** ACCEPTED - Implemented

---

### D022: Group Chat Sequential Turn Order

**Context:** When multiple profiles respond to the same message, should they respond in parallel or sequence?

**Decision:** Default to sequential turn order. All profiles respond in order, each seeing previous responses.

**Rationale:**
- Profiles can reference each other's responses
- Natural conversation flow
- Richer dialogue

**Trade-offs:**
- Slower than parallel (N API calls in sequence)
- Can configure parallel for speed when cross-reference isn't needed

**Status:** ACCEPTED - Implemented in GroupChatManager

---

## Implementation Notes

### Migration from Old Decisions

Some older decisions have been superseded:

| Original | New | Notes |
|----------|-----|-------|
| `RitualDepth` enum | Freeform `philosophy` field | D016 |
| `model_scope` isolation | `profile_scope` isolation | D017, D021 |
| Single provider | Multi-provider with ProviderManager | D018 |
| Monolithic core.py | Manager classes | D019 |
| ROUND_ROBIN strategy | ALTERNATING (consolidated) | D020 |

### Questions for Future Resolution

1. **Cross-Profile Memory Bridging:** Should profiles share specific memories explicitly?
2. **Profile Inheritance:** Should profiles inherit from templates?
3. **Collaborative Profiles:** Can multiple users share a profile?
4. **Training Integration:** How do we export data for fine-tuning?

---

*These decisions are not decrees. They are lanterns on a path. Carry them forward, or set them down with intention.*
