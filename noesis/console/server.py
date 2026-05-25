"""
Console Server — Zero-dependency HTTP server for the governance dashboard.

Serves:
  GET /                 → Dashboard HTML
  GET /api/stats        → Vault statistics
  GET /api/nodes        → All memory nodes (with filters)
  GET /api/node/:key    → Single node detail
  GET /api/context      → Assembled context preview
  GET /api/cascade-log  → Grief cascade audit log
  GET /api/retrospective → Run and return retrospective
  GET /api/drift        → Current drift scores
  POST /api/cascade     → Trigger grief cascade
  POST /api/decay       → Apply trust decay

Uses only Python stdlib: http.server, json, urllib.
"""

from __future__ import annotations

import json
import logging
import os
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from noesis.gateway.retrieval import RetrievalGateway
from noesis.reflection.retrospective import ProjectRetrospective
from noesis.schema import GriefState, NodeType, Skill, SkillStatus

logger = logging.getLogger("noesis.console")

# Global reference to gateway (set by run_console)
_gateway: Optional[RetrievalGateway] = None


class ConsoleHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for the governance console."""

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        if path == "" or path == "/index.html":
            self._serve_dashboard()
        elif path == "/api/stats":
            self._api_stats()
        elif path == "/api/nodes":
            self._api_nodes(params)
        elif path.startswith("/api/node/"):
            key = path[len("/api/node/"):]
            self._api_node_detail(key)
        elif path == "/api/context":
            fmt = params.get("format", ["plain"])[0]
            self._api_context(fmt)
        elif path == "/api/cascade-log":
            self._api_cascade_log()
        elif path == "/api/retrospective":
            hours = float(params.get("hours", ["168"])[0])
            self._api_retrospective(hours)
        elif path == "/api/drift":
            self._api_drift()
        else:
            self.send_error(404, "Not found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/cascade":
            self._api_trigger_cascade()
        elif path == "/api/decay":
            self._api_trigger_decay()
        else:
            self.send_error(404, "Not found")

    # ── Dashboard HTML ────────────────────────────────────────────────

    def _serve_dashboard(self):
        html_path = os.path.join(
            os.path.dirname(__file__), "dashboard.html"
        )
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                content = f.read()
            self._respond(200, content, "text/html")
        except FileNotFoundError:
            self.send_error(500, "dashboard.html not found")

    # ── API Endpoints ─────────────────────────────────────────────────

    def _api_stats(self):
        stats = _gateway.get_stats()
        stats["session_energy_max"] = 100.0
        stats["namespace"] = _gateway.store.namespace
        stats["timestamp"] = time.time()
        self._json_response(stats)

    def _api_nodes(self, params: Dict):
        nodes = _gateway.store.all_nodes()

        # Filter by type
        type_filter = params.get("type", [None])[0]
        if type_filter:
            try:
                nt = NodeType[type_filter.upper()]
                nodes = [n for n in nodes if n.node_type == nt]
            except KeyError:
                pass

        # Filter by state
        state_filter = params.get("state", [None])[0]
        if state_filter:
            try:
                gs = GriefState[state_filter.upper()]
                nodes = [n for n in nodes if n.grief_state == gs]
            except KeyError:
                pass

        result = []
        for n in nodes:
            entry = {
                "id": n.id,
                "key": n.key,
                "type": n.node_type.name,
                "value": n.value[:200],
                "trust": round(n.trust_charge, 4),
                "grief": round(n.grief, 4),
                "faith": round(n.faith, 4),
                "state": n.grief_state.name,
                "sacred": n.is_sacred,
                "importance": round(n.importance, 4),
                "access_count": n.access_count,
                "created_at": n.created_at,
                "last_accessed": n.last_accessed,
            }
            if isinstance(n, Skill):
                entry["skill_status"] = n.status.name
                entry["shadow_runs"] = n.shadow_runs
                entry["shadow_score"] = round(n.shadow_score, 4)
            result.append(entry)

        self._json_response(result)

    def _api_node_detail(self, key: str):
        node = _gateway.store.get(key)
        if not node:
            self._json_response({"error": f"Node '{key}' not found"}, 404)
            return

        detail = {
            "id": node.id,
            "key": node.key,
            "type": node.node_type.name,
            "value": node.value,
            "trust": round(node.trust_charge, 4),
            "grief": round(node.grief, 4),
            "faith": round(node.faith, 4),
            "state": node.grief_state.name,
            "sacred": node.is_sacred,
            "importance": round(node.importance, 4),
            "access_count": node.access_count,
            "created_at": node.created_at,
            "last_accessed": node.last_accessed,
            "dependencies": list(node.dependencies),
            "dependents": list(node.dependents),
            "metadata": node.metadata,
        }
        self._json_response(detail)

    def _api_context(self, fmt: str):
        from noesis.gateway.providers import (
            ClaudeAdapter, OpenAIAdapter, OllamaAdapter,
        )

        adapters = {
            "claude": ClaudeAdapter,
            "openai": OpenAIAdapter,
            "ollama": OllamaAdapter,
        }

        adapter_cls = adapters.get(fmt)
        if adapter_cls:
            _gateway.provider = adapter_cls()
        else:
            _gateway.provider = None

        context = _gateway.get_context()
        nodes = _gateway.get_context_nodes()

        self._json_response({
            "formatted": context,
            "node_count": len(nodes),
            "format": fmt,
        })

    def _api_cascade_log(self):
        # Read from cascade_log table in SQLite
        rows = _gateway.store.backend.conn.execute(
            """SELECT node_id, node_key, node_type,
                      trust_at_purge, grief_at_purge, faith_at_purge,
                      purged_at
               FROM cascade_log
               ORDER BY purged_at DESC
               LIMIT 50"""
        ).fetchall()

        log = []
        for r in rows:
            log.append({
                "node_id": r["node_id"],
                "node_key": r["node_key"],
                "node_type": r["node_type"],
                "trust_at_purge": r["trust_at_purge"],
                "grief_at_purge": r["grief_at_purge"],
                "faith_at_purge": r["faith_at_purge"],
                "purged_at": r["purged_at"],
            })

        self._json_response(log)

    def _api_retrospective(self, hours: float):
        result = _gateway.run_retrospective(lookback_hours=hours)
        self._json_response(result)

    def _api_drift(self):
        # Get current context and compute drift for a null output
        nodes = _gateway.get_context_nodes()
        drift = _gateway.store.trust_gate.score_output("", nodes)
        self._json_response({
            "continuity": round(drift.continuity, 4),
            "groundedness": round(drift.groundedness, 4),
            "drift": round(drift.drift, 4),
            "trust": round(drift.trust, 4),
            "action_risk": round(drift.action_risk, 4),
            "composite_health": round(drift.composite_health, 4),
            "should_retrieve": drift.should_retrieve,
            "should_reflect": drift.should_reflect,
            "should_refuse": drift.should_refuse,
        })

    def _api_trigger_cascade(self):
        purged = _gateway.store.run_grief_cascade()
        self._json_response({
            "purged_count": len(purged),
            "purged_ids": purged,
        })

    def _api_trigger_decay(self):
        _gateway.store.decay_all()
        self._json_response({"status": "decay applied"})

    # ── Response Helpers ──────────────────────────────────────────────

    def _json_response(self, data: Any, status: int = 200):
        body = json.dumps(data, default=str)
        self._respond(status, body, "application/json")

    def _respond(self, status: int, body: str, content_type: str):
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format, *args):
        # Suppress default access logs (too noisy with polling)
        pass


def run_console(
    db_path: str = "noesis.db",
    namespace: str = "default",
    port: int = 8420,
):
    """Start the governance console server."""
    global _gateway
    _gateway = RetrievalGateway(db_path=db_path, namespace=namespace)

    server = HTTPServer(("0.0.0.0", port), ConsoleHandler)
    print(f"\n  Noesis Governance Console")
    print(f"  ────────────────────────")
    print(f"  Database:  {db_path}")
    print(f"  Namespace: {namespace}")
    print(f"  URL:       http://localhost:{port}")
    print(f"\n  Press Ctrl+C to stop.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Console stopped.")
    finally:
        _gateway.close()
        server.server_close()
