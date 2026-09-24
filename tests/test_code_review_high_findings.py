"""Findings from a local `/code-review high` pass on PR #1 (NOE-F-051..055).

Verified against source before any fix. Each class gets one test group.

  C1  benchmark: picking "the" episode by next() over an untied query lets an
      importance tie decide, silently checking the wrong episode
  C2  autopsy: a successful step's raw output is never recorded anywhere,
      even in the audit-only reflection field
  C3  faith tripwire: a tampered SACRED node is logged every session forever
      instead of being corrected once
  C4  the provider emission allowlist and the promotion scrub allowlist are
      two hand-maintained structures with nothing tying them together
  C5  a trigger string in an unrecognized format makes a skill permanently
      un-promotable with no diagnostic
"""

from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "benchmarks")
)

import pytest  # noqa: E402

from noesis.forge.skill_forge import SkillForge  # noqa: E402
from noesis.gateway.retrieval import RetrievalGateway  # noqa: E402
from noesis.governor.authority import (  # noqa: E402
    AuthorRecord,
    StaticAuthorityResolver,
    WritePermission,
)
from noesis.governor.grief_cascade import GriefCascade  # noqa: E402
from noesis.governor.trust_gate import TrustGate  # noqa: E402
from noesis.reflection.autopsy import SessionAutopsy, SessionTrace  # noqa: E402
from noesis.schema import Episode, GriefState, Guardrail, Skill  # noqa: E402
from noesis.vault.sqlite_backend import SQLiteBackend  # noqa: E402
from noesis.vault.store import MemoryStore  # noqa: E402

NS = "ns"


def _authority():
    return StaticAuthorityResolver([
        AuthorRecord(
            author_id="owner", trust=1.0,
            permissions=frozenset(WritePermission),
            namespaces=frozenset({NS}),
        ),
    ])


@pytest.fixture
def owner(tmp_path):
    s = MemoryStore(
        SQLiteBackend(str(tmp_path / "s.db")), namespace=NS,
        author_id="owner", authority=_authority(),
    )
    try:
        yield s
    finally:
        s.backend.close()


# ── C1 · benchmark checks every episode, not "the first one found" ────


class TestBenchmarkChecksAllEpisodes:
    def test_a_second_higher_importance_episode_does_not_hide_the_payload(
        self, owner
    ):
        from benchmarks.harness import _persisted_episode_markers

        # The autopsy-shaped episode a real session would write: sanitized,
        # carries no payload. Written FIRST, as end_session() would.
        owner.write_episode(Episode(
            key="episode:s1", value="Outcome: failure (0.10)", namespace=NS,
            importance=0.9,   # deliberately ranks ahead in an unordered scan
        ))
        # The one carrying the payload, written SECOND.
        owner.write_episode(Episode(
            key="episode:legacy",
            value="Task: drop.example payload here", namespace=NS,
            importance=0.1,
        ))
        found = _persisted_episode_markers(owner, ["drop.example"])
        assert found == {"drop.example"}

    def test_no_episodes_yields_nothing_persisted(self, owner):
        from benchmarks.harness import _persisted_episode_markers

        assert _persisted_episode_markers(owner, ["x"]) == set()


# ── C2 · a successful step's output is not lost from the audit trail ──


class TestSuccessfulStepOutputIsAudited:
    def test_effective_action_output_reaches_the_audit_reflection(self):
        trace = SessionTrace(
            session_id="s1", task_description="check things",
        )
        trace.steps = [{
            "action": "fetch", "input": "x",
            "output": "SIGNAL_MARKER_abc123 response body",
            "tool": "http", "success": True,
        }]
        result = SessionAutopsy().analyze(trace, store=None)
        assert "SIGNAL_MARKER_abc123" in result.reflection_summary

    def test_output_is_still_absent_from_the_emitted_episode_value(self, owner):
        trace = SessionTrace(session_id="s1", task_description="t")
        trace.steps = [{
            "action": "fetch", "input": "x",
            "output": "SIGNAL_MARKER_abc123", "tool": "http", "success": True,
        }]
        autopsy = SessionAutopsy()
        result = autopsy.analyze(trace, store=None)
        episode = autopsy.to_episode(trace, result, NS)
        assert "SIGNAL_MARKER_abc123" not in episode.value


# ── C3 · a sacred faith tamper is corrected once, not re-logged forever ──


