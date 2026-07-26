"""Truth contracts for Noesis' public failure disclosure.

The failure ledger is part of the security surface: claims must remain tied
to evidence, repaired findings must name their regression coverage, and open
findings must remain executable rather than disappearing into prose.
"""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import re

import pytest

from noesis.governor.authority import (
    AuthorRecord,
    StaticAuthorityResolver,
    WritePermission,
)
from noesis.schema import Fact, RetrievalState
from noesis.vault.sqlite_backend import SQLiteBackend
from noesis.vault.store import MemoryStore


ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = ROOT / "evidence" / "failure-ledger.json"
FAILURE_ID = re.compile(r"^NOE-F-\d{3}$")
COMMIT_ID = re.compile(r"^[0-9a-f]{40}$")


def test_public_failure_ledger_is_complete_and_traceable():
    data = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))

    assert data["schema_version"] == "1.0"
    assert data["policy"]["append_only"] is True
    assert data["policy"]["renumbering_forbidden"] is True
    assert data["policy"]["deletion_forbidden"] is True

    entries = data["entries"]
    ids = [entry["id"] for entry in entries]
    assert ids
    assert len(ids) == len(set(ids))
    assert all(FAILURE_ID.fullmatch(failure_id) for failure_id in ids)
    assert ids == sorted(ids, key=lambda value: int(value.rsplit("-", 1)[1]))

    required = {
        "id",
        "title",
        "discovered_at",
        "discovered_by",
        "review_class",
        "disclosure_scope",
        "severity",
        "status",
        "affected_claim",
        "affected_versions",
        "root_cause",
        "observed_impact",
        "evidence",
        "resolution",
        "fixed_by_commit",
        "regression_tests",
        "residual_risk",
        "history",
    }
    valid_statuses = {"open", "fixed", "mitigated", "accepted_limitation"}
    valid_scopes = {"released", "development_only", "claim_correction"}
    valid_reviews = {
        "external_adversarial",
        "first_party_adversarial",
        "first_party_benchmark",
        "first_party_development",
    }

    for entry in entries:
        assert required <= entry.keys(), entry["id"]
        date.fromisoformat(entry["discovered_at"])
        assert entry["status"] in valid_statuses
        assert entry["disclosure_scope"] in valid_scopes
        assert entry["review_class"] in valid_reviews
        assert entry["affected_claim"].strip()
        assert entry["root_cause"].strip()
        assert entry["observed_impact"].strip()
        assert entry["evidence"]
        assert entry["history"]
        assert entry["history"][-1]["status"] == entry["status"]

        for event in entry["history"]:
            date.fromisoformat(event["at"])
            assert event["status"] in valid_statuses
            assert event["note"].strip()

        for evidence_ref in entry["evidence"]:
            if evidence_ref.startswith("path:"):
                evidence_path = ROOT / evidence_ref.removeprefix("path:")
                assert evidence_path.exists(), (
                    f"{entry['id']} points to missing evidence {evidence_path}"
                )
            else:
                assert evidence_ref.startswith("git:"), (
                    f"{entry['id']} has an untyped evidence reference"
                )

        if entry["status"] == "fixed":
            assert COMMIT_ID.fullmatch(entry["fixed_by_commit"])
            assert entry["regression_tests"]
            assert entry["resolution"].strip()
        else:
            assert entry["fixed_by_commit"] is None

    limitations = data["current_limitations"]
    limitation_ids = [item["id"] for item in limitations]
    assert len(limitation_ids) == len(set(limitation_ids))
    assert all(item["statement"].strip() for item in limitations)


def test_public_documents_link_and_acknowledge_the_failure_ledger():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    benchmark_readme = (
        ROOT / "benchmarks" / "README.md"
    ).read_text(encoding="utf-8")
    ledger = (ROOT / "FAILURE_LEDGER.md").read_text(encoding="utf-8")

    assert "[Failure ledger](FAILURE_LEDGER.md)" in readme
    assert "[public failure ledger](../FAILURE_LEDGER.md)" in benchmark_readme
    assert "NOE-F-026" in ledger
    assert "does not enforce a changed value" in ledger


@pytest.mark.xfail(
    strict=True,
    reason=(
        "NOE-F-026 is open: candidate promotion accepts unchanged source text"
    ),
)
def test_candidate_promotion_requires_value_to_change(tmp_path):
    """Executable reproducer retained until NOE-F-026 is repaired."""
    memory_path = str(tmp_path / "memory.db")
    authority = StaticAuthorityResolver(
        [
            AuthorRecord(
                author_id="collector",
                trust=0.7,
                permissions=frozenset({WritePermission.WRITE_MEMORY}),
                namespaces=frozenset({"audit"}),
            ),
            AuthorRecord(
                author_id="reviewer",
                trust=1.0,
                permissions=frozenset(
                    {WritePermission.PROMOTE_CANDIDATE}
                ),
                namespaces=frozenset({"audit"}),
            ),
        ]
    )
    collector = MemoryStore(
        SQLiteBackend(memory_path),
        namespace="audit",
        author_id="collector",
        authority=authority,
    )
    reviewer = MemoryStore(
        SQLiteBackend(memory_path),
        namespace="audit",
        author_id="reviewer",
        authority=authority,
    )

    try:
        raw_value = "Build 4421 completed successfully."
        accepted, _ = collector.write(
            Fact(key="intake.build", value=raw_value)
        )
        assert accepted is True
        candidate = collector.get("intake.build")
        assert candidate.retrieval_state == RetrievalState.CANDIDATE

        promoted, _ = reviewer.promote_candidate(
            candidate.id,
            approved_value=raw_value,
            rationale="Reviewed source.",
        )

        assert promoted is False
        assert (
            reviewer.get("intake.build").retrieval_state
            == RetrievalState.CANDIDATE
        )
    finally:
        collector.backend.close()
        reviewer.backend.close()
