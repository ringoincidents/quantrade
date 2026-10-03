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



class MarketStateCompiler:
    """Compress OHLCV into deterministic, LLM-friendly market state.

    This is a calculator, not a strategy. It describes the current market
    structure so AI employees can reason over a small structured payload
    instead of repeatedly interpreting raw chart images.
    """

    DEFAULT_INDICATORS = (
        {"name": "SMA", "period": 20},
        {"name": "SMA", "period": 50},
        {"name": "EMA", "period": 12},
        {"name": "EMA", "period": 26},
        {"name": "RSI", "period": 14},
        {"name": "BOLLINGER", "period": 20, "stddev": 2.0},
        {"name": "ATR", "period": 14},
        {"name": "ICHIMOKU"},
    )

    @staticmethod
    def _pct_change(start: float, end: float) -> float | None:
        if start == 0:
            return None
        return (end / start - 1.0) * 100.0

    @staticmethod
    def _last_valid(series: list[Any]) -> float | None:
        for value in reversed(series):
            if value is not None:
                return float(value)
        return None

    @staticmethod
    def _std(values: list[float]) -> float | None:
        if len(values) < 2:
            return None
        m = sum(values) / len(values)
        return math.sqrt(sum((x - m) ** 2 for x in values) / len(values))

    @classmethod
    def compile(cls, args: dict) -> dict:
        bars = args["bars"]
        if len(bars) < 2:
            raise ValueError("market state requires at least 2 OHLCV bars")

        closes = [float(b["close"]) for b in bars]
        opens = [float(b["open"]) for b in bars]
        highs = [float(b["high"]) for b in bars]
        lows = [float(b["low"]) for b in bars]
        volumes = [float(b["volume"]) for b in bars]
        latest = bars[-1]
        latest_open = opens[-1]
        latest_close = closes[-1]
        latest_high = highs[-1]
        latest_low = lows[-1]

        indicators = TechnicalEngine.indicators({
            "bars": bars,
            "indicators": list(args.get("indicators") or cls.DEFAULT_INDICATORS),
        })["series"]

        ema12 = cls._last_valid(indicators.get("EMA_12", []))
        ema26 = cls._last_valid(indicators.get("EMA_26", []))
        macd_line = None if ema12 is None or ema26 is None else ema12 - ema26

        # Compute MACD signal from the full EMA spread when available.
        ema12_series = indicators.get("EMA_12", [])
        ema26_series = indicators.get("EMA_26", [])
        spread_series = [
            float(a) - float(b)
            for a, b in zip(ema12_series, ema26_series)
            if a is not None and b is not None
        ]
        macd_signal = (
            TechnicalEngine._ema(spread_series, 9)[-1]
            if spread_series
            else None
        )
        macd_hist = (
            None if macd_line is None or macd_signal is None
            else macd_line - macd_signal
        )

        returns: dict[str, float | None] = {}
        for lookback in (1, 3, 5, 10, 20):
            returns[f"{lookback}_bar_pct"] = (
                cls._pct_change(closes[-lookback - 1], latest_close)
                if len(closes) > lookback
                else None
            )

        recent_returns = [
            math.log(cur / prev)
            for prev, cur in zip(closes[-21:-1], closes[-20:])
            if prev > 0 and cur > 0
        ]
        realized_vol_20_pct = cls._std(recent_returns)
        if realized_vol_20_pct is not None:
            realized_vol_20_pct *= 100.0

        prior_volumes = volumes[-21:-1] if len(volumes) >= 21 else volumes[:-1]
        avg_volume = mean(prior_volumes) if prior_volumes else 0.0
        volume_multiple = volumes[-1] / avg_volume if avg_volume else None

        candle_range = max(0.0, latest_high - latest_low)
        body = latest_close - latest_open
        upper_wick = latest_high - max(latest_open, latest_close)
        lower_wick = min(latest_open, latest_close) - latest_low
        body_fraction = abs(body) / candle_range if candle_range else 0.0
        labels: list[str] = []
        if body > 0:
            labels.append("BULLISH")
        elif body < 0:
            labels.append("BEARISH")
        else:
            labels.append("FLAT")
        if body_fraction <= 0.1:
            labels.append("DOJI_LIKE")
        if candle_range and upper_wick / candle_range >= 0.55:
            labels.append("LONG_UPPER_WICK")
        if candle_range and lower_wick / candle_range >= 0.55:
            labels.append("LONG_LOWER_WICK")

        sma20 = cls._last_valid(indicators.get("SMA_20", []))
        sma50 = cls._last_valid(indicators.get("SMA_50", []))
        rsi14 = cls._last_valid(indicators.get("RSI_14", []))
        atr14 = cls._last_valid(indicators.get("ATR_14", []))
        bb_mid = cls._last_valid(indicators.get("BB_MID_20", []))
        bb_upper = cls._last_valid(indicators.get("BB_UPPER_20", []))
        bb_lower = cls._last_valid(indicators.get("BB_LOWER_20", []))

        if sma20 is not None and sma50 is not None:
            if latest_close > sma20 > sma50:
                trend = "UPTREND"
            elif latest_close < sma20 < sma50:
                trend = "DOWNTREND"
            else:
                trend = "MIXED"
        else:
            trend = "INSUFFICIENT_HISTORY"

        bb_position = None
        if (
            bb_lower is not None
            and bb_upper is not None
            and bb_upper > bb_lower
        ):
            bb_position = (latest_close - bb_lower) / (bb_upper - bb_lower)

        recent_high = max(highs[-20:]) if highs else None
        recent_low = min(lows[-20:]) if lows else None

        return {
            "schema": "quantrade_market_state_v1",
            "symbol": args.get("symbol"),
            "timeframe": args.get("timeframe"),
            "timestamp": latest.get("timestamp"),
            "bar_count": len(bars),
            "price": {
                "open": latest_open,
                "high": latest_high,
                "low": latest_low,
                "close": latest_close,
            },
            "returns": returns,
            "trend": {
                "regime": trend,
                "sma20": sma20,
                "sma50": sma50,
                "ema12": ema12,
                "ema26": ema26,
                "macd": macd_line,
                "macd_signal": macd_signal,
                "macd_histogram": macd_hist,
            },
            "momentum": {
                "rsi14": rsi14,
                "bollinger_position_0_to_1": bb_position,
            },
            "volatility": {
                "atr14": atr14,
                "atr14_pct_of_price": (
                    atr14 / latest_close * 100.0
                    if atr14 is not None and latest_close
                    else None
                ),
                "realized_log_return_std_20_pct": realized_vol_20_pct,
            },
            "volume": {
                "latest": volumes[-1],
                "average_prior": avg_volume or None,
                "multiple": volume_multiple,
            },
            "levels": {
                "recent_high_20": recent_high,
                "recent_low_20": recent_low,
                "distance_to_high_20_pct": (
                    cls._pct_change(latest_close, recent_high)
                    if recent_high is not None
                    else None
                ),
                "distance_to_low_20_pct": (
                    cls._pct_change(latest_close, recent_low)
                    if recent_low is not None
                    else None
                ),
            },
            "candle": {
                "body_pct_of_open": (
                    body / latest_open * 100.0 if latest_open else None
                ),
                "range_pct_of_open": (
                    candle_range / latest_open * 100.0 if latest_open else None
                ),
                "upper_wick_fraction": (
                    upper_wick / candle_range if candle_range else None
                ),
                "lower_wick_fraction": (
                    lower_wick / candle_range if candle_range else None
                ),
                "labels": labels,
            },
            "ichimoku": {
                "tenkan": cls._last_valid(
                    indicators.get("ICHIMOKU_TENKAN", [])
                ),
                "kijun": cls._last_valid(
                    indicators.get("ICHIMOKU_KIJUN", [])
                ),
                "span_a_raw": cls._last_valid(
                    indicators.get("ICHIMOKU_SPAN_A_RAW", [])
                ),
                "span_b_raw": cls._last_valid(
                    indicators.get("ICHIMOKU_SPAN_B_RAW", [])
                ),
            },
            "interpretation_policy": (
                "Deterministic measurements only. This state is not a buy/sell "
                "recommendation and does not establish predictive edge."
            ),
        }


