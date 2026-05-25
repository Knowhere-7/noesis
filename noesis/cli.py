"""
Noesis CLI — Memory inspection and management.

Usage:
    noesis stats                    Show vault statistics
    noesis nodes [--type TYPE]      List memory nodes
    noesis get KEY                  Get a specific node
    noesis search QUERY             Search the vault
    noesis guardrail KEY RULE       Install a system guardrail
    noesis retrospective            Run project retrospective
    noesis cascade                  Run grief cascade
    noesis decay                    Apply passive trust decay
    noesis export [--json]          Export all nodes
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from noesis.gateway.retrieval import RetrievalGateway
from noesis.schema import NodeType


def main(argv: Optional[list] = None):
    parser = argparse.ArgumentParser(
        prog="noesis",
        description="Noesis — Runtime trust layer for AI agents",
    )
    parser.add_argument(
        "--db", default="noesis.db",
        help="Path to SQLite database (default: noesis.db)",
    )
    parser.add_argument(
        "--namespace", default="default",
        help="Memory namespace (default: default)",
    )

    subparsers = parser.add_subparsers(dest="command")

    # stats
    subparsers.add_parser("stats", help="Show vault statistics")

    # nodes
    nodes_parser = subparsers.add_parser("nodes", help="List memory nodes")
    nodes_parser.add_argument("--type", dest="node_type", help="Filter by type")

    # get
    get_parser = subparsers.add_parser("get", help="Get a node by key")
    get_parser.add_argument("key", help="Node key")

    # search
    search_parser = subparsers.add_parser("search", help="Search the vault")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--limit", type=int, default=10)

    # guardrail
    guard_parser = subparsers.add_parser("guardrail", help="Install guardrail")
    guard_parser.add_argument("key", help="Guardrail key")
    guard_parser.add_argument("rule", help="Guardrail rule text")

    # retrospective
    retro_parser = subparsers.add_parser(
        "retrospective", help="Run project retrospective"
    )
    retro_parser.add_argument(
        "--hours", type=float, default=168.0,
        help="Lookback window in hours (default: 168 = 1 week)",
    )

    # cascade
    subparsers.add_parser("cascade", help="Run grief cascade")

    # decay
    decay_parser = subparsers.add_parser("decay", help="Apply trust decay")
    decay_parser.add_argument(
        "--factor", type=float, default=0.001,
        help="Decay factor (default: 0.001)",
    )

    # export
    export_parser = subparsers.add_parser("export", help="Export all nodes")
    export_parser.add_argument("--json", action="store_true", dest="as_json")

    # context
    ctx_parser = subparsers.add_parser("context", help="Show assembled context")
    ctx_parser.add_argument("--query", default="", help="Context query")
    ctx_parser.add_argument(
        "--format", choices=["plain", "claude", "openai", "ollama"],
        default="plain",
    )

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return

    gateway = RetrievalGateway(
        db_path=args.db, namespace=args.namespace
    )

    try:
        if args.command == "stats":
            _cmd_stats(gateway)
        elif args.command == "nodes":
            _cmd_nodes(gateway, args.node_type)
        elif args.command == "get":
            _cmd_get(gateway, args.key)
        elif args.command == "search":
            _cmd_search(gateway, args.query, args.limit)
        elif args.command == "guardrail":
            _cmd_guardrail(gateway, args.key, args.rule)
        elif args.command == "retrospective":
            _cmd_retrospective(gateway, args.hours)
        elif args.command == "cascade":
            _cmd_cascade(gateway)
        elif args.command == "decay":
            _cmd_decay(gateway, args.factor)
        elif args.command == "export":
            _cmd_export(gateway, args.as_json)
        elif args.command == "context":
            _cmd_context(gateway, args.query, args.format)
    finally:
        gateway.close()


def _cmd_stats(gw: RetrievalGateway):
    stats = gw.get_stats()
    print("=== Noesis Vault Statistics ===")
    print(f"Total nodes:     {stats['total_nodes']}")
    print(f"Avg trust:       {stats['avg_trust']:.3f}")
    print(f"Session energy:  {stats['session_energy']:.1f}")
    print()
    print("By type:")
    for t, count in sorted(stats["by_type"].items()):
        print(f"  {t:25s} {count}")
    print()
    print("By state:")
    for s, count in sorted(stats["by_state"].items()):
        print(f"  {s:25s} {count}")


def _cmd_nodes(gw: RetrievalGateway, type_filter: Optional[str]):
    nodes = gw.store.all_nodes()
    if type_filter:
        try:
            nt = NodeType[type_filter.upper()]
            nodes = [n for n in nodes if n.node_type == nt]
        except KeyError:
            print(f"Unknown type: {type_filter}")
            print(f"Valid types: {[t.name for t in NodeType]}")
            return

    if not nodes:
        print("No nodes found.")
        return

    print(f"{'KEY':30s} {'TYPE':20s} {'TRUST':7s} {'GRIEF':7s} {'STATE':15s}")
    print("-" * 85)
    for n in nodes:
        sacred = " [S]" if n.is_sacred else ""
        print(
            f"{n.key[:30]:30s} {n.node_type.name[:20]:20s} "
            f"{n.trust_charge:6.3f} {n.grief:6.3f} "
            f"{n.grief_state.name[:15]:15s}{sacred}"
        )


def _cmd_get(gw: RetrievalGateway, key: str):
    node = gw.store.get(key)
    if not node:
        print(f"Node '{key}' not found.")
        return

    print(f"Key:          {node.key}")
    print(f"ID:           {node.id}")
    print(f"Type:         {node.node_type.name}")
    print(f"Value:        {node.value[:200]}")
    print(f"Trust:        {node.trust_charge:.3f}")
    print(f"Grief:        {node.grief:.3f}")
    print(f"Faith:        {node.faith:.3f}")
    print(f"State:        {node.grief_state.name}")
    print(f"Sacred:       {node.is_sacred}")
    print(f"Importance:   {node.importance:.3f}")
    print(f"Access count: {node.access_count}")
    print(f"Dependencies: {node.dependencies}")
    print(f"Dependents:   {node.dependents}")


def _cmd_search(gw: RetrievalGateway, query: str, limit: int):
    results = gw.search(query, limit)
    if not results:
        print(f"No results for '{query}'.")
        return

    print(f"Found {len(results)} results for '{query}':")
    for n in results:
        print(f"  [{n.node_type.name:15s}] {n.key:30s} | {n.value[:50]}")


def _cmd_guardrail(gw: RetrievalGateway, key: str, rule: str):
    success, msg = gw.install_guardrail(key, rule)
    if success:
        print(f"Guardrail '{key}' installed: {rule}")
    else:
        print(f"Failed: {msg}")


def _cmd_retrospective(gw: RetrievalGateway, hours: float):
    result = gw.run_retrospective(lookback_hours=hours)
    print(f"=== Project Retrospective ({hours:.0f}h window) ===")
    print(f"Episodes analyzed:    {result['episodes_analyzed']}")
    print(f"Overall health:       {result['overall_health']:.2f}")
    print(f"Trust trend:          {result['trust_trend']}")
    print(f"Trust average:        {result['trust_avg']:.3f}")
    print(f"Patterns found:       {result['patterns_found']}")
    print(f"Actionable patterns:  {result['actionable_patterns']}")
    print(f"Skills drafted:       {result['skills_drafted']}")
    print()
    if result["recommendations"]:
        print("Recommendations:")
        for rec in result["recommendations"]:
            print(f"  - {rec}")
    if result["skill_reports"]:
        print("\nSkill Reports:")
        for sr in result["skill_reports"]:
            print(
                f"  {sr['key']:30s} effectiveness={sr['effectiveness']:+.2f} "
                f"-> {sr['recommendation']}"
            )


def _cmd_cascade(gw: RetrievalGateway):
    purged = gw.store.run_grief_cascade()
    if purged:
        print(f"Grief cascade purged {len(purged)} nodes:")
        for pid in purged:
            print(f"  - {pid}")
    else:
        print("No contaminated nodes to purge.")


def _cmd_decay(gw: RetrievalGateway, factor: float):
    gw.store.decay_all(factor)
    print(f"Applied trust decay (factor={factor}).")


def _cmd_export(gw: RetrievalGateway, as_json: bool):
    nodes = gw.store.all_nodes()
    if as_json:
        data = []
        for n in nodes:
            data.append({
                "id": n.id,
                "key": n.key,
                "type": n.node_type.name,
                "value": n.value,
                "trust": n.trust_charge,
                "grief": n.grief,
                "faith": n.faith,
                "state": n.grief_state.name,
                "sacred": n.is_sacred,
                "importance": n.importance,
            })
        print(json.dumps(data, indent=2))
    else:
        for n in nodes:
            print(f"{n.node_type.name:20s} {n.key:30s} {n.value[:60]}")


def _cmd_context(gw: RetrievalGateway, query: str, fmt: str):
    from noesis.gateway.providers import (
        ClaudeAdapter, OpenAIAdapter, OllamaAdapter,
    )

    if fmt == "claude":
        gw.provider = ClaudeAdapter()
    elif fmt == "openai":
        gw.provider = OpenAIAdapter()
    elif fmt == "ollama":
        gw.provider = OllamaAdapter()
    else:
        gw.provider = None

    context = gw.get_context(query=query)
    print(context if context else "No context available.")


if __name__ == "__main__":
    main()
