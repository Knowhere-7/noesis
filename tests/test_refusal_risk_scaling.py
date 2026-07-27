"""
Refusal must actually consider what is at stake — NOE-F-027.

Two defects, both reproduced on master @ 4513c9c before this fix:

1. `score_context()` set `action_risk = 1.0 - trust`, so action_risk was not an
   independent signal at all — it was a relabeling of trust. That made the
   `should_refuse` conjunction collapse:

       action_risk > 0.7  <=>  trust < 0.3
       (trust < 0.3) AND (trust < 0.15)  ==  trust < 0.15

   The risk clause could never decide anything. It was mathematically dead.
   It also double-counted trust inside `composite_health` (trust at weight
   0.15, plus `1 - action_risk` at another 0.15).

2. When a host DID supply real independent risk through a configured output
   evaluator ("this action deletes production data", action_risk=0.99), the
   conjunction discarded it: refusal required memory trust to ALSO be nearly
   zero. A correctly-reported catastrophic action with merely-poor memory
   (trust=0.20) was not refused.

The contract these tests define:

- Core scoring does not invent a risk number it cannot measure. Noesis knows
  memory health; it does not know action consequences. This mirrors the
  existing doctrine that `score_output()` refuses to judge output without a
  host-supplied deterministic evaluator.
- Stakes scale the evidence bar. High risk does not mean "always refuse" (that
  is a wall, and it would block every dangerous-but-correct action). It means
  "demand proportionally more earned trust before acting."
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from noesis.governor.trust_gate import TrustGate  # noqa: E402
from noesis.schema import (  # noqa: E402
    DriftScore,
    Fact,
    Profile,
    ProjectState,
)


class TestCoreDoesNotFabricateRisk:
    """Noesis must not manufacture a stakes signal it has no way to observe."""

    def test_core_scoring_does_not_derive_risk_from_trust(self):
        gate = TrustGate()
        nodes = [
            Profile(key="p", role="engineer"),
            ProjectState(key="proj", objectives=["build"]),
            Fact(key="f1", value="Python is typed"),
        ]
        score = gate.score_context(nodes)
        assert score.action_risk != 1.0 - score.trust or score.action_risk == 0.0, (
            "action_risk must not be a relabeling of trust"
        )
        assert score.action_risk == 0.0, (
            "core context scoring cannot know action consequences; unassessed "
            "risk must be 0.0, not fabricated from trust"
        )

    def test_composite_health_does_not_double_count_trust(self):
        """With risk unassessed, health must not be penalised twice for trust."""
        low = DriftScore(trust=0.2, action_risk=0.0)
        high = DriftScore(trust=0.9, action_risk=0.0)
        assert high.composite_health > low.composite_health


class TestStakesScaleTheEvidenceBar:
    """The real defect: supplied risk must change the refusal decision."""

    def test_catastrophic_action_with_moderate_memory_is_refused(self):
        """THE BUG. Host reports maximum danger; memory is only moderate."""
        ds = DriftScore(action_risk=0.99, trust=0.5)
        assert ds.should_refuse is True, (
            "a catastrophic action must not proceed on merely-moderate memory"
        )

    def test_catastrophic_action_with_poor_memory_is_refused(self):
        ds = DriftScore(action_risk=0.99, trust=0.2)
        assert ds.should_refuse is True

    def test_catastrophic_action_with_well_grounded_memory_is_allowed(self):
        """NOT a wall. High risk with well-earned trust may proceed."""
        ds = DriftScore(action_risk=0.99, trust=0.95)
        assert ds.should_refuse is False, (
            "risk must raise the bar, not become an unconditional refusal"
        )

    def test_required_trust_rises_monotonically_with_risk(self):
        bars = [DriftScore(action_risk=r).required_trust
                for r in (0.0, 0.25, 0.5, 0.75, 1.0)]
        assert bars == sorted(bars)
        assert bars[0] < bars[-1]


class TestNoRegressionAtTheBaseline:
    """Unassessed risk must behave exactly as the shipped code did."""

    def test_baseline_threshold_is_unchanged_when_risk_is_unassessed(self):
        assert DriftScore(action_risk=0.0, trust=0.14).should_refuse is True
        assert DriftScore(action_risk=0.0, trust=0.16).should_refuse is False

    def test_existing_shipped_contract_still_holds(self):
        """From tests/test_core.py::test_drift_score_thresholds."""
        assert DriftScore(action_risk=0.9, trust=0.1).should_refuse is True

    def test_healthy_context_is_not_refused(self):
        gate = TrustGate()
        nodes = [
            Profile(key="p", role="engineer"),
            ProjectState(key="proj", objectives=["build"]),
            Fact(key="f1", value="grounded fact"),
        ]
        assert gate.score_context(nodes).should_refuse is False
