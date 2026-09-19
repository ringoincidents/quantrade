from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from .service import InstitutionalKernel


class ToolPermissionError(PermissionError):
    pass


class ToolBudgetExceeded(RuntimeError):
    pass


class ToolInputError(ValueError):
    pass


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict
    deterministic: bool = True
    side_effect_class: str = "READ_ONLY"


class ToolRegistry:
    """Typed capability registry used by LLM employees as their workstation."""

    def __init__(self, kernel: InstitutionalKernel):
        self.kernel = kernel
        self.conn = kernel.conn
        self._handlers: dict[str, Callable[[dict], Any]] = {}

    def register(self, definition: ToolDefinition, handler: Callable[[dict], Any]) -> None:
        if definition.side_effect_class not in {
            "READ_ONLY", "COMPUTE", "ARTIFACT_WRITE", "PRIVILEGED"
        }:
            raise ValueError("unsupported side effect class")
        self._handlers[definition.name] = handler
        with self.conn:
            self.conn.execute(
                """INSERT INTO tool_definitions
                (tool_name,description,input_schema_json,deterministic,side_effect_class,created_at)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(tool_name) DO UPDATE SET
                  description=excluded.description,
                  input_schema_json=excluded.input_schema_json,
                  deterministic=excluded.deterministic,
                  side_effect_class=excluded.side_effect_class""",
                (
                    definition.name, definition.description,
                    _json(definition.input_schema),
                    int(definition.deterministic),
                    definition.side_effect_class, _now(),
                ),
            )

    def grant(self, employee_id: str, tool_name: str) -> None:
        if not self.conn.execute(
            "SELECT 1 FROM tool_definitions WHERE tool_name=?", (tool_name,)
        ).fetchone():
            raise KeyError(tool_name)
        with self.conn:
            self.conn.execute(
                """INSERT OR IGNORE INTO employee_tool_grants
                (employee_id,tool_name,granted_at) VALUES (?,?,?)""",
                (employee_id, tool_name, _now()),
            )
        self.kernel.record_activity(
            "Employee", employee_id, "TOOL_GRANTED", {"tool_name": tool_name}
        )

    def discover(self, employee_id: str) -> list[dict]:
        rows = self.conn.execute(
            """SELECT d.tool_name,d.description,d.input_schema_json,
                      d.deterministic,d.side_effect_class
            FROM tool_definitions d
            JOIN employee_tool_grants g ON g.tool_name=d.tool_name
            WHERE g.employee_id=?
            ORDER BY d.tool_name""",
            (employee_id,),
        ).fetchall()
        return [
            {
                "name": r["tool_name"],
                "description": r["description"],
                "input_schema": json.loads(r["input_schema_json"]),
                "deterministic": bool(r["deterministic"]),
                "side_effect_class": r["side_effect_class"],
            }
            for r in rows
        ]

    def _validate_required(self, schema: dict, payload: dict) -> None:
        missing = [k for k in schema.get("required", []) if k not in payload]
        if missing:
            raise ToolInputError(f"missing required fields: {missing}")

    def _check_budget(self, work_order_id: str) -> None:
        row = self.conn.execute(
            "SELECT budget_json FROM work_orders WHERE work_order_id=?", (work_order_id,)
        ).fetchone()
        if not row:
            raise KeyError(work_order_id)
        budget = json.loads(row["budget_json"])
        limit = budget.get("max_tool_calls")
        if limit is None:
            return
        used = self.conn.execute(
            """SELECT COUNT(*) c FROM tool_invocations
            WHERE work_order_id=?""",
            (work_order_id,),
        ).fetchone()["c"]
        if used >= int(limit):
            raise ToolBudgetExceeded(
                f"work order {work_order_id} exhausted max_tool_calls={limit}"
            )

    def invoke(
        self,
        *,
        employee_id: str,
        work_order_id: str,
        tool_name: str,
        arguments: dict,
        task_id: str | None = None,
    ) -> Any:
        grant = self.conn.execute(
            """SELECT d.input_schema_json,d.side_effect_class
            FROM tool_definitions d
            JOIN employee_tool_grants g ON g.tool_name=d.tool_name
            WHERE g.employee_id=? AND g.tool_name=?""",
            (employee_id, tool_name),
        ).fetchone()
        if not grant:
            raise ToolPermissionError(
                f"employee {employee_id} is not granted tool {tool_name}"
            )
        if grant["side_effect_class"] == "PRIVILEGED":
            raise ToolPermissionError(
                "P1.3B does not execute privileged tools"
            )
        handler = self._handlers.get(tool_name)
        if handler is None:
            raise RuntimeError(f"tool handler not loaded: {tool_name}")

        self._check_budget(work_order_id)
        self._validate_required(json.loads(grant["input_schema_json"]), arguments)

        iid = _id("TOOL")
        started = _now()
        with self.conn:
            self.conn.execute(
                """INSERT INTO tool_invocations
                (invocation_id,work_order_id,task_id,employee_id,tool_name,input_json,
                 output_json,status,error_text,started_at,completed_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    iid, work_order_id, task_id, employee_id, tool_name,
                    _json(arguments), None, "RUNNING", None, started, None,
                ),
            )
        try:
            output = handler(arguments)
        except Exception as exc:
            completed = _now()
            with self.conn:
                self.conn.execute(
                    """UPDATE tool_invocations SET status='ERROR',error_text=?,completed_at=?
                    WHERE invocation_id=?""",
                    (str(exc), completed, iid),
                )
            self.kernel.record_activity(
                "WorkOrder", work_order_id, "TOOL_FAILED",
                {"invocation_id": iid, "employee_id": employee_id, "tool_name": tool_name},
            )
            raise

        completed = _now()
        with self.conn:
            self.conn.execute(
                """UPDATE tool_invocations
                SET status='COMPLETED',output_json=?,completed_at=?
                WHERE invocation_id=?""",
                (_json(output), completed, iid),
            )
        self.kernel.record_activity(
            "WorkOrder", work_order_id, "TOOL_COMPLETED",
            {"invocation_id": iid, "employee_id": employee_id, "tool_name": tool_name},
        )
        return output
