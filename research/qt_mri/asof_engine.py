"""QT-MRI: research-only point-in-time joins and first-signal evaluation.

No price feed, copyright-restricted data or trading order is bundled.
Input CSVs must carry verified first-publication timestamps; guessed releases fail closed.
Do not import into QuanTrade production market_indicators.py.
"""
from __future__ import annotations
import argparse
import csv
import json
from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Iterable

ALLOWED_CREDIT_IDS = {"BAMLH0A0HYM2", "BAA10Y"}


def utc(value: str) -> datetime:
    if not value or value in {"UNKNOWN", "null", "."}:
        raise ValueError("Missing first-publication timestamp: strict as-of gate")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("A timezone-aware timestamp is required")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class Release:
    series_id: str
    observation_date: str
    value: float
    first_public_at_utc: datetime


@dataclass(frozen=True)
class Close:
    date: str
    close: float
    close_at_utc: datetime


def read_releases(path: str, expected_series_id: str) -> list[Release]:
    releases = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row["series_id"] != expected_series_id:
                raise ValueError("Series mismatch: proxy substitution prohibited")
            val = float(row["value"])
            if expected_series_id != "VIXCLS" and expected_series_id not in ALLOWED_CREDIT_IDS:
                raise ValueError("Unsupported factor: explicit identity required")
            releases.append(Release(row["series_id"], row["observation_date"], val,
                                    utc(row["first_public_at_utc"])))
    if not releases:
        raise ValueError("No release observations")
    releases.sort(key=lambda r: r.first_public_at_utc)
    if len({r.first_public_at_utc for r in releases}) != len(releases):
        raise ValueError("Duplicate first-publication timestamp; resolve revisions")
    return releases


def read_prices(path: str) -> list[Close]:
    prices = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            c = Close(row["date"], float(row["close"]), utc(row["close_at_utc"]))
            if c.close <= 0:
                raise ValueError("Prices must be positive")
            prices.append(c)
    if not prices:
        raise ValueError("No market closes")
    prices.sort(key=lambda p: p.close_at_utc)
    if len({p.date for p in prices}) != len(prices):
        raise ValueError("Duplicate market day")
    if any(p.close_at_utc <= q.close_at_utc for p, q in zip(prices[1:], prices[:-1])):
        raise ValueError("Market closes out of order")
    return prices


def asof_panel(prices: list[Close], releases: list[Release], series_id: str):
    """Use the latest value actually known by the explicit equity close timestamp."""
    if any(r.series_id != series_id for r in releases):
        raise ValueError("Cannot silently splice or rename different indicators")
    times = [r.first_public_at_utc for r in releases]
    if times != sorted(times):
        raise ValueError("Sort verified publication times first")
    result = []
    for p in prices:
        i = bisect_right(times, p.close_at_utc) - 1
        result.append(releases[i] if i >= 0 else None)
    return result


def vix_crosses(aligned: list[Release | None]) -> list[int]:
    """Only first cross from <30 to >=30, no duplicate from unchanged release."""
    out = []
    for i in range(1, len(aligned)):
        prev, now = aligned[i - 1], aligned[i]
        if prev is None or now is None or now.first_public_at_utc == prev.first_public_at_utc:
            continue
        if prev.value < 30 <= now.value:
            out.append(i)
    return out


def hy_turns(aligned: list[Release | None], credit_id: str, lookback: int = 252) -> list[int]:
    """Prospective proxy: extreme preceding spread, 5 newly known spread observations narrowing >=15bp.

    Works for HY OAS and Baa-Treasury, but results must be labeled separately.
    Every value is percent points; delta <= -0.15 equals -15 basis points.
    """
    if credit_id not in ALLOWED_CREDIT_IDS:
        raise ValueError("Explicit credit series identity required")
    events = []
    known = []
    last_release_time = None
    last_emit = -999
    for i, item in enumerate(aligned):
        if item is None or item.first_public_at_utc == last_release_time:
            continue
        last_release_time = item.first_public_at_utc
        known.append(item.value)
        if len(known) < lookback + 6 or i - last_emit < 60:
            continue
        history = known[:-5]
        baseline = sorted(history[-lookback:])
        percentile80 = baseline[int(0.8 * (len(baseline) - 1))]
        stressed = max(known[-25:-5]) >= percentile80
        contracting = known[-1] - known[-6] <= -0.15
        if stressed and contracting:
            events.append(i)
            last_emit = i
    return events


def combine_events(vix_events: Iterable[int], credit_events: Iterable[int], max_lag=20) -> list[int]:
    """Signals only when the credit condition is newly known after VIX event."""
    vi = sorted(vix_events)
    return [c for c in sorted(credit_events) if any(0 <= c - v <= max_lag for v in vi)]


def evaluate_forward(prices: list[Close], events: Iterable[int], horizons=(5, 20, 60)) -> dict:
    """Descriptive future path stats. No significance/trading claim; no partial-horizon leakage."""
    results = {}
    for horizon in horizons:
        rows = []
        for i in events:
            if i < 0 or i + horizon >= len(prices):
                continue
            start, path = prices[i].close, [p.close for p in prices[i + 1:i + horizon + 1]]
            rows.append({"signal_date": prices[i].date,
                         "future_return": path[-1] / start - 1,
                         "max_adverse_excursion": min([start] + path) / start - 1})
        results[str(horizon)] = {
            "n": len(rows), "mean_forward_return": mean(r["future_return"] for r in rows) if rows else None,
            "median_forward_return": median(r["future_return"] for r in rows) if rows else None,
            "win_rate": mean(r["future_return"] > 0 for r in rows) if rows else None,
            "mean_max_adverse_excursion": mean(r["max_adverse_excursion"] for r in rows) if rows else None,
            "events": rows,
        }
    return results


def main():
    parser = argparse.ArgumentParser(description="Read-only, no-network as-of experiment")
    parser.add_argument("--prices", required=True, help="CSV date,close,close_at_utc")
    parser.add_argument("--vix", required=True, help="CSV series_id,observation_date,value,first_public_at_utc")
    parser.add_argument("--credit", required=True, help="CSV with separate credit series")
    parser.add_argument("--credit-id", choices=sorted(ALLOWED_CREDIT_IDS), required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    closes = read_prices(args.prices)
    vix = asof_panel(closes, read_releases(args.vix, "VIXCLS"), "VIXCLS")
    credit = asof_panel(closes, read_releases(args.credit, args.credit_id), args.credit_id)
    v, c = vix_crosses(vix), hy_turns(credit, args.credit_id)
    both = combine_events(v, c)
    summary = {
        "status": "EXPLORATORY_ONLY_NOT_VALIDATED", "credit_id": args.credit_id,
        "source_policy": "input timestamps must be independently verified; unknown rejected",
        "total_closes": len(closes), "vix_known_at_closes": sum(r is not None for r in vix),
        "credit_known_at_closes": sum(r is not None for r in credit),
        "event_counts": {"vix": len(v), "credit_turn": len(c), "combined": len(both)},
        "results": {name: evaluate_forward(closes, es) for name, es in
                    (("vix", v), ("credit_turn", c), ("combined", both))},
        "WARNING": "No economic/source inference or execution authorization. 2026 is not untouched holdout.",
    }
    Path(args.output).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote exploratory report to {args.output}; events={summary['event_counts']}")


if __name__ == "__main__":
    main()