class AICallGate:
    """Cheap deterministic gate that decides whether AI review is warranted."""

    @staticmethod
    def evaluate(args: dict) -> dict:
        state = args["market_state"]
        mandate = args.get("mandate_state") or {}
        research = args.get("research_state") or {}
        portfolio = args.get("portfolio_state") or {}

        reasons: list[str] = []
        required_offices: list[str] = []
        call_type = "NONE"

        one_bar = state.get("returns", {}).get("1_bar_pct")
        five_bar = state.get("returns", {}).get("5_bar_pct")
        volume_multiple = state.get("volume", {}).get("multiple")
        rsi = state.get("momentum", {}).get("rsi14")
        trend = state.get("trend", {}).get("regime")
        prior_trend = args.get("previous_market_state", {}).get(
            "trend", {}
        ).get("regime")

        if mandate.get("planning_conflicts"):
            reasons.append("CLIENT_MANDATE_CONFLICT")
            required_offices.extend(["CCO", "SPMG"])
            call_type = "CLIENT_STRATEGY_REVIEW"

        if portfolio.get("risk_policy_breach"):
            reasons.append("RISK_POLICY_BREACH")
            required_offices.append("IPRO")
            call_type = "FAST_RISK_REVIEW"

        if one_bar is not None and abs(float(one_bar)) >= float(
            args.get("shock_1bar_pct", 2.0)
        ):
            reasons.append("PRICE_SHOCK_1_BAR")
            required_offices.append("IPRO")
            call_type = "FAST_RISK_REVIEW"

        if (
            five_bar is not None
            and abs(float(five_bar)) >= float(args.get("material_5bar_pct", 4.0))
            and volume_multiple is not None
            and float(volume_multiple) >= float(args.get("volume_multiple", 2.0))
        ):
            reasons.append("PRICE_VOLUME_REGIME_EVENT")
            required_offices.extend(["SPMG", "IPRO"])
            if call_type == "NONE":
                call_type = "FULL_INVESTMENT_REVIEW"

        if rsi is not None and (float(rsi) >= 80.0 or float(rsi) <= 20.0):
            reasons.append("MOMENTUM_EXTREME")
            required_offices.append("SPMG")
            if call_type == "NONE":
                call_type = "FULL_INVESTMENT_REVIEW"

        if prior_trend and trend and prior_trend != trend:
            reasons.append("TREND_REGIME_CHANGE")
            required_offices.append("SPMG")
            if call_type == "NONE":
                call_type = "FULL_INVESTMENT_REVIEW"

        if research.get("material_update"):
            reasons.append("MATERIAL_RESEARCH_UPDATE")
            required_offices.extend(["SPMG", "IPRO"])
            if call_type == "NONE":
                call_type = "FULL_INVESTMENT_REVIEW"

        if portfolio.get("material_allocation_gap"):
            reasons.append("MATERIAL_ALLOCATION_GAP")
            required_offices.extend(["SPMG", "IPRO"])
            if call_type == "NONE":
                call_type = "FULL_INVESTMENT_REVIEW"

        required_offices = list(dict.fromkeys(required_offices))
        return {
            "schema": "quantrade_ai_call_gate_v1",
            "call_ai": call_type != "NONE",
            "call_type": call_type,
            "reasons": reasons,
            "required_offices": required_offices,
            "market_timestamp": state.get("timestamp"),
            "policy": (
                "The gate discovers review work only. It cannot approve or execute "
                "a trade and it cannot raise client risk limits."
            ),
        }


def install_chart_workstation(
    registry: ToolRegistry,
    employee_id: str,
    market: MarketDataPlane,
) -> None:
    engine = TechnicalEngine()
    market_state = MarketStateCompiler()
    ai_gate = AICallGate()
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
        (ToolDefinition(
            "technical.market_state",
            "Compress OHLCV into deterministic LLM-friendly price, trend, momentum, volatility, volume, level and candle features.",
            {"required": ["bars"]}, True, "COMPUTE",
        ), market_state.compile),
        (ToolDefinition(
            "ai.call_gate",
            "Deterministically decide whether current market/client/research/portfolio state warrants AI review; never decides or executes a trade.",
            {"required": ["market_state"]}, True, "COMPUTE",
        ), ai_gate.evaluate),
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
