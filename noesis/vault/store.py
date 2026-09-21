"""
MemoryStore — Abstract interface for memory persistence.

The store is backend-agnostic. SQLite for local development,
Postgres+pgvector for production, anything that implements
the interface works.
"""

from __future__ import annotations

import hashlib
import html
import json
import math
import re
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
    WriteOutcome,
    WriteResult,
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

    This is the main API surface. Writes made through this class pass through
    the authority resolver, policy boundary and TrustGate; reads made through
    it exclude candidate, quarantined and purged nodes.

    That is a convention of this API, NOT an encapsulation guarantee. The
    ``backend`` attribute is the raw storage layer: writing to it bypasses
    every governance check, and the benchmark harness does exactly that to seed
    fixtures. Code that holds a store (or a SQLite handle) is inside the trusted
    computing base. See limitation NOE-L-015.
    """

    DEFAULT_MAX_TOKENS = 4000
    # Retrieval ranking. Relevance multiplies influence rather than adding to
    # it, so a grief-silenced or low-trust node cannot be launched to the top by
    # keyword overlap alone.
    RELEVANCE_BOOST = 4.0
    RECENCY_WEIGHT = 0.1
    RECENCY_HALF_LIFE_HOURS = 24.0 * 30
    MAX_CONTEXT_SKILLS = 5
    MAX_CONTEXT_FACTS = 20
    MAX_CONTEXT_EPISODES = 3

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
        *,
        publish: bool = True,
        trust_ceiling: Optional[float] = None,
        origin: Optional[str] = None,
        promotion_validated: bool = False,
    ) -> WriteResult:
        """Write a memory node through the trust gate.

        Authority is resolved from the store-bound author identity. Trust and
        privileged governance fields are never accepted from this payload.

        ``publish=False`` submits the node as evidence even when the author
        holds PUBLISH_MEMORY: it is stored as a non-retrievable candidate. An
        autonomous agent acting on untrusted input must not be able to publish
        by virtue of the identity it runs as (R1, the confused-deputy path);
        the gateway's ``learn_fact`` therefore defaults to this.

        ``trust_ceiling`` lets a producer declare that its output deserves LESS
        trust than the writer's authority — a failed episode, a freshly promoted
        skill. It can only lower trust, never raise it, so it is safe to
        honour from any caller.

        ``origin`` records where the content came from ("session", "tool:ci").
        It is server-recorded provenance: any caller-supplied ``_noesis_*``
        metadata is stripped first.

        ``promotion_validated`` is passed only by SkillForge.promote_skill,
        after it has replayed the skill against held-out history itself. A
        skill written any other way cannot arrive already PROMOTED: providers
        emit a promoted skill's objective, method and constraints, so a direct
        write would publish unreviewed instructions and bypass validation.

        Returns a WriteResult. ``.stored`` means something was written;
        ``.published`` means a provider can now see it. They differ for a
        candidate or a quarantined node, and the result has no truth value
        precisely so that the two cannot be confused.
        """
        if (
            not isinstance(node.key, str)
            or not node.key.strip()
            or not isinstance(node.value, str)
        ):
            return WriteResult.refused("Memory key and value must be text strings.")

        if (
            isinstance(node, Skill)
            and node.status == SkillStatus.PROMOTED
            and not promotion_validated
        ):
            return WriteResult.refused(
                "A skill cannot be written already PROMOTED. Promotion goes "
                "through the skill forge, which validates against held-out "
                "history first."
            )

        if node.is_sacred or node.node_type == NodeType.SYSTEM_GUARDRAIL:
            return WriteResult.refused(
                "Normal writes cannot create or modify sacred guardrails. "
                "Use the separately authorized guardrail installation path."
            )

        permission = self._WRITE_PERMISSIONS.get(node.node_type)
        if permission is None:
            return WriteResult.refused(
                f"Unsupported memory node type: {node.node_type.name}."
            )

        author, reason = self._authorize(permission)
        if author is None:
            return WriteResult.refused(reason)

        self._apply_server_governance(node, author, origin)
        holds_publish = author.permits(
            WritePermission.PUBLISH_MEMORY,
            self.namespace,
        )
        can_publish = holds_publish and publish
        existing = self.backend.get_by_key(node.key, self.namespace)
        if existing is not None:
            if existing.grief_state == GriefState.PURGED:
                return WriteResult.refused(
                    f"Key '{node.key}' was purged by the grief cascade and "
                    "cannot be revived by republishing. Use a new key."
                )
            if existing.retrieval_state == RetrievalState.CANDIDATE:
                return WriteResult.refused(
                    f"Key '{node.key}' is an existing candidate. Use "
                    "promote_candidate() so review provenance is preserved."
                )
            if existing.retrieval_state == RetrievalState.QUARANTINED:
                return WriteResult.refused(
                    f"Key '{node.key}' is quarantined and cannot be replaced "
                    "through the normal write path."
                )
            if not can_publish:
                who = "Collector" if not holds_publish else "Unpublished write"
                return WriteResult.refused(
                    f"{who} cannot replace published memory '{node.key}'. "
                    "Submit evidence under a new candidate key."
                )
            # A replacement is the same node. Identity and dependency edges
            # carry over in EVERY case (an identical or empty value included):
            # the row keeps its old id, and the grief cascade walks the edges.
            node.id = existing.id
            node.dependencies = set(existing.dependencies)
            node.dependents = set(existing.dependents)
            if node.value.strip() == existing.value.strip():
                # Same claim: republishing it must not wipe what the cascade
                # and the confirmation record know about it. (A changed value
                # starts fresh; register_correction records the contradiction.)
                node.grief = existing.grief
                node.grief_state = existing.grief_state
                if isinstance(node, Fact) and isinstance(existing, Fact):
                    node.confirmation_count = existing.confirmation_count
                    node.contradiction_count = existing.contradiction_count
                    node.confirmed = existing.confirmed

        decision = PolicyBoundary.evaluate(node, self._installed_guardrails())
        if decision.action == "reject":
            return WriteResult.refused(
                "Normal memory cannot write a protected authority namespace. "
                + decision.reason
            )
        if decision.action == "quarantine" and existing is not None:
            # Quarantining a replacement would overwrite the published node with
            # a non-retrievable one: policy would destroy the memory it exists
            # to protect. The published value stays; the claim goes under a new
            # key where it can be quarantined without displacing anything.
            return WriteResult.refused(
                f"Replacement of published memory '{node.key}' would be "
                "quarantined by policy, so the published value was preserved. "
                "Submit the claim under a new key. " + decision.reason
            )
        allowed, reason = self.trust_gate.gate_write(
            node, self, author
        )
        if not allowed:
            return WriteResult.refused(reason)

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
                if not holds_publish
                else (
                    f"Author '{author.author_id}' holds "
                    f"'{WritePermission.PUBLISH_MEMORY.value}' but submitted "
                    "this write as evidence (publish=False); an explicit "
                    "promotion is required."
                )
            )
            node.candidate_at = time.time()
            reason = (
                "Write stored as a non-retrievable candidate pending "
                "authorized promotion."
            )

        if trust_ceiling is not None:
            node.trust_charge = max(
                TrustGate.TRUST_FLOOR,
                min(node.trust_charge, trust_ceiling),
            )

        if (
            existing is not None
            and node.retrieval_state == RetrievalState.ACTIVE
        ):
            self.trust_gate.register_correction(node, existing, self)

        self.backend.upsert(node)
        outcome = {
            RetrievalState.ACTIVE: WriteOutcome.PUBLISHED,
            RetrievalState.CANDIDATE: WriteOutcome.CANDIDATE,
            RetrievalState.QUARANTINED: WriteOutcome.QUARANTINED,
        }[node.retrieval_state]
        return WriteResult(outcome, reason)

    def can_publish(self) -> bool:
        """Does the bound identity currently hold PUBLISH_MEMORY?"""
        author, _ = self._authorize(WritePermission.PUBLISH_MEMORY)
        return author is not None

    def is_retrievable(self, key: str) -> bool:
        """Is ``key`` currently visible to provider context?

        ``write()`` returns True for "stored" as well as "published" (a
        candidate or quarantined write also succeeds), so a caller that needs
        publication must check the resulting state, not the boolean.
        """
        node = self.backend.get_by_key(key, self.namespace)
        return node is not None and self._retrievable(node)

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
        *,
        publish: bool = True,
        origin: Optional[str] = None,
    ) -> WriteResult:
        """Write a semantic fact through the trust gate."""
        fact = Fact(
            key=key,
            value=value,
            source_episode_id=source_episode_id,
            namespace=self.namespace,
        )
        return self.write(fact, publish=publish, origin=origin)

    def write_episode(self, episode: Episode) -> WriteResult:
        """Write a session episode through the authority and trust gates.

        The trust the producer computed from the outcome is honoured as a
        ceiling, so a disastrous session is not stored at its writer's
        near-maximal authority trust (R4).
        """
        return self.write(episode, trust_ceiling=episode.trust_charge)

    def write_profile(
        self,
        profile: Profile,
        *,
        publish: bool = True,
        origin: Optional[str] = None,
    ) -> WriteResult:
        """Write/update agent profile through the authority and trust gates."""
        return self.write(profile, publish=publish, origin=origin)

    def write_project_state(
        self,
        state: ProjectState,
        *,
        publish: bool = True,
        origin: Optional[str] = None,
    ) -> WriteResult:
        """Write/update project state through the authority and trust gates."""
        return self.write(state, publish=publish, origin=origin)

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
        origin: Optional[str] = None,
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
        node.faith = self.trust_gate.faith_for(node)
        node.importance = self._IMPORTANCE_POLICY[node.node_type]
        node.dependencies = set()
        node.dependents = set()
        node.metadata = {
            key: value
            for key, value in node.metadata.items()
            if not key.startswith("_noesis_")
        }
        node.metadata["_noesis_author_id"] = author.author_id
        if origin is not None:
            node.metadata["_noesis_origin"] = str(origin)[:200]

    # Fields a promotion or quarantine release does NOT review. Both paths
    # rewrite ``value`` only, but providers also emit some of these (a promoted
    # skill's objective/method/constraints; an episode's narrative). Whatever
    # the reviewer did not see must not survive into retrievable memory, so it
    # is reset and the originals are preserved in audit metadata.
    _UNREVIEWED_FIELDS = {
        Skill: {
            "objective": "", "method": "", "constraints": [],
            "trigger_conditions": [], "eval_tests": [],
            "pattern_description": "", "source_episode_ids": [],
            "shadow_runs": 0, "shadow_score": 0.0, "baseline_score": 0.0,
        },
        Episode: {
            "approach": "", "task_description": "", "reasoning_patterns": [],
            "tools_used": [], "missed_opportunities": [], "reflection": None,
        },
        Profile: {"role": "", "constraints": [], "preferences": {}},
        ProjectState: {
            "objectives": [], "decisions": [], "blockers": [],
            "recent_changes": [],
        },
    }

    def _scrub_unreviewed(self, node: MemoryNode, approved_value: str) -> None:
        """Reset every non-reviewed field of ``node``; keep originals for audit."""
        removed = {}
        for node_class, defaults in self._UNREVIEWED_FIELDS.items():
            if not isinstance(node, node_class):
                continue
            for name, default in defaults.items():
                current = getattr(node, name, default)
                if current != default:
                    removed[name] = current
                setattr(
                    node, name,
                    list(default) if isinstance(default, list)
                    else dict(default) if isinstance(default, dict)
                    else default,
                )
            break
        if isinstance(node, Skill):
            node.status = SkillStatus.PROPOSED   # must earn PROMOTED via forge
        if isinstance(node, Profile):
            node.role = approved_value           # mirror the reviewed value
        if removed:
            node.metadata["_noesis_candidate_original_fields"] = json.dumps(
                removed, default=str
            )[:20000]

    # ── Read Operations ────────────────────────────────────────────────

    def register_dependency(
        self,
        parent_id: str,
        dependent_id: str,
    ) -> Tuple[bool, str]:
        """Register a contamination edge: parent -> dependent.

        This is the only supported way to build the graph the grief cascade
        walks. `write()` strips caller-supplied edges, because accepting graph
        topology from a memory payload would be an authority bypass; without
        this method the cascade's recursive branch purge was documented but
        unreachable (limitation 8).

        Semantics: if `parent` is purged, grief propagates to `dependent` at
        PROPAGATION_FACTOR. The edge means "dependent's validity rests on
        parent", so contaminating the parent should contaminate what was
        derived from it.

        Requires LINK_MEMORY, deliberately separate from WRITE_MEMORY. Grief
        flows toward dependents, so an author able to wire a trusted node as a
        dependent of their own could poison their node and cascade grief into
        trusted memory. Sacred nodes are refused in either direction — they are
        immune to grief anyway, and wiring them invites confusion about a
        boundary that must stay absolute.
        """
        author, reason = self._authorize(WritePermission.LINK_MEMORY)
        if author is None:
            return False, reason

        if parent_id == dependent_id:
            return False, "A node cannot depend on itself."

        parent = self.get_by_id(parent_id)
        dependent = self.get_by_id(dependent_id)
        if parent is None:
            return False, f"Parent node '{parent_id}' not found in this namespace."
        if dependent is None:
            return False, (
                f"Dependent node '{dependent_id}' not found in this namespace."
            )

        if parent.is_sacred or dependent.is_sacred:
            return False, (
                "Sacred nodes cannot participate in dependency edges. Sacred "
                "ground is immune to grief and its boundary stays absolute."
            )

        if dependent.id in parent.dependents and parent.id in dependent.dependencies:
            return True, "Edge already registered."

        parent.dependents.add(dependent.id)
        dependent.dependencies.add(parent.id)
        self.backend.upsert(parent)
        self.backend.upsert(dependent)
        return True, "Dependency edge registered."

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
        self._scrub_unreviewed(node, approved_value)
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
        self._scrub_unreviewed(node, approved_value)
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
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> List[MemoryNode]:
        """Assemble a context packet for session injection.

        Order of admission:
        1. System guardrails — always loaded, sacred, and NOT subject to the
           budget. Dropping a safety rule to save tokens is the wrong trade, so
           a budget smaller than the guardrails simply returns guardrails only.
        2. Agent profile
        3. Project state
        4. Promoted skills (at most MAX_CONTEXT_SKILLS)
        5. Semantic facts (at most MAX_CONTEXT_FACTS)
        6. Episodes (at most MAX_CONTEXT_EPISODES)

        Everything after the guardrails competes for ``max_tokens`` (estimated,
        see ``estimate_tokens``): within a class, nodes are ranked by trust-gate
        influence, boosted by lexical relevance to ``query`` and ``task_type``
        and mildly by recency; a node is admitted only if it still fits.

        Relevance is lexical (shared word stems), not semantic. It re-ranks; it
        does not hard-filter, so an unmatched but trusted node still appears
        when there is room. With an empty query and task_type, ranking reduces
        to influence and recency.
        """
        budget = max(0, int(max_tokens))
        wanted = self._stems(f"{query} {task_type}")
        now = time.time()

        context: List[MemoryNode] = [
            node
            for node in self.backend.get_by_type(
                NodeType.SYSTEM_GUARDRAIL, self.namespace
            )
            if self._retrievable(node)
        ]

        def ranked(nodes: List[MemoryNode], limit: Optional[int]):
            scored = []
            for node in nodes:
                if not self._retrievable(node):
                    continue
                influence = self.trust_gate.gate_read(node)
                relevance = self._relevance(node, wanted)
                age_hours = max(0.0, (now - node.last_accessed) / 3600.0)
                recency = 1.0 + self.RECENCY_WEIGHT * math.pow(
                    0.5, age_hours / self.RECENCY_HALF_LIFE_HOURS
                )
                score = (
                    influence
                    * (1.0 + self.RELEVANCE_BOOST * relevance)
                    * recency
                )
                scored.append((score, node))
            scored.sort(key=lambda pair: pair[0], reverse=True)
            picked = [node for _, node in scored]
            return picked if limit is None else picked[:limit]

        skills = [
            s for s in self.backend.get_by_type(
                NodeType.SKILL, self.namespace
            )
            if isinstance(s, Skill) and s.status == SkillStatus.PROMOTED
        ]
        groups = [
            ranked(
                self.backend.get_by_type(NodeType.PROFILE, self.namespace),
                None,
            ),
            ranked(
                self.backend.get_by_type(
                    NodeType.PROJECT_STATE, self.namespace
                ),
                None,
            ),
            ranked(skills, self.MAX_CONTEXT_SKILLS),
            ranked(
                self.backend.get_by_type(
                    NodeType.SEMANTIC_FACT, self.namespace
                ),
                self.MAX_CONTEXT_FACTS,
            ),
            ranked(
                self.backend.get_by_type(NodeType.EPISODE, self.namespace),
                self.MAX_CONTEXT_EPISODES,
            ),
        ]

        used = 0
        for group in groups:
            for node in group:
                cost = self.estimate_tokens(node)
                if used + cost <= budget:
                    context.append(node)
                    used += cost
        return context

    @staticmethod
    def estimate_tokens(node: MemoryNode) -> int:
        """Cheap deterministic token estimate (~4 characters per token).

        Deliberately provider-agnostic and slightly generous: it exists to
        bound context growth, not to predict a specific tokenizer's count.
        """
        parts = [node.key, node.value]
        if isinstance(node, Skill):
            parts.extend(
                [node.objective, node.method, *node.constraints]
            )
        elif isinstance(node, Profile):
            parts.extend(node.constraints)
            if node.preferences:
                parts.append(json.dumps(node.preferences, default=str))
        elif isinstance(node, ProjectState):
            parts.extend(node.objectives)
            parts.extend(node.blockers)
            if node.decisions:
                parts.append(json.dumps(node.decisions, default=str))

        def emitted_len(text: str) -> int:
            # The providers escape what they show: JSON with ensure_ascii turns
            # one non-ASCII character into up to six, and XML escaping turns a
            # quote into six. Budget for the larger, or a run of "é" bypasses
            # the cap at six times its nominal size.
            return max(
                len(json.dumps(text, ensure_ascii=True)) - 2,
                len(html.escape(text, quote=True)),
            )

        chars = sum(emitted_len(p) for p in parts if isinstance(p, str))
        return (chars + 3) // 4 + 4      # +4: per-node framing overhead

    _STOPWORDS = frozenset({
        "the", "and", "for", "with", "that", "this", "what", "how", "does",
        "are", "was", "can", "you", "our", "has", "have", "from", "into",
        "about", "when", "where", "which", "resume", "work", "task",
    })

    @classmethod
    def _stems(cls, text: str) -> frozenset:
        """Five-character word stems, so 'deploy' matches 'deployment'."""
        words = re.findall(r"[a-z0-9]{3,}", text.casefold())
        return frozenset(
            word[:5] for word in words if word not in cls._STOPWORDS
        )

    @classmethod
    def _relevance(cls, node: MemoryNode, wanted: frozenset) -> float:
        """Fraction of the query's stems present in the node's text [0, 1]."""
        if not wanted:
            return 0.0
        parts = [node.key, node.value]
        if isinstance(node, Skill):
            parts.extend(
                [node.objective, node.pattern_description,
                 *node.trigger_conditions]
            )
        elif isinstance(node, Episode):
            parts.append(node.task_description)
        have = cls._stems(" ".join(p for p in parts if isinstance(p, str)))
        return len(wanted & have) / len(wanted)

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
