#!/usr/bin/env python3
"""QuanTrade research-only second-order forum sentiment validator.

No web scraping. Accepts user-vetted/authorized CSV annotations only.
Never turns post-hoc observations into historical tradable predictions.
No trading/execution, API access, personal identifiers or model training.
"""
import argparse
import csv
import datetime as dt
import json
from collections import Counter
from pathlib import Path

LAYERS = {"direct", "meta", "mixed", "unknown"}
DIRECTIONS = {"bullish", "bearish", "neutral", "ambiguous", "conditional"}
META_TYPES = {
    "inverse_crowd_forum", "recursive_inversion", "capitulation_exhaustion",
    "reputation_revision", "herd_warning", "information_quality",
    "epistemic_uncertainty", "anticipated_herd_flows", "crowd_following",
    "signal_saturation", "price_certainty", "buy_the_dip", "ladder_buying",
    "unknown"
}
BOARDS = {"dc_stockus", "dc_krstock", "dc_tenbagger", "reddit_soxl",
          "reddit_wsb", "reddit_other", "stocktwits_soxl", "news"}


def parse_time(v):
    if not v:
        return None
    t = dt.datetime.fromisoformat(v.replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError("timezone-aware date/time required")
    return t.astimezone(dt.timezone.utc)


def read_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def validate_rows(rows):
    ids = set()
    for r in rows:
        if r["case_id"] in ids:
            raise ValueError("duplicate case_id")
        ids.add(r["case_id"])
        if r["platform"] not in BOARDS:
            raise ValueError("unknown platform")
        if r["discourse_layer"] not in LAYERS:
            raise ValueError("invalid discourse layer")
        if r["meta_type"] not in META_TYPES:
            raise ValueError("invalid second order category")
        if r["implied_direction"] not in DIRECTIONS:
            raise ValueError("invalid direction")
        if r["source_precision"] not in {"date_only", "minute", "second"}:
            raise ValueError("bad source precision")
        if r["forward_eligible"].lower() != "false":
            raise ValueError("historical curated sources never forward eligible")
        if r["probability_sample"].lower() != "false":
            raise ValueError("curated event-selected samples cannot claim probability sampling")
        if parse_time(r.get("first_seen_at_utc")) and r["source_precision"] == "date_only":
            # It may have been retrieved accurately, but historical posting
            # time is still too coarse to align to intraday prices.
            continue
    return True


def summarize(rows):
    validate_rows(rows)
    return {
        "status": "CURATED_RETROSPECTIVE_NOT_FORECAST",
        "total_cases": len(rows),
        "layers": dict(sorted(Counter(r["discourse_layer"] for r in rows).items())),
        "categories": dict(sorted(Counter(r["meta_type"] for r in rows).items())),
        "platforms": dict(sorted(Counter(r["platform"] for r in rows).items())),
        "forward_eligible": 0,
        "population_share_estimable": False,
        "price_predictive_effect": "NOT_TESTED",
        "note": "All samples were hand-selected retrospectively; exact historical first-seen unavailable."
    }


def prospective_window(records, cutoff_utc, allowed_rights=("authorized",)):
    """At-time-t features only: no reliance on later discovered old posts.

    Every record must provide published_at_utc and first_seen_at_utc,
    retained rights/access authorization and timestamped selection frame.
    Items without those requirements are rejected from prediction use.
    """
    cutoff = parse_time(cutoff_utc)
    if cutoff is None:
        raise ValueError("cutoff required")
    output = []
    seen = set()
    for r in records:
        p = parse_time(r.get("published_at_utc"))
        f = parse_time(r.get("first_seen_at_utc"))
        if p is None or f is None:
            continue
        if f < p:
            raise ValueError("impossible first-seen time")
        if r.get("authorized_rights") not in allowed_rights:
            continue
        if r.get("sampling_frame") != "pre_registered_complete":
            continue
        if r.get("exact_time_verified") is not True:
            continue
        if r.get("source_pointer") in seen:
            continue
        seen.add(r.get("source_pointer"))
        if max(p, f) > cutoff - dt.timedelta(minutes=15):
            continue
        if r.get("discourse_layer") not in LAYERS:
            raise ValueError("bad layer")
        if r.get("implied_direction") not in DIRECTIONS:
            raise ValueError("bad direction")
        output.append(r)
    return output


def main():
    a = argparse.ArgumentParser()
    a.add_argument("cases_csv")
    a.add_argument("--output")
    args = a.parse_args()
    result = summarize(read_rows(args.cases_csv))
    txt = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(txt, encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
