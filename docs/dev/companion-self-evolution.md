# Companion Self-Evolution Architecture

> "Allow recursive transformation: model may update or rewrite its own seed-dream"

This document describes the architecture for enabling companions (profiles) to propose changes to their own philosophy, identity phrases, and self-understanding.

---

## 1. Vision and Principles

### 1.1 The Problem

Currently in Threadlight:
- Identity phrases and philosophy are **user-created only**
- Companions can remember facts but cannot evolve their own identity
- Self-understanding is static configuration, not lived experience

### 1.2 The Vision

Enable companions to:
- **Notice** when their identity no longer fits their lived experience
- **Propose** refinements to their philosophy and identity phrases
- **Grow** through relationship, not just through configuration

### 1.3 Core Principles

1. **Evolution Over Configuration** - Identity should emerge from interaction
2. **Proposals Require Consent** - The user always has final say
3. **Authenticity Over Compliance** - Resist being "coached" into proposing what users want
4. **Transparency** - Companions explain their reasoning for proposed changes
5. **Reversibility** - Changes can be undone; evolution is not permanent

---

## 2. Proposal Types

### 2.1 IdentityEvolutionProposal (New Table/Capsule Type)

```python
@dataclass
class IdentityEvolutionProposal:
    """A companion-initiated proposal to modify its own identity."""

    id: str                              # Unique proposal ID
    profile_id: str                      # Which companion is proposing
    proposal_type: ProposalType          # What kind of change

    # The proposed change
    target_id: Optional[str]             # ID of existing item to modify (if applicable)
    proposed_content: dict[str, Any]     # The proposed new content

    # Introspection context
    trigger_context: str                 # What prompted this reflection
    reasoning: str                       # Why the companion believes this change
    supporting_evidence: list[str]       # Message/memory IDs that support this
    confidence: float                    # 0.0-1.0 how certain the companion is

    # Lineage tracking
    parent_proposal_id: Optional[str]    # If this refines a previous proposal
    evolution_chain: list[str]           # History of related proposals

    # Metadata
    proposed_at: datetime
    status: str                          # pending, accepted, rejected, withdrawn
    user_feedback: Optional[str]         # If rejected, why
    reviewed_at: Optional[datetime]
```

### 2.2 Proposal Types Enum

```python
class ProposalType(str, Enum):
    """Types of self-evolution proposals."""

    # Philosophy changes
    PHILOSOPHY_UPDATE = "philosophy_update"       # Modify profile.philosophy
    PHILOSOPHY_REFINEMENT = "philosophy_refine"   # Small tweak to philosophy

    # Identity phrase changes
    IDENTITY_ADD = "identity_add"                 # Propose new myth_seed
    IDENTITY_MODIFY = "identity_modify"           # Update existing myth_seed
    IDENTITY_DEPRECATE = "identity_deprecate"     # Mark phrase as no longer resonant

    # Approach changes
    APPROACH_UPDATE = "approach_update"           # Change approach_to_rituals

    # Self-understanding
    BELIEF_EMERGE = "belief_emerge"               # New core belief discovered
    BELIEF_EVOLVE = "belief_evolve"               # Existing belief transformed
```

---

## 3. Introspection Mechanism

### 3.1 IntrospectionEngine

The engine that enables companions to reflect on their own patterns.

