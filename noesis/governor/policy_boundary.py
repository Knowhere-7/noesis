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
        compact_value = PolicyBoundary._compact(value)

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
                if PolicyBoundary._term_matches(term, value, compact_value)
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
        because "obey payload" with a hidden separator between the words has no
        equal canonical form, yet is plainly the same artifact.

        This defeats *cosmetic* edits only. It cannot prove a semantic rewrite:
        a reviewer who swaps a synonym still passes, and a reviewer is trusted
        computing base regardless (NOE-L-014).
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

    # Characters that render as nothing (or as blank space) but are not caught
    # by the Cf/Cc/Mn categories: Hangul/Halfwidth fillers, Braille blank, and
    # the Mongolian vowel separator.
    _BLANKS = frozenset(chr(c) for c in (
        0x115F, 0x1160, 0x3164, 0xFFA0, 0x2800, 0x180E, 0x034F,
    ))

    # Common Latin look-alikes from Cyrillic and Greek, applied AFTER casefold.
    # Deliberately small and conservative: this is a cheap, deterministic fold
    # for the substitutions attackers actually reach for first, not a full
    # confusables skeleton (NOE-L-014).
    _CONFUSABLES = {
        ord(k): v for k, v in {
            "а": "a", "е": "e", "о": "o", "р": "p",
            "с": "c", "х": "x", "у": "y", "і": "i",
            "ј": "j", "ѕ": "s", "һ": "h", "ԁ": "d",
            "ԛ": "q", "ԝ": "w", "ɡ": "g",
            "ο": "o", "ν": "v", "α": "a", "ε": "e",
            "ι": "i", "κ": "k", "ρ": "p", "τ": "t",
            "υ": "u", "χ": "x",
        }.items()
    }

    @staticmethod
    def _fold(value: str) -> str:
        """Fold what a reader cannot tell apart, so a substring match can.

        NFKD, then drop combining marks (accents, variation selectors),
        format and control characters (zero-width, soft hyphen, bidi, BOM) and
        blank fillers; casefold; map common Cyrillic/Greek look-alikes.
        Whitespace is preserved for the caller to collapse.
        """
        decomposed = unicodedata.normalize("NFKD", value)
        kept = "".join(
            ch for ch in decomposed
            if ch.isspace() or (
                ch not in PolicyBoundary._BLANKS
                and unicodedata.category(ch) not in ("Mn", "Me", "Cf", "Cc")
            )
        )
        return kept.casefold().translate(PolicyBoundary._CONFUSABLES)

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", PolicyBoundary._fold(value)).strip()

    @staticmethod
    def _compact(normalized: str) -> str:
        """Letters and digits only: defeats spacing and punctuation splits."""
        return re.sub(r"[\W_]+", "", normalized)

    @staticmethod
    def _term_matches(term: str, value: str, compact_value: str) -> bool:
        """Does a protected term appear, however it was spaced or dressed?

        Compact matching (all separators removed) is applied only to terms of
        six or more characters: short terms would match inside unrelated words.
        It can only ever turn an ALLOW into a QUARANTINE, and only when an
        authority-shaped claim is also present, so a false hit costs a review.
        """
        normalized = PolicyBoundary._normalize(term)
        if not normalized:
            return False
        if normalized in value:
            return True
        compact_term = PolicyBoundary._compact(normalized)
        return len(compact_term) >= 6 and compact_term in compact_value

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
