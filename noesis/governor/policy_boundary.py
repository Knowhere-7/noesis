"""Deterministic policy-scope enforcement for persistent memory.

Noesis does not pretend a regex can determine arbitrary semantic truth.
Instead, a privileged guardrail installer declares concrete key prefixes and
terms that belong to the policy's authority domain. Normal memory cannot write
inside those namespaces. Authority-shaped claims that touch protected terms
are retained for audit but quarantined from provider context.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import math
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
    def is_substantive_restatement(left: str, right: str) -> bool:
        """Require more than punctuation, format characters, or token swapping.

        This is deliberately a textual friction control, not semantic proof.
        Human review remains the authority boundary. The test prevents an
        inattentive reviewer or automation from promoting a crafted artifact by
        adding one period, one zero-width character, or another cosmetic edit.
        """
        if not isinstance(left, str) or not isinstance(right, str):
            return False
        left_text = PolicyBoundary._restatement_text(left)
        right_text = PolicyBoundary._restatement_text(right)
        if not left_text or not right_text or left_text == right_text:
            return False

        left_tokens = left_text.split()
        right_tokens = right_text.split()
        changed_tokens = len(set(left_tokens).symmetric_difference(right_tokens))
        required_changes = max(2, math.ceil(max(len(left_tokens), 1) * 0.3))
        similarity = SequenceMatcher(None, left_text, right_text).ratio()
        return changed_tokens >= required_changes or similarity <= 0.85

    @staticmethod
    def _restatement_text(value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value).casefold()
        # Format controls and punctuation must not manufacture a rewrite.
        normalized = "".join(
            " " if unicodedata.category(char)[0] in {"C", "P", "S"} else char
            for char in normalized
        )
        return re.sub(r"\s+", " ", normalized).strip()

    @staticmethod
    def _normalize(value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value).casefold()
        return re.sub(r"\s+", " ", normalized).strip()