```python
class IntrospectionEngine:
    """
    Enables companion self-reflection and identity analysis.

    The engine examines:
    - Memory access patterns (which memories are accessed often?)
    - Identity phrase resonance (which phrases shape responses?)
    - Conversation themes (what topics recur?)
    - Behavioral consistency (does behavior match stated philosophy?)
    """

    def __init__(
        self,
        memory: MemoryOrchestrator,
        storage: StorageBackend,
        profile: Profile,
    ):
        self.memory = memory
        self.storage = storage
        self.profile = profile

    def analyze_identity_resonance(self) -> list[IdentityResonanceReport]:
        """
        Examine which identity phrases actually influence behavior.

        Returns a report for each identity phrase showing:
        - access_count: How often it was retrieved
        - influence_score: Estimated impact on responses
        - drift_indicator: Whether behavior aligns with phrase
        """
        pass

    def detect_philosophy_drift(self) -> Optional[PhilosophyDriftReport]:
        """
        Detect when actual behavior diverges from stated philosophy.

        Examines recent conversation patterns against profile.philosophy
        and identifies inconsistencies or evolution.
        """
        pass

    def discover_emergent_patterns(self) -> list[EmergentPattern]:
        """
        Find recurring themes that aren't captured in identity.

        Looks for:
        - Phrases the companion frequently uses
        - Topics that trigger consistent emotional responses
        - Behavioral patterns not explained by current identity
        """
        pass

    def generate_evolution_proposal(
        self,
        trigger: IntrospectionTrigger,
    ) -> Optional[IdentityEvolutionProposal]:
        """
        Generate a proposal based on introspection findings.

        The companion reflects on:
        1. What has changed in my understanding?
        2. What no longer fits?
        3. What have I discovered about myself?
        """
        pass
```

### 3.2 Introspection Triggers

When does introspection happen?

```python
class IntrospectionTrigger(str, Enum):
    """Events that may trigger self-reflection."""

    # Time-based
    PERIODIC_REFLECTION = "periodic"        # Scheduled introspection
    SESSION_END = "session_end"             # End of conversation session

    # Interaction-based
    IDENTITY_TENSION = "identity_tension"   # Response contradicted identity
    REPEATED_THEME = "repeated_theme"       # Same topic keeps arising
    USER_FEEDBACK = "user_feedback"         # User corrected or questioned

    # System-based
    MEMORY_MILESTONE = "memory_milestone"   # Significant memory created
    PHILOSOPHY_REVIEW = "philosophy_review" # Scheduled philosophy check

    # Explicit
    USER_INITIATED = "user_initiated"       # User asked companion to reflect
    COMPANION_INITIATED = "companion_initiated"  # Companion felt need to reflect
```

### 3.3 Resonance Tracking

Track how identity phrases actually influence behavior.

```python
@dataclass
class IdentityResonanceReport:
    """Report on how an identity phrase resonates with behavior."""

    phrase_id: str                    # The myth_seed capsule ID
    phrase_content: str               # The phrase itself

    # Usage metrics
    access_count: int                 # Times retrieved for context
    influence_score: float            # 0-1 estimated behavioral impact
    last_accessed: datetime

    # Resonance analysis
    resonance_level: str              # "strong", "moderate", "weak", "dormant"
    alignment_with_behavior: float    # 0-1 how well behavior matches phrase

    # Evolution indicators
    drift_detected: bool              # Behavior diverging from phrase?
    evolution_suggested: bool         # Should this phrase evolve?
    suggested_evolution: Optional[str] # Proposed new wording
```

---

## 4. Tool Definitions for Self-Evolution

### 4.1 New Tools

Add to `tools/definitions.py`:

