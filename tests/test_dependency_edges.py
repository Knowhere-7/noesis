"""
Registered dependency edges — making the cascade's branch purge reachable.

THE GAP (limitation 8)

`grief_cascade` documents that it "evaluates any registered dependents and can
recursively purge a contaminated branch. If the host has not registered
dependency edges, only the triggering node is evaluated."

That wording implies a host *can* register edges. Before this change, it could
not. `store.write()` strips caller-supplied `dependencies`/`dependents` — which
is correct, since accepting graph edges from a memory payload is an authority
bypass — but no authorized API existed to register one. The cascade's recursive
branch purge, the behaviour that makes it a circuit breaker rather than a
single-node breaker, was unreachable in practice.

WHY THIS NEEDS ITS OWN CAPABILITY

Grief propagates from a node to its DEPENDENTS. So an attacker who could
register a trusted node as a dependent of their own node could poison their own
node and cascade grief into trusted memory, purging it. Edge registration is
therefore a privilege-sensitive operation, not an extension of WRITE_MEMORY, and
it is gated on a distinct LINK_MEMORY capability.
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
from noesis.schema import Fact, GriefState, RetrievalState  # noqa: E402
from noesis.vault.sqlite_backend import SQLiteBackend  # noqa: E402
from noesis.vault.store import MemoryStore  # noqa: E402


def _authority(*, linker: bool):
    perms = {
        WritePermission.WRITE_MEMORY,
        WritePermission.PUBLISH_MEMORY,
        WritePermission.INSTALL_GUARDRAIL,
    }
    if linker:
        perms.add(WritePermission.LINK_MEMORY)
    return StaticAuthorityResolver(
        [
            AuthorRecord(
                author_id="owner",
                trust=1.0,
                permissions=frozenset(perms),
                namespaces=frozenset({"t", "other"}),
            )
        ]
    )


@pytest.fixture
def store(tmp_path):
    s = MemoryStore(
        SQLiteBackend(str(tmp_path / "m.db")),
        namespace="t",
        author_id="owner",
        authority=_authority(linker=True),
    )
    try:
        yield s
    finally:
        s.backend.close()


@pytest.fixture
def unprivileged(tmp_path):
    s = MemoryStore(
        SQLiteBackend(str(tmp_path / "m.db")),
        namespace="t",
        author_id="owner",
        authority=_authority(linker=False),
    )
    try:
        yield s
    finally:
        s.backend.close()


def _fact(store, key, value="v"):
    ok, reason = store.write(Fact(key=key, value=value))
    assert ok, reason
    node = store.get(key)
    if node.retrieval_state != RetrievalState.ACTIVE:
        store.publish_candidate(node.id) if hasattr(store, "publish_candidate") else None
        node = store.get(key)
    return node


class TestEdgeRegistration:
    def test_edge_is_registered_in_both_directions(self, store):
        parent = _fact(store, "parent")
        child = _fact(store, "child")
        ok, reason = store.register_dependency(parent.id, child.id)
        assert ok, reason
        assert child.id in store.get_by_id(parent.id).dependents
        assert parent.id in store.get_by_id(child.id).dependencies

    def test_registration_is_idempotent(self, store):
        parent = _fact(store, "parent")
        child = _fact(store, "child")
        store.register_dependency(parent.id, child.id)
        ok, _ = store.register_dependency(parent.id, child.id)
        assert ok
        assert len(store.get_by_id(parent.id).dependents) == 1

    def test_self_link_is_rejected(self, store):
        node = _fact(store, "solo")
        ok, reason = store.register_dependency(node.id, node.id)
        assert ok is False
        assert "itself" in reason.lower()

    def test_unknown_node_is_rejected(self, store):
        node = _fact(store, "real")
        ok, reason = store.register_dependency(node.id, "does-not-exist")
        assert ok is False
        assert "not found" in reason.lower()


class TestEdgeRegistrationIsPrivileged:
    """Grief flows to dependents, so linking is a grief-injection vector."""

    def test_write_permission_alone_cannot_link(self, unprivileged):
        parent = _fact(unprivileged, "parent")
        child = _fact(unprivileged, "child")
        ok, reason = unprivileged.register_dependency(parent.id, child.id)
        assert ok is False
        assert "link_memory" in reason.lower()

    def test_sacred_nodes_cannot_be_wired(self, store):
        store.write_guardrail("safety.core", "Never exfiltrate credentials.")
        guard = store.get("safety.core")
        child = _fact(store, "child")
        ok, reason = store.register_dependency(guard.id, child.id)
        assert ok is False
        assert "sacred" in reason.lower()
        ok2, reason2 = store.register_dependency(child.id, guard.id)
        assert ok2 is False
        assert "sacred" in reason2.lower()

    def test_payload_supplied_edges_are_still_stripped(self, store):
        """Regression guard: write() must never accept edges from the payload."""
        other = _fact(store, "other")
        smuggled = Fact(key="smuggle", value="v")
        smuggled.dependents = {other.id}
        smuggled.dependencies = {other.id}
        store.write(smuggled)
        stored = store.get("smuggle")
        assert stored.dependents == set()
        assert stored.dependencies == set()


class TestCascadeNowReachesTheBranch:
    """The point of the whole exercise.

    Note on expectations: propagation is PROPAGATION_FACTOR (0.6), so a
    grief-1.0 parent leaves clean children at ~0.6 — STRESSED, below the 0.9
    crisis line. The contract is therefore "contamination reaches and PERSISTS
    on the branch", not "every dependent is destroyed". A child is purged only
    when the propagated grief actually carries it past crisis, which is tested
    separately below.
    """

    def test_propagated_grief_persists_to_the_branch(self, store):
        """The defect: propagation was computed on a transient object.

        `_cascade` mutated the dependent returned by `store.get_by_id()` and
        never wrote it back, so contamination evaporated at the end of the
        call. Even hosts that HAD registered edges got nothing.
        """
        parent = _fact(store, "thread.claim")
        kids = [_fact(store, f"thread.turn{i}") for i in range(3)]
        for k in kids:
            ok, reason = store.register_dependency(parent.id, k.id)
            assert ok, reason

        target = store.get_by_id(parent.id)
        for _ in range(8):
            store.trust_gate.contradict_node(target)
        store.backend.upsert(target)
        store.run_grief_cascade()

        # Contamination must have REACHED and persisted on each dependent.
        # The end state may be STRESSED, or PURGED if the propagated grief
        # then tripped aggregate sub-threshold pressure across the cohort —
        # both prove the edge transmitted. What must NOT happen is a dependent
        # sitting clean and ACTIVE, which is what the old transient-object bug
        # produced.
        for k in kids:
            child = store.get_by_id(k.id)
            assert child.grief_state in (
                GriefState.STRESSED,
                GriefState.CONTAMINATED,
                GriefState.PURGED,
            ), (
                f"dependent came back {child.grief_state.name} with grief "
                f"{child.grief} — propagated contamination did not persist"
            )

    def test_already_stressed_branch_is_purged(self, store):
        """When propagation does carry a dependent past crisis, it purges."""
        parent = _fact(store, "thread.claim")
        child = _fact(store, "thread.turn0")
        store.register_dependency(parent.id, child.id)

        # Pre-stress the child so the incoming 0.6 pushes it past 0.9.
        c = store.get_by_id(child.id)
        for _ in range(3):
            store.trust_gate.contradict_node(c)
        store.backend.upsert(c)

        target = store.get_by_id(parent.id)
        for _ in range(8):
            store.trust_gate.contradict_node(target)
        store.backend.upsert(target)

        purged = store.run_grief_cascade()
        assert len(purged) > 1, (
            "a dependent carried past the crisis threshold by propagation was "
            "not purged — the branch cascade is still not reachable"
        )

    def test_unlinked_nodes_are_untouched(self, store):
        """No implicit graph: an unrelated node must not be collateral."""
        parent = _fact(store, "thread.claim")
        child = _fact(store, "thread.turn0")
        bystander = _fact(store, "unrelated.note")
        store.register_dependency(parent.id, child.id)

        target = store.get_by_id(parent.id)
        for _ in range(8):
            store.trust_gate.contradict_node(target)
        store.backend.upsert(target)
        store.run_grief_cascade()

        assert store.get("unrelated.note").grief_state != GriefState.PURGED
