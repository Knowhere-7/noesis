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

    # Above this canonical-form similarity, an "approved" text is treated as the
    # collector's bytes with cosmetic edits, not a reviewer's restatement.
    RESTATEMENT_SIMILARITY = 0.9
    # SequenceMatcher is quadratic; beyond this, only canonical equality counts.
    _SIMILARITY_MAX_CHARS = 4000

    @staticmethod
    def is_same_text(left: str, right: str) -> bool:
        """Is `right` the same text as `left` once cosmetic variation is removed?

        Used by candidate promotion (NOE-F-026) so that a reviewer must
        actually restate the evidence. Cosmetic variation is not a restatement:
        whitespace, case, compatibility Unicode, zero-width / format characters,
        and punctuation. The canonical forms are also compared by similarity,
        because "obey payload" -> "obey​payload" has no equal canonical
        form once a separator is hidden, yet is plainly the same artifact.

        This defeats *cosmetic* edits only. It cannot prove a semantic rewrite:
        a reviewer who swaps a synonym or a homoglyph still passes, and a
        reviewer is trusted computing base regardless (NOE-L-014).
        """
        if not isinstance(left, str) or not isinstance(right, str):
            return False
        a = PolicyBoundary._canonical(left)
        b = PolicyBoundary._canonical(right)
        if a == b:
            return True
        if max(len(a), len(b)) > PolicyBoundary._SIMILARITY_MAX_CHARS:
            return False
        return (
            SequenceMatcher(None, a, b, autojunk=False).ratio()
            >= PolicyBoundary.RESTATEMENT_SIMILARITY
        )

    @staticmethod
    def _strip_invisible(value: str) -> str:
        """Drop format (Cf) and control (Cc) characters except whitespace.

        Zero-width space/joiner, soft hyphen, BOM, bidi controls: none change
        what a reader sees, all change what a substring match sees.
        """
        return "".join(
            ch for ch in value
            if ch.isspace() or unicodedata.category(ch) not in ("Cf", "Cc")
        )

    @staticmethod
    def _normalize(value: str) -> str:
        normalized = PolicyBoundary._strip_invisible(
            unicodedata.normalize("NFKC", value)
        ).casefold()
        return re.sub(r"\s+", " ", normalized).strip()

    @staticmethod
    def _canonical(value: str) -> str:
        """`_normalize` plus punctuation/symbols removed, for restatement only.

        Deliberately separate from `_normalize`: protected prefixes such as
        "safety." depend on punctuation surviving.
        """
        normalized = PolicyBoundary._normalize(value)
        stripped = "".join(
            " " if unicodedata.category(ch)[0] in ("P", "S") else ch
            for ch in normalized
        )
        return re.sub(r"\s+", " ", stripped).strip()
