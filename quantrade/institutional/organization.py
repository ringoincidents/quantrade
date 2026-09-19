from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from .service import InstitutionalKernel


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class OrganizationRuntime:
    """Common work/communication substrate for all QuanTrade offices.

    Office-specific intelligence belongs in employee/model/tool profiles. The
    transport, persistence and audit semantics remain shared.
    """

    def __init__(self, kernel: InstitutionalKernel):
        self.kernel = kernel
        self.conn = kernel.conn

    def create_employee(
        self,
        office_id: str,
        role: str,
        charter: str,
        *,
        authority: dict | None = None,
        model_profile: dict | None = None,
        workstation_profile: dict | None = None,
        employee_id: str | None = None,
    ) -> str:
        eid = employee_id or _id("EMP")
        now = _now()
        with self.conn:
            self.conn.execute(
                """INSERT INTO employees
                (employee_id,office_id,role,charter,authority_json,model_profile_json,
                 workstation_profile_json,status,created_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    eid, office_id, role, charter,
                    _json(authority or {}), _json(model_profile or {}),
                    _json(workstation_profile or {}), "ACTIVE", now,
                ),
            )
        self.kernel.record_activity(
            "Employee", eid, "EMPLOYEE_REGISTERED",
            {"office_id": office_id, "role": role},
        )
        return eid

    def create_work_order(
        self,
        *,
        issuer_type: str,
        issuer_id: str,
        objective: str,
        recipient_office: str | None = None,
        recipient_employee_id: str | None = None,
        constraints: dict | None = None,
        urgency: str = "NORMAL",
        linked_case_id: str | None = None,
        authority_scope: dict | None = None,
        budget: dict | None = None,
    ) -> str:
        wid = _id("WO")
        now = _now()
        with self.conn:
            self.conn.execute(
                """INSERT INTO work_orders
                (work_order_id,issuer_type,issuer_id,recipient_office,recipient_employee_id,
                 objective,constraints_json,urgency,linked_case_id,authority_scope_json,
                 budget_json,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    wid, issuer_type, issuer_id, recipient_office, recipient_employee_id,
                    objective, _json(constraints or {}), urgency, linked_case_id,
                    _json(authority_scope or {}), _json(budget or {}),
                    "OPEN", now, now,
                ),
            )
        self.kernel.record_activity(
            "WorkOrder", wid, "WORK_ORDER_CREATED",
            {
                "issuer_type": issuer_type,
                "issuer_id": issuer_id,
                "recipient_office": recipient_office,
                "recipient_employee_id": recipient_employee_id,
                "objective": objective,
            },
        )
        return wid

    def create_task(
        self,
        work_order_id: str,
        objective: str,
        *,
        creator_employee_id: str | None = None,
        assignee_employee_id: str | None = None,
        plan: dict | None = None,
    ) -> str:
        tid = _id("TASK")
        now = _now()
        with self.conn:
            self.conn.execute(
                """INSERT INTO tasks
                (task_id,work_order_id,creator_employee_id,assignee_employee_id,
                 objective,plan_json,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    tid, work_order_id, creator_employee_id, assignee_employee_id,
                    objective, _json(plan or {}), "OPEN", now, now,
                ),
            )
        self.kernel.record_activity(
            "WorkOrder", work_order_id, "TASK_CREATED",
            {"task_id": tid, "creator_employee_id": creator_employee_id, "objective": objective},
        )
        return tid

    def update_task_plan(self, task_id: str, plan: dict) -> None:
        now = _now()
        row = self.conn.execute(
            "SELECT work_order_id FROM tasks WHERE task_id=?", (task_id,)
        ).fetchone()
        if not row:
            raise KeyError(task_id)
        with self.conn:
            self.conn.execute(
                "UPDATE tasks SET plan_json=?,updated_at=? WHERE task_id=?",
                (_json(plan), now, task_id),
            )
        self.kernel.record_activity(
            "WorkOrder", row["work_order_id"], "TASK_PLAN_UPDATED",
            {"task_id": task_id, "plan": plan},
        )

    def create_work_request(
        self,
        work_order_id: str,
        issuer_employee_id: str,
        recipient_office: str,
        objective: str,
        *,
        task_id: str | None = None,
        recipient_employee_id: str | None = None,
        context_refs: list[str] | None = None,
    ) -> str:
        rid = _id("REQ")
        now = _now()
        with self.conn:
            self.conn.execute(
                """INSERT INTO work_requests
                (request_id,work_order_id,task_id,issuer_employee_id,recipient_office,
                 recipient_employee_id,objective,context_refs_json,status,response_note,
                 created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    rid, work_order_id, task_id, issuer_employee_id, recipient_office,
                    recipient_employee_id, objective, _json(context_refs or []),
                    "OPEN", None, now, now,
                ),
            )
        self.kernel.record_activity(
            "WorkOrder", work_order_id, "WORK_REQUEST_CREATED",
            {
                "request_id": rid,
                "issuer_employee_id": issuer_employee_id,
                "recipient_office": recipient_office,
                "objective": objective,
            },
        )
        return rid

    def respond_work_request(
        self,
        request_id: str,
        *,
        status: str,
        response_note: str,
    ) -> None:
        if status not in {"ACCEPTED", "NEEDS_CLARIFICATION", "REJECTED", "COMPLETED"}:
            raise ValueError(f"unsupported request status: {status}")
        row = self.conn.execute(
            "SELECT work_order_id FROM work_requests WHERE request_id=?", (request_id,)
        ).fetchone()
        if not row:
            raise KeyError(request_id)
        now = _now()
        with self.conn:
            self.conn.execute(
                """UPDATE work_requests
                SET status=?,response_note=?,updated_at=? WHERE request_id=?""",
                (status, response_note, now, request_id),
            )
        self.kernel.record_activity(
            "WorkOrder", row["work_order_id"], "WORK_REQUEST_UPDATED",
            {"request_id": request_id, "status": status, "response_note": response_note},
        )

    def send_message(
        self,
        *,
        sender_type: str,
        sender_id: str,
        recipient_type: str,
        recipient_id: str,
        body: str,
        work_order_id: str | None = None,
        task_id: str | None = None,
        request_id: str | None = None,
    ) -> str:
        mid = _id("MSG")
        now = _now()
        with self.conn:
            self.conn.execute(
                """INSERT INTO org_messages
                (message_id,work_order_id,task_id,request_id,sender_type,sender_id,
                 recipient_type,recipient_id,body,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    mid, work_order_id, task_id, request_id, sender_type, sender_id,
                    recipient_type, recipient_id, body, now,
                ),
            )
        if work_order_id:
            self.kernel.record_activity(
                "WorkOrder", work_order_id, "MESSAGE_SENT",
                {"message_id": mid, "sender_id": sender_id, "recipient_id": recipient_id},
            )
        return mid

    def get_or_create_workspace(self, employee_id: str, work_order_id: str) -> str:
        row = self.conn.execute(
            """SELECT workspace_id FROM workspaces
            WHERE employee_id=? AND work_order_id=?""",
            (employee_id, work_order_id),
        ).fetchone()
        if row:
            return row["workspace_id"]
        wsid = _id("WS")
        now = _now()
        with self.conn:
            self.conn.execute(
                """INSERT INTO workspaces
                (workspace_id,employee_id,work_order_id,state_json,created_at,updated_at)
                VALUES (?,?,?,?,?,?)""",
                (wsid, employee_id, work_order_id, _json({}), now, now),
            )
        self.kernel.record_activity(
            "WorkOrder", work_order_id, "WORKSPACE_CREATED",
            {"workspace_id": wsid, "employee_id": employee_id},
        )
        return wsid

    def save_workspace_state(self, workspace_id: str, state: dict) -> None:
        row = self.conn.execute(
            "SELECT work_order_id FROM workspaces WHERE workspace_id=?", (workspace_id,)
        ).fetchone()
        if not row:
            raise KeyError(workspace_id)
        now = _now()
        with self.conn:
            self.conn.execute(
                "UPDATE workspaces SET state_json=?,updated_at=? WHERE workspace_id=?",
                (_json(state), now, workspace_id),
            )
        self.kernel.record_activity(
            "WorkOrder", row["work_order_id"], "WORKSPACE_SAVED",
            {"workspace_id": workspace_id},
        )

    def create_artifact(
        self,
        work_order_id: str,
        artifact_type: str,
        title: str,
        *,
        producer_employee_id: str | None = None,
        task_id: str | None = None,
        content_ref: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        aid = _id("ART")
        now = _now()
        with self.conn:
            self.conn.execute(
                """INSERT INTO artifacts
                (artifact_id,work_order_id,task_id,producer_employee_id,artifact_type,
                 title,content_ref,metadata_json,created_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    aid, work_order_id, task_id, producer_employee_id, artifact_type,
                    title, content_ref, _json(metadata or {}), now,
                ),
            )
        self.kernel.record_activity(
            "WorkOrder", work_order_id, "ARTIFACT_CREATED",
            {"artifact_id": aid, "artifact_type": artifact_type, "title": title},
        )
        return aid

    def employee_inbox(self, employee_id: str) -> dict:
        orders = [
            dict(r) for r in self.conn.execute(
                """SELECT * FROM work_orders
                WHERE recipient_employee_id=? AND status NOT IN ('COMPLETED','CANCELLED')
                ORDER BY created_at""",
                (employee_id,),
            )
        ]
        requests = [
            dict(r) for r in self.conn.execute(
                """SELECT * FROM work_requests
                WHERE recipient_employee_id=? AND status NOT IN ('COMPLETED','REJECTED')
                ORDER BY created_at""",
                (employee_id,),
            )
        ]
        messages = [
            dict(r) for r in self.conn.execute(
                """SELECT * FROM org_messages
                WHERE recipient_type='EMPLOYEE' AND recipient_id=?
                ORDER BY created_at""",
                (employee_id,),
            )
        ]
        return {"work_orders": orders, "work_requests": requests, "messages": messages}
