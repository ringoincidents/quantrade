#!/usr/bin/env python3
"""Exploratory selected-date semiconductor ETF diagnostics.

The event dates were selected post hoc from 2026 news and are NOT a random,
independent, preregistered or comprehensive sample. This tool deliberately
does NOT calculate significance, causal effect, or trading alpha.
SOXX does not track the exact underlying index of SOXL (NYSE Semiconductor).
"""
import argparse
import csv
import json
import math
import pathlib
import statistics


def analyze(path: pathlib.Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    buckets = {}
    for row in rows:
        soxx, qqq, soxl = [
            float(row[key])
            for key in ("SOXX_return_pct", "QQQ_return_pct", "SOXL_return_pct")
        ]
        if not all(math.isfinite(x) for x in (soxx, qqq, soxl)):
            raise ValueError("Nonfinite return")
        relative = round(soxx - qqq, 3)
        row["sector_minus_qqq_pp"] = relative
        buckets.setdefault(row["event_group"], []).append(relative)
    summary = {
        key: {
            "n": len(vals),
            "soxx_outperformed_qqq": sum(x > 0 for x in vals),
            "soxx_underperformed_qqq": sum(x < 0 for x in vals),
            "median_relative_pp": round(statistics.median(vals), 3),
            "mean_relative_pp": round(statistics.mean(vals), 3)
        }
        for key, vals in buckets.items()
    }
    return {"status": "DESCRIPTIVE_SELECTED_EVENTS_NOT_CAUSAL",
            "n_event_dates": len(rows), "summary": summary,
            "events": [
                {"date": row["date"], "event_id": row["event_id"],
                 "relative_pp": row["sector_minus_qqq_pp"]}
                for row in rows
            ]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=pathlib.Path)
    args = parser.parse_args()
    print(json.dumps(analyze(args.csv), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
