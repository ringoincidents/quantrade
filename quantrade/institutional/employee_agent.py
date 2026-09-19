from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from .organization import OrganizationRuntime
from .service import InstitutionalKernel
from .tools import ToolRegistry


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


@dataclass(frozen=True)
class ModelAction:
    kind: str
    payload: dict


class ModelProvider(Protocol):
    provider_name: str
    model_name: str

    def next_action(self, context: dict) -> ModelAction:
        """Return one structured action. Provider must not mutate runtime state."""


class EmployeeAgent:
    """Provider-neutral reasoning loop for a QuanTrade employee.

    The model chooses structured actions; runtime code enforces permissions,
    budgets, persistence and audit.
    """

    ALLOWED_ACTIONS = {
        "TOOL",
        "UPDATE_PLAN",
        "REQUEST_WORK",
        "SAVE_WORKSPACE",
        "CREATE_ARTIFACT",
        "FINISH",
    }

    def __init__(
        self,
        kernel: InstitutionalKernel,
        organization: OrganizationRuntime,
        tools: ToolRegistry,
        provider: ModelProvider,
        *,
        max_iterations: int = 20,
    ):
        self.kernel = kernel
        self.org = organization
        self.tools = tools
        self.provider = provider
        self.max_iterations = max_iterations
        self.conn = kernel.conn

    def _employee(self, employee_id: str) -> dict:
        row = self.conn.execute(
            "SELECT * FROM employees WHERE employee_id=?", (employee_id,)
        ).fetchone()
        if not row:
            raise KeyError(employee_id)
        result = dict(row)
        for key in ("authority_json", "model_profile_json", "workstation_profile_json"):
            result[key[:-5]] = json.loads(result.pop(key))
        return result

    def _work_order(self, work_order_id: str) -> dict:
        row = self.conn.execute(
            "SELECT * FROM work_orders WHERE work_order_id=?", (work_order_id,)
        ).fetchone()
        if not row:
            raise KeyError(work_order_id)
        result = dict(row)
        for key in ("constraints_json", "authority_scope_json", "budget_json"):
            result[key[:-5]] = json.loads(result.pop(key))
        return result

    def _workspace(self, employee_id: str, work_order_id: str) -> tuple[str, dict]:
        wsid = self.org.get_or_create_workspace(employee_id, work_order_id)
        row = self.conn.execute(
            "SELECT state_json FROM workspaces WHERE workspace_id=?", (wsid,)
        ).fetchone()
        return wsid, json.loads(row["state_json"])

    def _task(self, task_id: str | None) -> dict | None:
        if not task_id:
            return None
        row = self.conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if not row:
            raise KeyError(task_id)
        result = dict(row)
        result["plan"] = json.loads(result.pop("plan_json"))
        return result

    def _messages(self, work_order_id: str) -> list[dict]:
        return [
            dict(r) for r in self.conn.execute(
                """SELECT sender_type,sender_id,recipient_type,recipient_id,body,created_at
                FROM org_messages WHERE work_order_id=? ORDER BY created_at""",
                (work_order_id,),
            )
        ]

    def _recent_tool_results(self, work_order_id: str, limit: int = 8) -> list[dict]:
        rows = self.conn.execute(
            """SELECT tool_name,input_json,output_json,status,error_text,completed_at
            FROM tool_invocations WHERE work_order_id=?
            ORDER BY started_at DESC LIMIT ?""",
            (work_order_id, limit),
        ).fetchall()
        out = []
        for r in reversed(rows):
            out.append({
                "tool_name": r["tool_name"],
                "input": json.loads(r["input_json"]),
                "output": json.loads(r["output_json"]) if r["output_json"] else None,
                "status": r["status"],
                "error": r["error_text"],
                "completed_at": r["completed_at"],
            })
        return out

    def _context(
        self, employee_id: str, work_order_id: str, task_id: str | None
    ) -> dict:
        wsid, workspace = self._workspace(employee_id, work_order_id)
        return {
            "employee": self._employee(employee_id),
            "work_order": self._work_order(work_order_id),
            "task": self._task(task_id),
            "workspace_id": wsid,
            "workspace": workspace,
            "available_tools": self.tools.discover(employee_id),
            "messages": self._messages(work_order_id),
            "recent_tool_results": self._recent_tool_results(work_order_id),
            "rules": {
                "do_not_invent_tools": True,
                "deterministic_calculations_via_tools": True,
                "live_orders_forbidden": True,
                "artifact_is_not_evidence_by_default": True,
            },
        }

    def _ask_model(
        self, employee_id: str, work_order_id: str, task_id: str | None, context: dict
    ) -> ModelAction:
        cid = _id("MODEL")
        started = _now()
        with self.conn:
            self.conn.execute(
                """INSERT INTO model_calls
                (model_call_id,employee_id,work_order_id,task_id,provider,model,
                 input_context_json,output_action_json,status,error_text,started_at,completed_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    cid, employee_id, work_order_id, task_id,
                    self.provider.provider_name, self.provider.model_name,
                    _json(context), None, "RUNNING", None, started, None,
                ),
            )
        try:
            action = self.provider.next_action(context)
            if action.kind not in self.ALLOWED_ACTIONS:
                raise ValueError(f"unsupported model action: {action.kind}")
        except Exception as exc:
            with self.conn:
                self.conn.execute(
                    """UPDATE model_calls SET status='ERROR',error_text=?,completed_at=?
                    WHERE model_call_id=?""",
                    (str(exc), _now(), cid),
                )
            raise
        with self.conn:
            self.conn.execute(
                """UPDATE model_calls
                SET output_action_json=?,status='COMPLETED',completed_at=?
                WHERE model_call_id=?""",
                (_json({"kind": action.kind, "payload": action.payload}), _now(), cid),
            )
        self.kernel.record_activity(
            "WorkOrder", work_order_id, "MODEL_ACTION",
            {
                "model_call_id": cid,
                "employee_id": employee_id,
                "kind": action.kind,
                "provider": self.provider.provider_name,
                "model": self.provider.model_name,
            },
        )
        return action

    def run(
        self,
        *,
        employee_id: str,
        work_order_id: str,
        task_id: str | None = None,
    ) -> dict:
        current_task = task_id
        if current_task is None:
            current_task = self.org.create_task(
                work_order_id,
                "Interpret the broad objective, plan the analysis, and produce a sourced report.",
                creator_employee_id=employee_id,
                assignee_employee_id=employee_id,
                plan={"status": "model_planning"},
            )

        for iteration in range(1, self.max_iterations + 1):
            context = self._context(employee_id, work_order_id, current_task)
            action = self._ask_model(
                employee_id, work_order_id, current_task, context
            )
            p = action.payload

            if action.kind == "TOOL":
                output = self.tools.invoke(
                    employee_id=employee_id,
                    work_order_id=work_order_id,
                    task_id=current_task,
                    tool_name=p["tool_name"],
                    arguments=p.get("arguments", {}),
                )
                wsid, state = self._workspace(employee_id, work_order_id)
                state.setdefault("tool_outputs", []).append({
                    "tool_name": p["tool_name"],
                    "label": p.get("label"),
                    "output": output,
                })
                self.org.save_workspace_state(wsid, state)

            elif action.kind == "UPDATE_PLAN":
                self.org.update_task_plan(current_task, p["plan"])

            elif action.kind == "REQUEST_WORK":
                self.org.create_work_request(
                    work_order_id,
                    employee_id,
                    p["recipient_office"],
                    p["objective"],
                    task_id=current_task,
                    recipient_employee_id=p.get("recipient_employee_id"),
                    context_refs=p.get("context_refs", []),
                )

            elif action.kind == "SAVE_WORKSPACE":
                wsid, state = self._workspace(employee_id, work_order_id)
                state.update(p["state"])
                self.org.save_workspace_state(wsid, state)

            elif action.kind == "CREATE_ARTIFACT":
                self.org.create_artifact(
                    work_order_id,
                    p["artifact_type"],
                    p["title"],
                    producer_employee_id=employee_id,
                    task_id=current_task,
                    content_ref=p.get("content_ref"),
                    metadata=p.get("metadata", {}),
                )

            elif action.kind == "FINISH":
                with self.conn:
                    self.conn.execute(
                        "UPDATE tasks SET status='COMPLETED',updated_at=? WHERE task_id=?",
                        (_now(), current_task),
                    )
                    self.conn.execute(
                        "UPDATE work_orders SET status='COMPLETED',updated_at=? WHERE work_order_id=?",
                        (_now(), work_order_id),
                    )
                self.kernel.record_activity(
                    "WorkOrder", work_order_id, "EMPLOYEE_WORK_FINISHED",
                    {
                        "employee_id": employee_id,
                        "task_id": current_task,
                        "summary": p.get("summary", ""),
                    },
                )
                return {
                    "status": "COMPLETED",
                    "iterations": iteration,
                    "task_id": current_task,
                    "summary": p.get("summary", ""),
                }

        raise RuntimeError(
            f"employee loop exceeded max_iterations={self.max_iterations}"
        )


class ScriptedModelProvider:
    """Deterministic CI provider.

    This proves the runtime contract, not LLM intelligence. Production model
    adapters must implement the same ModelProvider interface.
    """

    provider_name = "scripted"
    model_name = "ci-script-v1"

    def __init__(self, actions: list[ModelAction]):
        self.actions = list(actions)

    def next_action(self, context: dict) -> ModelAction:
        if not self.actions:
            raise RuntimeError("scripted provider exhausted")
        return self.actions.pop(0)
