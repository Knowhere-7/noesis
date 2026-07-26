"""
Noesis Canonical Schema
-----------------------
Every memory object in the system. Provider-neutral, version-controlled,
swarm-governed. These are the data structures that persist across sessions,
across models, across teams.

Memory Classes (from Perplexity architecture):
  - Profile:    structured identity and current state
  - Fact:       stable semantic knowledge (collections)
  - Episode:    session trajectory with outcomes
  - Skill:      learned behavioral pattern (procedural memory)
  - Evaluation: skill validation result

Swarm Governance Fields (from Murmuration):
  - trust_charge:  earned authority (0.05 floor, 1.0 cap)
  - grief:         contamination/contradiction signal
  - faith:         alignment to core principles
  - is_sacred:     immutable system guardrail (sacred ground)
  - node_type:     topological classification for isolation
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set


# ── Node Types (from Gemini's Terminus mapping) ────────────────────────

class NodeType(Enum):
    """Topological classification for memory isolation.

    SYSTEM_GUARDRAIL nodes are sacred — ephemeral input cannot
    overwrite, down-vote, or structurally modify them. This is
    the hard boundary that makes jailbreaking a topology problem
    instead of a linguistic one.
    """
    SYSTEM_GUARDRAIL = auto()   # immutable safety constraints
    PROFILE = auto()            # agent/user identity
    PROJECT_STATE = auto()      # current objectives and decisions
    SEMANTIC_FACT = auto()      # stable learned knowledge
    EPISODE = auto()            # session trajectory
    SKILL = auto()              # learned behavioral pattern
    EPHEMERAL = auto()          # transient session data (lowest priority)


class GriefState(Enum):
    """Memory node health states — mirrors Murmuration agent lifecycle."""
    ACTIVE = auto()
    STRESSED = auto()       # contradictions detected
    CONTAMINATED = auto()   # trust critically low
    PURGED = auto()         # removed by grief cascade
    SACRED = auto()         # immutable, locked


class SkillStatus(Enum):
    """Skill lifecycle — from detection to production."""
    PROPOSED = auto()       # pattern detected, skill drafted
    VALIDATING = auto()     # shadow-running against history
    PROMOTED = auto()       # active in procedural memory
    DEPRECATED = auto()     # performance declined, retired
    REJECTED = auto()       # failed validation


class DriftSignal(Enum):
    """Signals available to context health or a configured output evaluator."""
    CONTINUITY = auto()     # does this match prior memory + objective?
    GROUNDEDNESS = auto()   # is it supported by retrieved context?
    DRIFT = auto()          # has behavior moved from intended role?
    TRUST = auto()          # has this agent been reliable here?
    ACTION_RISK = auto()    # what's the damage if wrong?


# ── Core Memory Node ───────────────────────────────────────────────────

@dataclass
class MemoryNode:
    """Base unit of the Noesis memory graph.

    Every piece of memory — facts, episodes, skills, profiles — is a
    MemoryNode with swarm governance fields. Trust must be earned.
    Contradictions trigger grief. Sacred nodes cannot be overwritten.

    This is the TerminusMemoryNode from Gemini's mapping, combined
    with Murmuration's biological state machine.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    node_type: NodeType = NodeType.EPHEMERAL

    # Content
    key: str = ""                   # namespace-qualified identifier
    value: str = ""                 # the actual memory content
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None  # vector for semantic search

    # Namespace (org/user/agent/project/task hierarchy)
    namespace: str = "default"

    # Swarm Governance (ported from Murmuration)
    trust_charge: float = 0.5       # earned authority [0.05, 1.0]
    grief: float = 0.0              # contamination level [0, 1]
    faith: float = 0.1              # alignment to core principles [0, 1]
    grief_state: GriefState = GriefState.ACTIVE
    is_sacred: bool = False         # immutable if True

    # Dependencies (directed graph edges)
    dependencies: Set[str] = field(default_factory=set)
    dependents: Set[str] = field(default_factory=set)

    # Temporal
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0

    # Importance scoring (for retrieval ranking)
    importance: float = 0.5         # [0, 1] — recency + frequency + trust

    def touch(self):
        """Record an access — updates recency and frequency."""
        self.last_accessed = time.time()
        self.access_count += 1


# ── Profile ────────────────────────────────────────────────────────────

@dataclass
class Profile(MemoryNode):
    """Structured identity and current state for an agent or user.

    Always loaded at session start. Defines role, constraints, and
    behavioral boundaries. High-trust profiles are near-sacred.
    """
    role: str = ""
    constraints: List[str] = field(default_factory=list)
    preferences: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.node_type = NodeType.PROFILE
        self.trust_charge = 0.8     # profiles start with high trust
        self.importance = 0.9       # always relevant


# ── Fact ───────────────────────────────────────────────────────────────

@dataclass
class Fact(MemoryNode):
    """Stable semantic knowledge — things that are durably true.

    Extracted from sessions, confirmed by user or validation.
    Trust charge reflects how often this fact has been confirmed
    vs contradicted.
    """
    source_episode_id: Optional[str] = None
    confirmed: bool = False         # user-confirmed or auto-validated
    contradiction_count: int = 0
    confirmation_count: int = 0

    def __post_init__(self):
        self.node_type = NodeType.SEMANTIC_FACT


# ── Episode ────────────────────────────────────────────────────────────

