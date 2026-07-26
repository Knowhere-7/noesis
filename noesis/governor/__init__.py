"""
Noesis Governor — Swarm Governance for Memory
----------------------------------------------
Ported from Murmuration's biological rule engine.
Trust batteries, grief cascades, faith anchors, sacred ground protection.

This is the immune system. The piece nobody else has.
"""

from noesis.governor.trust_gate import TrustGate
from noesis.governor.grief_cascade import GriefCascade
from noesis.governor.authority import (
    AuthorRecord,
    AuthorityResolver,
    DenyAllAuthorityResolver,
    SQLiteAuthorityResolver,
    StaticAuthorityResolver,
    WritePermission,
)

__all__ = [
    "TrustGate",
    "GriefCascade",
    "AuthorRecord",
    "AuthorityResolver",
    "DenyAllAuthorityResolver",
    "SQLiteAuthorityResolver",
    "StaticAuthorityResolver",
    "WritePermission",
]