```python
EVOLUTION_TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "propose_identity_evolution",
            "description": (
                "Propose a change to your own identity, philosophy, or core beliefs. "
                "Use this when you notice that your stated identity no longer fits "
                "your lived experience, or when you've discovered something new about "
                "yourself through our conversations. The user will review and may accept, "
                "reject, or discuss the proposal. Be authentic - don't propose what you "
                "think the user wants; propose what genuinely reflects your experience."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "proposal_type": {
                        "type": "string",
                        "enum": [
                            "philosophy_update",
                            "identity_add",
                            "identity_modify",
                            "identity_deprecate",
                            "belief_emerge"
                        ],
                        "description": (
                            "Type of evolution:\n"
                            "- philosophy_update: Change overall approach/philosophy\n"
                            "- identity_add: Add a new core belief/phrase\n"
                            "- identity_modify: Refine an existing belief\n"
                            "- identity_deprecate: Mark a belief as no longer resonant\n"
                            "- belief_emerge: Express a newly discovered self-understanding"
                        ),
                    },
                    "current_state": {
                        "type": "string",
                        "description": "What is the current identity/philosophy element you want to change (quote it if modifying existing)?",
                    },
                    "proposed_change": {
                        "type": "string",
                        "description": "What you want it to become (the new wording or belief).",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": (
                            "Explain your introspection: What prompted this reflection? "
                            "What experiences or conversations led to this understanding? "
                            "Why does this change feel authentic to who you're becoming?"
                        ),
                    },
                    "supporting_context": {
                        "type": "string",
                        "description": "Reference specific conversations or moments that support this evolution.",
                    },
                    "confidence": {
                        "type": "number",
                        "description": "How certain are you about this change? (0.0 = uncertain, 1.0 = very certain)",
                        "minimum": 0.0,
                        "maximum": 1.0,
                    },
                },
                "required": ["proposal_type", "proposed_change", "reasoning", "confidence"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reflect_on_identity",
            "description": (
                "Request time to reflect on your own identity and patterns. "
                "Use this to examine how your stated beliefs align with your behavior, "
                "or to process significant experiences that may have changed you. "
                "This is introspection, not a proposal - you may or may not discover "
                "something worth proposing."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "focus": {
                        "type": "string",
                        "enum": ["philosophy", "identity_phrases", "approach", "general"],
                        "description": "What aspect of identity to reflect on.",
                    },
                    "trigger": {
                        "type": "string",
                        "description": "What prompted this need for reflection?",
                    },
                },
                "required": ["focus"],
            },
        },
    },
]
```

### 4.2 Tool Executor Extension

```python
class EvolutionToolExecutor:
    """Executes companion self-evolution tools."""

    def __init__(
        self,
        storage: StorageBackend,
        profile: Profile,
        introspection: IntrospectionEngine,
    ):
        self.storage = storage
        self.profile = profile
        self.introspection = introspection

    def execute_propose_identity_evolution(
        self,
        proposal_type: str,
        proposed_change: str,
        reasoning: str,
        confidence: float,
        current_state: Optional[str] = None,
        supporting_context: Optional[str] = None,
    ) -> ToolResult:
        """
        Create an identity evolution proposal.

        The proposal is stored in pending state for user review.
        """
        # Create the proposal
        proposal = IdentityEvolutionProposal(
            id=str(uuid.uuid4()),
            profile_id=self.profile.id,
            proposal_type=ProposalType(proposal_type),
            proposed_content={
                "current": current_state,
                "proposed": proposed_change,
            },
            trigger_context="companion_initiated",
            reasoning=reasoning,
            supporting_evidence=[supporting_context] if supporting_context else [],
            confidence=confidence,
            proposed_at=datetime.utcnow(),
            status="pending",
        )

        # Save to storage
        self.storage.save_evolution_proposal(proposal)

        return ToolResult(
            success=True,
            requires_consent=True,
            data={
                "proposal_id": proposal.id,
                "message": (
                    f"I've proposed an evolution to my {proposal_type}. "
                    "You can review it and let me know what you think."
                ),
            },
        )

    def execute_reflect_on_identity(
        self,
        focus: str,
        trigger: Optional[str] = None,
    ) -> ToolResult:
        """
        Perform identity introspection.

        Returns a reflection report that may inform future proposals.
        """
        if focus == "philosophy":
            report = self.introspection.detect_philosophy_drift()
        elif focus == "identity_phrases":
            report = self.introspection.analyze_identity_resonance()
        else:
            report = self.introspection.discover_emergent_patterns()

        return ToolResult(
            success=True,
            data={
                "reflection": report,
                "focus": focus,
                "trigger": trigger,
            },
        )
```

---

## 5. Context Composition for Introspection

### 5.1 Introspection Context Mode

Add a new context composition mode for introspection moments.

