"""QT-STRAT-005 pre-registered multi-stock KRX transfer Golden Run.

Frozen definition:
research/experiments/QT-STRAT-005_PRE_REGISTRATION.md

The runner evaluates the unchanged QT-STRAT-004 candidate families across a
new five-stock KRX scope. Selection uses TRAIN + VALIDATION only. TEST metrics
are computed only for candidates selected before TEST is opened.

No model, broker, portfolio mutation, strategy promotion, or execution path is
present.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
from statistics import median
from typing import Iterable

import requests

from quantrade.capabilities.review_gate import ReviewEvent, evaluate_review_need
from quantrade.capabilities.strategy_candidates import (
    CandidateGenerationContext,
    StaticCandidateProvider,
    compile_position_signals,
)
from quantrade.capabilities.strategy_research import (
    CandidateStrategy,
    DatasetMetadata,
    PositionSignal,
    PriceBar,
    ScreeningPolicy,
    evaluate_strategy,
)
from quantrade.capabilities.strategy_robustness import (
    SpecialistReviewContext,
    build_specialist_work,
    signal_similarity,
)


EXPERIMENT_ID = "QT-STRAT-005"
PREREGISTRATION_COMMIT = "7ea6d1b101cda4e635a2678d96a3b127ad6bb9fc"
SYMBOLS = ("000660", "207940", "005380", "005490", "006400")
MARKET_SCOPE = "KRX:TRANSFER-BASKET-005"
START_DATE = "2022-01-03"
END_DATE = "2026-09-30"
TRANSACTION_COST_BPS = 20.5
PERIODS_PER_YEAR = 252
SIMILARITY_THRESHOLD = 0.95
TOP_K = 2

PARTITIONS = {
    "train": ("2022-01-03", "2024-12-31"),
    "validation": ("2025-01-01", "2025-12-31"),
    "test": ("2026-01-01", "2026-09-30"),
}

RESULT_PATH = Path("research/experiments/QT-STRAT-005_RESULT.json")
DATASET_PATH = Path("research/experiments/QT-STRAT-005_DATASET.json")

NAVER_ENDPOINT = "https://api.finance.naver.com/siseJson.naver"
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; quantrade-bot/1.0)"}


def frozen_candidates() -> tuple[CandidateStrategy, ...]:
    return (
        CandidateStrategy(
            candidate_id="CAND-SMA-5-20",
            name="SMA 5/20 trend",
            source_type="PRE_REGISTERED_STATIC",
            source_ref="QT-STRAT-005_PRE_REGISTRATION",
            market_scope=MARKET_SCOPE,
            rebalance_horizon="DAILY",
            formula_ast={
                "op": "GT",
                "left": {"op": "SMA", "window": 5},
                "right": {"op": "SMA", "window": 20},
            },
            parameter_set={"short_window": 5, "long_window": 20},
        ),
        CandidateStrategy(
            candidate_id="CAND-SMA-20-60",
            name="SMA 20/60 trend",
            source_type="PRE_REGISTERED_STATIC",
            source_ref="QT-STRAT-005_PRE_REGISTRATION",
            market_scope=MARKET_SCOPE,
            rebalance_horizon="DAILY",
            formula_ast={
                "op": "GT",
                "left": {"op": "SMA", "window": 20},
                "right": {"op": "SMA", "window": 60},
            },
            parameter_set={"short_window": 20, "long_window": 60},
        ),
        CandidateStrategy(
            candidate_id="CAND-MOM-20",
            name="20-day momentum",
            source_type="PRE_REGISTERED_STATIC",
            source_ref="QT-STRAT-005_PRE_REGISTRATION",
            market_scope=MARKET_SCOPE,
            rebalance_horizon="DAILY",
            formula_ast={
                "op": "GT",
                "left": {"op": "RETURN", "window": 20},
                "right": {"op": "CONST", "value": 0.0},
            },
            parameter_set={"return_window": 20, "threshold": 0.0},
        ),
        CandidateStrategy(
            candidate_id="CAND-ZSCORE-MR-20",
            name="20-day z-score mean reversion",
            source_type="PRE_REGISTERED_STATIC",
            source_ref="QT-STRAT-005_PRE_REGISTRATION",
            market_scope=MARKET_SCOPE,
            rebalance_horizon="DAILY",
            formula_ast={
                "op": "LT",
                "left": {"op": "ZSCORE", "window": 20},
                "right": {"op": "CONST", "value": -1.0},
            },
            parameter_set={"zscore_window": 20, "threshold": -1.0},
        ),
    )


def fetch_symbol(symbol: str) -> tuple[list[dict], dict]:
    params = {
        "symbol": symbol,
        "requestType": 1,
        "startTime": START_DATE.replace("-", ""),
        "endTime": END_DATE.replace("-", ""),
        "timeframe": "day",
    }
    response = requests.get(
        NAVER_ENDPOINT,
        params=params,
        timeout=20,
        headers=HTTP_HEADERS,
    )
    response.raise_for_status()
    rows = re.findall(
        r"\[[\"'](\d{8})[\"'],\s*([\-\d.]+),\s*([\-\d.]+),\s*"
        r"([\-\d.]+),\s*([\-\d.]+),\s*([\-\d.]+)",
        response.text,
    )
    if not rows:
        raise RuntimeError(
            f"{symbol}: no parseable OHLCV rows in historical response"
        )
    parsed = [
        {
            "date": f"{row[0][:4]}-{row[0][4:6]}-{row[0][6:8]}",
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5]),
        }
        for row in rows
    ]
    dates = [item["date"] for item in parsed]
    if len(dates) != len(set(dates)):
        raise RuntimeError(f"{symbol}: duplicate dates")
    if dates != sorted(dates):
        raise RuntimeError(f"{symbol}: dates not strictly increasing")
    if any(item["close"] <= 0 for item in parsed):
        raise RuntimeError(f"{symbol}: non-positive close")
    if parsed[0]["date"] < START_DATE or parsed[-1]["date"] > END_DATE:
        raise RuntimeError(f"{symbol}: dataset escaped frozen date range")

    canonical = json.dumps(
        parsed,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    return parsed, {
        "symbol": symbol,
        "endpoint": NAVER_ENDPOINT,
        "params": params,
        "http_status": response.status_code,
        "row_count": len(parsed),
        "first_trading_date": parsed[0]["date"],
        "last_trading_date": parsed[-1]["date"],
        "strictly_increasing_dates": True,
        "duplicate_dates": False,
        "non_positive_close_count": 0,
        "sha256": digest,
    }


def to_price_bars(rows: list[dict]) -> list[PriceBar]:
    return [
        PriceBar(
            observed_at=f"{row['date']}T15:30:00+09:00",
            close=float(row["close"]),
        )
        for row in rows
    ]


def lag_one_bar(
    compiled: tuple[PositionSignal, ...],
    bars: list[PriceBar],
) -> tuple[PositionSignal, ...]:
    if len(compiled) != len(bars) - 1:
        raise RuntimeError("compiled signal/bar length mismatch")
    lagged = []
    for index in range(len(compiled)):
        if index == 0:
            target = 0.0
            cutoff = bars[0].observed_at
        else:
            target = compiled[index - 1].target_position
            cutoff = bars[index - 1].observed_at
        lagged.append(
            PositionSignal(
                effective_at=bars[index].observed_at,
                information_cutoff=cutoff,
                target_position=target,
            )
        )
    return tuple(lagged)


def always_long_signals(bars: list[PriceBar]) -> tuple[PositionSignal, ...]:
    return tuple(
        PositionSignal(
            effective_at=bars[index].observed_at,
            information_cutoff=bars[index].observed_at,
            target_position=1.0,
        )
        for index in range(len(bars) - 1)
    )


def bar_date(bar: PriceBar) -> str:
    return bar.observed_at[:10]


def partition_slice(
    bars: list[PriceBar],
    signals: tuple[PositionSignal, ...],
    partition_name: str,
) -> tuple[list[PriceBar], tuple[PositionSignal, ...]]:
    start, end = PARTITIONS[partition_name]
    indices = [
        index
        for index in range(len(bars) - 1)
        if start <= bar_date(bars[index]) <= end
        and start <= bar_date(bars[index + 1]) <= end
    ]
    if not indices:
        raise RuntimeError(f"partition {partition_name} has no return periods")
    if indices != list(range(indices[0], indices[-1] + 1)):
        raise RuntimeError(f"partition {partition_name} is not contiguous")
    first, last = indices[0], indices[-1]
    return bars[first : last + 2], signals[first : last + 1]


def dataset_metadata(
    symbol: str,
    digest: str,
    bars: list[PriceBar],
    partition_name: str,
) -> DatasetMetadata:
    return DatasetMetadata(
        dataset_id=(
            f"{EXPERIMENT_ID}:{symbol}:{partition_name}:{digest[:12]}"
        ),
        source=NAVER_ENDPOINT,
        provider="naver-finance-historical",
        version_or_revision="requestType=1;timeframe=day",
        as_of_start=bars[0].observed_at,
        as_of_end=bars[-1].observed_at,
        point_in_time=True,
        point_in_time_evidence_ref=f"sha256:{digest}",
    )


def evaluate_partition(
    symbol: str,
    candidate: CandidateStrategy,
    bars: list[PriceBar],
    signals: tuple[PositionSignal, ...],
    digest: str,
    partition_name: str,
) -> dict:
    part_bars, part_signals = partition_slice(
        bars,
        signals,
        partition_name,
    )
    result = evaluate_strategy(
        candidate,
        part_bars,
        part_signals,
        dataset_metadata(symbol, digest, part_bars, partition_name),
        transaction_cost_bps=TRANSACTION_COST_BPS,
        charge_terminal_liquidation=True,
        periods_per_year=PERIODS_PER_YEAR,
        screening_policy=ScreeningPolicy(
            min_return_periods=1,
            max_drawdown_pct=-100.0,
            min_benchmark_excess_return_pct=-100.0,
            max_turnover_per_period=None,
        ),
    )
    return asdict(result)


def median_non_null(values: Iterable[float | None]) -> float | None:
    usable = [
        float(value)
        for value in values
        if value is not None
    ]
    return median(usable) if usable else None


def aggregate_partition(
    per_stock: dict[str, dict],
    controls: dict[str, dict],
) -> dict:
    symbols = list(SYMBOLS)
    excesses = []
    beats = 0
    for symbol in symbols:
        candidate_net = float(
            per_stock[symbol]["metrics"]["net_total_return_pct"]
        )
        control_net = float(
            controls[symbol]["metrics"]["net_total_return_pct"]
        )
        excess = candidate_net - control_net
        excesses.append(excess)
        if candidate_net > control_net:
            beats += 1

    sharpe_median = median_non_null(
        per_stock[symbol]["metrics"]["sharpe"]
        for symbol in symbols
    )
    return {
        "stock_count": len(symbols),
        "median_net_return_pct": round(
            median(
                float(per_stock[s]["metrics"]["net_total_return_pct"])
                for s in symbols
            ),
            6,
        ),
        "median_sharpe": (
            None if sharpe_median is None else round(sharpe_median, 6)
        ),
        "median_turnover_per_period": round(
            median(
                float(per_stock[s]["metrics"]["turnover_per_period"])
                for s in symbols
            ),
            6,
        ),
        "worst_maximum_drawdown_pct": round(
            min(
                float(per_stock[s]["metrics"]["maximum_drawdown_pct"])
                for s in symbols
            ),
            6,
        ),
        "stocks_beating_cost_adjusted_control": beats,
        "median_excess_vs_control_pct": round(median(excesses), 6),
        "per_stock_excess_vs_control_pct": {
            symbol: round(excess, 6)
            for symbol, excess in zip(symbols, excesses)
        },
    }


def stage_a_criteria(
    train_by_stock: dict[str, dict],
    validation_summary: dict,
) -> dict:
    train_counts_ok = all(
        train_by_stock[symbol]["metrics"]["return_periods"] >= 200
        for symbol in SYMBOLS
    )
    validation_counts_ok = all(
        validation_summary["per_stock_return_periods"][symbol] >= 100
        for symbol in SYMBOLS
    )
    checks = {
        "all_five_train_return_periods_gte_200": train_counts_ok,
        "all_five_validation_return_periods_gte_100": validation_counts_ok,
        "validation_beats_control_on_at_least_3_of_5": (
            validation_summary["stocks_beating_cost_adjusted_control"] >= 3
        ),
        "validation_median_excess_gt_0": (
            validation_summary["median_excess_vs_control_pct"] > 0
        ),
        "validation_median_sharpe_gt_0": (
            validation_summary["median_sharpe"] is not None
            and validation_summary["median_sharpe"] > 0
        ),
        "validation_worst_mdd_gte_minus_30": (
            validation_summary["worst_maximum_drawdown_pct"] >= -30.0
        ),
        "validation_median_turnover_lte_0_25": (
            validation_summary["median_turnover_per_period"] <= 0.25
        ),
    }
    return {
        "checks": checks,
        "eligible": all(checks.values()),
    }


def stage_b_criteria(test_summary: dict) -> dict:
    checks = {
        "all_five_test_return_periods_gte_100": all(
            test_summary["per_stock_return_periods"][symbol] >= 100
            for symbol in SYMBOLS
        ),
        "test_beats_control_on_at_least_3_of_5": (
            test_summary["stocks_beating_cost_adjusted_control"] >= 3
        ),
        "test_median_excess_gt_0": (
            test_summary["median_excess_vs_control_pct"] > 0
        ),
        "test_median_sharpe_gt_0": (
            test_summary["median_sharpe"] is not None
            and test_summary["median_sharpe"] > 0
        ),
        "test_worst_mdd_gte_minus_30": (
            test_summary["worst_maximum_drawdown_pct"] >= -30.0
        ),
        "test_median_turnover_lte_0_25": (
            test_summary["median_turnover_per_period"] <= 0.25
        ),
    }
    return {
        "checks": checks,
        "test_confirmed": all(checks.values()),
    }


def selection_key(record: dict) -> tuple[float, float, float, float, str]:
    summary = record["validation_summary"]
    return (
        float(summary["stocks_beating_cost_adjusted_control"]),
        float(summary["median_excess_vs_control_pct"]),
        (
            float(summary["median_sharpe"])
            if summary["median_sharpe"] is not None
            else float("-inf")
        ),
        -float(summary["median_turnover_per_period"]),
        record["candidate"]["candidate_id"],
    )


def concatenated_pretest_positions(
    signal_map: dict[str, dict[str, tuple[PositionSignal, ...]]],
    candidate_id: str,
    bars_by_symbol: dict[str, list[PriceBar]],
) -> tuple[float, ...]:
    values: list[float] = []
    for symbol in SYMBOLS:
        signals = signal_map[candidate_id][symbol]
        _, train = partition_slice(
            bars_by_symbol[symbol],
            signals,
            "train",
        )
        _, validation = partition_slice(
            bars_by_symbol[symbol],
            signals,
            "validation",
        )
        values.extend(signal.target_position for signal in train)
        values.extend(signal.target_position for signal in validation)
    return tuple(values)


def add_return_periods(
    summary: dict,
    per_stock: dict[str, dict],
) -> dict:
    output = dict(summary)
    output["per_stock_return_periods"] = {
        symbol: int(per_stock[symbol]["metrics"]["return_periods"])
        for symbol in SYMBOLS
    }
    return output


def run() -> dict:
    rows_by_symbol: dict[str, list[dict]] = {}
    source_meta: dict[str, dict] = {}
    bars_by_symbol: dict[str, list[PriceBar]] = {}

    for symbol in SYMBOLS:
        rows, meta = fetch_symbol(symbol)
        rows_by_symbol[symbol] = rows
        source_meta[symbol] = meta
        bars_by_symbol[symbol] = to_price_bars(rows)

    basket_hash_payload = [
        {
            "symbol": symbol,
            "sha256": source_meta[symbol]["sha256"],
        }
        for symbol in SYMBOLS
    ]
    basket_hash = hashlib.sha256(
        json.dumps(
            basket_hash_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    controls: dict[str, dict[str, dict]] = {
        partition: {}
        for partition in PARTITIONS
    }
    for symbol in SYMBOLS:
        bars = bars_by_symbol[symbol]
        signals = always_long_signals(bars)
        control = CandidateStrategy(
            candidate_id=f"CONTROL-BUY-HOLD-{symbol}",
            name=f"Cost-adjusted buy and hold control {symbol}",
            source_type="PRE_REGISTERED_CONTROL",
            source_ref="QT-STRAT-005_PRE_REGISTRATION",
            market_scope=f"KRX:{symbol}",
            rebalance_horizon="DAILY",
        )
        for partition in PARTITIONS:
            controls[partition][symbol] = evaluate_partition(
                symbol,
                control,
                bars,
                signals,
                source_meta[symbol]["sha256"],
                partition,
            )

    provider = StaticCandidateProvider(frozen_candidates())
    candidates = provider.generate(
        CandidateGenerationContext(
            market_scope=MARKET_SCOPE,
            rebalance_horizon="DAILY",
        )
    )

    signal_map: dict[
        str,
        dict[str, tuple[PositionSignal, ...]],
    ] = {}
    records = []

    for candidate in candidates:
        train_by_stock: dict[str, dict] = {}
        validation_by_stock: dict[str, dict] = {}
        signal_map[candidate.candidate_id] = {}

        for symbol in SYMBOLS:
            bars = bars_by_symbol[symbol]
            immediate = compile_position_signals(candidate, bars)
            lagged = lag_one_bar(immediate, bars)
            signal_map[candidate.candidate_id][symbol] = lagged
            train_by_stock[symbol] = evaluate_partition(
                symbol,
                candidate,
                bars,
                lagged,
                source_meta[symbol]["sha256"],
                "train",
            )
            validation_by_stock[symbol] = evaluate_partition(
                symbol,
                candidate,
                bars,
                lagged,
                source_meta[symbol]["sha256"],
                "validation",
            )

        train_summary = add_return_periods(
            aggregate_partition(
                train_by_stock,
                controls["train"],
            ),
            train_by_stock,
        )
        validation_summary = add_return_periods(
            aggregate_partition(
                validation_by_stock,
                controls["validation"],
            ),
            validation_by_stock,
        )

        records.append(
            {
                "candidate": asdict(candidate),
                "timing": {
                    "one_bar_execution_lag": True,
                    "future_information_required": False,
                },
                "train_by_stock": train_by_stock,
                "train_summary": train_summary,
                "validation_by_stock": validation_by_stock,
                "validation_summary": validation_summary,
                "stage_a": stage_a_criteria(
                    train_by_stock,
                    validation_summary,
                ),
                "test_by_stock": None,
                "test_summary": None,
                "stage_b": None,
            }
        )

    eligible = [
        record for record in records
        if record["stage_a"]["eligible"]
    ]
    eligible.sort(key=selection_key, reverse=True)

    selected: list[dict] = []
    suppressed: list[dict] = []
    for record in eligible:
        candidate_id = record["candidate"]["candidate_id"]
        positions = concatenated_pretest_positions(
            signal_map,
            candidate_id,
            bars_by_symbol,
        )
        duplicate_of = None
        duplicate_similarity = None
        for prior in selected:
            prior_id = prior["candidate"]["candidate_id"]
            prior_positions = concatenated_pretest_positions(
                signal_map,
                prior_id,
                bars_by_symbol,
            )
            similarity = signal_similarity(positions, prior_positions)
            if similarity >= SIMILARITY_THRESHOLD:
                duplicate_of = prior_id
                duplicate_similarity = similarity
                break
        if duplicate_of is not None:
            suppressed.append(
                {
                    "candidate_id": candidate_id,
                    "reason": "NEAR_DUPLICATE_SIGNAL_PATH",
                    "duplicate_of": duplicate_of,
                    "signal_similarity": round(
                        float(duplicate_similarity),
                        6,
                    ),
                }
            )
            continue
        if len(selected) >= TOP_K:
            suppressed.append(
                {
                    "candidate_id": candidate_id,
                    "reason": f"TOP_K_BOUND:{TOP_K}",
                    "duplicate_of": None,
                    "signal_similarity": None,
                }
            )
            continue
        selected.append(record)

    selected_ids = {
        record["candidate"]["candidate_id"]
        for record in selected
    }

    # TEST is opened only after selected_ids is fixed.
    for record in records:
        candidate_id = record["candidate"]["candidate_id"]
        if candidate_id not in selected_ids:
            continue
        test_by_stock: dict[str, dict] = {}
        candidate = next(
            item for item in candidates
            if item.candidate_id == candidate_id
        )
        for symbol in SYMBOLS:
            test_by_stock[symbol] = evaluate_partition(
                symbol,
                candidate,
                bars_by_symbol[symbol],
                signal_map[candidate_id][symbol],
                source_meta[symbol]["sha256"],
                "test",
            )
        test_summary = add_return_periods(
            aggregate_partition(
                test_by_stock,
                controls["test"],
            ),
            test_by_stock,
        )
        record["test_by_stock"] = test_by_stock
        record["test_summary"] = test_summary
        record["stage_b"] = stage_b_criteria(test_summary)

    review_events = [
        ReviewEvent(
            "STRATEGY_RESEARCH_SURVIVOR",
            0.60,
            "Research",
        )
        for _ in selected
    ]
    review_gate = evaluate_review_need(review_events)
    work_requests = []
    if review_gate.level != "NO_REVIEW":
        context = SpecialistReviewContext(
            has_portfolio_context=False,
            risk_review_required=True,
            external_dependency_requires_review=False,
        )
        for record in selected:
            candidate_id = record["candidate"]["candidate_id"]
            work_requests.extend(
                asdict(work)
                for work in build_specialist_work(
                    candidate_id,
                    context,
                )
            )

    partition_counts: dict[str, dict[str, dict]] = {}
    for symbol in SYMBOLS:
        bars = bars_by_symbol[symbol]
        control_signals = always_long_signals(bars)
        partition_counts[symbol] = {}
        for partition in PARTITIONS:
            part_bars, part_signals = partition_slice(
                bars,
                control_signals,
                partition,
            )
            partition_counts[symbol][partition] = {
                "bar_count": len(part_bars),
                "return_periods": len(part_signals),
                "first_trading_date": bar_date(part_bars[0]),
                "last_trading_date": bar_date(part_bars[-1]),
            }

    test_confirmed_ids = [
        record["candidate"]["candidate_id"]
        for record in records
        if record["stage_b"]
        and record["stage_b"]["test_confirmed"]
    ]

    result = {
        "schema": "quantrade_qt_strat_005_transfer_run_v1",
        "experiment_id": EXPERIMENT_ID,
        "preregistration_commit": PREREGISTRATION_COMMIT,
        "market_scope": {
            "asset_class": "KRX_EQUITY",
            "scope_id": MARKET_SCOPE,
            "symbols": list(SYMBOLS),
            "bar_type": "DAILY",
            "requested_start": START_DATE,
            "requested_end": END_DATE,
        },
        "dataset": {
            "per_stock": source_meta,
            "basket_hash_payload": basket_hash_payload,
            "basket_sha256": basket_hash,
        },
        "partition_counts": partition_counts,
        "frozen_cost_model": {
            "transaction_cost_bps": TRANSACTION_COST_BPS,
            "terminal_liquidation_charged": True,
            "periods_per_year": PERIODS_PER_YEAR,
            "source_assumptions": {
                "fee_each_side_pct": 0.015,
                "slippage_each_side_pct": 0.10,
                "sell_tax_pct": 0.18,
                "symmetric_average_one_way_pct": 0.205,
            },
        },
        "controls": controls,
        "candidates": records,
        "selection": {
            "stage_a_eligible_ids": [
                record["candidate"]["candidate_id"]
                for record in eligible
            ],
            "selected_ids_before_test": sorted(selected_ids),
            "suppressed": suppressed,
            "signal_similarity_threshold": SIMILARITY_THRESHOLD,
            "top_k": TOP_K,
            "test_opened_only_for_selected": True,
            "test_confirmed_ids": test_confirmed_ids,
        },
        "review_planning": {
            "review_gate": {
                "level": review_gate.level,
                "reasons": list(review_gate.reasons),
                "event_count": review_gate.event_count,
            },
            "specialist_work_requests": work_requests,
            "specialists_planned": len(work_requests),
            "specialists_invoked": 0,
            "independence_status": "NOT_INVOKED",
        },
        "pipeline_result": {
            "operational_success": True,
            "alpha_found_required_for_success": False,
            "instrument_count": len(SYMBOLS),
            "candidate_count": len(records),
            "stage_a_eligible_count": len(eligible),
            "selected_count": len(selected_ids),
            "test_confirmed_count": len(test_confirmed_ids),
        },
        "authority": {
            "model_called": False,
            "canonical_evidence_created": False,
            "portfolio_proposal_created": False,
            "risk_limit_changed": False,
            "strategy_approved": False,
            "investment_decision_created": False,
            "paper_promotion_authorized": False,
            "execution_authorized": False,
            "live_order_possible": False,
        },
    }

    dataset_artifact = {
        "schema": "quantrade_qt_strat_005_dataset_v1",
        "experiment_id": EXPERIMENT_ID,
        "preregistration_commit": PREREGISTRATION_COMMIT,
        "basket_sha256": basket_hash,
        "sources": source_meta,
        "rows_by_symbol": rows_by_symbol,
    }

    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    DATASET_PATH.write_text(
        json.dumps(
            dataset_artifact,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return result


def compact_summary(result: dict) -> dict:
    return {
        "experiment_id": result["experiment_id"],
        "preregistration_commit": result["preregistration_commit"],
        "basket_sha256": result["dataset"]["basket_sha256"],
        "datasets": {
            symbol: {
                "row_count": result["dataset"]["per_stock"][symbol][
                    "row_count"
                ],
                "first": result["dataset"]["per_stock"][symbol][
                    "first_trading_date"
                ],
                "last": result["dataset"]["per_stock"][symbol][
                    "last_trading_date"
                ],
                "sha256": result["dataset"]["per_stock"][symbol]["sha256"],
            }
            for symbol in SYMBOLS
        },
        "candidates": [
            {
                "candidate_id": record["candidate"]["candidate_id"],
                "stage_a_eligible": record["stage_a"]["eligible"],
                "validation_summary": record["validation_summary"],
                "selected_for_test": (
                    record["candidate"]["candidate_id"]
                    in result["selection"]["selected_ids_before_test"]
                ),
                "test_summary": record["test_summary"],
                "test_confirmed": (
                    record["stage_b"]["test_confirmed"]
                    if record["stage_b"]
                    else None
                ),
            }
            for record in result["candidates"]
        ],
        "selection": result["selection"],
        "review_planning": {
            "review_level": result["review_planning"]["review_gate"][
                "level"
            ],
            "specialists_planned": result["review_planning"][
                "specialists_planned"
            ],
            "specialists_invoked": result["review_planning"][
                "specialists_invoked"
            ],
        },
        "pipeline_result": result["pipeline_result"],
        "authority": result["authority"],
    }


if __name__ == "__main__":
    outcome = run()
    print("QT_STRAT_005_SUMMARY_BEGIN")
    print(
        json.dumps(
            compact_summary(outcome),
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    print("QT_STRAT_005_SUMMARY_END")
