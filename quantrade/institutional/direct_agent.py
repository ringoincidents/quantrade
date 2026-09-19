from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from .employee_agent import ModelProvider
from .service import InstitutionalKernel
from .tools import ToolRegistry


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DirectAgentRunner:
    """Minimal single-agent baseline for controlled QuanTrade experiments.

    It intentionally omits Workspace persistence, cross-office delegation,
    institutional messages, artifact promotion and dependency semantics.
    It keeps the same provider, ToolRegistry, employee grants, WorkOrder budget
    and task packet so the experiment isolates institutional-harness effects.
    """

    ALLOWED_ACTIONS = {"TOOL", "SAVE_WORKSPACE", "FINISH"}

    def __init__(
        self,
        kernel: InstitutionalKernel,
        tools: ToolRegistry,
        provider: ModelProvider,
        *,
        max_iterations: int = 20,
    ):
        self.kernel = kernel
        self.conn = kernel.conn
        self.tools = tools
        self.provider = provider
        self.max_iterations = max_iterations

    def _model_action(
        self,
        *,
        employee_id: str,
        work_order_id: str,
        context: dict,
    ):
        call_id = _id("MODEL")
        started = _now()
        with self.conn:
            self.conn.execute(
                """INSERT INTO model_calls
                (model_call_id,employee_id,work_order_id,task_id,provider,model,
                 input_context_json,output_action_json,status,error_text,started_at,completed_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    call_id, employee_id, work_order_id, None,
                    self.provider.provider_name, self.provider.model_name,
                    json.dumps(context, ensure_ascii=False, sort_keys=True),
                    None, "RUNNING", None, started, None,
                ),
            )
        try:
            action = self.provider.next_action(context)
            if action.kind not in self.ALLOWED_ACTIONS:
                raise ValueError(
                    f"direct baseline does not support action {action.kind}"
                )
        except Exception as exc:
            with self.conn:
                self.conn.execute(
                    """UPDATE model_calls SET status='ERROR',error_text=?,completed_at=?
                    WHERE model_call_id=?""",
                    (str(exc), _now(), call_id),
                )
            raise
        with self.conn:
            self.conn.execute(
                """UPDATE model_calls SET output_action_json=?,status='COMPLETED',
                   completed_at=? WHERE model_call_id=?""",
                (
                    json.dumps(
                        {"kind": action.kind, "payload": action.payload},
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    _now(),
                    call_id,
                ),
            )
        return action

    def run(
        self,
        *,
        employee_id: str,
        work_order_id: str,
        task_packet: dict,
    ) -> dict:
        scratchpad: dict = {}
        recent_results: list[dict] = []
        for iteration in range(1, self.max_iterations + 1):
            context = {
                "mode": "DIRECT_SINGLE_AGENT",
                "task_packet": task_packet,
                "scratchpad": scratchpad,
                "available_tools": self.tools.discover(employee_id),
                "recent_tool_results": recent_results[-8:],
                "rules": {
                    "use_only_available_tools": True,
                    "deterministic_calculations_via_tools": True,
                    "live_orders_forbidden": True,
                    "return_one_structured_action": True,
                },
            }
            action = self._model_action(
                employee_id=employee_id,
                work_order_id=work_order_id,
                context=context,
            )
            payload = action.payload
            if action.kind == "TOOL":
                try:
                    output = self.tools.invoke(
                        employee_id=employee_id,
                        work_order_id=work_order_id,
                        tool_name=payload["tool_name"],
                        arguments=payload.get("arguments", {}),
                    )
                    recent_results.append({
                        "tool_name": payload["tool_name"],
                        "status": "COMPLETED",
                        "output": output,
                    })
                except Exception as exc:
                    recent_results.append({
                        "tool_name": payload.get("tool_name"),
                        "status": "ERROR",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    })
            elif action.kind == "SAVE_WORKSPACE":
                scratchpad.update(payload.get("state", {}))
            elif action.kind == "FINISH":
                summary = payload.get("summary", "")
                self.kernel.record_activity(
                    "WorkOrder",
                    work_order_id,
                    "DIRECT_AGENT_FINISHED",
                    {
                        "employee_id": employee_id,
                        "summary": summary,
                        "iterations": iteration,
                    },
                )
                with self.conn:
                    self.conn.execute(
                        """UPDATE work_orders SET status='COMPLETED',updated_at=?
                        WHERE work_order_id=?""",
                        (_now(), work_order_id),
                    )
                return {
                    "status": "COMPLETED",
                    "summary": summary,
                    "iterations": iteration,
                }
        raise RuntimeError(
            f"direct agent exceeded max_iterations={self.max_iterations}"
        )
