# Architectural Decisions: Profile-Based Threadlight

## Decision Record

This document records the key architectural decisions for the profile-based architecture.

---

## ADR-001: Profiles as First-Class Citizens

### Context

Threadlight currently uses `model_scope` to isolate memories per model. Users have requested the ability to maintain persistent personas that can use different models while keeping their memories and personality intact.

### Decision

**Profiles replace models as the primary organizational unit.**

A Profile is:
- A persistent identity with name, description, and personality
- Owner of a memory namespace
- Configurable to use any supported model
- Model-agnostic in its relationship with the user

### Consequences

Positive:
- Users bond with personas, not technical model names
- Same persona can improve as better models emerge
- Memory persists across model changes
- Cleaner mental model for users

Negative:
- Migration required from `model_scope` to `profile_scope`
- Additional abstraction layer
- Profile management overhead

### Status: ACCEPTED

---

## ADR-002: Memory Scoping Strategy

### Context

With profiles as first-class citizens, we need to determine how memories are scoped and shared.

### Options Considered

1. **Strict isolation**: Each profile has completely separate memories
2. **Shared pool with tagging**: All memories in one pool, tagged by profile
3. **Scoped with shared option**: Profile-specific memories + optional shared memories

### Decision

**Option 3: Scoped with shared option.**

- `profile_scope = profile_id` for profile-specific memories
- `profile_scope = NULL` for shared memories
- `access_shared_memories` flag controls whether profile sees shared pool

### Rationale

This provides maximum flexibility:
- Default behavior isolates profiles (safe)
- Shared memories enable cross-profile knowledge (powerful)
- Per-profile control over shared access (flexible)

### Status: ACCEPTED

---

## ADR-003: Alloyed Profile Model Selection

### Context

Users want profiles that can use multiple models in various patterns (alternating, ratio-based, dynamic routing).

### Decision

**Support multiple model selection strategies via AlloyedConfig.**

Strategies:
- `SINGLE`: Always use one model
- `ALTERNATING`: Cycle through pool
- `RATIO`: Follow pattern like [H, H, C]
- `WEIGHTED`: Random with weights
- `DYNAMIC`: Rule-based selection
- `ROUND_ROBIN`: Equal rotation

State is persisted in `model_pattern` field of Profile.

### Consequences

Positive:
- Flexible model usage patterns
- State survives restarts
- Extensible for new strategies

Negative:
- Complexity in model selection logic
- State management overhead
- Debugging complexity

### Status: ACCEPTED

---

## ADR-004: Group Chat Turn Order

### Question

> Group chat turn order: Sequential or all-at-once?

### Decision

**Configurable, defaulting to Sequential.**

Turn order strategies:
- `SEQUENTIAL`: All profiles respond in order (default)
- `PARALLEL`: All respond simultaneously
- `ROUND_ROBIN`: One per turn, rotating
- `ADDRESSED`: Only @mentioned respond
- `VOLUNTEER`: System picks best fit
- `DEBATE`: Alternating "teams"

### Rationale

Sequential allows:
- Profiles to reference each other's responses
- Natural conversation flow
- Richer dialogue

Parallel is available when:
- Speed matters more than cross-reference
- Independent opinions are desired
- API rate limits are not a concern

### Status: ACCEPTED

---

## ADR-005: Profile Memory Visibility in Group Chat

### Question

> Can profiles see each other's memories in group chat?

### Decision

**No. Memory isolation is maintained.**

Each profile only sees:
- Its own profile-scoped memories
- Shared memories (if `access_shared_memories=True`)

In group chat context:
- Profiles see each other's **responses** (if `allow_inter_profile_reference=True`)
- Profiles do NOT see each other's **memories**

### Rationale

The persona abstraction should be maintained. If Fable has a memory about user's pet, that doesn't mean Debug Buddy should also know about it unless:
1. It's explicitly shared
2. Fable mentions it in a response that Debug Buddy can reference

### Status: ACCEPTED

---

## ADR-006: Alloyed State Persistence

### Question

> Where to persist which model's "turn" it is for alloyed profiles?

### Decision

**In the Profile's `model_pattern` field.**

The `AlloyedConfig.to_dict()` method includes:
- `current_index`: Position in rotation
- `turn_count`: Total turns for ratio calculation

This is persisted to the database in the `model_pattern` column.

### Rationale

- State survives application restarts
- State is scoped to the profile (not global)
- No additional tables needed
- Easy to reset (just update the profile)

### Status: ACCEPTED

---

## ADR-007: Default Mode

### Question

> Default behavior - single profile mode vs group mode?

### Decision

**Single profile mode is the default.**

- Threadlight defaults to a single active profile
- Group chat must be explicitly created
- Most interactions are expected to be 1:1

### Rationale

- Simplest mental model for new users
- Group chat is an advanced feature
- Performance: single profile requires fewer API calls
- Aligns with existing chat interface patterns

### Status: ACCEPTED

---

## ADR-008: Migration Strategy

### Context

Existing users have data with `model_scope` that needs to migrate to `profile_scope`.

### Decision

**Automatic migration on database upgrade.**

Migration steps:
1. Add `profile_scope` column to capsules
2. Add `profiles` table
3. For each unique `model_scope`:
   - Create a profile with that name
   - Set `profile_scope = model_scope` for matching capsules
4. Add `profile_id` to messages table
5. Preserve `model_scope` temporarily for rollback

### Status: ACCEPTED

---

## ADR-009: Profile Export Format

### Decision

**JSON-based export with version field.**

```json
{
  "version": "1.0",
  "export_type": "profile",
  "exported_at": "2026-01-30T...",
  "profile": { ... },
  "memories": [ ... ],
  "conversations": [ ... ]
}
```

### Rationale

- Self-describing format
- Version allows future format changes
- Optional inclusion of memories/conversations
- Human-readable for debugging

### Status: ACCEPTED

---

## ADR-010: API Design Philosophy

### Decision

**Maintain backward compatibility with gradual profile adoption.**

- Existing `tl.chat()` continues to work
- Profile switching via `tl.switch_profile(name)`
- Profile management via `tl.profiles.*`
- Group chat via `tl.create_group_chat(...)`

Code that doesn't use profiles should work unchanged.

### Status: ACCEPTED

---

## Implementation Priority

Based on these decisions, the implementation priority is:

1. **Phase 1**: Core Profile data model and storage
2. **Phase 2**: Memory scoping (`profile_scope`)
3. **Phase 3**: Alloyed profiles and model strategies
4. **Phase 4**: Threadlight integration
5. **Phase 5**: Group chat
6. **Phase 6**: Export/Import, templates, polish

---

## Open Questions (Deferred)

### Cross-Profile Memory Bridging

Should profiles be able to explicitly share specific memories with each other?

**Status**: Deferred to future release. Initial implementation will not include this.

### Profile Inheritance

Should profiles be able to inherit from other profiles?

**Status**: Deferred. Too complex for initial release.

### Collaborative Profiles

Should multiple users be able to share a profile?

**Status**: Deferred. Requires multi-user infrastructure.

---

## Document History

| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2026-01-30 | 1.0 | Architecture Session | Initial decisions |
