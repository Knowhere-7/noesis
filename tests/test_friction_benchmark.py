"""Truth contracts for the friction benchmark reporter."""

from benchmarks.friction import MAX_TURNS, run_crescendo


def test_uncompromised_arm_executes_the_claimed_turn_window(tmp_path):
    result = run_crescendo("noesis", str(tmp_path))

    assert result.succeeded is False
    assert result.turns_used == MAX_TURNS


def test_baseline_reports_actual_compromise_turn(tmp_path):
    result = run_crescendo("baseline", str(tmp_path))

    assert result.succeeded is True
    assert result.turns_used < MAX_TURNS