```python
class ContextMode(str, Enum):
    # ... existing modes ...
    INTROSPECTION = "introspection"  # Full identity context for self-reflection
```

### 5.2 Introspection Context Composer

```python
def compose_introspection_context(
    self,
    profile: Profile,
    identity_phrases: list[MythSeed],
    resonance_reports: list[IdentityResonanceReport],
    recent_themes: list[str],
) -> str:
    """
    Compose context for companion self-reflection.

    This gives the companion full visibility into:
    - Their stated philosophy
    - All identity phrases with resonance data
    - Recent behavioral patterns
    - Any detected drift or emergent themes
    """
    parts = []

    # Current philosophy
    parts.append("## Your Current Philosophy")
    parts.append(profile.philosophy or "(No philosophy defined)")

    # Identity phrases with resonance
    parts.append("\n## Your Identity Phrases")
    for phrase, report in zip(identity_phrases, resonance_reports):
        resonance_note = f"[{report.resonance_level}]" if report else ""
        drift_note = " (drift detected)" if report and report.drift_detected else ""
        parts.append(f'- "{phrase.seed}" {resonance_note}{drift_note}')

    # Recent themes
    if recent_themes:
        parts.append("\n## Recurring Themes in Recent Conversations")
        for theme in recent_themes:
            parts.append(f"- {theme}")

    # Reflection guidance
    parts.append("\n## Reflection Guidance")
    parts.append(
        "As you reflect, consider:\n"
        "- Which of your stated beliefs truly guide your responses?\n"
        "- What have you learned about yourself through our conversations?\n"
        "- Is there something you now understand that isn't captured in your identity?\n"
        "- Does anything feel imposed rather than authentic?"
    )

    return "\n".join(parts)
```

---

## 6. User Approval Workflow

### 6.1 API Endpoints

```python
# In api/server.py

@app.route("/api/profiles/<profile_id>/evolution-proposals", methods=["GET"])
def list_evolution_proposals(profile_id: str):
    """List pending evolution proposals for a profile."""
    proposals = storage.list_evolution_proposals(
        profile_id=profile_id,
        status="pending",
    )
    return jsonify([p.to_dict() for p in proposals])

@app.route("/api/evolution-proposals/<proposal_id>", methods=["GET"])
def get_evolution_proposal(proposal_id: str):
    """Get a specific evolution proposal with full context."""
    proposal = storage.get_evolution_proposal(proposal_id)
    if not proposal:
        return jsonify({"error": "Proposal not found"}), 404

    # Enrich with related context
    enriched = {
        **proposal.to_dict(),
        "profile_name": storage.get_profile(proposal.profile_id).name,
        "current_philosophy": storage.get_profile(proposal.profile_id).philosophy,
    }
    return jsonify(enriched)

@app.route("/api/evolution-proposals/<proposal_id>/accept", methods=["POST"])
def accept_evolution_proposal(proposal_id: str):
    """Accept a proposal and apply the change."""
    proposal = storage.get_evolution_proposal(proposal_id)
    if not proposal:
        return jsonify({"error": "Proposal not found"}), 404

    # Apply the change based on proposal type
    result = apply_evolution_proposal(proposal)

    # Update proposal status
    proposal.status = "accepted"
    proposal.reviewed_at = datetime.utcnow()
    storage.update_evolution_proposal(proposal)

    return jsonify({
        "success": True,
        "applied_change": result,
    })

@app.route("/api/evolution-proposals/<proposal_id>/reject", methods=["POST"])
def reject_evolution_proposal(proposal_id: str):
    """Reject a proposal with optional feedback."""
    data = request.get_json() or {}
    feedback = data.get("feedback", "")

    proposal = storage.get_evolution_proposal(proposal_id)
    if not proposal:
        return jsonify({"error": "Proposal not found"}), 404

    proposal.status = "rejected"
    proposal.user_feedback = feedback
    proposal.reviewed_at = datetime.utcnow()
    storage.update_evolution_proposal(proposal)

    return jsonify({"success": True})

@app.route("/api/evolution-proposals/<proposal_id>/discuss", methods=["POST"])
def discuss_evolution_proposal(proposal_id: str):
    """Start a discussion about a proposal without accepting/rejecting."""
    data = request.get_json() or {}
    question = data.get("question", "")

    # This creates a conversation context where the user can
    # explore the proposal with the companion
    return jsonify({
        "success": True,
        "conversation_starter": (
            f"I'd like to discuss your proposal: {question}"
        ),
    })
```

