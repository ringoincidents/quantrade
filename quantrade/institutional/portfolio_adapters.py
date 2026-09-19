from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from portfolio_report import (
    RISK_ENGINE,
    THRESHOLDS,
    build_risk_engine,
    compute_positions,
    evaluate_rules,
    load_symbol_asset_type_map,
    update_loss_streaks,
)


def _active_symbols(config: dict | None, key: str) -> set[str]:
    if not config:
        return set()
    return {
        str(item["symbol"])
        for item in config.get(key, [])
        if item.get("symbol") and item.get("active", True)
    }


def audit_portfolio_data_quality(
    real: dict,
    asset_class_mapping: dict | None,
    role_mapping: dict | None,
    target_allocation: dict | None = None,
) -> dict:
    """Report mapping/policy drift without repairing it."""
    held = {
        str(p["symbol"])
        for p in real.get("positions", [])
        if p.get("symbol")
    }
    asset_active = _active_symbols(asset_class_mapping, "mappings")
    role_active = _active_symbols(role_mapping, "mappings")

    role_source = str((role_mapping or {}).get("source", ""))
    return {
        "held_symbols": sorted(held),
        "missing_asset_class_mapping": sorted(held - asset_active),
        "missing_role_mapping": sorted(held - role_active),
        "active_asset_mappings_not_held": sorted(asset_active - held),
        "active_role_mappings_not_held": sorted(role_active - held),
        "policy_flags": {
            "portfolio_thresholds_provisional": bool(THRESHOLDS.get("provisional")),
            "risk_engine_provisional": bool(RISK_ENGINE.get("provisional")),
            "target_allocation_provisional": bool(
                (target_allocation or {}).get("provisional", False)
            ),
            "role_mapping_provisional": bool(
                (role_mapping or {}).get("provisional", False)
                or "초안" in role_source
            ),
        },
    }


@dataclass(frozen=True)
class RealPortfolioSnapshotAdapter:
    source: str = "real_portfolio_read_only"

    def build(
        self,
        real: dict,
        *,
        asset_class_mapping: dict | None = None,
        role_mapping: dict | None = None,
        target_allocation: dict | None = None,
    ) -> dict:
        """Build a canonical snapshot without mutating the broker-sync payload."""
        raw = copy.deepcopy(real)
        calculated = compute_positions(raw)
        quality = audit_portfolio_data_quality(
            raw, asset_class_mapping, role_mapping, target_allocation
        )
        return {
            "schema": "institutional_portfolio_snapshot_v1",
            "source": self.source,
            "source_synced_at": raw.get("synced_at"),
            "cash": raw.get("cash"),
            "positions": copy.deepcopy(raw.get("positions", [])),
            "calculated": calculated,
            "data_quality": quality,
            "read_only": True,
        }


@dataclass(frozen=True)
class PortfolioRuleEventAdapter:
    source: str = "portfolio_report_deterministic_rules"

    def from_rule_match(self, match: dict) -> dict:
        return {
            "event_type": "PORTFOLIO_RULE_MATCH",
            "source": self.source,
            "subject": str(match.get("symbol") or "PORTFOLIO"),
            "payload": {
                "rule": match.get("rule"),
                "symbol": match.get("symbol"),
                "name": match.get("name"),
                "observed": match.get("observed"),
                "threshold": match.get("threshold"),
                "fact": match.get("fact"),
                "policy_provisional": bool(THRESHOLDS.get("provisional")),
                "observation_only": True,
            },
        }

    def build(self, matches: list[dict]) -> list[dict]:
        return [self.from_rule_match(match) for match in matches]


@dataclass(frozen=True)
class DeterministicRiskAdapter:
    policy_version: str = "portfolio_report_risk_engine_p1_1"

    def evaluate(
        self,
        snapshot: dict,
        *,
        symbol_closes: dict[str, list[float]] | None = None,
        asset_class_mapping: dict | None = None,
        loss_state: dict | None = None,
        today: str | None = None,
    ) -> dict:
        """Reuse existing deterministic portfolio/risk calculations; no LLM."""
        calculated = copy.deepcopy(snapshot["calculated"])
        rows = calculated["positions"]
        state = copy.deepcopy(loss_state or {"loss_since": {}})
        streaks = update_loss_streaks(rows, state, today)
        asset_type_map = (
            load_symbol_asset_type_map(asset_class_mapping)
            if asset_class_mapping is not None
            else {}
        )
        matches = evaluate_rules(
            rows, streaks, today=today, asset_type_map=asset_type_map
        )
        risk = build_risk_engine(
            rows,
            calculated["total_assets_krw"],
            symbol_closes or {},
            asset_type_map=asset_type_map,
        )
        limitations = []
        if not symbol_closes:
            limitations.append(
                "price history unavailable: volatility/correlation-dependent fields may be empty"
            )
        mdd = risk.get("mdd_budget")
        if mdd:
            limitations.append(
                "mdd_budget is an unrealized-return proxy, not peak-to-trough MDD"
            )
        return {
            "schema": "institutional_risk_assessment_v1",
            "deterministic": True,
            "llm_used": False,
            "policy_version": self.policy_version,
            "policy_provisional": bool(
                THRESHOLDS.get("provisional") or RISK_ENGINE.get("provisional")
            ),
            "rule_matches": matches,
            "risk_engine": risk,
            "loss_state": state,
            "limitations": limitations,
        }

    def attach(
        self,
        kernel: Any,
        case_id: str,
        snapshot_payload: dict,
        assessment: dict,
    ) -> tuple[str, str]:
        snapshot_id = kernel.add_snapshot(
            case_id, snapshot_payload, source=snapshot_payload.get("source", "adapter")
        )
        assessment_id = kernel.add_risk_assessment(
            case_id,
            snapshot_id,
            assessment,
            assessment["policy_version"],
        )
        return snapshot_id, assessment_id
