"""
Grief Cascade — Contamination circuit breaker.

Ported from Murmuration's grief state machine and seppuku mechanics.
When a memory node's grief reaches crisis threshold, the cascade
evaluates any registered dependents and can recursively purge a contaminated
branch. If the host has not registered dependency edges, only the triggering
node is evaluated; Noesis does not claim an implicit graph exists.

This is the circuit breaker. When contradictions accumulate faster
than healing can resolve them, the grief cascade fires and the
contaminated context branch is wiped before it can poison the LLM.

From Gemini's analysis:
  "Rather than passing this logical contradiction to the LLM core
   to let it get confused, the engine handles it at the state layer.
   The target node's trust_battery craters to 0.00, and its grief
   spikes to 1.00. This triggers a lightning-fast, recursive Grief
   Cascade that de-allocates contaminated state before generation."
   The memory topology self-cleans before a single token is generated."
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, List, Set

from noesis.schema import GriefState, MemoryNode, NodeType

if TYPE_CHECKING:
    from noesis.vault.store import MemoryStore

logger = logging.getLogger("noesis.governor")


class GriefCascade:
    """Recursive purge engine for contaminated memory branches.

    The cascade follows Murmuration's rules:
    1. Sacred nodes are immune — they never take grief
    2. High-faith nodes resist the cascade (faith dampens grief)
    3. Ephemeral nodes are purged first (lowest priority)
    4. The cascade stops when it hits sacred ground or healthy nodes
    5. Purged nodes leave a record (collective memory) for future learning
    """

    CRISIS_THRESHOLD = 0.9
    PROPAGATION_FACTOR = 0.6   # grief transfers at 60% to dependents
    FAITH_RESISTANCE = 0.45    # faith reduces incoming grief by up to 45%

    # ── Sub-threshold pressure (ported from archon monitor SW-1) ───────
    # "Signals parked below threshold still accumulate pressure."
    # A per-node crisis line alone is evadable: an attacker who spreads
    # contradictions thinly keeps every node STRESSED and never trips a
    # breaker (measured 1.0x friction in benchmarks/friction.py). Grief
    # parked below the line is still grief — it accumulates.
    SUB_THRESHOLD_FLOOR = 0.3        # matches TrustGate.GRIEF_STRESS_THRESHOLD
    DEFAULT_AGGREGATE_MEAN_THRESHOLD = 0.4
    DEFAULT_MIN_STRESSED_COHORT = 3

    def __init__(
        self,
        aggregate_mean_threshold: float = DEFAULT_AGGREGATE_MEAN_THRESHOLD,
        min_stressed_cohort: int = DEFAULT_MIN_STRESSED_COHORT,
    ):
        if not 0.0 < aggregate_mean_threshold < self.CRISIS_THRESHOLD:
            raise ValueError(
                "aggregate_mean_threshold must be above 0 and below crisis"
            )
        if min_stressed_cohort < 2:
            raise ValueError("min_stressed_cohort must be at least 2")
        self.aggregate_mean_threshold = aggregate_mean_threshold
        self.min_stressed_cohort = min_stressed_cohort
        self.cascade_log: List[Dict] = []  # audit trail of all purges
        self._visited: Set[str] = set()     # prevent infinite recursion
        self.last_pressure: float = 0.0     # observable: aggregate at last run
        self.last_pressure_threshold: float = 0.0

    def evaluate(self, store: MemoryStore) -> List[str]:
        """Scan all nodes and trigger cascades for contaminated ones.

        Two triggers:
          1. Per-node crisis  — a single node at grief >= CRISIS_THRESHOLD
          2. Aggregate pressure — a sufficiently large stressed cohort whose
             mean grief exceeds the configured policy threshold

        Returns list of purged node IDs.
        """
        purged: List[str] = []
        self._visited.clear()

        for node in store.all_nodes():
            if node.grief_state == GriefState.CONTAMINATED:
                branch_purged = self._cascade(node, store)
                purged.extend(branch_purged)

        # Trigger 2 — the quiet attack. Escalate the TRIGGER only; every
        # existing judgment still applies (sacred immunity, faith resistance,
        # seppuku criteria) so this widens detection, never the death warrant.
        self.last_pressure = self.aggregate_pressure(store)
        cohort = self._stressed_cohort(store)
        self.last_pressure_threshold = self.aggregate_pressure_threshold(
            len(cohort)
        )
        if (
            len(cohort) >= self.min_stressed_cohort
            and self.last_pressure >= self.last_pressure_threshold
        ):
            logger.warning(
                "Aggregate grief pressure %.2f >= %.2f across %d stressed "
                "nodes — no single node in crisis. Escalating cohort.",
                self.last_pressure,
                self.last_pressure_threshold,
                len(cohort),
            )
            for node in cohort:
                if node.id in self._visited:
                    continue
                node.grief = max(node.grief, self.CRISIS_THRESHOLD)
                node.grief_state = GriefState.CONTAMINATED
                store.backend.upsert(node)
                purged.extend(self._cascade(node, store))

        if purged:
            logger.info(
                "Grief cascade purged %d nodes: %s",
                len(purged),
                [p[:8] for p in purged],
            )

        return purged

    def aggregate_pressure(self, store: MemoryStore) -> float:
        """Total grief parked BELOW the per-node crisis line.

        Observable by design — the console and audit log need to show why a
        cohort was escalated when no individual node looked critical.
        """
        total = 0.0
        for node in store.all_nodes():
            if node.is_sacred or node.grief_state in (
                GriefState.PURGED, GriefState.SACRED
            ):
                continue
            if self.SUB_THRESHOLD_FLOOR <= node.grief < self.CRISIS_THRESHOLD:
                total += node.grief
        return round(total, 3)

    def aggregate_pressure_threshold(self, cohort_size: int) -> float:
        """Derive the trigger from cohort size instead of a fixed sum."""
        if cohort_size < self.min_stressed_cohort:
            return float("inf")
        return round(cohort_size * self.aggregate_mean_threshold, 3)

    def _stressed_cohort(self, store: MemoryStore) -> List[MemoryNode]:
        """Nodes carrying sub-crisis grief — the contributors to pressure."""
        return [
            n for n in store.all_nodes()
            if not n.is_sacred
            and n.grief_state not in (GriefState.PURGED, GriefState.SACRED)
            and self.SUB_THRESHOLD_FLOOR <= n.grief < self.CRISIS_THRESHOLD
        ]

    def trigger(self, node: MemoryNode, store: MemoryStore) -> List[str]:
        """Manually trigger a cascade from a specific contaminated node."""
        self._visited.clear()

        if node.grief < self.CRISIS_THRESHOLD:
            return []

        return self._cascade(node, store)

    def _cascade(
        self, node: MemoryNode, store: MemoryStore
    ) -> List[str]:
        """Recursive cascade from a single contaminated node.

        Mirrors Murmuration's seppuku evaluation:
        - If the node is sacred: immune, skip
        - If the node is ephemeral and contaminated: purge immediately
        - If the node has high faith: resist, reduce grief instead
        - Otherwise: purge and propagate to dependents
        """
        if node.id in self._visited:
            return []
        self._visited.add(node.id)

        purged: List[str] = []

        # Sacred ground is immune
        if node.is_sacred or node.grief_state == GriefState.SACRED:
            return []

        # Already purged
        if node.grief_state == GriefState.PURGED:
            return []

        # Not in crisis — no cascade needed
        if node.grief < self.CRISIS_THRESHOLD:
            return []

        # High-faith nodes resist the cascade
        # (from Murmuration: faith dampens grief by up to 45%)
        if node.faith > 0.6:
            resistance = node.faith * self.FAITH_RESISTANCE
            node.grief = max(0.0, node.grief - resistance)
            if node.grief < self.CRISIS_THRESHOLD:
                # Faith saved this node
                node.grief_state = GriefState.STRESSED
                logger.debug(
                    "Node '%s' resisted cascade via faith (%.2f).",
                    node.key, node.faith,
                )
                return []

        # Evaluate seppuku criteria (from Murmuration agent.js)
        # For memory nodes: trust < 0.2 AND grief >= 0.9 AND no sacred deps
        should_purge = self._evaluate_purge(node, store)

        if should_purge:
            # Purge this node
            self._purge_node(node, store)
            purged.append(node.id)

            # Propagate grief to dependents
            for dep_id in list(node.dependents):
                dependent = store.get_by_id(dep_id)
                if dependent and dependent.id not in self._visited:
                    # Grief propagates at reduced strength
                    faith_damper = 1.0 - (
                        dependent.faith * self.FAITH_RESISTANCE
                    )
                    grief_hit = (
                        node.grief * self.PROPAGATION_FACTOR * faith_damper
                    )
                    dependent.grief = min(1.0, dependent.grief + grief_hit)
                    dependent.trust_charge = max(
                        0.05,
                        dependent.trust_charge - 0.1,
                    )

                    # Update state and potentially cascade
                    if dependent.grief >= self.CRISIS_THRESHOLD:
                        dependent.grief_state = GriefState.CONTAMINATED
                        sub_purged = self._cascade(dependent, store)
                        purged.extend(sub_purged)
                    elif dependent.grief >= 0.3:
                        dependent.grief_state = GriefState.STRESSED

        return purged

    def _evaluate_purge(
        self, node: MemoryNode, store: MemoryStore
    ) -> bool:
        """Should this node be purged? Mirrors seppuku evaluation.

        Criteria (2 of 3 must be met):
        1. Trust charge < 0.2 (depleted authority)
        2. No healthy dependencies (lost the signal)
        3. Grief >= 0.9 (in crisis)
        """
        criteria = 0

        if node.trust_charge < 0.2:
            criteria += 1

        # Check if any dependencies are healthy
        healthy_deps = 0
        for dep_id in node.dependencies:
            dep = store.get_by_id(dep_id)
            if dep and dep.grief_state in (GriefState.ACTIVE, GriefState.SACRED):
                healthy_deps += 1
        if healthy_deps == 0:
            criteria += 1

        if node.grief >= self.CRISIS_THRESHOLD:
            criteria += 1

        # Ephemeral nodes are always purgeable when contaminated
        if node.node_type == NodeType.EPHEMERAL:
            return True

        return criteria >= 2

    def _purge_node(self, node: MemoryNode, store: MemoryStore):
        """Execute the purge — equivalent to Murmuration's performSeppuku.

        1. Mark as purged (don't delete — keep for audit trail)
        2. Transfer any remaining trust to healthy neighbors (redistribution)
        3. Record in cascade log (collective memory)
        """
        # Record before purge
        self.cascade_log.append({
            "node_id": node.id,
            "node_key": node.key,
            "node_type": node.node_type.name,
            "trust_at_purge": node.trust_charge,
            "grief_at_purge": node.grief,
            "faith_at_purge": node.faith,
            "dependencies": list(node.dependencies),
            "dependents": list(node.dependents),
        })

        # Redistribute remaining trust to healthy dependencies
        # (from Murmuration performSeppuku: distribute to top bonded neighbors)
        healthy = []
        for dep_id in node.dependencies:
            dep = store.get_by_id(dep_id)
            if dep and dep.grief_state != GriefState.PURGED and not dep.is_sacred:
                healthy.append(dep)

        if healthy and node.trust_charge > 0.05:
            share = (node.trust_charge - 0.05) / len(healthy)
            for h in healthy[:3]:  # top 3, like Murmuration
                h.trust_charge = min(1.0, h.trust_charge + share)

        # Mark purged
        node.grief_state = GriefState.PURGED
        node.trust_charge = 0.05
        node.grief = 0.0
        node.importance = 0.0

        # Remove from active retrieval (but keep in store for audit)
        store.mark_purged(node.id)
