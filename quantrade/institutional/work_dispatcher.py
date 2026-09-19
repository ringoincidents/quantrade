from __future__ import annotations

from collections.abc import Callable

from .employee_agent import EmployeeAgent, ModelProvider
from .organization import OrganizationRuntime
from .service import InstitutionalKernel
from .tools import ToolRegistry


ProviderFactory = Callable[[str, str], ModelProvider]


class WorkDispatcher:
    """Synchronous, event-driven employee work dispatcher.

    This is deliberately not a 24/7 scheduler. It proves that durable WorkOrders
    and WorkRequests can be picked up and executed by the correct employee
    runtime when a process is invoked. A future scheduler may call run_once()
    without changing the institutional work semantics.
    """

    def __init__(
        self,
        kernel: InstitutionalKernel,
        organization: OrganizationRuntime,
        tools: ToolRegistry,
        provider_factory: ProviderFactory,
        *,
        lease_seconds: int = 900,
        max_iterations: int = 20,
    ):
        self.kernel = kernel
        self.org = organization
        self.tools = tools
        self.provider_factory = provider_factory
        self.lease_seconds = lease_seconds
        self.max_iterations = max_iterations
        self.conn = kernel.conn

    def _existing_task(self, employee_id: str, work_order_id: str) -> str | None:
        row = self.conn.execute(
            """SELECT task_id FROM tasks
            WHERE work_order_id=? AND assignee_employee_id=?
              AND status='OPEN'
            ORDER BY created_at LIMIT 1""",
            (work_order_id, employee_id),
        ).fetchone()
        return row["task_id"] if row else None

    def _claim_next(self, employee_id: str, worker_id: str) -> dict | None:
        reclaimed = self.org.reclaim_expired_work_order(
            employee_id,
            worker_id=worker_id,
            lease_seconds=self.lease_seconds,
        )
        if reclaimed:
            return {**reclaimed, "source": "RECLAIMED"}

        direct = self.org.claim_employee_work_order(
            employee_id,
            worker_id=worker_id,
            lease_seconds=self.lease_seconds,
        )
        if direct:
            return {**direct, "source": "ASSIGNED"}

        request = self.org.claim_office_work_request(employee_id)
        if request:
            token = self.org.acquire_work_order_lease(
                request["child_work_order_id"],
                employee_id,
                worker_id=worker_id,
                lease_seconds=self.lease_seconds,
            )
            return {
                "work_order_id": request["child_work_order_id"],
                "lease_token": token,
                "request_id": request["request_id"],
                "source": "WORK_REQUEST",
            }

        work_order_id = self.org.claim_office_work_order(
            employee_id,
            worker_id=worker_id,
            lease_seconds=self.lease_seconds,
        )
        if work_order_id:
            lease = self.org.current_work_order_lease(work_order_id)
            return {
                "work_order_id": work_order_id,
                "lease_token": lease["lease_token"],
                "source": "OFFICE_QUEUE",
            }
        return None

    def run_once(self, *, employee_id: str, worker_id: str) -> dict:
        claim = self._claim_next(employee_id, worker_id)
        if not claim:
            return {"status": "IDLE", "employee_id": employee_id}

        work_order_id = claim["work_order_id"]
        lease_token = claim["lease_token"]
        if not self.org.validate_work_order_lease(
            work_order_id,
            lease_token=lease_token,
            worker_id=worker_id,
        ):
            raise RuntimeError("dispatcher acquired an invalid work lease")

        # Extend once immediately before the bounded employee loop. Long-running
        # external calls will later need an iteration-level heartbeat callback.
        self.org.heartbeat_work_order_lease(
            lease_token,
            worker_id=worker_id,
            lease_seconds=self.lease_seconds,
        )

        task_id = self._existing_task(employee_id, work_order_id)
        try:
            provider = self.provider_factory(employee_id, work_order_id)
            result = EmployeeAgent(
                self.kernel,
                self.org,
                self.tools,
                provider,
                max_iterations=self.max_iterations,
            ).run(
                employee_id=employee_id,
                work_order_id=work_order_id,
                task_id=task_id,
            )
        except Exception as exc:
            lease = self.org.current_work_order_lease(work_order_id)
            self.kernel.record_activity(
                "WorkOrder",
                work_order_id,
                "WORKER_RUN_FAILED",
                {
                    "employee_id": employee_id,
                    "worker_id": worker_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "lease_retained_until": lease["expires_at"] if lease else None,
                },
            )
            return {
                "status": "FAILED",
                "employee_id": employee_id,
                "work_order_id": work_order_id,
                "source": claim["source"],
                "error_type": type(exc).__name__,
                "error": str(exc),
                "lease_retained": lease is not None,
            }

        return {
            **result,
            "employee_id": employee_id,
            "work_order_id": work_order_id,
            "source": claim["source"],
        }
