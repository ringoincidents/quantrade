from __future__ import annotations

from copy import deepcopy
from typing import Any

from .tools import ToolDefinition, ToolRegistry


class StrategyDataPlane:
    """Provider-neutral tabular data plane for Strategy employees.

    P1.3C uses injected fixture/local rows. Real KRX/fundamental/flow providers
    can later populate the same named sources without changing employee logic.
    """

    def __init__(self, sources: dict[str, list[dict[str, Any]]]):
        self.sources = deepcopy(sources)

    def catalog(self, _: dict) -> dict:
        result = {}
        for name, rows in self.sources.items():
            fields = sorted({k for row in rows for k in row})
            result[name] = {
                "fields": fields,
                "row_count": len(rows),
                "available": True,
            }
        return result

    def query(self, args: dict) -> list[dict]:
        source_names = args["sources"]
        if not source_names:
            return []
        for source in source_names:
            if source not in self.sources:
                raise KeyError(f"data source unavailable: {source}")

        by_symbol: dict[str, dict] = {}
        first = source_names[0]
        for row in self.sources[first]:
            symbol = row["symbol"]
            by_symbol[symbol] = dict(row)

        for source in source_names[1:]:
            incoming = {row["symbol"]: row for row in self.sources[source]}
            joined: dict[str, dict] = {}
            for symbol, base in by_symbol.items():
                if symbol in incoming:
                    merged = dict(base)
                    for key, value in incoming[symbol].items():
                        if key != "symbol":
                            merged[key] = value
                    joined[symbol] = merged
            by_symbol = joined

        rows = list(by_symbol.values())
        for cond in args.get("conditions", []):
            field = cond["field"]
            op = cond["op"]
            value = cond["value"]
            filtered = []
            for row in rows:
                if field not in row:
                    continue
                expected = value
                if isinstance(value, dict) and "field" in value:
                    if value["field"] not in row:
                        continue
                    expected = row[value["field"]]
                if self._compare(row[field], op, expected):
                    filtered.append(row)
            rows = filtered

        select = args.get("select")
        if select:
            rows = [
                {field: row.get(field) for field in select}
                for row in rows
            ]
        sort = args.get("sort")
        if sort:
            field = sort["field"]
            reverse = sort.get("direction", "asc").lower() == "desc"
            rows.sort(key=lambda r: (r.get(field) is None, r.get(field)), reverse=reverse)
        limit = args.get("limit")
        if limit is not None:
            rows = rows[: int(limit)]
        return rows

    @staticmethod
    def _compare(actual: Any, op: str, expected: Any) -> bool:
        if op == ">":
            return actual > expected
        if op == ">=":
            return actual >= expected
        if op == "<":
            return actual < expected
        if op == "<=":
            return actual <= expected
        if op == "==":
            return actual == expected
        if op == "!=":
            return actual != expected
        if op == "in":
            return actual in expected
        raise ValueError(f"unsupported operator: {op}")


def install_strategy_workstation(
    registry: ToolRegistry,
    employee_id: str,
    data_plane: StrategyDataPlane,
) -> None:
    """Install composable Strategy workstation primitives for one employee."""
    registry.register(
        ToolDefinition(
            name="data.catalog",
            description=(
                "Discover available authorized tabular data sources, fields and row counts. "
                "Use before assuming a source or field exists."
            ),
            input_schema={"required": []},
            deterministic=True,
            side_effect_class="READ_ONLY",
        ),
        data_plane.catalog,
    )
    registry.register(
        ToolDefinition(
            name="data.query",
            description=(
                "Join authorized sources by symbol, apply arbitrary deterministic field "
                "conditions, project fields, sort and limit. This is a generic query "
                "primitive, not a hard-coded investment screen."
            ),
            input_schema={"required": ["sources"]},
            deterministic=True,
            side_effect_class="READ_ONLY",
        ),
        data_plane.query,
    )
    registry.grant(employee_id, "data.catalog")
    registry.grant(employee_id, "data.query")


def synthetic_korea_strategy_sources() -> dict[str, list[dict]]:
    """Clearly synthetic fixture data used only for runtime acceptance tests."""
    return {
        "securities": [
            {"symbol": "KRX001", "name": "Fixture Alpha", "market": "KOSPI", "sector": "Semiconductor"},
            {"symbol": "KRX002", "name": "Fixture Beta", "market": "KOSDAQ", "sector": "Biotech"},
            {"symbol": "KRX003", "name": "Fixture Gamma", "market": "KOSPI", "sector": "Shipbuilding"},
            {"symbol": "KRX004", "name": "Fixture Delta", "market": "KOSDAQ", "sector": "Power Equipment"},
            {"symbol": "KRX005", "name": "Fixture Epsilon", "market": "KOSPI", "sector": "Battery"},
        ],
        "fundamentals": [
            {"symbol": "KRX001", "sales_growth_yoy_pct": 28.0, "op_margin_q_minus_2": 7.0, "op_margin_q_minus_1": 9.0, "op_margin_q": 11.0},
            {"symbol": "KRX002", "sales_growth_yoy_pct": 34.0, "op_margin_q_minus_2": 4.0, "op_margin_q_minus_1": 3.0, "op_margin_q": 6.0},
            {"symbol": "KRX003", "sales_growth_yoy_pct": 23.0, "op_margin_q_minus_2": 5.0, "op_margin_q_minus_1": 7.0, "op_margin_q": 9.0},
            {"symbol": "KRX004", "sales_growth_yoy_pct": 21.0, "op_margin_q_minus_2": 8.0, "op_margin_q_minus_1": 9.0, "op_margin_q": 10.0},
            {"symbol": "KRX005", "sales_growth_yoy_pct": 12.0, "op_margin_q_minus_2": 6.0, "op_margin_q_minus_1": 7.0, "op_margin_q": 8.0},
        ],
        "investor_flows_10d": [
            {"symbol": "KRX001", "foreign_net_buy": 120.0, "institution_net_buy": 45.0, "pension_net_buy": 15.0},
            {"symbol": "KRX002", "foreign_net_buy": 80.0, "institution_net_buy": 20.0, "pension_net_buy": -3.0},
            {"symbol": "KRX003", "foreign_net_buy": 55.0, "institution_net_buy": 30.0, "pension_net_buy": 10.0},
            {"symbol": "KRX004", "foreign_net_buy": -10.0, "institution_net_buy": 25.0, "pension_net_buy": 12.0},
            {"symbol": "KRX005", "foreign_net_buy": 40.0, "institution_net_buy": 10.0, "pension_net_buy": 4.0},
        ],
    }
