"""
Noesis Governance Console — Live dashboard for memory inspection.

Zero-dependency web server using Python's stdlib http.server.
Serves the dashboard HTML and a JSON API backed by the vault.

Usage:
    python -m noesis.console --db noesis.db --port 8420
"""

from noesis.console.server import run_console

__all__ = ["run_console"]
