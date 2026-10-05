"""Safe declarative candidate generation for QuanTrade Strategy Research.

The DSL is intentionally small and deterministic. It can only read current or
past close prices supplied by the caller. It cannot execute Python, access the
network, call a model, mutate portfolio state, or authorize execution.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
import math
from typing import Protocol, Sequence

from quantrade.capabilities.strategy_research import (
    CandidateStrategy,
    PositionSignal,
    PriceBar,
    StrategyResearchError,
)


class CandidateValidationError(StrategyResearchError):
    """Raised when a generated/static candidate violates the safe DSL contract."""


@dataclass(frozen=True)
class CandidateProviderMetadata:
    provider_id: str
    implementation: str
    version_or_revision: str
    license: str
    deterministic: bool = True
    network_access: bool = False
    model_access: bool = False
    capital_effect: bool = False
    status: str = "SANDBOX"


@dataclass(frozen=True)
class CandidateGenerationContext:
    market_scope: str
    rebalance_horizon: str


@dataclass(frozen=True)
class CandidatePolicy:
    max_candidates: int = 20
    max_depth: int = 8
    max_nodes: int = 64
    max_window: int = 252
    max_abs_constant: float = 1_000_000.0


class StrategyCandidateProvider(Protocol):
    metadata: CandidateProviderMetadata

    def generate(
        self,
        context: CandidateGenerationContext,
    ) -> tuple[CandidateStrategy, ...]:
        ...


_NUMERIC_LEAVES = {"CLOSE", "CONST", "RETURN", "SMA", "EMA", "STD", "ZSCORE"}
_NUMERIC_BINARY = {"ADD", "SUB", "MUL", "DIV"}
_NUMERIC_UNARY = {"REF"}
_BOOLEAN_BINARY = {"AND", "OR"}
_COMPARISONS = {"GT", "LT"}
_ALLOWED_OPS = (
    _NUMERIC_LEAVES
    | _NUMERIC_BINARY
    | _NUMERIC_UNARY
    | _BOOLEAN_BINARY
    | _COMPARISONS
)


def _require_exact_keys(node: dict, keys: set[str]) -> None:
    extras = set(node) - keys
    missing = keys - set(node)
    if missing:
        raise CandidateValidationError(
            f"DSL node missing required keys: {sorted(missing)}"
        )
    if extras:
        raise CandidateValidationError(
            f"DSL node contains unsupported keys: {sorted(extras)}"
        )


def _require_window(value: object, policy: CandidatePolicy) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CandidateValidationError("window/periods must be an integer")
    if value < 1 or value > policy.max_window:
        raise CandidateValidationError(
            f"window/periods must be between 1 and {policy.max_window}"
        )
    return value


def _validate_constant(value: object, policy: CandidatePolicy) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CandidateValidationError("CONST value must be numeric")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise CandidateValidationError("CONST value must be finite")
    if abs(numeric) > policy.max_abs_constant:
        raise CandidateValidationError(
            "CONST absolute value exceeds safe policy bound"
        )
    return numeric


def validate_formula(
    formula_ast: dict,
    policy: CandidatePolicy | None = None,
) -> dict:
    """Validate and summarize a safe formula AST.

    The root expression must be boolean because the v1 compiler emits long/flat
    target positions. Only backward-looking close-price primitives are allowed.
    """
    policy = policy or CandidatePolicy()
    if policy.max_depth < 1 or policy.max_nodes < 1 or policy.max_candidates < 1:
        raise CandidateValidationError("candidate policy bounds must be positive")

    node_count = 0

    def visit(node: object, depth: int) -> str:
        nonlocal node_count
        if not isinstance(node, dict):
            raise CandidateValidationError("every DSL node must be an object")
        node_count += 1
        if node_count > policy.max_nodes:
            raise CandidateValidationError(
                f"formula exceeds max_nodes={policy.max_nodes}"
            )
        if depth > policy.max_depth:
            raise CandidateValidationError(
                f"formula exceeds max_depth={policy.max_depth}"
            )

        op = node.get("op")
        if not isinstance(op, str) or op not in _ALLOWED_OPS:
            raise CandidateValidationError(f"unsupported DSL operator: {op!r}")

        if op == "CLOSE":
            _require_exact_keys(node, {"op"})
            return "numeric"
        if op == "CONST":
            _require_exact_keys(node, {"op", "value"})
            _validate_constant(node["value"], policy)
            return "numeric"
        if op in {"RETURN", "SMA", "EMA", "STD", "ZSCORE"}:
            _require_exact_keys(node, {"op", "window"})
            _require_window(node["window"], policy)
            if op in {"STD", "ZSCORE"} and node["window"] < 2:
                raise CandidateValidationError(
                    f"{op} window must be at least 2"
                )
            return "numeric"
        if op == "REF":
            _require_exact_keys(node, {"op", "value", "periods"})
            _require_window(node["periods"], policy)
            child_type = visit(node["value"], depth + 1)
            if child_type != "numeric":
                raise CandidateValidationError("REF value must be numeric")
            return "numeric"
        if op in _NUMERIC_BINARY:
            _require_exact_keys(node, {"op", "left", "right"})
            if visit(node["left"], depth + 1) != "numeric":
                raise CandidateValidationError(f"{op} left operand must be numeric")
            if visit(node["right"], depth + 1) != "numeric":
                raise CandidateValidationError(f"{op} right operand must be numeric")
            return "numeric"
        if op in _COMPARISONS:
            _require_exact_keys(node, {"op", "left", "right"})
            if visit(node["left"], depth + 1) != "numeric":
                raise CandidateValidationError(f"{op} left operand must be numeric")
            if visit(node["right"], depth + 1) != "numeric":
                raise CandidateValidationError(f"{op} right operand must be numeric")
            return "boolean"
        if op in _BOOLEAN_BINARY:
            _require_exact_keys(node, {"op", "left", "right"})
            if visit(node["left"], depth + 1) != "boolean":
                raise CandidateValidationError(f"{op} left operand must be boolean")
            if visit(node["right"], depth + 1) != "boolean":
                raise CandidateValidationError(f"{op} right operand must be boolean")
            return "boolean"
        raise CandidateValidationError(f"unhandled DSL operator: {op}")

    root_type = visit(formula_ast, 1)
    if root_type != "boolean":
        raise CandidateValidationError(
            "strategy formula root must be boolean for long/flat v1 compiler"
        )
    return {
        "schema": "quantrade_strategy_formula_validation_v1",
        "root_type": root_type,
        "node_count": node_count,
        "max_depth": policy.max_depth,
        "max_nodes": policy.max_nodes,
        "allowed_operators": sorted(_ALLOWED_OPS),
        "safe_for_compilation": True,
        "arbitrary_code_execution": False,
    }


def canonical_formula_fingerprint(formula_ast: dict) -> str:
    """Stable textual fingerprint used for duplicate detection."""
    return json.dumps(
        formula_ast,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _window(values: Sequence[float], index: int, window: int) -> list[float] | None:
    if index + 1 < window:
        return None
    return [float(v) for v in values[index - window + 1 : index + 1]]


def _numeric(
    node: dict,
    closes: Sequence[float],
    index: int,
) -> float | None:
    op = node["op"]
    if index < 0:
        return None
    if op == "CLOSE":
        return float(closes[index])
    if op == "CONST":
        return float(node["value"])
    if op == "RETURN":
        window = int(node["window"])
        if index < window:
            return None
        previous = float(closes[index - window])
        if previous == 0:
            return None
        return float(closes[index]) / previous - 1.0
    if op in {"SMA", "EMA", "STD", "ZSCORE"}:
        window = int(node["window"])
        sample = _window(closes, index, window)
        if sample is None:
            return None
        if op == "SMA":
            return sum(sample) / len(sample)
        if op == "EMA":
            alpha = 2.0 / (window + 1.0)
            value = sample[0]
            for item in sample[1:]:
                value = alpha * item + (1.0 - alpha) * value
            return value
        mean = sum(sample) / len(sample)
        variance = sum((value - mean) ** 2 for value in sample) / len(sample)
        std = math.sqrt(variance)
        if op == "STD":
            return std
        if std == 0:
            return 0.0
        return (float(closes[index]) - mean) / std
    if op == "REF":
        return _numeric(
            node["value"],
            closes,
            index - int(node["periods"]),
        )
    if op in _NUMERIC_BINARY:
        left = _numeric(node["left"], closes, index)
        right = _numeric(node["right"], closes, index)
        if left is None or right is None:
            return None
        if op == "ADD":
            return left + right
        if op == "SUB":
            return left - right
        if op == "MUL":
            return left * right
        if abs(right) <= 1e-15:
            return None
        return left / right
    raise CandidateValidationError(f"numeric evaluation unsupported for {op}")


def _boolean(
    node: dict,
    closes: Sequence[float],
    index: int,
) -> bool:
    op = node["op"]
    if op in _COMPARISONS:
        left = _numeric(node["left"], closes, index)
        right = _numeric(node["right"], closes, index)
        if left is None or right is None:
            return False
        if op == "GT":
            return left > right
        return left < right
    if op == "AND":
        return _boolean(node["left"], closes, index) and _boolean(
            node["right"], closes, index
        )
    if op == "OR":
        return _boolean(node["left"], closes, index) or _boolean(
            node["right"], closes, index
        )
    raise CandidateValidationError(f"boolean evaluation unsupported for {op}")


def compile_position_signals(
    candidate: CandidateStrategy,
    bars: Sequence[PriceBar],
    policy: CandidatePolicy | None = None,
) -> tuple[PositionSignal, ...]:
    """Compile a safe AST into long/flat signals using current/past closes only."""
    policy = policy or CandidatePolicy()
    formula_ast = candidate.formula_ast
    if not isinstance(formula_ast, dict):
        raise CandidateValidationError("candidate formula_ast is required")
    validate_formula(formula_ast, policy)

    bars = list(bars)
    if len(bars) < 2:
        raise CandidateValidationError("at least two price bars are required")
    closes = []
    for bar in bars:
        if not isinstance(bar.close, (int, float)) or bar.close <= 0:
            raise CandidateValidationError("all close values must be positive numbers")
        closes.append(float(bar.close))

    signals = []
    for index in range(len(bars) - 1):
        active = _boolean(formula_ast, closes, index)
        signals.append(
            PositionSignal(
                effective_at=bars[index].observed_at,
                information_cutoff=bars[index].observed_at,
                target_position=1.0 if active else 0.0,
            )
        )
    return tuple(signals)


class StaticCandidateProvider:
    """Deterministic provider used to validate the candidate-provider seam."""

    def __init__(
        self,
        candidates: Sequence[CandidateStrategy],
        *,
        metadata: CandidateProviderMetadata | None = None,
        policy: CandidatePolicy | None = None,
    ) -> None:
        self._candidates = tuple(candidates)
        self.metadata = metadata or CandidateProviderMetadata(
            provider_id="quantrade.static.strategy_candidates.v1",
            implementation="quantrade-static-fixture-provider",
            version_or_revision="v1",
            license="repository-license",
        )
        self.policy = policy or CandidatePolicy()

    def generate(
        self,
        context: CandidateGenerationContext,
    ) -> tuple[CandidateStrategy, ...]:
        if len(self._candidates) > self.policy.max_candidates:
            raise CandidateValidationError(
                f"candidate batch exceeds max_candidates={self.policy.max_candidates}"
            )

        seen_ids: set[str] = set()
        seen_formulas: set[str] = set()
        output = []
        provider = asdict(self.metadata)

        for candidate in self._candidates:
            if not candidate.candidate_id.strip():
                raise CandidateValidationError("candidate_id is required")
            if candidate.candidate_id in seen_ids:
                raise CandidateValidationError(
                    f"duplicate candidate_id: {candidate.candidate_id}"
                )
            if candidate.market_scope != context.market_scope:
                raise CandidateValidationError(
                    "candidate market_scope does not match generation context"
                )
            if candidate.rebalance_horizon != context.rebalance_horizon:
                raise CandidateValidationError(
                    "candidate rebalance_horizon does not match generation context"
                )
            if not isinstance(candidate.formula_ast, dict):
                raise CandidateValidationError("candidate formula_ast is required")

            validate_formula(candidate.formula_ast, self.policy)
            fingerprint = canonical_formula_fingerprint(candidate.formula_ast)
            if fingerprint in seen_formulas:
                raise CandidateValidationError(
                    "duplicate candidate formula in batch"
                )
            seen_ids.add(candidate.candidate_id)
            seen_formulas.add(fingerprint)
            output.append(
                replace(
                    candidate,
                    generator_provider=provider,
                )
            )

        return tuple(output)
