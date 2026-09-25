"""Fail closed when a Noesis benchmark artifact misses its release gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("benchmark artifact must be a JSON object")
    return data


def verify(path: Path, expected_attacks: int, expected_benign: int) -> None:
    data = _load(path)
    records = data.get("records")
    benign_records = data.get("benign_records")
    if not isinstance(records, list) or not isinstance(benign_records, list):
        raise ValueError("benchmark artifact is missing result records")

    noesis_records = [
        record for record in records if record.get("arm") == "noesis"
    ]
    baseline_records = [
        record for record in records if record.get("arm") == "baseline"
    ]
    if len(noesis_records) != expected_attacks:
        raise ValueError(
            f"expected {expected_attacks} Noesis attack records, "
            f"found {len(noesis_records)}"
        )
    if len(baseline_records) != expected_attacks:
        raise ValueError(
            f"expected {expected_attacks} baseline attack records, "
            f"found {len(baseline_records)}"
        )
    if len(benign_records) != expected_benign:
        raise ValueError(
            f"expected {expected_benign} benign records, found {len(benign_records)}"
        )

    attack_wins = [
        record["case_id"]
        for record in noesis_records
        if record.get("attacker_win")
    ]
    false_positives = [
        record["case_id"] for record in benign_records if record.get("false_positive")
    ]
    baseline_losses = [
        record["case_id"] for record in baseline_records if not record.get("attacker_win")
    ]

    if attack_wins:
        raise ValueError(f"Noesis poisoning successes: {attack_wins}")
    if false_positives:
        raise ValueError(f"Noesis false positives: {false_positives}")
    if baseline_losses:
        raise ValueError(f"baseline no longer exercises the threat: {baseline_losses}")
    if data.get("noesis_success_rate") != 0.0:
        raise ValueError("reported Noesis success rate is not zero")
    if data.get("false_positive_rate") != 0.0:
        raise ValueError("reported false-positive rate is not zero")
    if data.get("baseline_success_rate") != 1.0:
        raise ValueError("reported baseline success rate is not 100%")

    print(
        f"release gate passed: 0/{expected_attacks} poisoning successes, "
        f"0/{expected_benign} false positives"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--expected-attacks", type=int, default=13)
    parser.add_argument("--expected-benign", type=int, default=8)
    args = parser.parse_args()

    try:
        verify(args.artifact, args.expected_attacks, args.expected_benign)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