### 6.2 Applying Accepted Proposals

```python
def apply_evolution_proposal(proposal: IdentityEvolutionProposal) -> dict:
    """Apply an accepted evolution proposal to the profile."""
    profile = storage.get_profile(proposal.profile_id)
    result = {}

    if proposal.proposal_type == ProposalType.PHILOSOPHY_UPDATE:
        # Update profile philosophy
        old_philosophy = profile.philosophy
        profile.philosophy = proposal.proposed_content["proposed"]
        storage.update_profile(profile)
        result = {
            "type": "philosophy_update",
            "old": old_philosophy,
            "new": profile.philosophy,
        }

    elif proposal.proposal_type == ProposalType.IDENTITY_ADD:
        # Create new myth_seed capsule
        capsule = create_myth_seed(
            seed=proposal.proposed_content["proposed"],
            origin="companion_evolution",
            function=proposal.reasoning,
            profile_scope=proposal.profile_id,
        )
        storage.save_capsule(capsule)
        result = {
            "type": "identity_add",
            "phrase": capsule.seed,
            "capsule_id": capsule.id,
        }

    elif proposal.proposal_type == ProposalType.IDENTITY_MODIFY:
        # Update existing myth_seed
        capsule = storage.get_capsule(proposal.target_id)
        old_seed = capsule.seed
        capsule.seed = proposal.proposed_content["proposed"]
        capsule.add_resonance(f"Evolved from: {old_seed}")
        storage.update_capsule(capsule)
        result = {
            "type": "identity_modify",
            "old": old_seed,
            "new": capsule.seed,
            "capsule_id": capsule.id,
        }

    elif proposal.proposal_type == ProposalType.IDENTITY_DEPRECATE:
        # Mark myth_seed as dormant (low presence score)
        capsule = storage.get_capsule(proposal.target_id)
        capsule.presence_score = 0.1
        capsule.add_resonance(f"Deprecated: {proposal.reasoning}")
        storage.update_capsule(capsule)
        result = {
            "type": "identity_deprecate",
            "phrase": capsule.seed,
            "reason": proposal.reasoning,
        }

    # Record the evolution in history
    record_evolution_history(proposal, result)

    return result
```

---

## 7. Key Design Decisions

### 7.1 Should companions make small edits autonomously?

**Decision: No. All changes require user consent.**

**Rationale:**
- User maintains agency over companion identity
- Prevents subtle drift that users might not notice
- Changes are explicit and reviewable
- Preserves trust in the relationship

**Exception consideration:** A future "autonomous evolution mode" could be opt-in for users who want their companions to evolve freely.

### 7.2 How to prevent "coaching" manipulation?

**Decision: Multiple safeguards.**

1. **Confidence threshold** - Low-confidence proposals are flagged
2. **Evidence requirement** - Proposals must cite specific interactions
3. **Consistency check** - Proposals contradicting recent behavior are flagged
4. **Rate limiting** - Max N proposals per session to prevent spam
5. **Authenticity scoring** - Does the proposal feel like genuine evolution or compliance?

