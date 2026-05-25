"""Allow running as: python -m noesis.console"""
import argparse
from noesis.console.server import run_console

parser = argparse.ArgumentParser(description="Noesis Governance Console")
parser.add_argument("--db", default="noesis.db", help="SQLite database path")
parser.add_argument("--namespace", default="default", help="Memory namespace")
parser.add_argument("--port", type=int, default=8420, help="HTTP port")

args = parser.parse_args()
run_console(db_path=args.db, namespace=args.namespace, port=args.port)
