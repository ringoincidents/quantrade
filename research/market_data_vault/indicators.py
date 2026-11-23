"""Reusable deterministic indicators for OFFLINE RESEARCH ONLY.

Inputs are oldest->newest, 1 value per completed bar (no future data).
Not production FeatureProvider, risk decision or trading signal.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

LIBRARY_VERSION = "market_data_vault.indicators.v0.1"


def _prices(values: Sequence[float]) -> list[float]:
    p = [float(x) for x in values]
    if not p or any(not math.isfinite(x) or x <= 0 for x in p):
        raise ValueError("Finite positive price data required; no silent forward fill")
    return p


def _window(period: int) -> int:
    if not isinstance(period, int) or isinstance(period, bool) or period < 1:
        raise ValueError("Period must be a positive integer")
    return period


def sma(values: Sequence[float], period: int) -> list[float | None]:
    """Trailing simple moving average, first non-null at period-1."""
    p = _prices(values)
    n = _window(period)
    result: list[float | None] = []
    window_sum = 0.0
    for i, x in enumerate(p):
        window_sum += x
        if i >= n:
            window_sum -= p[i - n]
        result.append(window_sum / n if i >= n - 1 else None)
    return result


def ema(values: Sequence[float], period: int) -> list[float | None]:
    """EMA alpha=2/(period+1), initial value=first period SMA; no hindsight."""
    p = _prices(values)
    n = _window(period)
    result: list[float | None] = [None] * len(p)
    if len(p) < n:
        return result
    result[n - 1] = sum(p[:n]) / n
    alpha = 2.0 / (n + 1)
    for i in range(n, len(p)):
        result[i] = alpha * p[i] + (1 - alpha) * result[i - 1]
    return result


def rsi_wilder(values: Sequence[float], period: int = 14) -> list[float | None]:
    """Wilder RSI, seeded by mean of first N changes (first index N).

    When both avg gains/losses are zero RSI is neutral (50), rising-only=100,
    falling-only=0. Historical indicator_significance_test.rolling_rsi
    returns 100 for fully flat observations: deliberately DIFFERENT here;
    a future canonical-library migration requires a parity decision and tests.
    """
    p = _prices(values)
    n = _window(period)
    result: list[float | None] = [None] * len(p)
    if len(p) <= n:
        return result
    diffs = [p[i] - p[i - 1] for i in range(1, len(p))]
    avg_up = sum(max(d, 0) for d in diffs[:n]) / n
    avg_down = sum(max(-d, 0) for d in diffs[:n]) / n

    def value(up: float, down: float) -> float:
        if up == 0 and down == 0:
            return 50.0
        if down == 0:
            return 100.0
        if up == 0:
            return 0.0
        rs = up / down
        return 100 - (100 / (1 + rs))

    result[n] = value(avg_up, avg_down)
    for i in range(n + 1, len(p)):
        d = diffs[i - 1]
        avg_up = (avg_up * (n - 1) + max(d, 0)) / n
        avg_down = (avg_down * (n - 1) + max(-d, 0)) / n
        result[i] = value(avg_up, avg_down)
    return result


def atr_wilder(highs: Sequence[float], lows: Sequence[float],
               closes: Sequence[float], period: int = 14) -> list[float | None]:
    """Wilder ATR. First true range=high-low; seed mean of first period TRs.

    Older indicator_significance_test.rolling_atr is SMA(TR); this
    implementation intentionally uses Wilder smoothing and has a new name.
    """
    n = _window(period)
    h, l, c = map(_prices, (highs, lows, closes))
    if len(h) != len(l) or len(h) != len(c) or any(
        lo > min(hi, cl) or hi < max(lo, cl)
        for hi, lo, cl in zip(h, l, c)
    ):
        raise ValueError("Invalid or misaligned OHLC arrays")
    tr = []
    for i in range(len(c)):
        previous = c[i-1] if i else c[i]
        tr.append(max(h[i] - l[i], abs(h[i] - previous),
                      abs(l[i] - previous)))
    result: list[float | None] = [None] * len(c)
    if len(c) < n:
        return result
    result[n - 1] = sum(tr[:n]) / n
    for i in range(n, len(c)):
        result[i] = ((n-1)*result[i-1] + tr[i]) / n
    return result


INDICATOR_CATALOG = {
    "SMA:v1": {"formula": "trailing arithmetic mean", "input": "close", "function": sma.__name__},
    "EMA:SMA_SEED:v1": {"formula": "alpha=2/(N+1), SMA seed", "input": "close", "function": ema.__name__},
    "RSI:WILDER_NEUTRAL_FLAT:v1": {"formula": "Wilder smoothing; flat=50", "input": "close", "function": rsi_wilder.__name__},
    "ATR:WILDER:v1": {"formula": "Wilder true range; seed first N", "input": "high,low,close", "function": atr_wilder.__name__},
}