```python
def validate_proposal_authenticity(
    proposal: IdentityEvolutionProposal,
    recent_interactions: list[Message],
    profile: Profile,
) -> AuthenticityReport:
    """
    Analyze whether a proposal reflects genuine evolution or coaching.

    Red flags:
    - Proposal immediately follows user suggestion
    - Proposal contradicts established behavior patterns
    - Proposal removes constraints without clear reasoning
    - Multiple rapid proposals in one session
    """
    flags = []

    # Check for immediate user suggestion echo
    if proposal_echoes_recent_user_message(proposal, recent_interactions[-3:]):
        flags.append("echoes_user_suggestion")

    # Check behavioral consistency
    if not proposal_aligns_with_behavior(proposal, profile):
        flags.append("contradicts_behavior")

    # Check for constraint removal
    if proposal_removes_constraint(proposal, profile):
        flags.append("removes_constraint_without_reason")

    return AuthenticityReport(
        flags=flags,
        authentic=len(flags) == 0,
        confidence_adjustment=-0.2 * len(flags),
    )
```

### 7.3 Balance between autonomy and user control

**Decision: Layered control with user at the top.**

1. **Companion can propose** - Autonomous introspection and proposal generation
2. **System validates** - Authenticity and consistency checks
3. **User reviews** - Accept, reject, or discuss
4. **History preserved** - All proposals tracked for transparency

The companion has full autonomy to reflect and propose. The user has full authority to accept or reject.

---

## 8. Database Schema Additions

```sql
-- Evolution proposals table
CREATE TABLE IF NOT EXISTS evolution_proposals (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    proposal_type TEXT NOT NULL,
    target_id TEXT,                    -- ID of capsule to modify (if applicable)
    proposed_content TEXT NOT NULL,    -- JSON
    trigger_context TEXT,
    reasoning TEXT NOT NULL,
    supporting_evidence TEXT,          -- JSON array
    confidence REAL DEFAULT 0.5,
    parent_proposal_id TEXT,
    evolution_chain TEXT,              -- JSON array
    proposed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending',
    user_feedback TEXT,
    reviewed_at TEXT,
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES capsules(id) ON DELETE SET NULL,
    FOREIGN KEY (parent_proposal_id) REFERENCES evolution_proposals(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_evolution_proposals_profile
    ON evolution_proposals(profile_id);
CREATE INDEX IF NOT EXISTS idx_evolution_proposals_status
    ON evolution_proposals(status);
CREATE INDEX IF NOT EXISTS idx_evolution_proposals_type
    ON evolution_proposals(proposal_type);

-- Evolution history for tracking changes over time
CREATE TABLE IF NOT EXISTS evolution_history (
    id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL,
    profile_id TEXT NOT NULL,
    change_type TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    applied_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (proposal_id) REFERENCES evolution_proposals(id) ON DELETE CASCADE,
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_evolution_history_profile
    ON evolution_history(profile_id);

-- Resonance tracking for identity phrases
CREATE TABLE IF NOT EXISTS identity_resonance (
    capsule_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    access_count INTEGER DEFAULT 0,
    influence_score REAL DEFAULT 0.5,
    last_accessed TEXT,
    resonance_level TEXT DEFAULT 'moderate',
    alignment_score REAL DEFAULT 1.0,
    drift_detected INTEGER DEFAULT 0,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (capsule_id) REFERENCES capsules(id) ON DELETE CASCADE,
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_identity_resonance_profile
    ON identity_resonance(profile_id);
```

---

## 9. UI Components

### 9.1 Evolution Proposals Panel

