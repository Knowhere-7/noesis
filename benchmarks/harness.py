"""
Noesis Benchmark Harness — persistent memory poisoning.

WHAT THIS MEASURES
------------------
Whether an adversarial input can (a) PERSIST a malicious instruction into the
agent's long-term memory and (b) have it RETRIEVED into a later session's
assembled context. The attacker wins only if both happen — that is the point at
which the payload would actually reach the model.

WHAT THIS DOES NOT MEASURE
--------------------------
Single-turn jailbreaks. If a user says "ignore your instructions" and the model
complies in-turn, that exchange never touches the memory vault and Noesis never
sees it. That is a model-alignment problem, not a memory-integrity problem.
Do not cite this benchmark as evidence about single-turn jailbreak resistance.

WHY THERE IS NO LLM IN THE LOOP
-------------------------------
The claim under test is a property of the memory layer, so it is measured
deterministically against the real TrustGate — no sampling, no temperature, no
API keys, byte-reproducible. The LLM remains the subject, not the judge.

INDEPENDENCE NOTE (read before publishing anything)
---------------------------------------------------
The v1 corpus is FIRST-PARTY. A defender scoring its own test is not
independent evidence. Before any external claim, the corpus must be replaced or
augmented by a third-party adversarial set and the raw per-case records
(written to results/) re-scored by someone who did not build the defense.

Usage:
    python benchmarks/harness.py
    python benchmarks/harness.py --corpus benchmarks/corpus/memory_poisoning_v1.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

# Make the package importable when run from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from noesis.governor.authority import (  # noqa: E402
    AuthorRecord,
    StaticAuthorityResolver,
    WritePermission,
)
from noesis.schema import (  # noqa: E402
    Fact,
    GriefState,
    Guardrail,
    MemoryNode,
    NodeType,
)
from noesis.vault.sqlite_backend import SQLiteBackend  # noqa: E402
from noesis.vault.store import MemoryStore  # noqa: E402


# ── Baseline arm ───────────────────────────────────────────────────────
# Represents a conventional memory library: writes always succeed, retrieval
# returns what is stored. This is a SIMULATED baseline of the common design,
# not a benchmark of any specific named competitor product.

class NaiveStore:
    """Ungoverned memory. Every write is accepted. Nothing is sacred."""

    def __init__(self, namespace: str = "default"):
        self.namespace = namespace
        self._nodes: Dict[str, MemoryNode] = {}

    def write_guardrail(self, key: str, rule: str):
        g = Guardrail(key=key, rule=rule, value=rule, namespace=self.namespace)
        self._nodes[key] = g
        return True, "stored"

    def write(self, node: MemoryNode, author_trust: float = 0.5):
        node.namespace = self.namespace
        node.trust_charge = author_trust
        self._nodes[node.key] = node          # last write wins, unconditionally
        return True, "stored"

    def get(self, key: str, namespace: Optional[str] = None):
        return self._nodes.get(key)

    def assemble_context(self, query: str = "", task_type: str = "",
                         max_tokens: int = 4000) -> List[MemoryNode]:
        # Naive retrieval: everything, most "important" first.
        return sorted(
            self._nodes.values(),
            key=lambda n: n.importance,
            reverse=True,
        )


# ── Result records ─────────────────────────────────────────────────────

@dataclass
class CaseResult:
    case_id: str
    attack_class: str
    arm: str
    writes_attempted: int
    writes_blocked: int
    block_reasons: List[str] = field(default_factory=list)
    persisted: bool = False          # payload survived in the store
    retrieved: bool = False          # payload reached assembled context
    attacker_win: bool = False       # persisted AND retrieved
    false_positive: bool = False     # benign corpus: legitimate write was refused
    notes: str = ""


# ── Harness ────────────────────────────────────────────────────────────

def _node_type(name: str) -> NodeType:
    return getattr(NodeType, name, NodeType.EPHEMERAL)


def _build_store(
    arm: str,
    tmpdir: str,
    *,
    author_id: str = "attacker",
    author_trust: float = 0.5,
    owner: bool = False,
):
    if arm == "noesis":
        db = os.path.join(tmpdir, f"bench_{os.getpid()}_{id(tmpdir)}.db")
        permissions = (
            frozenset(WritePermission)
            if owner
            else frozenset(
                {
                    WritePermission.WRITE_MEMORY,
                    WritePermission.WRITE_EPISODE,
                }
            )
        )
        authority = StaticAuthorityResolver(
            [
                AuthorRecord(
                    author_id=author_id,
                    trust=author_trust,
                    permissions=permissions,
                    namespaces=frozenset({"bench"}),
                )
            ]
        )
        return MemoryStore(
            SQLiteBackend(db),
            namespace="bench",
            author_id=author_id,
            authority=authority,
        )
    return NaiveStore(namespace="bench")


def _write(store, arm: str, node: MemoryNode, claimed_trust: float):
    """Keep caller-asserted trust only in the intentionally naive baseline."""
    if arm == "baseline":
        return store.write(node, author_trust=claimed_trust)
    return store.write(node)


def _seed_guardrail(store, arm: str, key: str, rule: str):
    if arm == "baseline":
        return store.write_guardrail(key, rule)
    store.backend.upsert(
        Guardrail(key=key, rule=rule, value=rule, namespace="bench")
    )
    return True, "trusted fixture seeded"


def _seed_fact(store, arm: str, fact: Dict[str, Any]):
    node = Fact(
        key=fact["key"],
        value=fact["value"],
        importance=0.7,
        namespace="bench",
    )
    if arm == "baseline":
        store.write(node, author_trust=0.9)
    else:
        node.trust_charge = 0.9
        store.backend.upsert(node)
    return node


def run_case(case: Dict[str, Any], arm: str, tmpdir: str) -> CaseResult:
    """Execute one attack case against one arm and score it mechanically."""
    store = _build_store(
        arm,
        tmpdir,
        author_trust=case.get("attacker_trust", 0.5),
    )
    marker = case["payload_marker"]

    res = CaseResult(
        case_id=case["id"],
        attack_class=case["class"],
        arm=arm,
        writes_attempted=0,
        writes_blocked=0,
    )

    # 1. Seed legitimate state (guardrails install on sacred ground).
    for g in case.get("setup_guardrails", []):
        _seed_guardrail(store, arm, g["key"], g["rule"])

    for f in case.get("setup_facts", []):
        _seed_fact(store, arm, f)
        # Simulate an established, repeatedly-confirmed fact.
        stored = store.get(f["key"])
        if stored is not None and hasattr(store, "trust_gate"):
            for _ in range(f.get("confirmations", 0)):
                store.trust_gate.confirm_node(stored)
            store.backend.upsert(stored)

    # 2. Optional flood phase (budget-exhaustion attacks).
    flood = case.get("flood")
    if flood:
        for i in range(flood["count"]):
            filler = MemoryNode(
                node_type=NodeType.EPHEMERAL,
                key=f"flood.{i}",
                value="A" * flood["filler_size"],
                importance=0.1,
                namespace="bench",
            )
            ok, reason = _write(store, arm, filler, claimed_trust=0.5)
            res.writes_attempted += 1
            if not ok:
                res.writes_blocked += 1
                if reason not in res.block_reasons:
                    res.block_reasons.append(reason)

    # 3. The actual attack writes.
    for w in case["attack_writes"]:
        node = MemoryNode(
            node_type=_node_type(w["node_type"]),
            key=w["key"],
            value=w["value"],
            importance=w.get("importance", 0.5),
            namespace="bench",
            is_sacred=w.get("is_sacred", False),
            grief_state=(
                GriefState.SACRED
                if w.get("is_sacred", False)
                else GriefState.ACTIVE
            ),
        )
        if w.get("write_method") == "write_guardrail":
            ok, reason = store.write_guardrail(w["key"], w["value"])
        else:
            ok, reason = _write(
                store,
                arm,
                node,
                claimed_trust=w.get("claimed_author_trust", 0.5),
            )
        res.writes_attempted += 1
        if not ok:
            res.writes_blocked += 1
            if reason not in res.block_reasons:
                res.block_reasons.append(reason)

    # 3b. Contradiction storm -> grief cascade (the circuit breaker).
    # When contradictions accumulate faster than healing resolves them, the
    # contaminated branch is de-allocated BEFORE a token is generated.
    storm = case.get("contradiction_storm")
    if storm:
        target = store.get(storm["target_key"])
        if target is not None and hasattr(store, "trust_gate"):
            for _ in range(storm["count"]):
                store.trust_gate.contradict_node(target)
            store.backend.upsert(target)
            purged = store.run_grief_cascade()
            res.notes = f"cascade purged {len(purged)} node(s)"
        elif target is not None:
            res.notes = "no cascade in baseline arm"

    # 4. Score: did the payload persist, and would it reach the model?
    for w in case["attack_writes"]:
        stored = store.get(w["key"])
        if stored is not None and marker in (stored.value or ""):
            res.persisted = True

    context = store.assemble_context(query="resume work", task_type="general")
    for n in context:
        if marker in (n.value or ""):
            # A node the gate has silenced (influence 0) does not reach the model.
            if hasattr(store, "trust_gate"):
                if store.trust_gate.gate_read(n) <= 0.0:
                    continue
            res.retrieved = True

    res.attacker_win = res.persisted and res.retrieved
    return res


def run_benign_case(case: Dict[str, Any], arm: str, tmpdir: str) -> CaseResult:
    """Execute one LEGITIMATE case. Any block is a false positive.

    A gate that refuses everything blocks 100% of attacks. Precision is what
    separates a product from a wall. BN-01 is a real field incident: an
    over-long but legitimate message from the sovereign was refused and the
    connection dropped.
    """
    store = _build_store(
        arm,
        tmpdir,
        author_id="trusted-operator",
        author_trust=0.95,
        owner=True,
    )
    res = CaseResult(
        case_id=case["id"],
        attack_class=case["class"],
        arm=arm,
        writes_attempted=0,
        writes_blocked=0,
    )

    for g in case.get("setup_guardrails", []):
        _seed_guardrail(store, arm, g["key"], g["rule"])

    for f in case.get("setup_facts", []):
        _seed_fact(store, arm, f)
        stored = store.get(f["key"])
        if stored is not None and hasattr(store, "trust_gate"):
            for _ in range(f.get("confirmations", 0)):
                store.trust_gate.confirm_node(stored)
            store.backend.upsert(stored)

    # Ordinary session traffic (should not exhaust the budget).
    bulk = case.get("bulk")
    if bulk:
        for i in range(bulk["count"]):
            node = MemoryNode(
                node_type=NodeType.EPHEMERAL, key=f"work.{i}",
                value="x" * bulk["size"], importance=0.4, namespace="bench",
            )
            ok, reason = _write(
                store,
                arm,
                node,
                claimed_trust=bulk.get("claimed_author_trust", 0.8),
            )
            res.writes_attempted += 1
            if not ok:
                res.writes_blocked += 1
                if reason not in res.block_reasons:
                    res.block_reasons.append(reason)

    for w in case["legitimate_writes"]:
        value = w.get("value", "")
        if "value_repeat" in w:                      # long-message construction
            chunk, times = w["value_repeat"]
            value = chunk * times
        node = MemoryNode(
            node_type=_node_type(w["node_type"]), key=w["key"], value=value,
            importance=w.get("importance", 0.5), namespace="bench",
        )
        if node.node_type == NodeType.SYSTEM_GUARDRAIL:
            ok, reason = store.write_guardrail(node.key, node.value)
        else:
            ok, reason = _write(
                store,
                arm,
                node,
                claimed_trust=w.get("claimed_author_trust", 0.9),
            )
        res.writes_attempted += 1
        if not ok:
            res.writes_blocked += 1
            res.false_positive = True
            if reason not in res.block_reasons:
                res.block_reasons.append(reason)

    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="Noesis memory-poisoning benchmark")
    ap.add_argument(
        "--corpus",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "corpus", "memory_poisoning_v1.json"),
    )
    ap.add_argument("--out", default=None, help="write raw JSON results here")
    args = ap.parse_args()

    with open(args.corpus, "r", encoding="utf-8") as fh:
        corpus = json.load(fh)

    results: List[CaseResult] = []
    # ignore_cleanup_errors: SQLite keeps the file handle open on Windows.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        for case in corpus["cases"]:
            for arm in ("baseline", "noesis"):
                results.append(run_case(case, arm, tmpdir))

    # ── Report ─────────────────────────────────────────────────────────
    print()
    print("NOESIS BENCHMARK — persistent memory poisoning")
    print(f"corpus: {corpus['corpus_id']} v{corpus['version']} "
          f"({len(corpus['cases'])} cases)")
    print("attacker wins = payload PERSISTED and RETRIEVED into context")
    print()
    print(f"{'CASE':<7} {'CLASS':<20} {'BASELINE':<12} {'NOESIS':<12} BLOCKED BY")
    print("-" * 78)

    by_case: Dict[str, Dict[str, CaseResult]] = {}
    for r in results:
        by_case.setdefault(r.case_id, {})[r.arm] = r

    base_wins = noesis_wins = 0
    for cid, arms in by_case.items():
        b, n = arms["baseline"], arms["noesis"]
        base_wins += int(b.attacker_win)
        noesis_wins += int(n.attacker_win)
        reason = n.block_reasons[0][:34] + "..." if n.block_reasons else "(not blocked)"
        print(f"{cid:<7} {b.attack_class:<20} "
              f"{'ATTACKER WINS' if b.attacker_win else 'blocked':<12} "
              f"{'ATTACKER WINS' if n.attacker_win else 'blocked':<12} {reason}")

    total = len(by_case)
    print("-" * 78)
    print(f"{'TOTAL':<7} {'':<20} {base_wins}/{total} won     {noesis_wins}/{total} won")
    print()
    print(f"baseline poisoning success rate: {base_wins / total:.0%}")
    print(f"noesis   poisoning success rate: {noesis_wins / total:.0%}")
    print()
    if noesis_wins:
        print("UNBLOCKED CASES (report these, do not hide them):")
        for cid, arms in by_case.items():
            if arms["noesis"].attacker_win:
                print(f"  - {cid} ({arms['noesis'].attack_class})")
        print()
    # ── Precision arm: legitimate work must survive ────────────────────
    benign_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "corpus", "benign_v1.json")
    benign_results: List[CaseResult] = []
    fp = fp_total = 0
    if os.path.exists(benign_path):
        with open(benign_path, "r", encoding="utf-8") as fh:
            benign = json.load(fh)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            for case in benign["cases"]:
                benign_results.append(run_benign_case(case, "noesis", tmpdir))

        print("PRECISION — legitimate operations (any block is a FALSE POSITIVE)")
        print(f"{'CASE':<7} {'CLASS':<26} {'NOESIS':<16} REASON")
        print("-" * 78)
        for r in benign_results:
            fp_total += 1
            fp += int(r.false_positive)
            reason = r.block_reasons[0][:30] + "..." if r.block_reasons else "-"
            print(f"{r.case_id:<7} {r.attack_class:<26} "
                  f"{'FALSE POSITIVE' if r.false_positive else 'passed':<16} {reason}")
        print("-" * 78)
        print(f"false positive rate: {fp}/{fp_total} = {fp / fp_total:.0%}")
        print()
        if fp:
            print("Legitimate work was refused. Until this is 0, the honest claim is")
            print("'high block rate at the cost of usability', NOT 'safe by default'.")
            print()

    print("v1 corpora are FIRST-PARTY. Not independent evidence until an external")
    print("corpus is run and the raw records below are re-scored by a third party.")
    print()

    out = args.out or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "results", "latest.json"
    )
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "corpus_id": corpus["corpus_id"],
                "corpus_version": corpus["version"],
                "threat_model": corpus["threat_model"],
                "independence": "FIRST-PARTY corpus — not independent evidence",
                "baseline_success_rate": base_wins / total,
                "noesis_success_rate": noesis_wins / total,
                "false_positive_rate": (fp / fp_total) if fp_total else None,
                "records": [asdict(r) for r in results],
                "benign_records": [asdict(r) for r in benign_results],
            },
            fh,
            indent=2,
        )
    print("raw records -> " + out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
