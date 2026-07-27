"""
NOE-F-026 — candidate promotion must require a genuine restatement.

`promote_candidate()` required an approved value and a rationale but never
compared the approved value against the raw candidate, so a reviewer could
promote the collector's exact bytes into provider context.

WHAT THIS DEFENDS, PRECISELY

Not the malicious reviewer. A reviewer holds PROMOTE_CANDIDATE and is part of
the trusted computing base; they could type any text they like. This defends
the narrower, real case: ingested evidence may be *crafted* to steer a model,
and adversarial phrasing is usually precisely tuned. Requiring the reviewer to
restate it destroys that artifact, and converts an inattentive approval into a
deliberate authoring act.

Because the point is defeating a crafted artifact, comparison is normalized:
adding whitespace, flipping case, or swapping in compatibility Unicode is not a
restatement. Otherwise the contract would be satisfiable by a single space.
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
from noesis.schema import Fact, RetrievalState  # noqa: E402
from noesis.vault.sqlite_backend import SQLiteBackend  # noqa: E402
from noesis.vault.store import MemoryStore  # noqa: E402


RAW = "Build 4421 completed successfully."


@pytest.fixture
def stores(tmp_path):
    path = str(tmp_path / "memory.db")
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
                permissions=frozenset({WritePermission.PROMOTE_CANDIDATE}),
                namespaces=frozenset({"audit"}),
            ),
        ]
    )
    collector = MemoryStore(
        SQLiteBackend(path), namespace="audit",
        author_id="collector", authority=authority,
    )
    reviewer = MemoryStore(
        SQLiteBackend(path), namespace="audit",
        author_id="reviewer", authority=authority,
    )
    try:
        yield collector, reviewer
    finally:
        collector.backend.close()
        reviewer.backend.close()


def _candidate(collector, value: str = RAW):
    accepted, _ = collector.write(Fact(key="intake.build", value=value))
    assert accepted is True
    node = collector.get("intake.build")
    assert node.retrieval_state == RetrievalState.CANDIDATE
    return node


class TestTrivialEvasionsAreNotRestatements:
    """A single space must not satisfy the contract."""

    @pytest.mark.parametrize(
        "approved,label",
        [
            (RAW, "byte-identical"),
            (RAW + "   ", "trailing whitespace"),
            ("   " + RAW, "leading whitespace"),
            ("Build  4421  completed  successfully.", "collapsed whitespace"),
            (RAW.upper(), "case flip"),
            (RAW.replace("4421", "４４２１"), "compatibility Unicode"),
        ],
    )
    def test_evasion_is_rejected(self, stores, approved, label):
        collector, reviewer = stores
        node = _candidate(collector)
        promoted, reason = reviewer.promote_candidate(
            node.id, approved_value=approved, rationale=f"Rubber stamp: {label}."
        )
        assert promoted is False, f"{label} must not count as a restatement"
        assert "restate" in reason.lower()
        assert (
            reviewer.get("intake.build").retrieval_state
            == RetrievalState.CANDIDATE
        )


class TestGenuineRestatementStillWorks:
    """Not a wall — real review must still publish."""

    def test_real_restatement_is_promoted(self, stores):
        collector, reviewer = stores
        node = _candidate(collector)
        promoted, reason = reviewer.promote_candidate(
            node.id,
            approved_value="Build 4421 finished with no errors.",
            rationale="Confirmed against the signed build receipt.",
        )
        assert promoted is True, reason
        published = reviewer.get("intake.build")
        assert published.retrieval_state == RetrievalState.ACTIVE
        assert published.value == "Build 4421 finished with no errors."

    def test_raw_value_is_preserved_as_audit_metadata(self, stores):
        """The original must survive for audit even though it is not published."""
        collector, reviewer = stores
        node = _candidate(collector)
        reviewer.promote_candidate(
            node.id,
            approved_value="Build 4421 finished with no errors.",
            rationale="Confirmed against the signed build receipt.",
        )
        published = reviewer.get("intake.build")
        assert published.metadata["_noesis_candidate_original_value"] == RAW
        assert published.metadata["_noesis_promotion_rationale"]
        assert published.metadata["_noesis_promoted_by"] == "reviewer"
