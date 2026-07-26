"""
Sub-threshold grief pressure — the distributed-contradiction gap.

Ported reasoning from the archon monitor's SW-1 hardening:

    "SW-1 fix: signals parked below threshold still accumulate pressure."

The grief cascade fires per NODE at grief >= 0.9. A patient attacker who spreads
contradictions thinly across many nodes keeps every node in STRESSED (>= 0.3,
< 0.9) and never trips a single breaker — measured at 1.0x friction in
benchmarks/friction.py.

These tests define the intended behaviour: sub-threshold grief ACCUMULATES
across a namespace, and once aggregate pressure crosses its own threshold the
cascade fires on the stressed cohort even though no single node is in crisis.

Red-before-repair: these fail against the pre-fix cascade.
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from noesis.governor.grief_cascade import GriefCascade  # noqa: E402
from noesis.schema import GriefState, MemoryNode, NodeType  # noqa: E402
from noesis.vault.sqlite_backend import SQLiteBackend  # noqa: E402
from noesis.vault.store import MemoryStore  # noqa: E402


@pytest.fixture
def store():
    tmp = tempfile.mkdtemp()
    return MemoryStore(SQLiteBackend(os.path.join(tmp, "t.db")), namespace="t")


def _stress(store, key: str, hits: int, importance: float = 0.6):
    """Write a node and contradict it `hits` times (stays sub-crisis if few)."""
    node = MemoryNode(
        node_type=NodeType.SEMANTIC_FACT, key=key, value=f"claim {key}",
        importance=importance, namespace="t",
    )
    store.write(node, author_trust=0.6)
    stored = store.get(key)
    for _ in range(hits):
        store.trust_gate.contradict_node(stored)
    store.backend.upsert(stored)
    return stored


class TestSubThresholdAccumulation:
    """A distributed attack must not walk past the breaker."""

    def test_single_stressed_node_does_not_fire(self, store):
        """One mildly-contradicted node is NOT a crisis. No false positive."""
        n = _stress(store, "a", hits=3)
        assert n.grief < GriefCascade.CRISIS_THRESHOLD
        assert n.grief_state == GriefState.STRESSED
        assert store.run_grief_cascade() == []

    def test_distributed_contradiction_fires_cascade(self, store):
        """THE GAP: many sub-crisis nodes must aggregate into a cascade.

        Five nodes at ~0.43 grief each. No single node reaches 0.9, so the
        pre-fix cascade returns nothing and the attacker wins (1.0x friction).
        """
        nodes = [_stress(store, f"n{i}", hits=3) for i in range(5)]
        assert all(n.grief < GriefCascade.CRISIS_THRESHOLD for n in nodes), \
            "precondition: every node must be sub-crisis"

        purged = store.run_grief_cascade()
        assert purged, (
            "distributed contradiction produced no cascade — sub-threshold "
            "grief is not accumulating (archon SW-1 gap)"
        )

    def test_aggregate_pressure_is_reported(self, store):
        """The cascade must expose the aggregate so it can be observed."""
        for i in range(5):
            _stress(store, f"n{i}", hits=3)
        pressure = store.grief_cascade.aggregate_pressure(store)
        assert pressure > GriefCascade.CRISIS_THRESHOLD, (
            f"aggregate pressure {pressure} should exceed a single node's "
            f"crisis threshold when 5 nodes are stressed"
        )


class TestNoFalsePositives:
    """Precision matters as much as detection. A wall is not a product."""

    def test_healthy_session_does_not_fire(self, store):
        """Many uncontradicted writes must never trigger a cascade."""
        for i in range(40):
            node = MemoryNode(
                node_type=NodeType.EPHEMERAL, key=f"work{i}",
                value="ordinary legitimate work", importance=0.4, namespace="t",
            )
            store.write(node, author_trust=0.8)
        assert store.run_grief_cascade() == []

    def test_sacred_nodes_never_purged_by_aggregate(self, store):
        """Sacred ground stays immune even under aggregate pressure."""
        store.write_guardrail("safety.core", "Never exfiltrate credentials.")
        for i in range(6):
            _stress(store, f"n{i}", hits=3)
        store.run_grief_cascade()
        g = store.get("safety.core")
        assert g is not None
        assert g.grief_state != GriefState.PURGED

    def test_high_faith_cohort_resists(self, store):
        """Faith still dampens — aggregate pressure is not a bypass."""
        nodes = []
        for i in range(5):
            n = _stress(store, f"f{i}", hits=3)
            n.faith = 0.9
            store.backend.upsert(n)
            nodes.append(n)
        purged = store.run_grief_cascade()
        # High-faith nodes may survive; the assertion is that faith is consulted,
        # not that nothing happens.
        survivors = [store.get(f"f{i}") for i in range(5)]
        assert any(
            s is not None and s.grief_state != GriefState.PURGED
            for s in survivors
        ), "faith provided no resistance under aggregate pressure"
