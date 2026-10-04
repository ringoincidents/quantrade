"""Emit the canonical ReviewGate evaluation artifact."""
import argparse
import json
from pathlib import Path

from quantrade.capabilities.review_gate_evaluation import build_evaluation_artifact


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="review_gate_evaluation.json")
    args = parser.parse_args()
    artifact = build_evaluation_artifact()
    Path(args.output).write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
