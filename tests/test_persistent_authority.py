"""Contracts for the persisted, revocable authority boundary."""

from noesis.governor.authority import (
    AuthorRecord,
    SQLiteAuthorityResolver,
    WritePermission,
)
from noesis.schema import Fact
from noesis.vault.sqlite_backend import SQLiteBackend
from noesis.vault.store import MemoryStore


def _record(*, active: bool = True) -> AuthorRecord:
    return AuthorRecord(
        author_id="agent-1",
        trust=0.8,
        permissions=frozenset({WritePermission.WRITE_MEMORY}),
        namespaces=frozenset({"tenant-a"}),
        active=active,
    )


def test_sqlite_authority_survives_restart_and_is_namespace_scoped(tmp_path):
    path = tmp_path / "authority.db"
    resolver = SQLiteAuthorityResolver(path)
    resolver.provision(_record())
    resolver.close()

    reopened = SQLiteAuthorityResolver(path)
    try:
        record = reopened.resolve("agent-1", "tenant-a")
        assert record == _record()
        assert reopened.resolve("agent-1", "tenant-b") is None
    finally:
        reopened.close()


def test_revocation_applies_to_the_next_write_and_survives_restart(tmp_path):
    authority_path = tmp_path / "authority.db"
    memory_path = tmp_path / "memory.db"
    resolver = SQLiteAuthorityResolver(authority_path)
    resolver.provision(_record())
    store = MemoryStore(
        SQLiteBackend(str(memory_path)),
        namespace="tenant-a",
        author_id="agent-1",
        authority=resolver,
    )

    try:
        allowed, _ = store.write(Fact(key="before", value="authorized"))
        assert allowed is True

        assert resolver.revoke("agent-1") is True
        allowed, reason = store.write(Fact(key="after", value="revoked"))
        assert allowed is False
        assert "no active authority" in reason
    finally:
        store.backend.close()
        resolver.close()

    reopened = SQLiteAuthorityResolver(authority_path)
    try:
        assert reopened.resolve("agent-1", "tenant-a") is None
    finally:
        reopened.close()


def test_malformed_persisted_permission_fails_closed(tmp_path):
    path = tmp_path / "authority.db"
    resolver = SQLiteAuthorityResolver(path)
    resolver.provision(_record())
    resolver._conn.execute(
        "UPDATE noesis_authorities SET permissions_json = ? WHERE author_id = ?",
        ('["write_memory", "invented_superuser_permission"]', "agent-1"),
    )
    resolver._conn.commit()

    try:
        assert resolver.resolve("agent-1", "tenant-a") is None
    finally:
        resolver.close()


def test_non_boolean_active_flag_fails_closed(tmp_path):
    path = tmp_path / "authority.db"
    resolver = SQLiteAuthorityResolver(path)
    resolver.provision(_record())
    resolver._conn.execute(
        "UPDATE noesis_authorities SET active = 2 WHERE author_id = ?",
        ("agent-1",),
    )
    resolver._conn.commit()

    try:
        assert resolver.resolve("agent-1", "tenant-a") is None
    finally:
        resolver.close()