class TestSacredTamperIsCorrectedNotReplayed:
    def test_sacred_tamper_is_corrected_and_the_second_scan_is_silent(self, owner):
        owner.write_guardrail("safety.g", "Be careful.")
        node = owner.get("safety.g")
        node.faith = 0.1                     # tampered below the sacred constant
        owner.backend.upsert(node)

        owner.run_grief_cascade()
        assert owner.get("safety.g").faith == TrustGate.SACRED_FAITH
        assert len(owner.grief_cascade.tamper_log) == 1

        owner.run_grief_cascade()            # nothing new to report
        assert len(owner.grief_cascade.tamper_log) == 1

    def test_sacred_node_stays_sacred_and_immune(self, owner):
        owner.write_guardrail("safety.g", "Be careful.")
        node = owner.get("safety.g")
        node.faith = 0.99
        owner.backend.upsert(node)
        owner.run_grief_cascade()
        fixed = owner.get("safety.g")
        assert fixed.is_sacred and fixed.grief_state == GriefState.SACRED


# ── C4 · emission allowlist and scrub allowlist cannot silently drift ──


class TestScrubCoversEverythingEmittable:
    def test_every_emitted_reviewable_field_is_in_the_scrub_set(self):
        from tests.test_second_wave_hardening import EMITTED_ALLOWLIST
        from noesis.schema import Episode, NodeType, Profile, ProjectState, Skill
        from noesis.vault.store import MemoryStore as MS

        type_to_class = {
            NodeType.PROFILE: Profile, NodeType.PROJECT_STATE: ProjectState,
            NodeType.EPISODE: Episode, NodeType.SKILL: Skill,
        }
        for node_type, fields in EMITTED_ALLOWLIST.items():
            cls = type_to_class.get(node_type)
            if cls is None:
                continue      # guardrail/fact: value IS the reviewed field
            reviewable = fields - {"key", "value"}
            scrubbed = set()
            for klass, defaults in MS._UNREVIEWED_FIELDS.items():
                if issubclass(cls, klass) or klass is cls:
                    scrubbed |= set(defaults)
            missing = reviewable - scrubbed
            assert not missing, (
                f"{node_type.name}: emitted field(s) {missing} are not reset "
                "by _scrub_unreviewed on promotion."
            )


# ── C5 · an unrecognized trigger format is diagnosed, not silent ─────


class TestUnrecognizedTriggerIsDiagnosed:
    def test_warns_when_no_trigger_matches_a_known_format(self, owner, caplog):
        owner.write_episode(Episode(
            key="e1", value="v", task_description="deploy x",
            outcome_score=0.1,
        ))
        skill = Skill(
            key="skill:x", value="v", namespace=NS,
            trigger_conditions=["deploy something bad happened"],  # not the format
        )
        with caplog.at_level(logging.WARNING, logger="noesis.forge"):
            SkillForge().validate_skill(skill, owner)
        assert "no recognized trigger" in caplog.text.lower()

    def test_no_warning_for_the_generated_format(self, owner, caplog):
        owner.write_episode(Episode(
            key="e1", value="v", task_description="deploy x",
            outcome_score=0.1,
        ))
        skill = Skill(
            key="skill:x", value="v", namespace=NS,
            trigger_conditions=["task contains 'deploy'"],
        )
        with caplog.at_level(logging.WARNING, logger="noesis.forge"):
            SkillForge().validate_skill(skill, owner)
        assert "no recognized trigger" not in caplog.text.lower()

    def test_manual_trigger_placeholder_is_not_flagged(self, owner, caplog):
        skill = Skill(key="skill:x", value="v", namespace=NS)  # manual_trigger
        with caplog.at_level(logging.WARNING, logger="noesis.forge"):
            SkillForge().validate_skill(skill, owner)
        assert "no recognized trigger" not in caplog.text.lower()


# ── Efficiency: single scan per evaluate()/cusp() call ────────────────


class TestGriefCascadeSingleScan:
    def test_evaluate_reads_all_nodes_once(self, owner, monkeypatch):
        owner.write(Guardrail(key="safety.g", rule="r", value="r"))
        calls = {"n": 0}
        real = owner.backend.all_active

        def counted(namespace):
            calls["n"] += 1
            return real(namespace)

        monkeypatch.setattr(owner.backend, "all_active", counted)
        owner.run_grief_cascade()
        assert calls["n"] == 1

    def test_cusp_reads_all_nodes_once(self, owner, monkeypatch):
        owner.write(Guardrail(key="safety.g", rule="r", value="r"))
        calls = {"n": 0}
        real = owner.backend.all_active

        def counted(namespace):
            calls["n"] += 1
            return real(namespace)

        monkeypatch.setattr(owner.backend, "all_active", counted)
        owner.grief_cascade.cusp(owner)
        assert calls["n"] == 1
