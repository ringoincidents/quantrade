"""Research-only Darvas breakout vs strong-momentum/new-high event study.

Requires public CSV files pinned by SOURCE_COMMIT; uses Python stdlib only.
Never places orders. Does not measure realizable portfolio performance.
"""
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median
from urllib.request import urlopen

SOURCE_COMMIT = "8d16e26815964c88306ec91bf6614e9c67fd89e4"
TICKERS = ("AAPL", "MSFT", "NVDA", "TSLA", "META", "TSM")
YEARS = (2023, 2024, 2025)
HOLD = 20


@dataclass(frozen=True)
class Bar:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


def load_bars(root: Path, ticker: str) -> list[Bar]:
    bars = []
    for year in YEARS:
        path = root / ticker / f"{year}.csv"
        with path.open(newline="", encoding="utf-8") as file:
            rows = list(csv.DictReader(file))
        for row in rows:
            bar = Bar(row["date"], *(float(row[k]) for k in ("open", "high", "low", "close", "volume")))
            if not (bar.low > 0 and bar.low <= min(bar.open, bar.close)
                    <= max(bar.open, bar.close) <= bar.high and bar.volume >= 0):
                raise ValueError(f"Invalid OHLCV: {ticker} {bar.date}")
            bars.append(bar)
    if len(bars) != len({b.date for b in bars}) or any(a.date >= b.date for a, b in zip(bars, bars[1:])):
        raise ValueError(f"Nonmonotonic or duplicate dates for {ticker}")
    return bars


def fetch_data(root: Path) -> None:
    for ticker in TICKERS:
        for year in YEARS:
            target = root / ticker / f"{year}.csv"
            target.parent.mkdir(parents=True, exist_ok=True)
            uri = (f"https://raw.githubusercontent.com/Pubmarks/datasets/"
                   f"{SOURCE_COMMIT}/data/stocks/{ticker}/{year}/ohlcv.csv")
            if not target.exists():
                with urlopen(uri, timeout=30) as response:
                    target.write_bytes(response.read())


def make_events(ticker: str, bars: list[Bar]) -> tuple[list[dict], int]:
    """Confirmed 126d-high top, 3 bars, confirmed floor, 3 bars, then close breakout.

    State transitions use information through t only; future prices affect only
    forward-return labels, never the signal. Research variant, NOT original Darvas.
    """
    phase, top, ti, floor, fi = "seek", 0.0, -1, 0.0, -1
    last_signal, last_high, raw = -10000, -10000, 0
    out = []
    for t in range(252, len(bars) - HOLD - 1):
        bar = bars[t]
        high126 = max(z.high for z in bars[t-126:t])
        high252 = max(z.high for z in bars[t-252:t])
        mom = bar.close / bars[t-60].close - 1
        near = bar.close / high252
        prev_volume = mean(z.volume for z in bars[t-20:t])
        if prev_volume <= 0:
            raise ValueError(f"No volume baseline for {ticker} at index {t}")
        volratio = bar.volume / prev_volume
        eligible = mom > 0 and near >= .90
        ret = bars[t+HOLD+1].open / bars[t+1].open - 1
        common = {"ticker": ticker, "t": t, "date": bar.date,
                  "year": int(bar.date[:4]), "ret": ret,
                  "momentum60": mom, "near252": near, "volratio": volratio}
        if eligible:
            out.append({**common, "type": "eligible"})
        if eligible and bar.close > high252 and t - last_high >= HOLD:
            out.append({**common, "type": "newhigh"})
            last_high = t

        if phase == "seek":
            if bar.high > high126:
                phase, top, ti = "top", bar.high, t
        elif phase == "top":
            if bar.high >= top:
                top, ti = bar.high, t
            elif t - ti >= 3:
                phase = "bottom"
                floor, fi = min((bars[k].low, k) for k in range(ti, t+1))
                if t - fi >= 3:
                    phase = "ready"
        elif phase == "bottom":
            if bar.high > top:
                phase, top, ti = "top", bar.high, t
            elif bar.low <= floor:
                floor, fi = bar.low, t
            elif t - fi >= 3:
                phase = "ready"
        elif phase == "ready":
            if bar.low < floor:  # ambiguous floor-break + top-break: reject
                phase = "seek"
            elif bar.close > top:
                raw += 1
                if eligible and t - last_signal >= HOLD:
                    out.append({**common, "type": "darvas",
                                "box_top": top, "box_bottom": floor})
                    last_signal = t
                phase = "seek"
    return out, raw


def describe(rows: list[dict]) -> dict:
    vals = [row["ret"] for row in rows]
    return {"n": len(vals), "mean": mean(vals) if vals else None,
            "median": median(vals) if vals else None,
            "win_rate": sum(x > 0 for x in vals)/len(vals) if vals else None}


def matched_controls(events: list[dict], year: int, max_distance: int = 63) -> dict:
    """Retrospective matches on prior features only; NOT a causal estimate."""
    signals = [e for e in events if e["year"] == year and e["type"] == "darvas"]
    pool = [e for e in events if e["year"] == year and e["type"] == "eligible"]
    pairs, used = [], set()
    for s in signals:
        cs = [c for c in pool if c["ticker"] == s["ticker"]
              and HOLD <= abs(c["t"]-s["t"]) <= max_distance
              and (c["ticker"], c["t"]) not in used
              and not any(d["ticker"] == c["ticker"] and abs(d["t"]-c["t"]) < HOLD
                          for d in signals)]
        if not cs:
            continue
        def distance(c: dict) -> float:
            return (abs(c["momentum60"]-s["momentum60"])/.2
                    + abs(c["near252"]-s["near252"])/.1
                    + abs(c["volratio"]-s["volratio"])*.1
                    + abs(c["t"]-s["t"])/63*.25)
        c = min(cs, key=distance)
        used.add((c["ticker"], c["t"]))
        pairs.append({"ticker": s["ticker"], "signal_date": s["date"],
                      "control_date": c["date"], "signal_return": s["ret"],
                      "control_return": c["ret"], "ret": s["ret"]-c["ret"]})
    return {"signals": len(signals), "matched_pairs": len(pairs),
            "excess_vs_control": describe(pairs), "pairs": pairs}


def evaluate(root: Path) -> dict:
    all_events, counts = [], []
    for ticker in TICKERS:
        bars = load_bars(root, ticker)
        events, raw = make_events(ticker, bars)
        all_events.extend(events)
        counts.append({"ticker": ticker, "rows": len(bars),
                       "start": bars[0].date, "end": bars[-1].date,
                       "raw_boxes": raw,
                       "signals": sum(e["type"] == "darvas" for e in events)})
    results = []
    for year in (2024, 2025):
        items = [e for e in all_events if e["year"] == year]
        results.append({"year": year,
                        "momentum_days": describe([e for e in items if e["type"] == "eligible"]),
                        "newhigh_signals": describe([e for e in items if e["type"] == "newhigh"]),
                        "darvas_signals": describe([e for e in items if e["type"] == "darvas"]),
                        "darvas_volume_1_25x": describe(
                            [e for e in items if e["type"] == "darvas" and e["volratio"] >= 1.25]),
                        "matching": matched_controls(items, year)})
    return {"status": "exploratory_only", "source_commit": SOURCE_COMMIT,
            "trading_authorized": False, "costs_included": False,
            "sample": counts, "results": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("/tmp/darvas_pubmarks"))
    parser.add_argument("--fetch", action="store_true",
                        help="Download pinned public OHLCV CSV files")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.fetch:
        fetch_data(args.data_root)
    result = evaluate(args.data_root)
    payload = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(payload+"\n", encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    main()
