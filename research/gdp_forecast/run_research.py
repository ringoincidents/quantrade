"""Offline research CLI. Hash verification is not provider authentication."""
import argparse
import hashlib
import json
from pathlib import Path
from contextlib import closing
from forecast_ledger import connect
from pipeline import replay

def run(input_path, evidence_dir, db_path, asof):
    rows=json.loads(Path(input_path).read_text(encoding="utf-8"))
    for digest in {r["source_sha256"] for r in rows}:
        if len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Invalid digest")
        raw=(Path(evidence_dir)/digest).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=digest:
            raise ValueError("Evidence hash mismatch")
    with closing(connect(db_path)) as db:
        return replay(db,rows,asof)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for arg in ("input","evidence","db","asof"): p.add_argument("--"+arg,required=True)
    a=p.parse_args()
    print(json.dumps(run(a.input,a.evidence,a.db,a.asof),indent=2,allow_nan=False))
