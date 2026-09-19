from __future__ import annotations

import math
from copy import deepcopy
from statistics import mean
from typing import Any

from .tools import ToolDefinition, ToolRegistry


class MarketDataPlane:
    """Provider-neutral OHLCV access. P1.3E uses injected synthetic/local bars."""

    def __init__(self, bars: dict[tuple[str, str], list[dict[str, Any]]]):
        self.bars = deepcopy(bars)

    def catalog(self, _: dict) -> dict:
        symbols: dict[str, list[str]] = {}
        for symbol, timeframe in self.bars:
            symbols.setdefault(symbol, []).append(timeframe)
        return {
            symbol: {"timeframes": sorted(tfs), "available": True}
            for symbol, tfs in sorted(symbols.items())
        }

    def ohlcv(self, args: dict) -> dict:
        key = (args["symbol"], args["timeframe"])
        if key not in self.bars:
            raise KeyError(
                f"OHLCV unavailable for symbol={key[0]} timeframe={key[1]}"
            )
        rows = deepcopy(self.bars[key])
        start = args.get("start")
        end = args.get("end")
        if start:
            rows = [r for r in rows if r["timestamp"] >= start]
        if end:
            rows = [r for r in rows if r["timestamp"] <= end]
        limit = args.get("limit")
        if limit:
            rows = rows[-int(limit):]
        return {
            "symbol": key[0],
            "timeframe": key[1],
            "adjustment": "synthetic_unadjusted",
            "bars": rows,
        }

    def event_scan(self, args: dict) -> list[dict]:
        timeframe = args["timeframe"]
        lookback = int(args["lookback_bars"])
        min_return = args.get("min_return_pct")
        max_return = args.get("max_return_pct")
        min_volume_multiple = args.get("min_volume_multiple")
        results = []
        symbols = sorted({s for s, tf in self.bars if tf == timeframe})
        for symbol in symbols:
            rows = self.bars[(symbol, timeframe)]
            if len(rows) <= lookback:
                continue
            start = rows[-lookback - 1]["close"]
            end = rows[-1]["close"]
            ret = (end / start - 1.0) * 100.0 if start else None
            prior_volumes = [r["volume"] for r in rows[-lookback - 1:-1]]
            avg_volume = mean(prior_volumes) if prior_volumes else 0
            volume_multiple = rows[-1]["volume"] / avg_volume if avg_volume else None
            if min_return is not None and (ret is None or ret < min_return):
                continue
            if max_return is not None and (ret is None or ret > max_return):
                continue
            if min_volume_multiple is not None and (
                volume_multiple is None or volume_multiple < min_volume_multiple
            ):
                continue
            results.append({
                "symbol": symbol,
                "timeframe": timeframe,
                "return_pct": round(ret, 4),
                "volume_multiple": round(volume_multiple, 4) if volume_multiple is not None else None,
                "event_timestamp": rows[-1]["timestamp"],
            })
        return results


class TechnicalEngine:
    @staticmethod
    def indicators(args: dict) -> dict:
        bars = args["bars"]
        requested = args["indicators"]
        closes = [float(b["close"]) for b in bars]
        highs = [float(b["high"]) for b in bars]
        lows = [float(b["low"]) for b in bars]
        out: dict[str, list[Any]] = {}
        for spec in requested:
            name = spec["name"].upper()
            if name == "SMA":
                period = int(spec["period"])
                out[f"SMA_{period}"] = TechnicalEngine._sma(closes, period)
            elif name == "EMA":
                period = int(spec["period"])
                out[f"EMA_{period}"] = TechnicalEngine._ema(closes, period)
            elif name == "RSI":
                period = int(spec.get("period", 14))
                out[f"RSI_{period}"] = TechnicalEngine._rsi(closes, period)
            elif name == "BOLLINGER":
                period = int(spec.get("period", 20))
                stddev = float(spec.get("stddev", 2.0))
                mid = TechnicalEngine._sma(closes, period)
                upper, lower = [], []
                for i, m in enumerate(mid):
                    if m is None:
                        upper.append(None); lower.append(None); continue
                    window = closes[i - period + 1:i + 1]
                    variance = sum((x - m) ** 2 for x in window) / period
                    sd = math.sqrt(variance)
                    upper.append(m + stddev * sd)
                    lower.append(m - stddev * sd)
                out[f"BB_MID_{period}"] = mid
                out[f"BB_UPPER_{period}"] = upper
                out[f"BB_LOWER_{period}"] = lower
            elif name == "ATR":
                period = int(spec.get("period", 14))
                tr = []
                for i in range(len(bars)):
                    if i == 0:
                        tr.append(highs[i] - lows[i])
                    else:
                        tr.append(max(
                            highs[i] - lows[i],
                            abs(highs[i] - closes[i - 1]),
                            abs(lows[i] - closes[i - 1]),
                        ))
                out[f"ATR_{period}"] = TechnicalEngine._sma(tr, period)
            elif name == "ICHIMOKU":
                out.update(TechnicalEngine._ichimoku(highs, lows))
            else:
                raise ValueError(f"unsupported indicator: {name}")
        return {"count": len(bars), "series": out}

    @staticmethod
    def chart_spec(args: dict) -> dict:
        return {
            "type": "candlestick",
            "symbol": args["symbol"],
            "timeframe": args["timeframe"],
            "bars": args["bars"],
            "overlays": args.get("overlays", {}),
            "annotations": args.get("annotations", []),
            "renderer_contract": "quantrade_chart_v1",
        }

    @staticmethod
    def event_study(args: dict) -> dict:
        bars = args["bars"]
        event_index = int(args["event_index"])
        horizons = [int(h) for h in args["forward_horizons"]]
        if event_index < 0:
            event_index = len(bars) + event_index
        if event_index < 0 or event_index >= len(bars):
            raise IndexError("event_index outside bars")
        base = float(bars[event_index]["close"])
        returns = {}
        for h in horizons:
            idx = event_index + h
            returns[str(h)] = None if idx >= len(bars) else round(
                (float(bars[idx]["close"]) / base - 1.0) * 100.0, 6
            )
        return {
            "event_timestamp": bars[event_index]["timestamp"],
            "event_close": base,
            "forward_return_pct": returns,
        }

    @staticmethod
    def _sma(values: list[float], period: int) -> list[Any]:
        out = []
        for i in range(len(values)):
            if i + 1 < period:
                out.append(None)
            else:
                out.append(sum(values[i - period + 1:i + 1]) / period)
        return out

    @staticmethod
    def _ema(values: list[float], period: int) -> list[Any]:
        if not values:
            return []
        alpha = 2.0 / (period + 1.0)
        out = [values[0]]
        for value in values[1:]:
            out.append(alpha * value + (1 - alpha) * out[-1])
        return out

    @staticmethod
    def _rsi(values: list[float], period: int) -> list[Any]:
        if len(values) < 2:
            return [None] * len(values)
        gains = [0.0]
        losses = [0.0]
        for prev, cur in zip(values, values[1:]):
            delta = cur - prev
            gains.append(max(delta, 0.0))
            losses.append(max(-delta, 0.0))
        out = [None] * len(values)
        for i in range(period, len(values)):
            avg_gain = sum(gains[i - period + 1:i + 1]) / period
            avg_loss = sum(losses[i - period + 1:i + 1]) / period
            if avg_loss == 0:
                out[i] = 100.0
            else:
                rs = avg_gain / avg_loss
                out[i] = 100.0 - 100.0 / (1.0 + rs)
        return out

    @staticmethod
    def _ichimoku(highs: list[float], lows: list[float]) -> dict:
        def midpoint(period: int) -> list[Any]:
            out = []
            for i in range(len(highs)):
                if i + 1 < period:
                    out.append(None)
                else:
                    h = max(highs[i - period + 1:i + 1])
                    l = min(lows[i - period + 1:i + 1])
                    out.append((h + l) / 2.0)
            return out
        tenkan = midpoint(9)
        kijun = midpoint(26)
        span_b_raw = midpoint(52)
        span_a = [
            None if t is None or k is None else (t + k) / 2.0
            for t, k in zip(tenkan, kijun)
        ]
        return {
            "ICHIMOKU_TENKAN": tenkan,
            "ICHIMOKU_KIJUN": kijun,
            "ICHIMOKU_SPAN_A_RAW": span_a,
            "ICHIMOKU_SPAN_B_RAW": span_b_raw,
        }


