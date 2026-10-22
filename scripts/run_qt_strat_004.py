"""QT-STRAT-004 pre-registered KRX Golden Run.

The experiment definition is frozen in:
research/experiments/QT-STRAT-004_PRE_REGISTRATION.md

This runner fetches only the pre-registered historical 005930 daily window,
compiles only the frozen candidates, applies a one-bar execution lag, uses the
frozen cost model, selects candidates using TRAIN+VALIDATION only, and opens
the TEST holdout only for the already-selected candidates.

No model call, portfolio mutation, broker action, or automatic promotion exists
in this file.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import date
import hashlib
import json
from pathlib import Path
import re

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


EXPERIMENT_ID = "QT-STRAT-004"
PREREGISTRATION_COMMIT = "8ea6b3ff2a08466923bb78df49cdbfb26f83b599"
SYMBOL = "005930"
MARKET_SCOPE = "KRX:005930"
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

RESULT_PATH = Path("research/experiments/QT-STRAT-004_RESULT.json")
DATASET_PATH = Path("research/experiments/QT-STRAT-004_DATASET.json")

NAVER_ENDPOINT = "https://api.finance.naver.com/siseJson.naver"
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; quantrade-bot/1.0)"}


def _frozen_candidates() -> tuple[CandidateStrategy, ...]:
    return (
        CandidateStrategy(
            candidate_id="CAND-SMA-5-20",
            name="SMA 5/20 trend",
            source_type="PRE_REGISTERED_STATIC",
            source_ref="QT-STRAT-004_PRE_REGISTRATION",
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
            source_ref="QT-STRAT-004_PRE_REGISTRATION",
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
            source_ref="QT-STRAT-004_PRE_REGISTRATION",
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
            source_ref="QT-STRAT-004_PRE_REGISTRATION",
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


def fetch_dataset() -> tuple[list[dict], dict]:
    params = {
        "symbol": SYMBOL,
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
            "Naver historical response contained no parseable OHLCV rows"
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
        raise RuntimeError("dataset contains duplicate trading dates")
    if dates != sorted(dates):
        raise RuntimeError("dataset dates are not strictly increasing")
    if any(item["close"] <= 0 for item in parsed):
        raise RuntimeError("dataset contains non-positive close")
    if parsed[0]["date"] < START_DATE or parsed[-1]["date"] > END_DATE:
        raise RuntimeError("dataset escaped the pre-registered date range")

    canonical = json.dumps(
        parsed,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    dataset_hash = hashlib.sha256(canonical).hexdigest()

    metadata = {
        "endpoint": NAVER_ENDPOINT,
        "params": params,
        "http_status": response.status_code,
        "row_count": len(parsed),
        "first_trading_date": parsed[0]["date"],
        "last_trading_date": parsed[-1]["date"],
        "strictly_increasing_dates": True,
        "duplicate_dates": False,
        "non_positive_close_count": 0,
        "sha256": dataset_hash,
    }
    return parsed, metadata


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


def _bar_date(bar: PriceBar) -> str:
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
        if start <= _bar_date(bars[index]) <= end
        and start <= _bar_date(bars[index + 1]) <= end
    ]
    if not indices:
        raise RuntimeError(f"partition {partition_name} has no return periods")
    if indices != list(range(indices[0], indices[-1] + 1)):
        raise RuntimeError(f"partition {partition_name} is not contiguous")
    first = indices[0]
    last = indices[-1]
    return bars[first : last + 2], signals[first : last + 1]


def dataset_metadata(
    dataset_hash: str,
    bars: list[PriceBar],
    partition_name: str,
) -> DatasetMetadata:
    return DatasetMetadata(
        dataset_id=f"{EXPERIMENT_ID}:{SYMBOL}:{partition_name}:{dataset_hash[:12]}",
        source=NAVER_ENDPOINT,
        provider="naver-finance-historical",
        version_or_revision="requestType=1;timeframe=day",
        as_of_start=bars[0].observed_at,
        as_of_end=bars[-1].observed_at,
        point_in_time=True,
        point_in_time_evidence_ref=f"sha256:{dataset_hash}",
    )


def evaluate_partition(
    candidate: CandidateStrategy,
    bars: list[PriceBar],
    signals: tuple[PositionSignal, ...],
    dataset_hash: str,
    partition_name: str,
) -> dict:
    part_bars, part_signals = partition_slice(
        bars,
        signals,
        partition_name,
    )
    evaluation = evaluate_strategy(
        candidate,
        part_bars,
        part_signals,
        dataset_metadata(dataset_hash, part_bars, partition_name),
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
    return asdict(evaluation)


def stage_a_criteria(
    train: dict,
    validation: dict,
    validation_control: dict,
) -> dict:
    train_m = train["metrics"]
    val_m = validation["metrics"]
    control_m = validation_control["metrics"]
    checks = {
        "train_return_periods_gte_200": train_m["return_periods"] >= 200,
        "validation_return_periods_gte_100": val_m["return_periods"] >= 100,
        "validation_beats_cost_adjusted_control": (
            val_m["net_total_return_pct"]
            > control_m["net_total_return_pct"]
        ),
        "validation_sharpe_gt_0": (
            val_m["sharpe"] is not None and val_m["sharpe"] > 0
        ),
        "validation_mdd_gte_minus_20": (
            val_m["maximum_drawdown_pct"] is not None
            and val_m["maximum_drawdown_pct"] >= -20.0
        ),
        "validation_turnover_lte_0_25": (
            val_m["turnover_per_period"] <= 0.25
        ),
    }
    return {
        "checks": checks,
        "eligible": all(checks.values()),
        "validation_excess_vs_cost_adjusted_control_pct": round(
            val_m["net_total_return_pct"]
            - control_m["net_total_return_pct"],
            6,
        ),
    }


def stage_b_criteria(test: dict, test_control: dict) -> dict:
    test_m = test["metrics"]
    control_m = test_control["metrics"]
    checks = {
        "test_return_periods_gte_100": test_m["return_periods"] >= 100,
        "test_beats_cost_adjusted_control": (
            test_m["net_total_return_pct"]
            > control_m["net_total_return_pct"]
        ),
        "test_sharpe_gt_0": (
            test_m["sharpe"] is not None and test_m["sharpe"] > 0
        ),
        "test_mdd_gte_minus_20": (
            test_m["maximum_drawdown_pct"] is not None
            and test_m["maximum_drawdown_pct"] >= -20.0
        ),
        "test_turnover_lte_0_25": (
            test_m["turnover_per_period"] <= 0.25
        ),
    }
    return {
        "checks": checks,
        "test_confirmed": all(checks.values()),
        "test_excess_vs_cost_adjusted_control_pct": round(
            test_m["net_total_return_pct"]
            - control_m["net_total_return_pct"],
            6,
        ),
    }


def _selection_key(record: dict) -> tuple[float, float, float, str]:
    metrics = record["validation"]["metrics"]
    return (
        record["stage_a"][
            "validation_excess_vs_cost_adjusted_control_pct"
        ],
        metrics["sharpe"] if metrics["sharpe"] is not None else float("-inf"),
        -metrics["turnover_per_period"],
        record["candidate"]["candidate_id"],
    )


def _pretest_positions(
    bars: list[PriceBar],
    signals: tuple[PositionSignal, ...],
) -> tuple[float, ...]:
    _, train_signals = partition_slice(bars, signals, "train")
    _, validation_signals = partition_slice(bars, signals, "validation")
    return tuple(
        [signal.target_position for signal in train_signals]
        + [signal.target_position for signal in validation_signals]
    )


def run() -> dict:
    rows, source_meta = fetch_dataset()
    bars = to_price_bars(rows)
    dataset_hash = source_meta["sha256"]

    control = CandidateStrategy(
        candidate_id="CONTROL-BUY-HOLD",
        name="Cost-adjusted buy and hold control",
        source_type="PRE_REGISTERED_CONTROL",
        source_ref="QT-STRAT-004_PRE_REGISTRATION",
        market_scope=MARKET_SCOPE,
        rebalance_horizon="DAILY",
    )
    control_signals = always_long_signals(bars)
    control_results = {
        partition: evaluate_partition(
            control,
            bars,
            control_signals,
            dataset_hash,
            partition,
        )
        for partition in PARTITIONS
    }

    provider = StaticCandidateProvider(_frozen_candidates())
    candidates = provider.generate(
        CandidateGenerationContext(
            market_scope=MARKET_SCOPE,
            rebalance_horizon="DAILY",
        )
    )

    records = []
    signal_map = {}
    for candidate in candidates:
        immediate = compile_position_signals(candidate, bars)
        lagged = lag_one_bar(immediate, bars)
        signal_map[candidate.candidate_id] = lagged
        train = evaluate_partition(
            candidate,
            bars,
            lagged,
            dataset_hash,
            "train",
        )
        validation = evaluate_partition(
            candidate,
            bars,
            lagged,
            dataset_hash,
            "validation",
        )
        stage_a = stage_a_criteria(
            train,
            validation,
            control_results["validation"],
        )
        records.append(
            {
                "candidate": asdict(candidate),
                "timing": {
                    "one_bar_execution_lag": True,
                    "future_information_required": False,
                },
                "train": train,
                "validation": validation,
                "stage_a": stage_a,
                "test": None,
                "stage_b": None,
            }
        )

    eligible = [record for record in records if record["stage_a"]["eligible"]]
    eligible.sort(key=_selection_key, reverse=True)

    selected = []
    suppressed = []
    for record in eligible:
        candidate_id = record["candidate"]["candidate_id"]
        positions = _pretest_positions(bars, signal_map[candidate_id])
        duplicate_of = None
        duplicate_similarity = None
        for prior in selected:
            prior_id = prior["candidate"]["candidate_id"]
            prior_positions = _pretest_positions(bars, signal_map[prior_id])
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
        record["candidate"]["candidate_id"] for record in selected
    }

    # The TEST holdout is opened only after selected_ids is frozen above.
    for record in records:
        candidate_id = record["candidate"]["candidate_id"]
        if candidate_id not in selected_ids:
            continue
        test = evaluate_partition(
            next(c for c in candidates if c.candidate_id == candidate_id),
            bars,
            signal_map[candidate_id],
            dataset_hash,
            "test",
        )
        record["test"] = test
        record["stage_b"] = stage_b_criteria(
            test,
            control_results["test"],
        )

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
                for work in build_specialist_work(candidate_id, context)
            )

    partition_counts = {}
    for name in PARTITIONS:
        part_bars, part_signals = partition_slice(
            bars,
            control_signals,
            name,
        )
        partition_counts[name] = {
            "bar_count": len(part_bars),
            "return_periods": len(part_signals),
            "first_trading_date": _bar_date(part_bars[0]),
            "last_trading_date": _bar_date(part_bars[-1]),
        }

    test_confirmed_ids = [
        record["candidate"]["candidate_id"]
        for record in records
        if record["stage_b"] and record["stage_b"]["test_confirmed"]
    ]

    result = {
        "schema": "quantrade_qt_strat_004_golden_run_v1",
        "experiment_id": EXPERIMENT_ID,
        "preregistration_commit": PREREGISTRATION_COMMIT,
        "market_scope": {
            "asset_class": "KRX_EQUITY",
            "symbol": SYMBOL,
            "scope_id": MARKET_SCOPE,
            "bar_type": "DAILY",
            "requested_start": START_DATE,
            "requested_end": END_DATE,
        },
        "dataset": source_meta,
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
        "control": control_results,
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
        "schema": "quantrade_qt_strat_004_dataset_v1",
        "experiment_id": EXPERIMENT_ID,
        "preregistration_commit": PREREGISTRATION_COMMIT,
        "source": source_meta,
        "rows": rows,
    }

    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    DATASET_PATH.write_text(
        json.dumps(dataset_artifact, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return result


def _compact_summary(result: dict) -> dict:
    return {
        "experiment_id": result["experiment_id"],
        "preregistration_commit": result["preregistration_commit"],
        "dataset": {
            "row_count": result["dataset"]["row_count"],
            "first_trading_date": result["dataset"]["first_trading_date"],
            "last_trading_date": result["dataset"]["last_trading_date"],
            "sha256": result["dataset"]["sha256"],
        },
        "control": {
            partition: {
                "net_total_return_pct": result["control"][partition]["metrics"][
                    "net_total_return_pct"
                ],
                "sharpe": result["control"][partition]["metrics"]["sharpe"],
                "maximum_drawdown_pct": result["control"][partition]["metrics"][
                    "maximum_drawdown_pct"
                ],
            }
            for partition in PARTITIONS
        },
        "candidates": [
            {
                "candidate_id": record["candidate"]["candidate_id"],
                "stage_a_eligible": record["stage_a"]["eligible"],
                "validation_net_total_return_pct": record["validation"]["metrics"][
                    "net_total_return_pct"
                ],
                "validation_excess_vs_control_pct": record["stage_a"][
                    "validation_excess_vs_cost_adjusted_control_pct"
                ],
                "selected_for_test": (
                    record["candidate"]["candidate_id"]
                    in result["selection"]["selected_ids_before_test"]
                ),
                "test_confirmed": (
                    record["stage_b"]["test_confirmed"]
                    if record["stage_b"]
                    else None
                ),
                "test_net_total_return_pct": (
                    record["test"]["metrics"]["net_total_return_pct"]
                    if record["test"]
                    else None
                ),
                "test_excess_vs_control_pct": (
                    record["stage_b"][
                        "test_excess_vs_cost_adjusted_control_pct"
                    ]
                    if record["stage_b"]
                    else None
                ),
            }
            for record in result["candidates"]
        ],
        "selection": result["selection"],
        "review_planning": {
            "review_level": result["review_planning"]["review_gate"]["level"],
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
    result = run()
    print("QT_STRAT_004_SUMMARY_BEGIN")
    print(json.dumps(_compact_summary(result), ensure_ascii=False, sort_keys=True))
    print("QT_STRAT_004_SUMMARY_END")
