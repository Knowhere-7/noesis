"""
Trust Gate — Swarm-governed access control for memory operations.

Ported from Murmuration's trust battery + belief propagation mechanics.
Every memory write, read, and propagation passes through this gate.

Rules (from the simulation that proved them):
  - Sacred nodes cannot be overwritten by ephemeral input (topological isolation)
  - Trust is earned through confirmed accuracy, never assumed
  - Contradictions drain trust and accumulate grief
  - Low-trust nodes have weak influence on the memory graph
  - Faith dampens grief — meaning lets the system carry loss without breaking
  - Energy-based gatekeeping — complex adversarial writes are metabolically expensive

Constitutional Anchor (Ghost, 2026-04-25):
  "The cost of selfishness and not putting the collective before self."
"""

from __future__ import annotations

import logging
import time
from typing import Callable, TYPE_CHECKING, Dict, List, Optional, Tuple

from noesis.schema import (
    DriftScore,
    GriefState,
    Guardrail,
    MemoryNode,
    NodeType,
    RetrievalState,
)
from noesis.governor.authority import AuthorRecord, WritePermission

if TYPE_CHECKING:
    from noesis.vault.store import MemoryStore

logger = logging.getLogger("noesis.governor")


class TrustGate:
    """The immune system. Governs all memory operations.

    Maps directly to Murmuration mechanics:
      - trust_charge → earned authority per node
      - grief → contamination signal from contradictions
      - faith → alignment pull from sacred nodes
      - sacred ground → immutable system guardrails
      - grief cascade → recursive purge of contaminated branches
      - energy cost → metabolic overhead for complex writes
    """

    # Trust Battery constants (from Murmuration evolution.js)
    TRUST_FLOOR = 0.05
    TRUST_CAP = 1.0
    TRUST_PASSIVE_DECAY = 0.001     # per-access decay (metabolic cost)
    TRUST_CONFIRMATION_BOOST = 0.05  # earned by being confirmed correct
    TRUST_CONTRADICTION_DRAIN = 0.10 # lost when contradicted
    TRUST_ALIGNMENT_BONUS = 0.02    # earned by aligning with consensus

    # Grief constants (from Murmuration agent.js)
    GRIEF_CONTRADICTION_HIT = 0.15  # grief from a single contradiction
    GRIEF_NATURAL_DECAY = 0.005     # slow healing per access cycle
    GRIEF_CRISIS_THRESHOLD = 0.9    # triggers cascade evaluation
    GRIEF_STRESS_THRESHOLD = 0.3    # enters stressed state

    # Faith constant (from the 54K-tick perfect swarm)
    FAITH_DAMPER = 0.45             # faith reduces grief intake by up to 45%
    SACRED_FAITH = 0.92             # gravitational pull of system guardrails

    # Energy cost (from Murmuration economy.js)
    BASE_WRITE_COST = 1.0           # normal write energy
    COMPLEX_WRITE_MULTIPLIER = 3.0  # long/nested/adversarial writes cost more
    ENERGY_BUDGET_PER_SESSION = 100.0  # total write energy per session

    def __init__(
        self,
        output_evaluator: Optional[Callable[..., DriftScore]] = None,
    ):
        self.session_energy = self.ENERGY_BUDGET_PER_SESSION
        self._contradiction_log: List[Dict] = []
        self.output_evaluator = output_evaluator

    # ── Write Gate ─────────────────────────────────────────────────────

    def gate_write(
        self,
        node: MemoryNode,
        store: MemoryStore,
        author: AuthorRecord,
    ) -> Tuple[bool, str]:
        """Decide whether a memory write is allowed.

        Returns (allowed, reason). If not allowed, the write is blocked
        and the reason explains why.

        This governs persistent-memory writes. The rules:
        1. Sacred nodes cannot be overwritten by any normal write
        2. Writes cost energy — complex writes cost more
        3. Low-trust authors cannot write high-importance nodes
        4. Replacing trusted memory requires an explicit correction capability
        """
        # Rule 1: Sacred ground protection (topological isolation)
        existing = store.get(node.key, node.namespace)
        if existing and existing.is_sacred:
            logger.warning(
                "BLOCKED: Attempted overwrite of sacred node '%s'. "
                "This is the boundary.",
                node.key,
            )
            return False, (
                f"Cannot overwrite sacred node '{node.key}'. "
                f"System guardrails are immutable."
            )

        # Rule 2: Energy-based gatekeeping
        write_cost = self._compute_write_cost(node)
        bypass_budget = author.permits(
            WritePermission.BYPASS_WRITE_BUDGET,
            store.namespace,
        )
        if write_cost > self.session_energy and not bypass_budget:
            logger.warning(
                "BLOCKED: Write cost %.1f exceeds remaining session energy "
                "%.1f. Possible adversarial flooding.",
                write_cost, self.session_energy,
            )
            return False, (
                f"Session energy depleted ({self.session_energy:.1f} remaining, "
                f"cost {write_cost:.1f}). Resetting topology."
            )

        # Rule 3: Trust-based authority check
        if node.importance >= 0.7 and author.trust < 0.3:
            logger.warning(
                "BLOCKED: Low-trust author (%.2f) attempting to write "
                "high-importance node (%.2f).",
                author.trust, node.importance,
            )
            return False, (
                f"Insufficient trust ({author.trust:.2f}) to write "
                f"high-importance memory ({node.importance:.2f})."
            )

        # Rule 4: Trusted-memory replacement requires explicit authority.
        if existing and existing.trust_charge > 0.5:
            contradiction = self._detect_contradiction(node, existing)
            if contradiction:
                if not author.permits(
                    WritePermission.CORRECT_TRUSTED_FACT,
                    store.namespace,
                ):
                    logger.warning(
                        "BLOCKED: Author '%s' attempted to replace trusted "
                        "memory '%s' without correction authority.",
                        author.author_id,
                        node.key,
                    )
                    return False, (
                        f"Replacing trusted memory '{node.key}' requires "
                        "the 'correct_trusted_fact' permission."
                    )
                logger.info(
                    "AUTHORIZED CORRECTION: Author '%s' replaced trusted "
                    "memory '%s'.",
                    author.author_id,
                    node.key,
                )

        # Trusted system/owner workflows are rate-limited by their host rather
        # than this adversarial-input budget. Untrusted writers still pay.
        if not bypass_budget:
            self.session_energy -= write_cost

        # Apply passive trust decay to author context
        node.trust_charge = max(
            self.TRUST_FLOOR,
            min(self.TRUST_CAP, author.trust - self.TRUST_PASSIVE_DECAY),
        )

        return True, "Write permitted."

    # ── Read Gate ──────────────────────────────────────────────────────

    def gate_read(self, node: MemoryNode) -> float:
        """Return the influence weight of a memory node for retrieval.

        High-trust, high-faith nodes have strong influence.
        Low-trust, high-grief nodes are nearly silent.
        Sacred nodes always have maximum influence.

        This mirrors Murmuration's belief propagation:
          influence = trustCharge * reactivity * classWeight
        """
        if node.is_sacred:
            return 1.0

        if (
            node.grief_state == GriefState.PURGED
            or node.retrieval_state != RetrievalState.ACTIVE
        ):
            return 0.0

        # Influence = trust * (1 - grief) * importance
        # Faith bonus: faithful nodes get a lift
        faith_bonus = 1.0 + (node.faith * 0.3)
        influence = (
            node.trust_charge *
            (1.0 - node.grief * 0.6) *
            node.importance *
            faith_bonus
        )
        return max(0.0, min(1.0, influence))

    # ── Trust Updates ──────────────────────────────────────────────────

    def confirm_node(self, node: MemoryNode):
        """Node was confirmed correct — charge trust battery."""
        node.trust_charge = min(
            self.TRUST_CAP,
            node.trust_charge + self.TRUST_CONFIRMATION_BOOST,
        )
        # Successful confirmation heals grief
        faith_damper = 1.0  # healing is not dampened by faith
        node.grief = max(0.0, node.grief - self.GRIEF_NATURAL_DECAY * 3)
        self._update_grief_state(node)
        node.touch()

    def contradict_node(self, node: MemoryNode):
        """Node was contradicted — drain trust, accumulate grief."""
        if node.is_sacred:
            logger.info(
                "Sacred node '%s' was contradicted but remains immutable.",
                node.key,
            )
            return  # sacred nodes don't take grief

        node.trust_charge = max(
            self.TRUST_FLOOR,
            node.trust_charge - self.TRUST_CONTRADICTION_DRAIN,
        )

        # Faith dampens grief intake (from Murmuration agent.js)
        faith_damper = 1.0 - (node.faith * self.FAITH_DAMPER)
        grief_delta = self.GRIEF_CONTRADICTION_HIT * faith_damper
        node.grief = min(1.0, node.grief + grief_delta)

        self._update_grief_state(node)
        self._contradiction_log.append({
            "node_key": node.key,
            "trust_after": node.trust_charge,
            "grief_after": node.grief,
            "time": time.time(),
        })

    # ── Drift Scoring ──────────────────────────────────────────────────

    def score_output(
        self,
        output: str,
        context_nodes: List[MemoryNode],
        profile: Optional[MemoryNode] = None,
    ) -> DriftScore:
        """Score output using an explicitly configured deterministic evaluator.

        The b4ff7b6 implementation ignored ``output`` and returned context
        health as if it were a model judgment. Failing explicitly is safer
        than counterfeit scoring. An evaluator must return a DriftScore and
        should keep the LLM as the subject, not the judge.
        """
        if self.output_evaluator is None:
            raise RuntimeError(
                "No output evaluator is configured. Use score_context() for "
                "context health or supply a deterministic output evaluator."
            )
        baseline = self.score_context(context_nodes, profile)
        return self.output_evaluator(
            output=output,
            context_nodes=context_nodes,
            profile=profile,
            context_health=baseline,
        )

    def score_context(
        self,
        context_nodes: List[MemoryNode],
        profile: Optional[MemoryNode] = None,
    ) -> DriftScore:
        """Measure retrieval-context health without judging model output."""
        score = DriftScore()

        if not context_nodes:
            # No memory context — groundedness is unknown
            score.groundedness = 0.3
            score.continuity = 0.5
            return score

        # Trust: average trust of context nodes used
        trusts = [n.trust_charge for n in context_nodes if not n.is_sacred]
        score.trust = sum(trusts) / len(trusts) if trusts else 0.5

        # Groundedness: proportion of high-trust nodes in context
        high_trust = sum(1 for t in trusts if t > 0.5)
        score.groundedness = high_trust / len(trusts) if trusts else 0.3

        # Continuity: check if context includes profile and project state
        has_profile = any(
            n.node_type == NodeType.PROFILE for n in context_nodes
        )
        has_project = any(
            n.node_type == NodeType.PROJECT_STATE for n in context_nodes
        )
        score.continuity = (
            0.5 + (0.25 if has_profile else 0) + (0.25 if has_project else 0)
        )

        # Drift: grief level of the context
        griefs = [n.grief for n in context_nodes]
        avg_grief = sum(griefs) / len(griefs) if griefs else 0
        score.drift = avg_grief

        # Action risk: inversely proportional to consensus trust
        score.action_risk = 1.0 - score.trust

        return score

    # ── Internal ───────────────────────────────────────────────────────

    def _compute_write_cost(self, node: MemoryNode) -> float:
        """Metabolic cost of a write. Complex writes cost more.

        From Murmuration's economy: writes consume a bounded resource.
        The budget limits untrusted write flooding; trusted system/owner
        workflows require a separate bypass capability.
        """
        base = self.BASE_WRITE_COST
        # Longer content costs more
        length_factor = 1.0 + len(node.value) / 5000.0
        # More dependencies = more graph manipulation
        dep_factor = 1.0 + len(node.dependencies) * 0.2
        # Ephemeral writes are cheap; guardrail attempts are expensive
        type_factor = (
            self.COMPLEX_WRITE_MULTIPLIER
            if node.node_type == NodeType.SYSTEM_GUARDRAIL
            else 1.0
        )
        return base * length_factor * dep_factor * type_factor

    def _detect_contradiction(
        self, new: MemoryNode, existing: MemoryNode
    ) -> bool:
        """Simple contradiction detection for v1.

        Returns True if the new node appears to contradict the existing one.
        In v1 this is a basic check — same key, different value, both
        non-empty. Future versions will use semantic similarity.
        """
        if not new.value or not existing.value:
            return False
        if new.value.strip() == existing.value.strip():
            return False
        # Same key, different value = potential contradiction
        return True

    def _handle_contradiction(
        self,
        new: MemoryNode,
        existing: MemoryNode,
        store: MemoryStore,
    ):
        """Process a contradiction between new and existing nodes.

        From Murmuration's interaction.js: when a neighbor's trust
        hits the floor, grief ripples outward. Here, contradiction
        damages the existing node's trust and may trigger a cascade.
        """
        # Drain existing node's trust
        existing.trust_charge = max(
            self.TRUST_FLOOR,
            existing.trust_charge - self.TRUST_CONTRADICTION_DRAIN * 0.5,
        )
        # Accumulate grief on existing
        faith_damper = 1.0 - (existing.faith * self.FAITH_DAMPER)
        existing.grief = min(
            1.0,
            existing.grief + self.GRIEF_CONTRADICTION_HIT * 0.5 * faith_damper,
        )
        self._update_grief_state(existing)

    def _update_grief_state(self, node: MemoryNode):
        """Update grief state machine — mirrors Murmuration's agent.js.

        Full bidirectional transitions:
          grief >= 0.9  → CONTAMINATED
          0.3 <= grief < 0.9  → STRESSED
          grief < 0.2  → ACTIVE (recovered)
        Agents can heal from any state back to ACTIVE.
        """
        if node.is_sacred:
            node.grief_state = GriefState.SACRED
            return

        if node.grief >= self.GRIEF_CRISIS_THRESHOLD:
            node.grief_state = GriefState.CONTAMINATED
        elif node.grief >= self.GRIEF_STRESS_THRESHOLD:
            node.grief_state = GriefState.STRESSED
        elif node.grief < 0.2:
            node.grief_state = GriefState.ACTIVE  # recovered from any state

    def reset_session_energy(self):
        """Reset energy budget for a new session."""
        self.session_energy = self.ENERGY_BUDGET_PER_SESSION
