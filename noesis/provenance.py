"""Data-origin labels for the Noesis publication boundary.

Authority answers *who may perform an operation*. Provenance answers *where the
content came from*. Those are deliberately separate: a trusted agent process
can still be handling hostile user, tool, or model-generated text.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import time


class ProvenanceKind(str, Enum):
    """Origin classes accepted by the safe ingestion API."""

    USER_INPUT = "user_input"
    TOOL_OUTPUT = "tool_output"
    MODEL_DERIVED = "model_derived"
    EXTERNAL_SOURCE = "external_source"
    TRUSTED_OPERATOR = "trusted_operator"
    REVIEWED = "reviewed"


@dataclass(frozen=True)
class Provenance:
    """Server-attached origin record for one memory artifact."""

    kind: ProvenanceKind
    source_ref: str = ""
    observed_at: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ProvenanceKind):
            raise TypeError("kind must be a ProvenanceKind")
        if not isinstance(self.source_ref, str):
            raise TypeError("source_ref must be a string")
        if self.observed_at == 0.0:
            object.__setattr__(self, "observed_at", time.time())
        elif self.observed_at < 0.0:
            raise ValueError("observed_at must be non-negative")