def install_chart_workstation(
    registry: ToolRegistry,
    employee_id: str,
    market: MarketDataPlane,
) -> None:
    engine = TechnicalEngine()
    tools = [
        (ToolDefinition(
            "market.catalog",
            "Discover symbols and OHLCV timeframes actually available from the authorized market-data plane.",
            {"required": []}, True, "READ_ONLY",
        ), market.catalog),
        (ToolDefinition(
            "market.ohlcv",
            "Retrieve OHLCV for a symbol/timeframe/date window. Fails explicitly if coverage is unavailable.",
            {"required": ["symbol", "timeframe"]}, True, "READ_ONLY",
        ), market.ohlcv),
        (ToolDefinition(
            "market.event_scan",
            "Scan available symbols for generic return and volume events over a configurable lookback.",
            {"required": ["timeframe", "lookback_bars"]}, True, "COMPUTE",
        ), market.event_scan),
        (ToolDefinition(
            "technical.indicators",
            "Calculate requested deterministic technical indicators over supplied OHLCV bars.",
            {"required": ["bars", "indicators"]}, True, "COMPUTE",
        ), engine.indicators),
        (ToolDefinition(
            "chart.candlestick_spec",
            "Build a renderer-neutral candlestick chart specification with overlays and annotations.",
            {"required": ["symbol", "timeframe", "bars"]}, True, "ARTIFACT_WRITE",
        ), engine.chart_spec),
        (ToolDefinition(
            "technical.event_study",
            "Calculate forward returns from a chosen event bar for configurable horizons.",
            {"required": ["bars", "event_index", "forward_horizons"]}, True, "COMPUTE",
        ), engine.event_study),
    ]
    for definition, handler in tools:
        registry.register(definition, handler)
        registry.grant(employee_id, definition.name)


def synthetic_chart_bars() -> dict[tuple[str, str], list[dict]]:
    def series(symbol_seed: float, n: int, jump: float = 0.0) -> list[dict]:
        rows = []
        price = symbol_seed
        for i in range(n):
            drift = 0.35 + (i % 5 - 2) * 0.08
            if i == n - 1:
                drift += jump
            open_ = price
            close = max(1.0, open_ + drift)
            high = max(open_, close) + 0.4
            low = min(open_, close) - 0.35
            volume = 1000 + i * 12
            if i == n - 1 and jump:
                volume *= 4
            rows.append({
                "timestamp": f"2026-01-{i + 1:02d}" if i < 31 else f"2026-02-{i - 30:02d}",
                "open": round(open_, 4),
                "high": round(high, 4),
                "low": round(low, 4),
                "close": round(close, 4),
                "volume": volume,
            })
            price = close
        return rows

    return {
        ("KRX001", "D"): series(50.0, 55, jump=8.0),
        ("KRX002", "D"): series(70.0, 55, jump=-0.2),
        ("KRX003", "D"): series(40.0, 55, jump=5.0),
        ("KRX001", "60m"): series(52.0, 30, jump=2.0),
    }
