"""Upgrade contracts for databases created before retrieval quarantine."""

import json
import sqlite3
import time

from noesis.schema import Fact, RetrievalState
from noesis.vault.sqlite_backend import SQLiteBackend


def test_existing_database_gains_retrieval_state_without_data_loss(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE memory_nodes (
            id TEXT PRIMARY KEY,
            key TEXT NOT NULL,
            namespace TEXT NOT NULL DEFAULT 'default',
            node_type TEXT NOT NULL,
            grief_state TEXT NOT NULL DEFAULT 'ACTIVE',
            is_sacred INTEGER NOT NULL DEFAULT 0,
            trust_charge REAL NOT NULL DEFAULT 0.5,
            grief REAL NOT NULL DEFAULT 0.0,
            faith REAL NOT NULL DEFAULT 0.1,
            importance REAL NOT NULL DEFAULT 0.5,
            created_at REAL NOT NULL,
            last_accessed REAL NOT NULL,
            access_count INTEGER NOT NULL DEFAULT 0,
            value TEXT NOT NULL DEFAULT '',
            data_json TEXT NOT NULL DEFAULT '{}',
            UNIQUE(key, namespace)
        )
        """
    )
    now = time.time()
    conn.execute(
        """
        INSERT INTO memory_nodes
            (id, key, namespace, node_type, grief_state, is_sacred,
             trust_charge, grief, faith, importance, created_at,
             last_accessed, access_count, value, data_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "old-quarantine",
            "notes.old",
            "n",
            "SEMANTIC_FACT",
            "ACTIVE",
            0,
            0.5,
            0.0,
            0.1,
            0.7,
            now,
            now,
            0,
            "old quarantined payload",
            json.dumps(
                {
                    "retrieval_state": "QUARANTINED",
                    "quarantine_reason": "transitional record",
                }
            ),
        ),
    )
    conn.commit()
    conn.close()

    backend = SQLiteBackend(str(path))
    try:
        columns = {
            row["name"]
            for row in backend.conn.execute(
                "PRAGMA table_info(memory_nodes)"
            ).fetchall()
        }
        assert "retrieval_state" in columns
        old = backend.get_by_key("notes.old", "n")
        assert old is not None
        assert old.retrieval_state == RetrievalState.QUARANTINED
        assert backend.search("payload", "n") == []

        backend.upsert(
            Fact(key="existing-compatible", value="survives", namespace="n")
        )
        stored = backend.get_by_key("existing-compatible", "n")
        assert stored is not None
        assert stored.retrieval_state == RetrievalState.ACTIVE
    finally:
        backend.close()