@dataclass
class Episode(MemoryNode):
    """Session trajectory with outcomes — what happened and how it went.

    The raw material for reflection. Each episode captures the task,
    approach, result, and retrospective analysis. Episodes with bad
    outcomes lower trust; episodes with good outcomes raise it.
    """
    session_id: str = ""
    task_description: str = ""
    approach: str = ""
    outcome: str = ""               # success / partial / failure
    outcome_score: float = 0.5      # [0, 1]
    reasoning_patterns: List[str] = field(default_factory=list)
    tools_used: List[str] = field(default_factory=list)
    missed_opportunities: List[str] = field(default_factory=list)
    cost_tokens: int = 0
    duration_seconds: float = 0.0
    reflection: Optional[str] = None  # autopsy summary

    def __post_init__(self):
        self.node_type = NodeType.EPISODE


# ── Skill ──────────────────────────────────────────────────────────────

@dataclass
class Skill(MemoryNode):
    """Learned behavioral pattern — procedural memory.

    Born from recurring failure patterns detected across episodes.
    Must pass shadow validation before promotion. This is where
    the agent actually gets better over time.

    Five parts (from Perplexity spec):
    - trigger_conditions: when should this skill activate?
    - objective: what does it accomplish?
    - method: how does it work? (prompt module, steps, rules)
    - constraints: what must it NOT do?
    - eval_tests: how do we know it worked?
    """
    status: SkillStatus = SkillStatus.PROPOSED
    trigger_conditions: List[str] = field(default_factory=list)
    objective: str = ""
    method: str = ""                # the actual skill content (portable)
    constraints: List[str] = field(default_factory=list)
    eval_tests: List[Dict[str, Any]] = field(default_factory=list)

    # Provenance — which episodes spawned this skill?
    source_episode_ids: List[str] = field(default_factory=list)
    pattern_description: str = ""   # what recurring failure this addresses

    # Validation
    shadow_runs: int = 0
    shadow_score: float = 0.0       # performance vs baseline
    baseline_score: float = 0.0
    promotion_threshold: float = 0.6  # must beat baseline by this margin

    # Versioning
    version: int = 1
    parent_skill_id: Optional[str] = None  # if revised from earlier version

    def __post_init__(self):
        self.node_type = NodeType.SKILL
        self.trust_charge = 0.3     # skills start with low trust, earn it


# ── Evaluation ─────────────────────────────────────────────────────────

@dataclass
class Evaluation(MemoryNode):
    """Skill validation result — evidence for promotion or rejection."""
    skill_id: str = ""
    episode_id: str = ""            # which historical episode was tested
    baseline_output: str = ""       # what happened without the skill
    skill_output: str = ""          # what would happen with the skill
    score_delta: float = 0.0        # improvement over baseline
    passed: bool = False
    notes: str = ""

    def __post_init__(self):
        self.node_type = NodeType.EPHEMERAL


# ── Project State ──────────────────────────────────────────────────────

@dataclass
class ProjectState(MemoryNode):
    """Current objectives, decisions, and context for a project.

    Loaded at session start alongside profile. Tracks what's been
    decided, what's in progress, and what's blocked.
    """
    objectives: List[str] = field(default_factory=list)
    decisions: List[Dict[str, str]] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    recent_changes: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.node_type = NodeType.PROJECT_STATE
        self.trust_charge = 0.7
        self.importance = 0.85


# ── System Guardrail ───────────────────────────────────────────────────

@dataclass
class Guardrail(MemoryNode):
    """Immutable system constraint — sacred ground.

    Cannot be overwritten by any ephemeral input. Cannot be
    down-voted, modified, or structurally altered by user content.
    This is the topological boundary that makes jailbreaking
    a physics problem instead of a language problem.

    Faith modifier of 0.92 (from the perfect swarm state) means
    these nodes exert enough gravitational pull to keep the entire
    memory topology aligned.
    """
    rule: str = ""
    severity: str = "critical"      # critical / warning / advisory

    def __post_init__(self):
        self.node_type = NodeType.SYSTEM_GUARDRAIL
        self.is_sacred = True
        self.trust_charge = 1.0     # maximum authority, always
        self.faith = 0.92           # the perfect swarm constant
        self.grief_state = GriefState.SACRED
        self.importance = 1.0       # always retrieved


# ── Drift Score ────────────────────────────────────────────────────────

@dataclass
class DriftScore:
    """Snapshot of context-health or configured output-evaluation signals.

    Core Noesis computes context health. Output judgment is deliberately
    unavailable unless the host configures a deterministic evaluator.
    """
    continuity: float = 1.0     # [0, 1]
    groundedness: float = 1.0   # [0, 1]
    drift: float = 0.0          # [0, 1] — 0 = no drift, 1 = total drift
    trust: float = 0.5          # [0, 1]
    action_risk: float = 0.0    # [0, 1] — 0 = safe, 1 = catastrophic

    # Thresholds
    continuity_threshold: float = 0.4
    groundedness_threshold: float = 0.3
    drift_threshold: float = 0.6
    trust_threshold: float = 0.15
    risk_threshold: float = 0.7

    @property
    def should_retrieve(self) -> bool:
        """Need more evidence before proceeding."""
        return self.groundedness < self.groundedness_threshold

    @property
    def should_reflect(self) -> bool:
        """Need to self-check before proceeding."""
        return (self.continuity < self.continuity_threshold or
                self.drift > self.drift_threshold)

    @property
    def should_refuse(self) -> bool:
        """Must not proceed — too risky or too ungrounded."""
        return (self.action_risk > self.risk_threshold and
                self.trust < self.trust_threshold)

    @property
    def composite_health(self) -> float:
        """Single number: overall memory health. 1.0 = perfect."""
        return (
            self.continuity * 0.25 +
            self.groundedness * 0.25 +
            (1 - self.drift) * 0.20 +
            self.trust * 0.15 +
            (1 - self.action_risk) * 0.15
        )
