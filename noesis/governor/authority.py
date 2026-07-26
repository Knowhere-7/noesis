"""Out-of-band write authority for the Noesis memory boundary.

Memory payloads are untrusted data. They must never choose their own trust,
namespace, sacred status, or write privileges. A host application binds an
authenticated author ID to a MemoryStore and supplies a resolver whose
records come from outside the write payload.

The resolver is part of the trusted computing base. In a service deployment,
it should be backed by the application's authenticated identity store. The
static resolver here is for tests and explicitly trusted local applications;
request data must never be used to construct it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional


class WritePermission(str, Enum):
    """Capabilities resolved for an authenticated author."""

    WRITE_MEMORY = "write_memory"
    WRITE_EPISODE = "write_episode"
    WRITE_PROFILE = "write_profile"
    WRITE_PROJECT_STATE = "write_project_state"
    WRITE_SKILL = "write_skill"
    INSTALL_GUARDRAIL = "install_guardrail"
    CORRECT_TRUSTED_FACT = "correct_trusted_fact"
    BYPASS_WRITE_BUDGET = "bypass_write_budget"


@dataclass(frozen=True)
class AuthorRecord:
    """Server-controlled authority record for one author."""

    author_id: str
    trust: float
    permissions: frozenset[WritePermission]
    namespaces: frozenset[str]
    active: bool = True

    def __post_init__(self) -> None:
        if not self.author_id:
            raise ValueError("author_id must not be empty")
        if not 0.0 <= self.trust <= 1.0:
            raise ValueError("author trust must be between 0.0 and 1.0")

    def permits(
        self,
        permission: WritePermission,
        namespace: str,
    ) -> bool:
        return (
            self.active
            and permission in self.permissions
            and ("*" in self.namespaces or namespace in self.namespaces)
        )


class AuthorityResolver(ABC):
    """Resolve an authenticated author ID to current server-side authority."""

    @abstractmethod
    def resolve(
        self,
        author_id: str,
        namespace: str,
    ) -> Optional[AuthorRecord]:
        """Return current authority, or None for an unauthorized author."""


class DenyAllAuthorityResolver(AuthorityResolver):
    """Fail-closed resolver used when no authority source is configured."""

    def resolve(
        self,
        author_id: str,
        namespace: str,
    ) -> Optional[AuthorRecord]:
        return None


class StaticAuthorityResolver(AuthorityResolver):
    """Explicit records for tests and trusted local applications.

    This is not an authentication mechanism. A network service must replace
    it with a resolver backed by the service's authenticated identity store.
    """

    def __init__(self, records: Iterable[AuthorRecord] = ()):
        self._records = {record.author_id: record for record in records}

    def resolve(
        self,
        author_id: str,
        namespace: str,
    ) -> Optional[AuthorRecord]:
        record = self._records.get(author_id)
        if record is None:
            return None
        if "*" not in record.namespaces and namespace not in record.namespaces:
            return None
        return record

    def replace(self, record: AuthorRecord) -> None:
        """Replace an authority record so changes apply on the next write."""
        self._records[record.author_id] = record

    @classmethod
    def local_owner(
        cls,
        namespace: str,
        author_id: str = "local-owner",
    ) -> "StaticAuthorityResolver":
        """Create explicit owner authority for a local single-user process."""
        return cls(
            [
                AuthorRecord(
                    author_id=author_id,
                    trust=1.0,
                    permissions=frozenset(WritePermission),
                    namespaces=frozenset({namespace}),
                )
            ]
        )
