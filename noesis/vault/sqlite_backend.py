"""
SQLite Backend — Local-first memory storage.

Zero dependencies beyond Python stdlib. Ships with the package.
Stores all memory nodes as JSON in SQLite with full-text search.
No pgvector needed for v1 — keyword + importance ranking is enough
to prove the architecture.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from noesis.schema import (
    Episode,
    Evaluation,
    Fact,
    GriefState,
    Guardrail,
    MemoryNode,
    NodeType,
    Profile,
    ProjectState,
    Skill,
    SkillStatus,
)
from noesis.vault.store import StorageBackend


# Type registry for deserialization
_TYPE_MAP = {
    NodeType.SYSTEM_GUARDRAIL: Guardrail,
    NodeType.PROFILE: Profile,
    NodeType.PROJECT_STATE: ProjectState,
    NodeType.SEMANTIC_FACT: Fact,
    NodeType.EPISODE: Episode,
    NodeType.SKILL: Skill,
    NodeType.EPHEMERAL: MemoryNode,
}


class SQLiteBackend(StorageBackend):
    """SQLite storage backend with JSON serialization.

    Each node is stored as a row with indexed columns for fast
    filtering (namespace, node_type, grief_state, key) plus a
    JSON blob for the full state.
    """

    def __init__(self, db_path: str = "noesis.db"):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._ensure_schema()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def _ensure_schema(self):
        """Create tables if they don't exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS memory_nodes (
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
            );

            CREATE INDEX IF NOT EXISTS idx_ns_type
                ON memory_nodes(namespace, node_type);
            CREATE INDEX IF NOT EXISTS idx_ns_grief
                ON memory_nodes(namespace, grief_state);
            CREATE INDEX IF NOT EXISTS idx_ns_importance
                ON memory_nodes(namespace, importance DESC);
            CREATE INDEX IF NOT EXISTS idx_key_ns
                ON memory_nodes(key, namespace);

            -- Full-text search index for keyword retrieval
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                key, value, node_id UNINDEXED,
                content='memory_nodes',
                content_rowid='rowid'
            );

            -- Cascade audit log (collective memory of purged nodes)
            CREATE TABLE IF NOT EXISTS cascade_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL,
                node_key TEXT NOT NULL,
                node_type TEXT NOT NULL,
                trust_at_purge REAL,
                grief_at_purge REAL,
                faith_at_purge REAL,
                purged_at REAL NOT NULL,
                data_json TEXT NOT NULL DEFAULT '{}'
            );
        """)
        self.conn.commit()

    # ── Serialization ──────────────────────────────────────────────────

    def _serialize(self, node: MemoryNode) -> Dict[str, Any]:
        """Convert a MemoryNode to a flat dict for storage."""
        data = {}
        # Capture all dataclass fields beyond the base columns
        for attr in vars(node):
            if attr.startswith("_"):
                continue
            val = getattr(node, attr)
            if isinstance(val, (set, frozenset)):
                data[attr] = list(val)
            elif isinstance(val, (NodeType, GriefState, SkillStatus)):
                data[attr] = val.name
            else:
                data[attr] = val
        return data

    def _deserialize(self, row: sqlite3.Row) -> MemoryNode:
        """Reconstruct a MemoryNode from a database row."""
        data = json.loads(row["data_json"])
        node_type = NodeType[row["node_type"]]
        cls = _TYPE_MAP.get(node_type, MemoryNode)

        node = cls.__new__(cls)
        # Set base fields from indexed columns
        node.id = row["id"]
        node.key = row["key"]
        node.namespace = row["namespace"]
        node.node_type = node_type
        node.grief_state = GriefState[row["grief_state"]]
        node.is_sacred = bool(row["is_sacred"])
        node.trust_charge = row["trust_charge"]
        node.grief = row["grief"]
        node.faith = row["faith"]
        node.importance = row["importance"]
        node.created_at = row["created_at"]
        node.last_accessed = row["last_accessed"]
        node.access_count = row["access_count"]
        node.value = row["value"]

        # Restore additional fields from JSON
        node.metadata = data.get("metadata", {})
        node.embedding = data.get("embedding")
        node.dependencies = set(data.get("dependencies", []))
        node.dependents = set(data.get("dependents", []))

        # Restore type-specific fields
        if isinstance(node, Profile):
            node.role = data.get("role", "")
            node.constraints = data.get("constraints", [])
            node.preferences = data.get("preferences", {})
        elif isinstance(node, Fact):
            node.source_episode_id = data.get("source_episode_id")
            node.confirmed = data.get("confirmed", False)
            node.contradiction_count = data.get("contradiction_count", 0)
            node.confirmation_count = data.get("confirmation_count", 0)
        elif isinstance(node, Episode):
            node.session_id = data.get("session_id", "")
            node.task_description = data.get("task_description", "")
            node.approach = data.get("approach", "")
            node.outcome = data.get("outcome", "")
            node.outcome_score = data.get("outcome_score", 0.5)
            node.reasoning_patterns = data.get("reasoning_patterns", [])
            node.tools_used = data.get("tools_used", [])
            node.missed_opportunities = data.get("missed_opportunities", [])
            node.cost_tokens = data.get("cost_tokens", 0)
            node.duration_seconds = data.get("duration_seconds", 0.0)
            node.reflection = data.get("reflection")
        elif isinstance(node, Skill):
            node.status = SkillStatus[data.get("status", "PROPOSED")]
            node.trigger_conditions = data.get("trigger_conditions", [])
            node.objective = data.get("objective", "")
            node.method = data.get("method", "")
            node.constraints = data.get("constraints", [])
            node.eval_tests = data.get("eval_tests", [])
            node.source_episode_ids = data.get("source_episode_ids", [])
            node.pattern_description = data.get("pattern_description", "")
            node.shadow_runs = data.get("shadow_runs", 0)
            node.shadow_score = data.get("shadow_score", 0.0)
            node.baseline_score = data.get("baseline_score", 0.0)
            node.version = data.get("version", 1)
            node.parent_skill_id = data.get("parent_skill_id")
        elif isinstance(node, Guardrail):
            node.rule = data.get("rule", "")
            node.severity = data.get("severity", "critical")
        elif isinstance(node, ProjectState):
            node.objectives = data.get("objectives", [])
            node.decisions = data.get("decisions", [])
            node.blockers = data.get("blockers", [])
            node.recent_changes = data.get("recent_changes", [])

        return node

    # ── StorageBackend Interface ───────────────────────────────────────

    def upsert(self, node: MemoryNode) -> None:
        data = self._serialize(node)
        self.conn.execute(
            """
            INSERT INTO memory_nodes
                (id, key, namespace, node_type, grief_state, is_sacred,
                 trust_charge, grief, faith, importance, created_at,
                 last_accessed, access_count, value, data_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(key, namespace) DO UPDATE SET
                node_type = excluded.node_type,
                grief_state = excluded.grief_state,
                is_sacred = excluded.is_sacred,
                trust_charge = excluded.trust_charge,
                grief = excluded.grief,
                faith = excluded.faith,
                importance = excluded.importance,
                last_accessed = excluded.last_accessed,
                access_count = excluded.access_count,
                value = excluded.value,
                data_json = excluded.data_json
            """,
            (
                node.id, node.key, node.namespace, node.node_type.name,
                node.grief_state.name, int(node.is_sacred),
                node.trust_charge, node.grief, node.faith, node.importance,
                node.created_at, node.last_accessed, node.access_count,
                node.value, json.dumps(data),
            ),
        )
        self.conn.commit()

    def get_by_key(self, key: str, namespace: str) -> Optional[MemoryNode]:
        row = self.conn.execute(
            "SELECT * FROM memory_nodes WHERE key = ? AND namespace = ?",
            (key, namespace),
        ).fetchone()
        return self._deserialize(row) if row else None

    def get_by_id(self, node_id: str) -> Optional[MemoryNode]:
        row = self.conn.execute(
            "SELECT * FROM memory_nodes WHERE id = ?",
            (node_id,),
        ).fetchone()
        return self._deserialize(row) if row else None

    def get_by_type(
        self, node_type: NodeType, namespace: str
    ) -> List[MemoryNode]:
        rows = self.conn.execute(
            """SELECT * FROM memory_nodes
               WHERE node_type = ? AND namespace = ? AND grief_state != 'PURGED'
               ORDER BY importance DESC, last_accessed DESC""",
            (node_type.name, namespace),
        ).fetchall()
        return [self._deserialize(r) for r in rows]

    def all_active(self, namespace: str) -> List[MemoryNode]:
        rows = self.conn.execute(
            """SELECT * FROM memory_nodes
               WHERE namespace = ? AND grief_state != 'PURGED'
               ORDER BY importance DESC""",
            (namespace,),
        ).fetchall()
        return [self._deserialize(r) for r in rows]

    def mark_purged(self, node_id: str) -> None:
        # Archive to cascade log before marking
        row = self.conn.execute(
            "SELECT * FROM memory_nodes WHERE id = ?", (node_id,)
        ).fetchone()
        if row:
            self.conn.execute(
                """INSERT INTO cascade_log
                   (node_id, node_key, node_type, trust_at_purge,
                    grief_at_purge, faith_at_purge, purged_at, data_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row["id"], row["key"], row["node_type"],
                    row["trust_charge"], row["grief"],
                    row["faith"], time.time(), row["data_json"],
                ),
            )
        self.conn.execute(
            """UPDATE memory_nodes
               SET grief_state = 'PURGED', trust_charge = 0.05,
                   grief = 0.0, importance = 0.0
               WHERE id = ?""",
            (node_id,),
        )
        self.conn.commit()

    def search(
        self, query: str, namespace: str, limit: int = 20
    ) -> List[MemoryNode]:
        """Keyword search via FTS5. Semantic search requires pgvector."""
        rows = self.conn.execute(
            """SELECT m.* FROM memory_nodes m
               WHERE m.namespace = ? AND m.grief_state != 'PURGED'
                 AND (m.key LIKE ? OR m.value LIKE ?)
               ORDER BY m.importance DESC, m.trust_charge DESC
               LIMIT ?""",
            (namespace, f"%{query}%", f"%{query}%", limit),
        ).fetchall()
        return [self._deserialize(r) for r in rows]

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
