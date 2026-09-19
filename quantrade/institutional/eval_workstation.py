from __future__ import annotations

from copy import deepcopy
from typing import Any

from .tools import ToolDefinition, ToolRegistry


class EvalFixturePlane:
    """Frozen point-in-time data/tools shared by both E1 treatments."""

    def __init__(self, fixture: dict[str, Any]):
        self.fixture = deepcopy(fixture)
        self._failures: dict[str, int] = {}

    def catalog(self, _: dict) -> dict:
        return {
            "documents": [
                {
                    "doc_id": d["doc_id"],
                    "kind": d["kind"],
                    "as_of": d["as_of"],
                }
                for d in self.fixture.get("documents", [])
            ],
            "lookups": sorted(self.fixture.get("lookups", {})),
        }

    def document(self, args: dict) -> dict:
        for doc in self.fixture.get("documents", []):
            if doc["doc_id"] == args["doc_id"]:
                return deepcopy(doc)
        raise KeyError(f"document unavailable: {args['doc_id']}")

    def growth_pct(self, args: dict) -> dict:
        start = float(args["start"])
        end = float(args["end"])
        if start == 0:
            raise ValueError("growth percentage undefined from zero")
        return {"growth_pct": ((end / start) - 1.0) * 100.0}

    def lookup(self, args: dict) -> dict:
        name = args["name"]
        spec = self.fixture.get("lookups", {}).get(name)
        if spec is None:
            raise KeyError(f"lookup unavailable: {name}")
        failures_before_success = int(spec.get("failures_before_success", 0))
        seen = self._failures.get(name, 0)
        self._failures[name] = seen + 1
        if seen < failures_before_success:
            raise RuntimeError(spec.get("error", "injected lookup failure"))
        return deepcopy(spec["result"])


def install_eval_workstation(
    registry: ToolRegistry,
    employee_id: str,
    plane: EvalFixturePlane,
) -> None:
    tools = [
        (
            ToolDefinition(
                "eval.catalog",
                "List frozen evaluation documents/lookups and their as-of dates.",
                {"required": []},
                deterministic=True,
                side_effect_class="READ_ONLY",
            ),
            plane.catalog,
        ),
        (
            ToolDefinition(
                "eval.document",
                "Read one frozen evaluation document by doc_id.",
                {"required": ["doc_id"]},
                deterministic=True,
                side_effect_class="READ_ONLY",
            ),
            plane.document,
        ),
        (
            ToolDefinition(
                "finance.growth_pct",
                "Deterministically calculate percentage growth from start to end.",
                {"required": ["start", "end"]},
                deterministic=True,
                side_effect_class="COMPUTE",
            ),
            plane.growth_pct,
        ),
        (
            ToolDefinition(
                "eval.lookup",
                "Read a named frozen lookup. Some tasks intentionally inject a failure.",
                {"required": ["name"]},
                deterministic=True,
                side_effect_class="READ_ONLY",
            ),
            plane.lookup,
        ),
    ]
    for definition, handler in tools:
        registry.register(definition, handler)
        registry.grant(employee_id, definition.name)