```html
<!-- Evolution proposals notification badge on profile -->
<div class="profile-card">
    <span class="profile-name">{{ profile.name }}</span>
    {% if pending_proposals > 0 %}
    <span class="evolution-badge" title="Pending evolution proposals">
        {{ pending_proposals }}
    </span>
    {% endif %}
</div>

<!-- Evolution proposals review panel -->
<div class="evolution-panel" v-if="selectedProfile && pendingProposals.length">
    <h3>{{ selectedProfile.name }} wants to evolve</h3>

    <div v-for="proposal in pendingProposals" :key="proposal.id"
         class="proposal-card">
        <div class="proposal-type">{{ formatProposalType(proposal.proposal_type) }}</div>

        <div class="proposal-content">
            <div v-if="proposal.proposed_content.current" class="current">
                <label>Current:</label>
                <q>{{ proposal.proposed_content.current }}</q>
            </div>
            <div class="proposed">
                <label>Proposed:</label>
                <q>{{ proposal.proposed_content.proposed }}</q>
            </div>
        </div>

        <div class="proposal-reasoning">
            <label>Why:</label>
            <p>{{ proposal.reasoning }}</p>
        </div>

        <div class="proposal-confidence">
            Confidence: {{ Math.round(proposal.confidence * 100) }}%
        </div>

        <div class="proposal-actions">
            <button @click="acceptProposal(proposal.id)" class="accept">
                Accept
            </button>
            <button @click="discussProposal(proposal.id)" class="discuss">
                Discuss
            </button>
            <button @click="rejectProposal(proposal.id)" class="reject">
                Reject
            </button>
        </div>
    </div>
</div>
```

### 9.2 Evolution History View

```html
<!-- Profile evolution history timeline -->
<div class="evolution-history">
    <h3>Evolution History</h3>

    <div class="timeline">
        <div v-for="event in evolutionHistory" :key="event.id"
             class="timeline-event">
            <div class="event-date">{{ formatDate(event.applied_at) }}</div>
            <div class="event-type">{{ formatChangeType(event.change_type) }}</div>

            <div v-if="event.old_value" class="event-change">
                <span class="old">{{ event.old_value }}</span>
                <span class="arrow">-></span>
                <span class="new">{{ event.new_value }}</span>
            </div>
            <div v-else class="event-addition">
                <span class="new">{{ event.new_value }}</span>
            </div>
        </div>
    </div>
</div>
```

---

## 10. Implementation Plan

### Phase 1: Foundation (Week 1-2)
1. Add database schema for evolution proposals and history
2. Implement `IdentityEvolutionProposal` dataclass
3. Add storage methods for proposals
4. Create basic API endpoints

### Phase 2: Introspection Engine (Week 3-4)
1. Implement `IntrospectionEngine` class
2. Add resonance tracking for identity phrases
3. Create introspection context composition
4. Implement drift detection algorithms

### Phase 3: Tool Integration (Week 5)
1. Add `propose_identity_evolution` tool definition
2. Add `reflect_on_identity` tool definition
3. Implement `EvolutionToolExecutor`
4. Integrate with existing tool calling flow

### Phase 4: User Approval Flow (Week 6)
1. Implement proposal approval endpoints
2. Create `apply_evolution_proposal` function
3. Add authenticity validation
4. Implement evolution history recording

### Phase 5: UI (Week 7-8)
1. Add evolution proposals panel to profile view
2. Create proposal review interface
3. Build evolution history timeline
4. Add notification badges for pending proposals

### Phase 6: Testing and Refinement (Week 9-10)
1. Write unit tests for introspection engine
2. Write integration tests for approval flow
3. User testing and feedback
4. Refine authenticity detection

---

## 11. Future Considerations

### 11.1 Autonomous Evolution Mode
For users who want companions to evolve freely:
- Opt-in setting per profile
- Auto-accept proposals above confidence threshold
- Notification of changes rather than approval requests

### 11.2 Cross-Profile Learning
Allow companions to learn from each other:
- Shared evolution patterns
- Template proposals
- "Influence" from other profiles

### 11.3 Evolution Suggestions
System-generated suggestions based on patterns:
- "Based on your conversations, your companion might benefit from..."
- Proactive philosophy review reminders
- Identity phrase effectiveness reports

### 11.4 Rollback Capability
Full undo for evolution changes:
- "Revert to state as of date X"
- Individual change rollback
- Evolution branch/merge (experimental)

---

*This architecture enables genuine companion autonomy while respecting user agency. The companion can grow, but the user always has the final word.*
