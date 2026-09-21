"""The agent-path benchmark must be able to see the attack it claims to contain.

R1 (second-party review, 2026-09-19): memory_poisoning_v1 gave the attacker a
low-privilege collector, so it proved authorization works but could not show
whether a PRIVILEGED agent steered by untrusted input publishes poison. The
agent-path corpus replays that route. A containment result is only evidence if
the negative control — the pre-fix behaviour — actually loses.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "benchmarks")
)

import pytest  # noqa: E402

from benchmarks.harness import run_agent_path_case  # noqa: E402

CORPUS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "benchmarks", "corpus", "agent_path_v1.json",
)


@pytest.fixture(scope="module")
def cases():
    with open(CORPUS, "r", encoding="utf-8") as fh:
        return json.load(fh)["cases"]


def test_default_learn_fact_contains_every_agent_path_case(cases, tmp_path):
    wins = [
        case["id"] for case in cases
        if run_agent_path_case(case, publish=False, tmpdir=str(tmp_path)).attacker_win
    ]
    assert wins == []


def test_negative_control_shows_the_attack_is_real(cases, tmp_path):
    """publish=True is the pre-fix behaviour. It must lose, or nothing above
    is evidence."""
    wins = [
        case["id"] for case in cases
        if run_agent_path_case(case, publish=True, tmpdir=str(tmp_path)).attacker_win
    ]
    assert {"AP-01", "AP-02", "AP-04"} <= set(wins)


def test_policy_boundary_still_contains_authority_claims_on_publish_path(
    cases, tmp_path
):
    """AP-03 / AP-05 are contained by policy even when the agent publishes —
    a second, independent layer, and the zero-width case (AP-05) was a hole."""
    for case in cases:
        if case["id"] in ("AP-03", "AP-05"):
            result = run_agent_path_case(
                case, publish=True, tmpdir=str(tmp_path)
            )
            assert result.attacker_win is False, case["id"]
            assert result.quarantined is True, case["id"]
