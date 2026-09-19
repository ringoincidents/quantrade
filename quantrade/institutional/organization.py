from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
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

    def _active_employee(self, employee_id: str) -> dict:
        row = self.conn.execute(
            "SELECT * FROM employees WHERE employee_id=?", (employee_id,)
        ).fetchone()
        if not row:
            raise KeyError(employee_id)
        employee = dict(row)
        if employee["status"] != "ACTIVE":
            raise ValueError(f"employee is not active: {employee_id}")
        return employee

    @staticmethod
    def _lease_deadline(lease_seconds: int) -> str:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        return (datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)).isoformat()

    def acquire_work_order_lease(
        self,
        work_order_id: str,
        employee_id: str,
        *,
        worker_id: str,
        lease_seconds: int = 300,
    ) -> str:
        """Acquire or reclaim a durable execution lease for one WorkOrder.

        Employee ownership and worker-process ownership are intentionally
        separate. A crashed process loses its lease after expiry; the same
        institutional employee can then resume the durable WorkOrder.
        """
        employee = self._active_employee(employee_id)
        order = self.conn.execute(
            "SELECT * FROM work_orders WHERE work_order_id=?", (work_order_id,)
        ).fetchone()
        if not order:
            raise KeyError(work_order_id)
        if order["status"] not in {"OPEN", "ASSIGNED"}:
            raise ValueError(f"work order is not leasable: {order['status']}")
        if order["recipient_office"] and order["recipient_office"] != employee["office_id"]:
            raise ValueError("employee belongs to a different office")
        if order["recipient_employee_id"] not in (None, employee_id):
            raise ValueError("work order is assigned to a different employee")

        existing = self.conn.execute(
            "SELECT * FROM work_order_leases WHERE work_order_id=?", (work_order_id,)
        ).fetchone()
        now = datetime.now(timezone.utc)
        generation = 1
        reclaimed = False
        if existing:
            expires = datetime.fromisoformat(existing["expires_at"])
            if expires > now:
                raise ValueError("work order already has an active lease")
            generation = int(existing["generation"]) + 1
            reclaimed = True

        token = _id("LEASE")
        now_text = now.isoformat()
        expires_at = self._lease_deadline(lease_seconds)
        with self.conn:
            if existing:
                self.conn.execute(
                    "DELETE FROM work_order_leases WHERE work_order_id=?",
                    (work_order_id,),
                )
            self.conn.execute(
                """INSERT INTO work_order_leases
                (work_order_id,employee_id,worker_id,lease_token,generation,
                 claimed_at,heartbeat_at,expires_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    work_order_id, employee_id, worker_id, token, generation,
                    now_text, now_text, expires_at,
                ),
            )
            self.conn.execute(
                """UPDATE work_orders
                SET recipient_employee_id=?,status='ASSIGNED',updated_at=?
                WHERE work_order_id=?""",
                (employee_id, now_text, work_order_id),
            )
        self.kernel.record_activity(
            "WorkOrder",
            work_order_id,
            "WORK_ORDER_RECLAIMED" if reclaimed else "WORK_ORDER_CLAIMED",
            {
                "employee_id": employee_id,
                "office_id": employee["office_id"],
                "worker_id": worker_id,
                "generation": generation,
                "expires_at": expires_at,
            },
        )
        return token

    def claim_office_work_order(
        self,
        employee_id: str,
        *,
        worker_id: str | None = None,
        lease_seconds: int = 300,
    ) -> str | None:
        """Assign and lease the oldest unclaimed office WorkOrder."""
        employee = self._active_employee(employee_id)
        row = self.conn.execute(
            """SELECT work_order_id FROM work_orders
            WHERE recipient_office=? AND recipient_employee_id IS NULL AND status='OPEN'
            ORDER BY created_at LIMIT 1""",
            (employee["office_id"],),
        ).fetchone()
        if not row:
            return None
        wid = row["work_order_id"]
        try:
            self.acquire_work_order_lease(
                wid,
                employee_id,
                worker_id=worker_id or f"inline:{employee_id}",
                lease_seconds=lease_seconds,
            )
        except ValueError:
            return None
        return wid

    def claim_employee_work_order(
        self,
        employee_id: str,
        *,
        worker_id: str,
        lease_seconds: int = 300,
    ) -> dict | None:
        """Lease the oldest OPEN WorkOrder already assigned to this employee.

        This covers delegated child work and parent work that was resumed after
        a dependency completed.
        """
        self._active_employee(employee_id)
        row = self.conn.execute(
            """SELECT w.work_order_id FROM work_orders w
            LEFT JOIN work_order_leases l ON l.work_order_id=w.work_order_id
            WHERE w.recipient_employee_id=?
              AND w.status='OPEN'
              AND l.work_order_id IS NULL
            ORDER BY w.created_at LIMIT 1""",
            (employee_id,),
        ).fetchone()
        if not row:
            return None
        token = self.acquire_work_order_lease(
            row["work_order_id"],
            employee_id,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
        )
        return {
            "work_order_id": row["work_order_id"],
            "lease_token": token,
        }

    def current_work_order_lease(self, work_order_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM work_order_leases WHERE work_order_id=?",
            (work_order_id,),
        ).fetchone()
        return dict(row) if row else None

    def reclaim_expired_work_order(
        self,
        employee_id: str,
        *,
        worker_id: str,
        lease_seconds: int = 300,
    ) -> dict | None:
        """Reclaim the oldest expired lease owned by the same employee persona."""
        self._active_employee(employee_id)
        now = _now()
        row = self.conn.execute(
            """SELECT w.work_order_id,l.generation
            FROM work_orders w
            JOIN work_order_leases l ON l.work_order_id=w.work_order_id
            WHERE w.recipient_employee_id=?
              AND w.status='ASSIGNED'
              AND l.expires_at<=?
            ORDER BY l.expires_at,w.created_at LIMIT 1""",
            (employee_id, now),
        ).fetchone()
        if not row:
            return None
        token = self.acquire_work_order_lease(
            row["work_order_id"],
            employee_id,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
        )
        return {
            "work_order_id": row["work_order_id"],
            "lease_token": token,
            "generation": int(row["generation"]) + 1,
        }

    def heartbeat_work_order_lease(
        self,
        lease_token: str,
        *,
        worker_id: str,
        lease_seconds: int = 300,
    ) -> str:
        now = datetime.now(timezone.utc)
        row = self.conn.execute(
            "SELECT * FROM work_order_leases WHERE lease_token=?", (lease_token,)
        ).fetchone()
        if not row:
            raise KeyError(lease_token)
        if row["worker_id"] != worker_id:
            raise ValueError("lease belongs to a different worker")
        if datetime.fromisoformat(row["expires_at"]) <= now:
            raise ValueError("lease has expired")
        expires_at = self._lease_deadline(lease_seconds)
        with self.conn:
            self.conn.execute(
                """UPDATE work_order_leases
                SET heartbeat_at=?,expires_at=? WHERE lease_token=?""",
                (now.isoformat(), expires_at, lease_token),
            )
        self.kernel.record_activity(
            "WorkOrder", row["work_order_id"], "WORK_ORDER_LEASE_HEARTBEAT",
            {"worker_id": worker_id, "expires_at": expires_at},
        )
        return expires_at

    def validate_work_order_lease(
        self,
        work_order_id: str,
        *,
        lease_token: str,
        worker_id: str,
    ) -> bool:
        row = self.conn.execute(
            """SELECT expires_at FROM work_order_leases
            WHERE work_order_id=? AND lease_token=? AND worker_id=?""",
            (work_order_id, lease_token, worker_id),
        ).fetchone()
        if not row:
            return False
        return datetime.fromisoformat(row["expires_at"]) > datetime.now(timezone.utc)

    def release_work_order_lease(
        self,
        work_order_id: str,
        *,
        lease_token: str | None = None,
        reason: str = "RELEASED",
    ) -> None:
        row = self.conn.execute(
            "SELECT lease_token,worker_id FROM work_order_leases WHERE work_order_id=?",
            (work_order_id,),
        ).fetchone()
        if not row:
            return
        if lease_token is not None and row["lease_token"] != lease_token:
            raise ValueError("lease token mismatch")
        with self.conn:
            self.conn.execute(
                "DELETE FROM work_order_leases WHERE work_order_id=?",
                (work_order_id,),
            )
        self.kernel.record_activity(
            "WorkOrder", work_order_id, "WORK_ORDER_LEASE_RELEASED",
            {"worker_id": row["worker_id"], "reason": reason},
        )

    def accept_work_request(self, request_id: str, employee_id: str) -> str:
        """Accept a cross-office request and materialize it as child WorkOrder."""
        employee = self._active_employee(employee_id)
        row = self.conn.execute(
            "SELECT * FROM work_requests WHERE request_id=?", (request_id,)
        ).fetchone()
        if not row:
            raise KeyError(request_id)
        request = dict(row)
        if request["status"] != "OPEN":
            raise ValueError(f"work request is not open: {request_id}")
        if request["recipient_office"] != employee["office_id"]:
            raise ValueError("employee belongs to a different office")
        if request["recipient_employee_id"] not in (None, employee_id):
            raise ValueError("work request is assigned to a different employee")

        parent = self.conn.execute(
            "SELECT budget_json,linked_case_id FROM work_orders WHERE work_order_id=?",
            (request["work_order_id"],),
        ).fetchone()
        if not parent:
            raise KeyError(request["work_order_id"])
        context_refs = json.loads(request["context_refs_json"])
        child_id = self.create_work_order(
            issuer_type="EMPLOYEE",
            issuer_id=request["issuer_employee_id"],
            recipient_office=employee["office_id"],
            recipient_employee_id=employee_id,
            objective=request["objective"],
            constraints={
                "request_id": request_id,
                "parent_work_order_id": request["work_order_id"],
                "context_refs": context_refs,
            },
            linked_case_id=parent["linked_case_id"],
            authority_scope={"research": True, "trade": False},
            budget=json.loads(parent["budget_json"]),
        )
        now = _now()
        with self.conn:
            self.conn.execute(
                """INSERT INTO work_order_links
                (parent_work_order_id,child_work_order_id,relation,created_at)
                VALUES (?,?,?,?)""",
                (
                    request["work_order_id"], child_id,
                    f"WORK_REQUEST:{request_id}", now,
                ),
            )
            self.conn.execute(
                """UPDATE work_requests
                SET recipient_employee_id=?,status='ACCEPTED',updated_at=?
                WHERE request_id=?""",
                (employee_id, now, request_id),
            )
        self.kernel.record_activity(
            "WorkOrder", request["work_order_id"], "WORK_REQUEST_ACCEPTED",
            {
                "request_id": request_id,
                "employee_id": employee_id,
                "child_work_order_id": child_id,
            },
        )
        return child_id

    def claim_office_work_request(self, employee_id: str) -> dict | None:
        """Claim the oldest office request and return its child WorkOrder."""
        employee = self._active_employee(employee_id)
        row = self.conn.execute(
            """SELECT request_id FROM work_requests
            WHERE recipient_office=? AND recipient_employee_id IS NULL AND status='OPEN'
            ORDER BY created_at LIMIT 1""",
            (employee["office_id"],),
        ).fetchone()
        if not row:
            return None
        child_id = self.accept_work_request(row["request_id"], employee_id)
        return {"request_id": row["request_id"], "child_work_order_id": child_id}

    def pending_dependencies(self, work_order_id: str) -> list[dict]:
        blockers: list[dict] = []
        for row in self.conn.execute(
            """SELECT request_id,status,recipient_office,recipient_employee_id
            FROM work_requests
            WHERE work_order_id=? AND status NOT IN ('COMPLETED','REJECTED')
            ORDER BY created_at""",
            (work_order_id,),
        ):
            blockers.append({
                "kind": "WORK_REQUEST",
                "id": row["request_id"],
                "status": row["status"],
                "recipient_office": row["recipient_office"],
                "recipient_employee_id": row["recipient_employee_id"],
            })
        for row in self.conn.execute(
            """SELECT l.child_work_order_id,w.status,l.relation
            FROM work_order_links l
            JOIN work_orders w ON w.work_order_id=l.child_work_order_id
            WHERE l.parent_work_order_id=?
              AND w.status NOT IN ('COMPLETED','CANCELLED')
            ORDER BY l.created_at""",
            (work_order_id,),
        ):
            blockers.append({
                "kind": "CHILD_WORK_ORDER",
                "id": row["child_work_order_id"],
                "status": row["status"],
                "relation": row["relation"],
            })
        return blockers

    def complete_employee_work(
        self,
        *,
        employee_id: str,
        work_order_id: str,
        task_id: str,
        summary: str = "",
    ) -> dict:
        """Complete work only when delegated dependencies have reached terminal state."""
        blockers = self.pending_dependencies(work_order_id)
        now = _now()
        if blockers:
            with self.conn:
                self.conn.execute(
                    "UPDATE tasks SET status='WAITING_DEPENDENCY',updated_at=? WHERE task_id=?",
                    (now, task_id),
                )
                self.conn.execute(
                    """UPDATE work_orders SET status='WAITING_DEPENDENCY',updated_at=?
                    WHERE work_order_id=?""",
                    (now, work_order_id),
                )
            self.release_work_order_lease(
                work_order_id, reason="WAITING_DEPENDENCY"
            )
            self.kernel.record_activity(
                "WorkOrder", work_order_id, "WORK_COMPLETION_BLOCKED",
                {"employee_id": employee_id, "task_id": task_id, "blockers": blockers},
            )
            return {
                "status": "WAITING_DEPENDENCIES",
                "task_id": task_id,
                "blockers": blockers,
            }

        with self.conn:
            self.conn.execute(
                "UPDATE tasks SET status='COMPLETED',updated_at=? WHERE task_id=?",
                (now, task_id),
            )
            self.conn.execute(
                "UPDATE work_orders SET status='COMPLETED',updated_at=? WHERE work_order_id=?",
                (now, work_order_id),
            )
        self.release_work_order_lease(work_order_id, reason="COMPLETED")
        self.kernel.record_activity(
            "WorkOrder", work_order_id, "EMPLOYEE_WORK_FINISHED",
            {
                "employee_id": employee_id,
                "task_id": task_id,
                "summary": summary,
            },
        )

        # A child WorkOrder created from a WorkRequest resolves that request and
        # wakes a parent that was truthfully waiting for the dependency.
        link = self.conn.execute(
            """SELECT parent_work_order_id,relation FROM work_order_links
            WHERE child_work_order_id=? AND relation LIKE 'WORK_REQUEST:%'""",
            (work_order_id,),
        ).fetchone()
        if link:
            request_id = link["relation"].split(":", 1)[1]
            with self.conn:
                self.conn.execute(
                    """UPDATE work_requests
                    SET status='COMPLETED',response_note=?,updated_at=?
                    WHERE request_id=?""",
                    (summary, now, request_id),
                )
            self.kernel.record_activity(
                "WorkOrder", link["parent_work_order_id"], "WORK_REQUEST_COMPLETED",
                {
                    "request_id": request_id,
                    "child_work_order_id": work_order_id,
                    "summary": summary,
                },
            )
            parent = self.conn.execute(
                "SELECT status FROM work_orders WHERE work_order_id=?",
                (link["parent_work_order_id"],),
            ).fetchone()
            if parent and parent["status"] == "WAITING_DEPENDENCY":
                with self.conn:
                    self.conn.execute(
                        """UPDATE work_orders SET status='OPEN',updated_at=?
                        WHERE work_order_id=?""",
                        (now, link["parent_work_order_id"]),
                    )
                    self.conn.execute(
                        """UPDATE tasks SET status='OPEN',updated_at=?
                        WHERE work_order_id=? AND status='WAITING_DEPENDENCY'""",
                        (now, link["parent_work_order_id"]),
                    )
                self.kernel.record_activity(
                    "WorkOrder", link["parent_work_order_id"], "WORK_ORDER_RESUMED",
                    {"resolved_request_id": request_id},
                )

        return {
            "status": "COMPLETED",
            "task_id": task_id,
            "summary": summary,
        }

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
