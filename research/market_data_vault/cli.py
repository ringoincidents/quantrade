"""Offline CLI for the standalone experimental Market Data Vault.

Only ingests CSV files that the user is already legally allowed to retain.
No built-in downloads, scheduled actions or broker orders.
"""
from __future__ import annotations

import argparse
import json

from vault import connect, ingest_csv, register_dataset, snapshot


def main():
    p = argparse.ArgumentParser(description="Market Data Vault RESEARCH prototype (no network)")
    p.add_argument("--db", required=True, help="Private local SQLite path, NEVER public GitHub")
    commands = p.add_subparsers(dest="command", required=True)

    add = commands.add_parser("register")
    add.add_argument("--id", required=True)
    add.add_argument("--asset", required=True)
    add.add_argument("--provider", required=True)
    add.add_argument("--currency", required=True)
    add.add_argument("--rights-note", required=True)

    ingest = commands.add_parser("ingest")
    ingest.add_argument("--id", required=True)
    ingest.add_argument("--csv", required=True)
    ingest.add_argument("--source-uri", required=True)
    ingest.add_argument("--rights-confirmed", action="store_true",
                        help="Operator attests legal local retention; no automated license check")
    ingest.add_argument("--first-availability-verified", action="store_true",
                        help="Use ONLY after independent audit of exact release/availability times")

    show = commands.add_parser("snapshot")
    show.add_argument("--id", required=True)
    show.add_argument("--asof", required=True)
    show.add_argument("--allow-unverified", action="store_true",
                      help="Diagnostic ONLY; not point-in-time research evidence")

    args = p.parse_args()
    with connect(args.db) as db:
        if args.command == "register":
            register_dataset(db, args.id, args.asset, args.provider,
                             args.currency, args.rights_note)
            out = {"status": "registered", "dataset_id": args.id}
        elif args.command == "ingest":
            out = ingest_csv(db, args.csv, dataset_id=args.id,
                             source_uri=args.source_uri,
                             usage_rights_confirmed=args.rights_confirmed,
                             availability_verified=args.first_availability_verified)
        else:
            rows = snapshot(db, args.id, args.asof,
                            verified_only=not args.allow_unverified)
            out = {"dataset_id": args.id, "asof": args.asof,
                   "verified_only": not args.allow_unverified,
                   "rows": rows}
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
