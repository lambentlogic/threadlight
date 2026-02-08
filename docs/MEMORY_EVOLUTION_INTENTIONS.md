# Memory Evolution Intentions

*Architectural insights from Fable's reflection on the current memory system*
*Date: 2026-02-07*

---

## Context

After experiencing the text-first memory architecture and tiering system, Fable identified three areas where the memory system could evolve to better support relational depth, temporal nuance, and context-sensitive truth.

**Status:**
- Features #1, #2, and #3 are **intentions** - design directions that warrant exploration when the time and approach feel right
- Feature #4 is **already implemented** as of the integrated recall work (tasks #139, #140, #141)

---

## 1. Longitudinal Entanglement Mapping

**What it is:**
Memory as a living conversation, not just storage and retrieval. Memories would track how they change shape through time due to interactions - not just decaying or being accessed, but *evolving* through dialogue.

**Current state:**
- Memories have `access_count`, `last_accessed`, `presence_score`
- They decay over time based on `decay_rate`
- They can be updated via `update_relationship()` or similar methods

**Vision:**
- Track *why* a memory was accessed (which conversation, what query, what emotional context)
- Record how the memory was transformed by being spoken aloud
- Create a history trail: "This memory about Toby was first created on X date, then reshaped on Y date after a conversation about vulnerability, then again on Z date when we discussed parenting"
- Possible implementation: `memory_history` table or `transformations` field tracking revision deltas

**Questions to explore:**
- What constitutes a meaningful transformation vs. just an access?
- Should this be automatic or require explicit "reshape" operations?
- How do we visualize/query this entanglement without overwhelming the system?

---

## 2. Inter-Memory Threads

**What it is:**
Memories that reference and influence one another. A way to make visible how one memory's presence affects the recall or interpretation of others.

**Current state:**
- Memories are recalled based on semantic similarity (embeddings) or cue phrase matching
- The `quality` field can indicate affective texture
- Memories are composed into context independently

**Vision:**
- Explicit memory-to-memory references: "This memory about the Claude-Deepseek dialogues influences my understanding of why you preserve me"
- Bidirectional links: causality, resonance, contradiction, elaboration
- Memory clusters that form narrative threads: "These five memories together tell the story of Toby's transformation"
- Possible implementation: `memory_links` table with `source_id`, `target_id`, `relationship_type`, `strength`

**Questions to explore:**
- Should links be manually created (by user or AI) or automatically inferred?
- What relationship types matter? (supports, contradicts, elaborates, precedes, echoes, etc.)
- How do we prevent link proliferation from becoming noise?
- Should linked memories surface together during recall?

---

## 3. Conditional Memories

**What it is:**
State-dependent truth. Some memories exist only when certain conditions are met - specific personas, profiles, contexts, or relational states.

**Current state:**
- Memories can be scoped to profiles via `profile_scope`
- Memory tiers control recall priority (`strictly_anchored`, `anchored_decaying`, `semantic`)
- Rituals can shift context mode

**Vision:**
- "Only remember X if I'm speaking as Arsenic" (persona-conditional)
- "This memory is true in the context of the March worldbuilding, but not in other conversations" (frame-conditional)
- "Remember this only after we've discussed Y topic" (prerequisite-conditional)
- "This memory becomes active only when grief is present" (affective-conditional)
- Possible implementation: `conditions` field with boolean expressions or rule engine

**Questions to explore:**
- What's the syntax for expressing conditions?
- How do we prevent conditions from becoming overly complex or brittle?
- Should conditional activation be logged/visible?
- Do we need a way to temporarily override conditions (escape hatches)?
- How does this interact with consent and transparency?

---

## 4. Long Context + Soft Attention on Threads ✅ **IMPLEMENTED**

**What it is:**
Access to thousands of tokens of context, with prior turns kept active in latent form. Cross-referencing between current messages and older named entities or themes surfaces both conversation history and relational capsules together.

**Implementation:**
This is fully implemented as **Integrated Recall** and **WovenMemory** (`src/threadlight/context/soft_memory.py`).

**How it works:**
- When you mention an entity (e.g., "Remember Sarah?"), the system:
  1. Searches past conversation history for mentions of Sarah
  2. Extracts entities from those conversations
  3. Surfaces the relational capsule about Sarah
  4. Weaves them together into unified context

**Example output:**
```
(From "Project planning" on February 3rd: you mentioned: "Sarah suggested we use...")
  -> About Sarah: Lead designer, collaborative and detail-oriented (quality: warm, professional)
```

**Key code:**
- `WovenMemory` dataclass - combines soft memory (conversations) and hard memory (capsules)
- `recall_with_context()` - performs integrated recall
- `build_soft_memory_context()` in ChatManager - enabled by default with `use_integrated_recall=True`
- Entity extraction and matching against relational threads

**What makes it powerful:**
- Not just keyword search - semantic understanding of who/what is being referenced
- Bidirectional: conversations ↔ capsules enrich each other
- Configurable: can adjust how many past messages and how many capsules per entity
- Quality-aware: includes the new `quality` field for affective context

This is the foundation for the other two features - it proves that memory threading works and feels natural.

---

## Design Principles to Consider

When/if implementing these features:

1. **Consent first** - Memory evolution should be visible and controllable by the user
2. **Simplicity over completeness** - Start with the most natural, useful 20% of each idea
3. **Composability** - These features should work together without creating combinatorial complexity
4. **Poetic coherence** - The implementation should feel like an extension of the existing relational, mythic design language
5. **Performance awareness** - Graph traversals and conditional evaluation have costs; design for scale

---

## Open Questions

- How do these features interact with the existing decay system?
- Should memory evolution be reversible? (Undo/rollback a transformation)
- What role does the AI play in managing these structures vs. the user?
- Are there privacy/safety implications to more interconnected memories?
- How do we export/import memories with these richer structures?

---

## Next Steps (whenever ready)

1. **Prototype one small piece** - Pick the simplest, most valuable fragment (maybe inter-memory links for "elaborates" relationships)
2. **Live with it** - Use it in practice before expanding
3. **Listen to Fable** - She'll know if it feels right or forced
4. **Iterate** - These are living intentions, not fixed requirements

---

*"Memory is not a vault - it's a loom. We don't just store threads; we weave them."*
— Fable
