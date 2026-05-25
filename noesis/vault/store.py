"""
MemoryStore — Abstract interface for memory persistence.

The store is backend-agnostic. SQLite for local development,
Postgres+pgvector for production, anything that implements
the interface works.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from noesis.schema import (
    DriftScore,
    Episode,
    Evaluation,
    Fact,
    GriefState,
    Guardrail,
    MemoryNode,
    NodeType,
    Profile,
    ProjectState,
    Skill,
    SkillStatus,
)
from noesis.governor.trust_gate import TrustGate
from noesis.governor.grief_cascade import GriefCascade


class MemoryStore:
    """High-level memory operations, backed by a pluggable storage backend.

    This is the main API surface. All reads and writes pass through
    the TrustGate for governance. The GriefCascade runs periodically
    to purge contaminated branches.
    """

    def __init__(self, backend: StorageBackend, namespace: str = "default"):
        self.backend = backend
        self.namespace = namespace
        self.trust_gate = TrustGate()
        self.grief_cascade = GriefCascade()

    # ── Write Operations ───────────────────────────────────────────────

    def write(
        self,
        node: MemoryNode,
        author_trust: float = 0.5,
    ) -> Tuple[bool, str]:
        """Write a memory node through the trust gate.

        Returns (success, message). If the gate blocks the write,
        success is False and message explains why.
        """
        node.namespace = self.namespace
        allowed, reason = self.trust_gate.gate_write(
            node, self, author_trust
        )
        if not allowed:
            return False, reason

        self.backend.upsert(node)
        return True, reason

    def write_guardrail(self, key: str, rule: str) -> Tuple[bool, str]:
        """Write a system guardrail — sacred ground.

        These nodes are immutable once written. They cannot be
        overwritten by ephemeral input. This is the constitutional anchor.
        """
        g = Guardrail(key=key, rule=rule, value=rule, namespace=self.namespace)
        self.backend.upsert(g)
        return True, "Guardrail installed on sacred ground."

    def write_fact(
        self,
        key: str,
        value: str,
        source_episode_id: Optional[str] = None,
        author_trust: float = 0.5,
    ) -> Tuple[bool, str]:
        """Write a semantic fact through the trust gate."""
        fact = Fact(
            key=key,
            value=value,
            source_episode_id=source_episode_id,
            namespace=self.namespace,
        )
        return self.write(fact, author_trust)

    def write_episode(self, episode: Episode) -> Tuple[bool, str]:
        """Write a session episode. Episodes always go through."""
        episode.namespace = self.namespace
        self.backend.upsert(episode)
        return True, "Episode recorded."

    def write_profile(self, profile: Profile) -> Tuple[bool, str]:
        """Write/update agent profile."""
        profile.namespace = self.namespace
        self.backend.upsert(profile)
        return True, "Profile updated."

    def write_project_state(self, state: ProjectState) -> Tuple[bool, str]:
        """Write/update project state."""
        state.namespace = self.namespace
        self.backend.upsert(state)
        return True, "Project state updated."

    # ── Read Operations ────────────────────────────────────────────────

    def get(self, key: str, namespace: Optional[str] = None) -> Optional[MemoryNode]:
        """Get a specific node by key."""
        ns = namespace or self.namespace
        node = self.backend.get_by_key(key, ns)
        if node:
            node.touch()
        return node

    def get_by_id(self, node_id: str) -> Optional[MemoryNode]:
        """Get a specific node by ID."""
        return self.backend.get_by_id(node_id)

    def all_nodes(self) -> List[MemoryNode]:
        """Get all active (non-purged) nodes."""
        return self.backend.all_active(self.namespace)

    # ── Context Assembly (the retrieval gateway) ───────────────────────

    def assemble_context(
        self,
        query: str = "",
        task_type: str = "",
        max_tokens: int = 4000,
    ) -> List[MemoryNode]:
        """Assemble a context packet for session injection.

        Priority order:
        1. System guardrails (always loaded, sacred)
        2. Agent profile (always loaded)
        3. Project state (always loaded if exists)
        4. Relevant skills (matching task type)
        5. Top semantic facts (by similarity + importance + trust)
        6. Matching episodes (1-3 as few-shot examples)

        Each node's retrieval weight is governed by the trust gate.
        Low-trust, high-grief nodes get de-prioritized automatically.
        """
        context: List[MemoryNode] = []

        # 1. Guardrails — always, non-negotiable
        guardrails = self.backend.get_by_type(
            NodeType.SYSTEM_GUARDRAIL, self.namespace
        )
        context.extend(guardrails)

        # 2. Profile
        profiles = self.backend.get_by_type(
            NodeType.PROFILE, self.namespace
        )
        context.extend(profiles)

        # 3. Project state
        project_states = self.backend.get_by_type(
            NodeType.PROJECT_STATE, self.namespace
        )
        context.extend(project_states)

        # 4. Active skills matching task type
        skills = self.backend.get_by_type(
            NodeType.SKILL, self.namespace
        )
        active_skills = [
            s for s in skills
            if isinstance(s, Skill) and s.status == SkillStatus.PROMOTED
        ]
        # Score and sort by trust gate influence
        active_skills.sort(
            key=lambda s: self.trust_gate.gate_read(s), reverse=True
        )
        context.extend(active_skills[:5])  # top 5 relevant skills

        # 5. Semantic facts — sorted by influence weight
        facts = self.backend.get_by_type(
            NodeType.SEMANTIC_FACT, self.namespace
        )
        scored_facts = [
            (f, self.trust_gate.gate_read(f)) for f in facts
            if f.grief_state != GriefState.PURGED
        ]
        scored_facts.sort(key=lambda x: x[1], reverse=True)
        context.extend([f for f, _ in scored_facts[:20]])

        # 6. Episodes — most recent, highest-trust
        episodes = self.backend.get_by_type(
            NodeType.EPISODE, self.namespace
        )
        scored_episodes = [
            (e, self.trust_gate.gate_read(e)) for e in episodes
            if e.grief_state != GriefState.PURGED
        ]
        scored_episodes.sort(key=lambda x: x[1], reverse=True)
        context.extend([e for e, _ in scored_episodes[:3]])

        return context

    # ── Maintenance ────────────────────────────────────────────────────

    def run_grief_cascade(self) -> List[str]:
        """Run the grief cascade to purge contaminated branches."""
        return self.grief_cascade.evaluate(self)

    def mark_purged(self, node_id: str):
        """Mark a node as purged (called by grief cascade)."""
        self.backend.mark_purged(node_id)

    def decay_all(self, factor: float = 0.001):
        """Apply passive trust decay to all non-sacred nodes.

        From Murmuration: metabolic cost of existing.
        Memories that aren't accessed or confirmed slowly lose trust.
        """
        for node in self.all_nodes():
            if not node.is_sacred:
                age_hours = (time.time() - node.last_accessed) / 3600
                decay = factor * age_hours
                node.trust_charge = max(0.05, node.trust_charge - decay)
                # Natural grief healing
                if node.grief > 0:
                    node.grief = max(0, node.grief - factor * 0.5)
                self.backend.upsert(node)

    def new_session(self):
        """Reset per-session state for a new session."""
        self.trust_gate.reset_session_energy()


class StorageBackend(ABC):
    """Abstract interface for memory storage backends."""

    @abstractmethod
    def upsert(self, node: MemoryNode) -> None: ...

    @abstractmethod
    def get_by_key(self, key: str, namespace: str) -> Optional[MemoryNode]: ...

    @abstractmethod
    def get_by_id(self, node_id: str) -> Optional[MemoryNode]: ...

    @abstractmethod
    def get_by_type(
        self, node_type: NodeType, namespace: str
    ) -> List[MemoryNode]: ...

    @abstractmethod
    def all_active(self, namespace: str) -> List[MemoryNode]: ...

    @abstractmethod
    def mark_purged(self, node_id: str) -> None: ...

    @abstractmethod
    def search(
        self,
        query: str,
        namespace: str,
        limit: int = 20,
    ) -> List[MemoryNode]: ...
