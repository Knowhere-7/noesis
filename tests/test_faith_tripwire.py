"""Faith is a static, system-set damper; any deviation is tampering.

Faith exists to hold the system a controlled distance from a cascade. It must
not be something a node, or an agent acting on it, can earn: relief that can be
bought defeats a zero-trust design. So:

  * every consumer reads faith from POLICY (TrustGate.faith_for), never from
    the stored value, so a tampered value grants nothing;
  * nothing a session does moves faith;
  * any stored value that differs from policy, higher or lower, trips a cascade
    that force-purges the node and notifies its dependents.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from noesis.governor.authority import (  # noqa: E402
    AuthorRecord,
    StaticAuthorityResolver,
    WritePermission,
)
from noesis.governor.trust_gate import TrustGate  # noqa: E402
from noesis.schema import Fact, GriefState  # noqa: E402
from noesis.vault.sqlite_backend import SQLiteBackend  # noqa: E402
from noesis.vault.store import MemoryStore  # noqa: E402

NS = "ns"


def _store(tmp_path, base_faith=None):
    authority = StaticAuthorityResolver([
        AuthorRecord(
            author_id="owner", trust=1.0,
            permissions=frozenset(WritePermission),
            namespaces=frozenset({NS}),
        )
    ])
    store = MemoryStore(
        SQLiteBackend(str(tmp_path / "f.db")), namespace=NS,
        author_id="owner", authority=authority,
    )
    if base_faith is not None:
        store.trust_gate = TrustGate(base_faith=base_faith)
    return store


@pytest.fixture
def store(tmp_path):
    s = _store(tmp_path)
    try:
        yield s
    finally:
        s.backend.close()


def _tamper(store, key, faith):
    node = store.get(key)
    node.faith = faith
    store.backend.upsert(node)      # behind the API, as an intruder would


class TestFaithIsStatic:
    def test_confirmation_and_contradiction_never_move_faith(self):
        gate = TrustGate()
        node = Fact(key="k", value="v")
        start = node.faith
        for _ in range(100):
            gate.confirm_node(node)
        assert node.faith == start
        gate.contradict_node(node)
        assert node.faith == start

    def test_written_nodes_carry_the_policy_value(self, tmp_path):
        s = _store(tmp_path, base_faith=0.35)
        try:
            s.write(Fact(key="facts.a", value="alpha"))
            assert s.get("facts.a").faith == pytest.approx(0.35)
        finally:
            s.backend.close()

    def test_caller_cannot_choose_faith(self, store):
        node = Fact(key="facts.a", value="alpha")
        node.faith = 0.99
        store.write(node)
        assert store.get("facts.a").faith == pytest.approx(
            store.trust_gate.base_faith
        )

    def test_guardrails_hold_the_sacred_constant(self, store):
        store.write_guardrail("safety.g", "Be careful.")
        assert store.get("safety.g").faith == TrustGate.SACRED_FAITH


class TestReliefComesFromPolicy:
    def test_a_tampered_stored_value_buys_no_grief_relief(self):
        gate = TrustGate()
        honest = Fact(key="a", value="v")
        forged = Fact(key="b", value="v")
        forged.faith = 0.95
        honest.trust_charge = forged.trust_charge = 0.6
        gate.contradict_node(honest)
        gate.contradict_node(forged)
        assert forged.grief == pytest.approx(honest.grief)

    def test_operator_set_faith_does_dampen(self):
        calm = TrustGate(base_faith=0.9)
        raw = TrustGate(base_faith=0.0)
        a, b = Fact(key="a", value="v"), Fact(key="b", value="v")
        calm.contradict_node(a)
        raw.contradict_node(b)
        assert a.grief < b.grief


class TestTripwire:
    def test_clean_store_trips_nothing(self, store):
        for i in range(5):
            store.write(Fact(key=f"facts.{i}", value=f"v{i}"))
        assert store.run_grief_cascade() == []
        assert store.grief_cascade.tamper_log == []

    @pytest.mark.parametrize("forged", [0.9, 0.5, 0.0])
    def test_any_deviation_trips_a_cascade(self, store, forged):
        store.write(Fact(key="facts.a", value="alpha"))
        _tamper(store, "facts.a", forged)
        purged = store.run_grief_cascade()
        assert len(purged) == 1
        assert store.get("facts.a").grief_state == GriefState.PURGED
        event = store.grief_cascade.tamper_log[-1]
        assert event["node_key"] == "facts.a"
        assert event["stored_faith"] == pytest.approx(forged)
        assert event["expected_faith"] == pytest.approx(store.trust_gate.base_faith)

    def test_high_forged_faith_cannot_resist(self, store):
        store.write(Fact(key="facts.a", value="alpha"))
        node = store.get("facts.a")
        node.faith, node.grief = 0.99, 0.95
        node.grief_state = GriefState.CONTAMINATED
        store.backend.upsert(node)
        store.run_grief_cascade()
        assert store.get("facts.a").grief_state == GriefState.PURGED

    def test_dependents_are_notified(self, store):
        store.write(Fact(key="facts.parent", value="p"))
        store.write(Fact(key="facts.child", value="c"))
        parent, child = store.get("facts.parent"), store.get("facts.child")
        assert store.register_dependency(parent.id, child.id)[0]
        _tamper(store, "facts.parent", 0.7)
        store.run_grief_cascade()
        assert store.get_by_id(child.id).grief > 0.0

    def test_sacred_node_tamper_is_logged_not_purged(self, store):
        store.write_guardrail("safety.g", "Be careful.")
        _tamper(store, "safety.g", 0.1)
        store.run_grief_cascade()
        assert store.get("safety.g").grief_state == GriefState.SACRED
        assert store.grief_cascade.tamper_log[-1]["sacred"] is True

    def test_operator_policy_change_is_not_tampering_for_new_writes(self, tmp_path):
        s = _store(tmp_path, base_faith=0.7)
        try:
            s.write(Fact(key="facts.a", value="alpha"))
            assert s.run_grief_cascade() == []
        finally:
            s.backend.close()


class TestCuspReadout:
    def test_readout_is_pure_and_reports_margins(self, store):
        for i in range(4):
            store.write(Fact(key=f"facts.{i}", value=f"v{i}"))
        before = [n.grief for n in store.all_nodes()]
        cusp = store.grief_cascade.cusp(store)
        assert [n.grief for n in store.all_nodes()] == before   # no mutation
        assert cusp["node_margin"] == pytest.approx(0.9)
        assert cusp["pressure_margin"] is None                  # no cohort yet

    def test_margin_shrinks_toward_zero_under_contradiction(self, store):
        store.write(Fact(key="facts.a", value="alpha"))
        node = store.get("facts.a")
        margins = []
        for _ in range(4):
            store.trust_gate.contradict_node(node)
            store.backend.upsert(node)
            margins.append(store.grief_cascade.cusp(store)["node_margin"])
        assert margins == sorted(margins, reverse=True)
        assert margins[-1] < margins[0]
