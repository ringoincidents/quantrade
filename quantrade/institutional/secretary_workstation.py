from __future__ import annotations

from datetime import datetime, timezone

from .organization import OrganizationRuntime
from .tools import ToolDefinition, ToolRegistry


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SecretaryWorkstation:
    """Organizational tools used by the Founder-facing Secretary employee."""

    def __init__(self, organization: OrganizationRuntime):
        self.org = organization
        self.conn = organization.conn

    def employee_directory(self, args: dict) -> list[dict]:
        office = args.get("office_id")
        if office:
            rows = self.conn.execute(
                """SELECT employee_id,office_id,role,charter,status
                FROM employees WHERE status='ACTIVE' AND office_id=?
                ORDER BY employee_id""",
                (office,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT employee_id,office_id,role,charter,status
                FROM employees WHERE status='ACTIVE' ORDER BY office_id,employee_id"""
            ).fetchall()
        return [dict(r) for r in rows]

    def delegate_work(self, args: dict) -> dict:
        parent = args["parent_work_order_id"]
        if not self.conn.execute(
            "SELECT 1 FROM work_orders WHERE work_order_id=?", (parent,)
        ).fetchone():
            raise KeyError(parent)

        child = self.org.create_work_order(
            issuer_type="EMPLOYEE",
            issuer_id=args["issuer_employee_id"],
            recipient_office=args["recipient_office"],
            recipient_employee_id=args.get("recipient_employee_id"),
            objective=args["objective"],
            constraints=args.get("constraints", {}),
            urgency=args.get("urgency", "NORMAL"),
            authority_scope=args.get("authority_scope", {"research": True, "trade": False}),
            budget=args.get("budget", {}),
        )
        with self.conn:
            self.conn.execute(
                """INSERT INTO work_order_links
                (parent_work_order_id,child_work_order_id,relation,created_at)
                VALUES (?,?,?,?)""",
                (parent, child, "DELEGATED", _now()),
            )
        self.org.kernel.record_activity(
            "WorkOrder", parent, "WORK_DELEGATED",
            {
                "child_work_order_id": child,
                "recipient_office": args["recipient_office"],
                "recipient_employee_id": args.get("recipient_employee_id"),
            },
        )
        return {"child_work_order_id": child, "status": "OPEN"}

    def child_status(self, args: dict) -> list[dict]:
        rows = self.conn.execute(
            """SELECT w.work_order_id,w.recipient_office,w.recipient_employee_id,
                      w.objective,w.status,w.updated_at
            FROM work_order_links l
            JOIN work_orders w ON w.work_order_id=l.child_work_order_id
            WHERE l.parent_work_order_id=?
            ORDER BY w.created_at""",
            (args["parent_work_order_id"],),
        ).fetchall()
        return [dict(r) for r in rows]


def install_secretary_workstation(
    registry: ToolRegistry,
    employee_id: str,
    organization: OrganizationRuntime,
) -> None:
    workstation = SecretaryWorkstation(organization)
    definitions = [
        (
            ToolDefinition(
                "org.employee_directory",
                "Discover active offices/employees and their charters before routing work.",
                {"required": []},
                True,
                "READ_ONLY",
            ),
            workstation.employee_directory,
        ),
        (
            ToolDefinition(
                "org.delegate_work",
                "Create a bounded child WorkOrder and link it to the current Founder/Secretary WorkOrder.",
                {
                    "required": [
                        "parent_work_order_id", "issuer_employee_id",
                        "recipient_office", "objective",
                    ]
                },
                True,
                "ARTIFACT_WRITE",
            ),
            workstation.delegate_work,
        ),
        (
            ToolDefinition(
                "org.child_status",
                "Read status of child WorkOrders delegated from a parent WorkOrder.",
                {"required": ["parent_work_order_id"]},
                True,
                "READ_ONLY",
            ),
            workstation.child_status,
        ),
    ]
    for definition, handler in definitions:
        registry.register(definition, handler)
        registry.grant(employee_id, definition.name)
