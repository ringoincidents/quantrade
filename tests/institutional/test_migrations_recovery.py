from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest

from quantrade.institutional.db import SCHEMA, connect, schema_version
from quantrade.institutional.organization import OrganizationRuntime
from quantrade.institutional.service import InstitutionalKernel


class MigrationAndRecoveryTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)

    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_legacy_bootstrap_database_is_forward_migrated_once(self):
        legacy = sqlite3.connect(self.path)
        legacy.executescript(SCHEMA)
        legacy.close()

        conn = connect(self.path)
        self.assertEqual(1, schema_version(conn))
        columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(work_order_leases)")
        }
        self.assertIn("lease_token", columns)
        self.assertIn("expires_at", columns)
        self.assertEqual(
            1,
            conn.execute("SELECT COUNT(*) c FROM schema_migrations").fetchone()["c"],
        )
        conn.close()

        reopened = connect(self.path)
        self.assertEqual(1, schema_version(reopened))
        self.assertEqual(
            1,
            reopened.execute("SELECT COUNT(*) c FROM schema_migrations").fetchone()["c"],
        )
        reopened.close()

    def test_expired_worker_lease_is_reclaimed_after_process_restart(self):
        kernel = InstitutionalKernel(self.path)
        org = OrganizationRuntime(kernel)
        employee = org.create_employee(
            "SPMG",
            "Strategy Analyst",
            "Resume durable research after worker crashes.",
            authority={"read_only_research": True, "live_orders": False},
            employee_id="EMP-RECOVERY-STRATEGY",
        )
        work_order = org.create_work_order(
            issuer_type="SYSTEM",
            issuer_id="AUTONOMOUS_WORK_ENGINE",
            recipient_office="SPMG",
            objective="Investigate a durable recovery fixture.",
            authority_scope={"research": True, "trade": False},
        )
        claimed = org.claim_office_work_order(
            employee, worker_id="worker-before-crash", lease_seconds=300
        )
        self.assertEqual(work_order, claimed)

        workspace_id = org.get_or_create_workspace(employee, work_order)
        org.save_workspace_state(
            workspace_id,
            {
                "checkpoint": "screen complete",
                "next_step": "independent chart review",
            },
        )
        first = kernel.conn.execute(
            "SELECT lease_token,generation FROM work_order_leases WHERE work_order_id=?",
            (work_order,),
        ).fetchone()
        self.assertEqual(1, first["generation"])

        # Deterministically simulate a process dying and its lease expiring.
        with kernel.conn:
            kernel.conn.execute(
                """UPDATE work_order_leases
                SET expires_at='2000-01-01T00:00:00+00:00'
                WHERE work_order_id=?""",
                (work_order,),
            )
        kernel.close()

        restarted = InstitutionalKernel(self.path)
        resumed_org = OrganizationRuntime(restarted)
        reclaimed = resumed_org.reclaim_expired_work_order(
            employee, worker_id="worker-after-restart", lease_seconds=300
        )
        self.assertIsNotNone(reclaimed)
        self.assertEqual(work_order, reclaimed["work_order_id"])
        self.assertEqual(2, reclaimed["generation"])
        self.assertTrue(
            resumed_org.validate_work_order_lease(
                work_order,
                lease_token=reclaimed["lease_token"],
                worker_id="worker-after-restart",
            )
        )

        same_workspace = resumed_org.get_or_create_workspace(employee, work_order)
        self.assertEqual(workspace_id, same_workspace)
        state = json.loads(
            restarted.conn.execute(
                "SELECT state_json FROM workspaces WHERE workspace_id=?",
                (same_workspace,),
            ).fetchone()["state_json"]
        )
        self.assertEqual("screen complete", state["checkpoint"])
        self.assertEqual("independent chart review", state["next_step"])

        types = [e["event_type"] for e in restarted.ledger(work_order)]
        self.assertIn("WORK_ORDER_CLAIMED", types)
        self.assertIn("WORK_ORDER_RECLAIMED", types)
        self.assertTrue(restarted.verify_ledger_chain())
        restarted.close()

    def test_active_lease_cannot_be_stolen_and_heartbeat_extends_it(self):
        kernel = InstitutionalKernel(self.path)
        org = OrganizationRuntime(kernel)
        employee = org.create_employee(
            "SPMG",
            "Strategy Analyst",
            "Lease ownership fixture.",
            employee_id="EMP-LEASE-STRATEGY",
        )
        work_order = org.create_work_order(
            issuer_type="SYSTEM",
            issuer_id="AUTONOMOUS_WORK_ENGINE",
            recipient_office="SPMG",
            objective="Lease fixture.",
        )
        org.claim_office_work_order(
            employee, worker_id="worker-a", lease_seconds=300
        )
        lease = kernel.conn.execute(
            "SELECT lease_token,expires_at FROM work_order_leases WHERE work_order_id=?",
            (work_order,),
        ).fetchone()

        with self.assertRaisesRegex(ValueError, "active lease"):
            org.acquire_work_order_lease(
                work_order,
                employee,
                worker_id="worker-b",
                lease_seconds=300,
            )

        extended = org.heartbeat_work_order_lease(
            lease["lease_token"], worker_id="worker-a", lease_seconds=600
        )
        self.assertGreater(extended, lease["expires_at"])
        with self.assertRaisesRegex(ValueError, "different worker"):
            org.heartbeat_work_order_lease(
                lease["lease_token"], worker_id="worker-b", lease_seconds=600
            )
        kernel.close()


if __name__ == "__main__":
    unittest.main()
