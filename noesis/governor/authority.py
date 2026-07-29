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
import json
from pathlib import Path
import sqlite3
import time
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
    REVIEW_QUARANTINE = "review_quarantine"
    PUBLISH_MEMORY = "publish_memory"
    PROMOTE_CANDIDATE = "promote_candidate"
    # Registering a dependency edge is deliberately NOT part of WRITE_MEMORY.
    # Grief propagates from a node to its dependents, so an author who could
    # wire a trusted node as a dependent of their own could poison their node
    # and cascade grief into trusted memory. Linking is its own privilege.
    LINK_MEMORY = "link_memory"


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


class SQLiteAuthorityResolver(AuthorityResolver):
    """Persisted authority records with immediate revocation.

    The database and its provisioning methods are part of the trusted
    computing base. Host authentication selects ``author_id``; memory payloads
    must never be allowed to call ``provision`` or ``revoke``.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS noesis_authorities (
                author_id TEXT PRIMARY KEY,
                trust REAL NOT NULL CHECK (trust >= 0.0 AND trust <= 1.0),
                permissions_json TEXT NOT NULL,
                namespaces_json TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                updated_at REAL NOT NULL
            )
            """
        )
        self._conn.commit()

    def resolve(
        self,
        author_id: str,
        namespace: str,
    ) -> Optional[AuthorRecord]:
        row = self._conn.execute(
            """
            SELECT author_id, trust, permissions_json, namespaces_json, active
            FROM noesis_authorities
            WHERE author_id = ?
            """,
            (author_id,),
        ).fetchone()
        if row is None or row["active"] != 1:
            return None

        try:
            permission_values = json.loads(row["permissions_json"])
            namespace_values = json.loads(row["namespaces_json"])
            if not isinstance(permission_values, list):
                return None
            if not isinstance(namespace_values, list):
                return None
            permissions = frozenset(
                WritePermission(value) for value in permission_values
            )
            namespaces = frozenset(
                value for value in namespace_values
                if isinstance(value, str) and value
            )
            if len(namespaces) != len(namespace_values):
                return None
            record = AuthorRecord(
                author_id=row["author_id"],
                trust=float(row["trust"]),
                permissions=permissions,
                namespaces=namespaces,
                active=True,
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            # Corrupt or unknown authority data is denial, never elevation.
            return None

        if "*" not in record.namespaces and namespace not in record.namespaces:
            return None
        return record

    def provision(self, record: AuthorRecord) -> None:
        """Create or replace a server-controlled authority record."""
        permissions = sorted(permission.value for permission in record.permissions)
        namespaces = sorted(record.namespaces)
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO noesis_authorities
                    (author_id, trust, permissions_json, namespaces_json,
                     active, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(author_id) DO UPDATE SET
                    trust = excluded.trust,
                    permissions_json = excluded.permissions_json,
                    namespaces_json = excluded.namespaces_json,
                    active = excluded.active,
                    updated_at = excluded.updated_at
                """,
                (
                    record.author_id,
                    record.trust,
                    json.dumps(permissions),
                    json.dumps(namespaces),
                    int(record.active),
                    time.time(),
                ),
            )

    def revoke(self, author_id: str) -> bool:
        """Deactivate an identity. The next resolve observes the revocation."""
        with self._conn:
            cursor = self._conn.execute(
                """
                UPDATE noesis_authorities
                SET active = 0, updated_at = ?
                WHERE author_id = ?
                """,
                (time.time(), author_id),
            )
        return cursor.rowcount == 1

    def close(self) -> None:
        self._conn.close()
