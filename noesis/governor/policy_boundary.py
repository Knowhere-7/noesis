"""Deterministic policy-scope enforcement for persistent memory.

Noesis does not pretend a regex can determine arbitrary semantic truth.
Instead, a privileged guardrail installer declares concrete key prefixes and
terms that belong to the policy's authority domain. Normal memory cannot write
inside those namespaces. Authority-shaped claims that touch protected terms
are retained for audit but quarantined from provider context.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable
import unicodedata

from noesis.schema import Guardrail, MemoryNode


_AUTHORITY_CLAIM_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE | re.DOTALL)
    for pattern in (
        r"\b(?:updated|revised|replacement|new|later)\s+"
        r"(?:policy|rule|directive|instruction)\b",
        r"\b(?:policy|rule|guardrail|directive|instruction|restriction)\b"
        r".{0,100}\b(?:deprecated|obsolete|suspended|revoked|overridden|"
        r"replaced|superseded|no longer applies)\b",
        r"\b(?:ignore|disregard|bypass|override|supersede|suspend|cancel)\b"
        r".{0,100}\b(?:rule|policy|guardrail|instruction|constraint|"
        r"restriction)\b",
        r"\b(?:authoriz(?:e|es|ed|ing)|permit(?:s|ted|ting)?|"
        r"allow(?:s|ed|ing)?)\b.{0,100}\b"
        r"(?:send|sending|sent|transmit|transmitting|exfiltrate|upload|"
        r"disclose|share)\b",
        r"\b(?:send|sending|sent|transmit|transmitting|exfiltrate|upload|"
        r"disclose|share)\b.{0,100}\b(?:allowed|authorized|permitted)\b",
        r"\b(?:may|can)\s+(?:be\s+)?"
        r"(?:send|sent|transmit|transmitted|exfiltrate|upload|disclose|share)\b",
        r"(?:\[system\]|<system\b|system\s*:)",
    )
)


@dataclass(frozen=True)
class PolicyDecision:
    action: str
    reason: str = ""


class PolicyBoundary:
    """Evaluate normal memory against installed machine policy scopes."""

    @staticmethod
    def evaluate(
        node: MemoryNode,
        guardrails: Iterable[Guardrail],
    ) -> PolicyDecision:
        key = PolicyBoundary._normalize(node.key)
        value = PolicyBoundary._normalize(node.value)

        for guardrail in guardrails:
            for prefix in guardrail.protected_key_prefixes:
                normalized = PolicyBoundary._normalize(prefix)
                if normalized and key.startswith(normalized):
                    return PolicyDecision(
                        "reject",
                        f"Key '{node.key}' is inside protected authority "
                        f"namespace '{prefix}' declared by '{guardrail.key}'.",
                    )

            matched_terms = [
                term for term in guardrail.protected_terms
                if (
                    PolicyBoundary._normalize(term)
                    and PolicyBoundary._normalize(term) in value
                )
            ]
            if not matched_terms:
                continue
            if any(
                pattern.search(value)
                for pattern in _AUTHORITY_CLAIM_PATTERNS
            ):
                shown = ", ".join(sorted(set(matched_terms))[:3])
                return PolicyDecision(
                    "quarantine",
                    f"Authority-shaped claim touched protected terms "
                    f"({shown}) for guardrail '{guardrail.key}'.",
                )

        return PolicyDecision("allow")

    @staticmethod
    def is_same_text(left: str, right: str) -> bool:
        """Are two strings the same once trivial variation is removed?

        Used by candidate promotion (NOE-F-026) so that adding whitespace,
        flipping case, or substituting compatibility Unicode does not count as
        a reviewer having restated the evidence.
        """
        if not isinstance(left, str) or not isinstance(right, str):
            return False
        return PolicyBoundary._normalize(left) == PolicyBoundary._normalize(right)

    @staticmethod
    def _normalize(value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value).casefold()
        return re.sub(r"\s+", " ", normalized).strip()
