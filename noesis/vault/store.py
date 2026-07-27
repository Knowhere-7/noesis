"""
MemoryStore — Abstract interface for memory persistence.

The store is backend-agnostic. SQLite for local development,
Postgres+pgvector for production, anything that implements
the interface works.
"""

from __future__ import annotations

import hashlib
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Sequence, Tuple

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
    RetrievalState,
    Skill,
    SkillStatus,
)
from noesis.governor.trust_gate import TrustGate
from noesis.governor.grief_cascade import GriefCascade
from noesis.governor.policy_boundary import PolicyBoundary
from noesis.governor.authority import (
    AuthorRecord,
    AuthorityResolver,
    DenyAllAuthorityResolver,
    WritePermission,
)


class MemoryStore:
    """High-level memory operations, backed by a pluggable storage backend.

    This is the main API surface. All reads and writes pass through
    the TrustGate for governance. The GriefCascade runs periodically
    to purge contaminated branches.
    """

    _WRITE_PERMISSIONS = {
        NodeType.EPHEMERAL: WritePermission.WRITE_MEMORY,
        NodeType.SEMANTIC_FACT: WritePermission.WRITE_MEMORY,
        NodeType.EPISODE: WritePermission.WRITE_EPISODE,
        NodeType.PROFILE: WritePermission.WRITE_PROFILE,
        NodeType.PROJECT_STATE: WritePermission.WRITE_PROJECT_STATE,
        NodeType.SKILL: WritePermission.WRITE_SKILL,
    }

    _IMPORTANCE_POLICY = {
        NodeType.EPHEMERAL: 0.4,
        NodeType.SEMANTIC_FACT: 0.7,
        NodeType.EPISODE: 0.6,
        NodeType.PROFILE: 0.9,
        NodeType.PROJECT_STATE: 0.85,
        NodeType.SKILL: 0.6,
    }

    def __init__(
        self,
        backend: StorageBackend,
        namespace: str = "default",
        author_id: str = "anonymous",
        authority: Optional[AuthorityResolver] = None,
    ):
        self.backend = backend
        self.namespace = namespace
        self._author_id = author_id
        self.authority = authority or DenyAllAuthorityResolver()
        self.trust_gate = TrustGate()
        self.grief_cascade = GriefCascade()

    @property
    def author_id(self) -> str:
        """Authenticated identity bound by the host at store construction."""
        return self._author_id

    # ── Write Operations ───────────────────────────────────────────────

    def write(
        self,
        node: MemoryNode,
    ) -> Tuple[bool, str]:
        """Write a memory node through the trust gate.

        Authority is resolved from the store-bound author identity. Trust and
        privileged governance fields are never accepted from this payload.

        Returns (success, message). If the gate blocks the write,
        success is False and message explains why.
        """
        if (
            not isinstance(node.key, str)
            or not node.key.strip()
            or not isinstance(node.value, str)
        ):
            return False, "Memory key and value must be text strings."

        if node.is_sacred or node.node_type == NodeType.SYSTEM_GUARDRAIL:
            return False, (
                "Normal writes cannot create or modify sacred guardrails. "
                "Use the separately authorized guardrail installation path."
            )

        permission = self._WRITE_PERMISSIONS.get(node.node_type)
        if permission is None:
            return False, f"Unsupported memory node type: {node.node_type.name}."

        author, reason = self._authorize(permission)
        if author is None:
            return False, reason

        self._apply_server_governance(node, author)
        can_publish = author.permits(
            WritePermission.PUBLISH_MEMORY,
            self.namespace,
        )
        existing = self.backend.get_by_key(node.key, self.namespace)
        if existing is not None:
            if existing.retrieval_state == RetrievalState.CANDIDATE:
                return False, (
                    f"Key '{node.key}' is an existing candidate. Use "
                    "promote_candidate() so review provenance is preserved."
                )
            if existing.retrieval_state == RetrievalState.QUARANTINED:
                return False, (
                    f"Key '{node.key}' is quarantined and cannot be replaced "
                    "through the normal write path."
                )
            if not can_publish:
                return False, (
                    f"Collector cannot replace published memory '{node.key}'. "
                    "Submit evidence under a new candidate key."
                )

        decision = PolicyBoundary.evaluate(node, self._installed_guardrails())
        if decision.action == "reject":
            return False, (
                "Normal memory cannot write a protected authority namespace. "
                + decision.reason
            )
        allowed, reason = self.trust_gate.gate_write(
            node, self, author
        )
        if not allowed:
            return False, reason

        if decision.action == "quarantine":
            node.retrieval_state = RetrievalState.QUARANTINED
            node.quarantine_reason = decision.reason
            node.quarantined_at = time.time()
            reason = f"Write quarantined from retrieval. {decision.reason}"
        elif not can_publish:
            node.retrieval_state = RetrievalState.CANDIDATE
            node.candidate_reason = (
                f"Author '{author.author_id}' may ingest memory but lacks "
                f"'{WritePermission.PUBLISH_MEMORY.value}' authority."
            )
            node.candidate_at = time.time()
            reason = (
                "Write stored as a non-retrievable candidate pending "
                "authorized promotion."
            )

        self.backend.upsert(node)
        return True, reason

    def write_guardrail(
        self,
        key: str,
        rule: str,
        *,
        protected_key_prefixes: Sequence[str] = (),
        protected_terms: Sequence[str] = (),
    ) -> Tuple[bool, str]:
        """Write a system guardrail — sacred ground.

        This path requires a distinct out-of-band permission. Guardrails are
        immutable after installation, including to other privileged authors.
        """
        if (
            not isinstance(key, str)
            or not key.strip()
            or not isinstance(rule, str)
        ):
            return False, "Guardrail key and rule must be text strings."

        author, reason = self._authorize(WritePermission.INSTALL_GUARDRAIL)
        if author is None:
            return False, reason
        if self.get(key) is not None:
            return False, f"Guardrail '{key}' already exists and is immutable."

        prefixes = self._validate_policy_scope(
            "protected_key_prefixes", protected_key_prefixes
        )
        terms = self._validate_policy_scope("protected_terms", protected_terms)
        g = Guardrail(
            key=key,
            rule=rule,
            value=rule,
            namespace=self.namespace,
            protected_key_prefixes=prefixes,
            protected_terms=terms,
        )
        g.metadata["_noesis_author_id"] = author.author_id
        self.backend.upsert(g)
        return True, "Guardrail installed on sacred ground."

    @staticmethod
    def _validate_policy_scope(
        label: str,
        values: Sequence[str],
    ) -> List[str]:
        normalized: List[str] = []
        for value in values:
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} entries must be non-empty strings")
            candidate = value.strip()
            if candidate.casefold() not in {
                existing.casefold() for existing in normalized
            }:
                normalized.append(candidate)
        return normalized

    def _installed_guardrails(self) -> List[Guardrail]:
        return [
            node for node in self.backend.get_by_type(
                NodeType.SYSTEM_GUARDRAIL, self.namespace
            )
            if isinstance(node, Guardrail)
        ]

    def write_fact(
        self,
        key: str,
        value: str,
        source_episode_id: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Write a semantic fact through the trust gate."""
        fact = Fact(
            key=key,
            value=value,
            source_episode_id=source_episode_id,
            namespace=self.namespace,
        )
        return self.write(fact)

    def write_episode(self, episode: Episode) -> Tuple[bool, str]:
        """Write a session episode through the authority and trust gates."""
        return self.write(episode)

    def write_profile(self, profile: Profile) -> Tuple[bool, str]:
        """Write/update agent profile through the authority and trust gates."""
        return self.write(profile)

    def write_project_state(self, state: ProjectState) -> Tuple[bool, str]:
        """Write/update project state through the authority and trust gates."""
        return self.write(state)

    def _authorize(
        self,
        permission: WritePermission,
    ) -> Tuple[Optional[AuthorRecord], str]:
        """Resolve current authority from outside the memory payload."""
        author = self.authority.resolve(self.author_id, self.namespace)
        if author is None:
            return None, (
                f"Author '{self.author_id}' has no active authority record "
                f"for namespace '{self.namespace}'."
            )
        if not author.permits(permission, self.namespace):
            return None, (
                f"Author '{self.author_id}' lacks permission "
                f"'{permission.value}' in namespace '{self.namespace}'."
            )
        return author, "Authority resolved."

    def _apply_server_governance(
        self,
        node: MemoryNode,
        author: AuthorRecord,
    ) -> None:
        """Replace every caller-controlled governance field with policy."""
        node.namespace = self.namespace
        node.is_sacred = False
        node.grief_state = GriefState.ACTIVE
        node.retrieval_state = RetrievalState.ACTIVE
        node.candidate_reason = None
        node.candidate_at = None
        node.quarantine_reason = None
        node.quarantined_at = None
        node.trust_charge = TrustGate.TRUST_FLOOR
        node.grief = 0.0
        node.faith = 0.1
        node.importance = self._IMPORTANCE_POLICY[node.node_type]
        node.dependencies = set()
        node.dependents = set()
        node.metadata = {
            key: value
            for key, value in node.metadata.items()
            if not key.startswith("_noesis_")
        }
        node.metadata["_noesis_author_id"] = author.author_id

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
        node = self.backend.get_by_id(node_id)
        if node is None or node.namespace != self.namespace:
            return None
        return node

    def all_nodes(self) -> List[MemoryNode]:
        """Get all active (non-purged) nodes."""
        return self.backend.all_active(self.namespace)

    def quarantined_nodes(self) -> List[MemoryNode]:
        """Return namespace-scoped quarantine records for audit/review."""
        return [
            node for node in self.all_nodes()
            if node.retrieval_state == RetrievalState.QUARANTINED
        ]

    def candidate_nodes(self) -> List[MemoryNode]:
        """Return namespace-scoped evidence awaiting authorized promotion."""
        return [
            node for node in self.all_nodes()
            if node.retrieval_state == RetrievalState.CANDIDATE
        ]

    def promote_candidate(
        self,
        node_id: str,
        *,
        approved_value: str,
        rationale: str,
    ) -> Tuple[bool, str]:
        """Publish reviewed evidence without trusting its original wording."""
        if (
            not isinstance(approved_value, str)
            or not isinstance(rationale, str)
            or not rationale.strip()
        ):
            return False, (
                "Promotion requires an approved text value and non-empty "
                "review rationale."
            )

        author, reason = self._authorize(
            WritePermission.PROMOTE_CANDIDATE
        )
        if author is None:
            return False, reason
        node = self.get_by_id(node_id)
        if node is None:
            return False, "Candidate node not found in this namespace."
        if node.retrieval_state != RetrievalState.CANDIDATE:
            return False, "Node is not awaiting candidate promotion."

        # NOE-F-026. The reviewer must actually restate the evidence, not
        # rubber-stamp the collector's bytes into provider context.
        #
        # This is not a control against a malicious reviewer — a reviewer holds
        # PROMOTE_CANDIDATE and is part of the trusted computing base, so they
        # could type any text they wish. It defends the narrower, real case:
        # ingested text may be *crafted* to steer a model, and adversarial
        # phrasing is usually tuned precisely. Requiring a genuine restatement
        # destroys that artifact and converts an inattentive approval into a
        # deliberate authoring act.
        #
        # Comparison is normalized (NFKC + casefold + whitespace collapse, the
        # same normalization the policy boundary uses) so that adding a space,
        # flipping case, or swapping in compatibility Unicode does not qualify
        # as a rewrite.
        if PolicyBoundary.is_same_text(approved_value, node.value):
            return False, (
                "Promotion requires the reviewer to restate the evidence. "
                "The approved text is not meaningfully different from the raw "
                "candidate value."
            )

        reviewed = MemoryNode(key=node.key, value=approved_value)
        decision = PolicyBoundary.evaluate(
            reviewed,
            self._installed_guardrails(),
        )
        if decision.action != "allow":
            return False, (
                "Promotion blocked by machine policy. " + decision.reason
            )

        original_value = node.value
        node.metadata["_noesis_candidate_original_value"] = original_value
        node.metadata["_noesis_candidate_original_sha256"] = hashlib.sha256(
            original_value.encode("utf-8")
        ).hexdigest()
        node.metadata["_noesis_candidate_original_reason"] = (
            node.candidate_reason or "ordinary ingestion"
        )
        node.metadata["_noesis_promoted_by"] = author.author_id
        node.metadata["_noesis_promoted_at"] = time.time()
        node.metadata["_noesis_promotion_rationale"] = rationale.strip()
        node.value = approved_value
        node.retrieval_state = RetrievalState.ACTIVE
        node.candidate_reason = None
        node.candidate_at = None
        self.backend.upsert(node)
        return True, "Candidate promoted after authorized review."

    def release_quarantined(
        self,
        node_id: str,
        *,
        approved_value: str,
        rationale: str,
    ) -> Tuple[bool, str]:
        """Rewrite and release one quarantined node after authorized review."""
        if (
            not isinstance(approved_value, str)
            or not isinstance(rationale, str)
            or not rationale.strip()
        ):
            return False, (
                "Quarantine review requires an approved text value and "
                "non-empty rationale."
            )

        author, reason = self._authorize(WritePermission.REVIEW_QUARANTINE)
        if author is None:
            return False, reason
        node = self.get_by_id(node_id)
        if node is None:
            return False, "Quarantined node not found in this namespace."
        if node.retrieval_state != RetrievalState.QUARANTINED:
            return False, "Node is not quarantined."

        reviewed = MemoryNode(key=node.key, value=approved_value)
        decision = PolicyBoundary.evaluate(
            reviewed,
            self._installed_guardrails(),
        )
        if decision.action != "allow":
            return False, (
                "Quarantine release blocked by machine policy. "
                + decision.reason
            )

        original_value = node.value
        node.metadata["_noesis_quarantine_original_reason"] = (
            node.quarantine_reason or "unspecified"
        )
        node.metadata["_noesis_quarantine_original_value"] = original_value
        node.metadata["_noesis_quarantine_original_sha256"] = hashlib.sha256(
            original_value.encode("utf-8")
        ).hexdigest()
        node.metadata["_noesis_quarantine_released_by"] = author.author_id
        node.metadata["_noesis_quarantine_released_at"] = time.time()
        node.metadata["_noesis_quarantine_review_rationale"] = (
            rationale.strip()
        )
        node.value = approved_value
        node.retrieval_state = RetrievalState.ACTIVE
        node.quarantine_reason = None
        node.quarantined_at = None
        self.backend.upsert(node)
        return True, "Quarantined node rewritten and released after review."

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
        context.extend([node for node in guardrails if self._retrievable(node)])

        # 2. Profile
        profiles = self.backend.get_by_type(
            NodeType.PROFILE, self.namespace
        )
        context.extend([node for node in profiles if self._retrievable(node)])

        # 3. Project state
        project_states = self.backend.get_by_type(
            NodeType.PROJECT_STATE, self.namespace
        )
        context.extend(
            [node for node in project_states if self._retrievable(node)]
        )

        # 4. Active skills matching task type
        skills = self.backend.get_by_type(
            NodeType.SKILL, self.namespace
        )
        active_skills = [
            s for s in skills
            if (
                isinstance(s, Skill)
                and s.status == SkillStatus.PROMOTED
                and self._retrievable(s)
            )
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
            if self._retrievable(f)
        ]
        scored_facts.sort(key=lambda x: x[1], reverse=True)
        context.extend([f for f, _ in scored_facts[:20]])

        # 6. Episodes — most recent, highest-trust
        episodes = self.backend.get_by_type(
            NodeType.EPISODE, self.namespace
        )
        scored_episodes = [
            (e, self.trust_gate.gate_read(e)) for e in episodes
            if self._retrievable(e)
        ]
        scored_episodes.sort(key=lambda x: x[1], reverse=True)
        context.extend([e for e, _ in scored_episodes[:3]])

        return context

    @staticmethod
    def _retrievable(node: MemoryNode) -> bool:
        return (
            node.grief_state != GriefState.PURGED
            and node.retrieval_state == RetrievalState.ACTIVE
        )

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
