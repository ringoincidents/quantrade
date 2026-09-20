from __future__ import annotations

import sqlite3


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS clients (
  client_id TEXT PRIMARY KEY,
  base_currency TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS client_profile_versions (
  profile_version_id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES clients(client_id),
  version INTEGER NOT NULL,
  profile_json TEXT NOT NULL,
  effective_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(client_id, version)
);

CREATE TABLE IF NOT EXISTS client_goals (
  goal_id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES clients(client_id),
  name TEXT NOT NULL,
  target_amount REAL NOT NULL,
  target_date TEXT NOT NULL,
  priority TEXT NOT NULL,
  required INTEGER NOT NULL,
  metadata_json TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS client_cashflows (
  cashflow_id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES clients(client_id),
  flow_type TEXT NOT NULL,
  amount REAL NOT NULL,
  cadence TEXT NOT NULL,
  start_date TEXT NOT NULL,
  end_date TEXT,
  reserved INTEGER NOT NULL,
  label TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS capital_plans (
  capital_plan_id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES clients(client_id),
  as_of TEXT NOT NULL,
  input_json TEXT NOT NULL,
  result_json TEXT NOT NULL,
  policy_version TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS investment_mandates (
  mandate_id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES clients(client_id),
  capital_plan_id TEXT NOT NULL REFERENCES capital_plans(capital_plan_id),
  mandate_json TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS performance_records (
  performance_id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES clients(client_id),
  period_start TEXT NOT NULL,
  period_end TEXT NOT NULL,
  start_value REAL NOT NULL,
  end_value REAL NOT NULL,
  net_external_flows REAL NOT NULL,
  realized_pnl REAL NOT NULL,
  investment_income REAL NOT NULL,
  fees REAL NOT NULL,
  taxes REAL NOT NULL,
  attribution_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS capital_reconciliations (
  reconciliation_id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES clients(client_id),
  performance_id TEXT REFERENCES performance_records(performance_id),
  previous_mandate_id TEXT REFERENCES investment_mandates(mandate_id),
  new_capital_plan_id TEXT NOT NULL REFERENCES capital_plans(capital_plan_id),
  new_mandate_id TEXT NOT NULL REFERENCES investment_mandates(mandate_id),
  result_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS autonomous_work_triggers (
  trigger_id TEXT PRIMARY KEY,
  mandate_id TEXT NOT NULL REFERENCES investment_mandates(mandate_id),
  trigger_type TEXT NOT NULL,
  fingerprint TEXT NOT NULL UNIQUE,
  work_order_id TEXT REFERENCES work_orders(work_order_id),
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS employees (
  employee_id TEXT PRIMARY KEY,
  office_id TEXT NOT NULL,
  role TEXT NOT NULL,
  charter TEXT NOT NULL,
  authority_json TEXT NOT NULL,
  model_profile_json TEXT NOT NULL,
  workstation_profile_json TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS work_orders (
  work_order_id TEXT PRIMARY KEY,
  issuer_type TEXT NOT NULL,
  issuer_id TEXT NOT NULL,
  recipient_office TEXT,
  recipient_employee_id TEXT REFERENCES employees(employee_id),
  objective TEXT NOT NULL,
  constraints_json TEXT NOT NULL,
  urgency TEXT NOT NULL,
  linked_case_id TEXT REFERENCES cases(case_id),
  authority_scope_json TEXT NOT NULL,
  budget_json TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS work_order_links (
  parent_work_order_id TEXT NOT NULL REFERENCES work_orders(work_order_id),
  child_work_order_id TEXT NOT NULL REFERENCES work_orders(work_order_id),
  relation TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (parent_work_order_id, child_work_order_id)
);

CREATE TABLE IF NOT EXISTS tasks (
  task_id TEXT PRIMARY KEY,
  work_order_id TEXT NOT NULL REFERENCES work_orders(work_order_id),
  creator_employee_id TEXT REFERENCES employees(employee_id),
  assignee_employee_id TEXT REFERENCES employees(employee_id),
  objective TEXT NOT NULL,
  plan_json TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS work_requests (
  request_id TEXT PRIMARY KEY,
  work_order_id TEXT NOT NULL REFERENCES work_orders(work_order_id),
  task_id TEXT REFERENCES tasks(task_id),
  issuer_employee_id TEXT NOT NULL REFERENCES employees(employee_id),
  recipient_office TEXT NOT NULL,
  recipient_employee_id TEXT REFERENCES employees(employee_id),
  objective TEXT NOT NULL,
  context_refs_json TEXT NOT NULL,
  status TEXT NOT NULL,
  response_note TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS org_messages (
  message_id TEXT PRIMARY KEY,
  work_order_id TEXT REFERENCES work_orders(work_order_id),
  task_id TEXT REFERENCES tasks(task_id),
  request_id TEXT REFERENCES work_requests(request_id),
  sender_type TEXT NOT NULL,
  sender_id TEXT NOT NULL,
  recipient_type TEXT NOT NULL,
  recipient_id TEXT NOT NULL,
  body TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workspaces (
  workspace_id TEXT PRIMARY KEY,
  employee_id TEXT NOT NULL REFERENCES employees(employee_id),
  work_order_id TEXT NOT NULL REFERENCES work_orders(work_order_id),
  state_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(employee_id, work_order_id)
);

CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id TEXT PRIMARY KEY,
  work_order_id TEXT NOT NULL REFERENCES work_orders(work_order_id),
  task_id TEXT REFERENCES tasks(task_id),
  producer_employee_id TEXT REFERENCES employees(employee_id),
  artifact_type TEXT NOT NULL,
  title TEXT NOT NULL,
  content_ref TEXT,
  metadata_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tool_definitions (
  tool_name TEXT PRIMARY KEY,
  description TEXT NOT NULL,
  input_schema_json TEXT NOT NULL,
  deterministic INTEGER NOT NULL,
  side_effect_class TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS employee_tool_grants (
  employee_id TEXT NOT NULL REFERENCES employees(employee_id),
  tool_name TEXT NOT NULL REFERENCES tool_definitions(tool_name),
  granted_at TEXT NOT NULL,
  PRIMARY KEY (employee_id, tool_name)
);

CREATE TABLE IF NOT EXISTS tool_invocations (
  invocation_id TEXT PRIMARY KEY,
  work_order_id TEXT NOT NULL REFERENCES work_orders(work_order_id),
  task_id TEXT REFERENCES tasks(task_id),
  employee_id TEXT NOT NULL REFERENCES employees(employee_id),
  tool_name TEXT NOT NULL REFERENCES tool_definitions(tool_name),
  input_json TEXT NOT NULL,
  output_json TEXT,
  status TEXT NOT NULL,
  error_text TEXT,
  started_at TEXT NOT NULL,
  completed_at TEXT
);

CREATE TABLE IF NOT EXISTS model_calls (
  model_call_id TEXT PRIMARY KEY,
  employee_id TEXT NOT NULL REFERENCES employees(employee_id),
  work_order_id TEXT NOT NULL REFERENCES work_orders(work_order_id),
  task_id TEXT REFERENCES tasks(task_id),
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  input_context_json TEXT NOT NULL,
  output_action_json TEXT,
  status TEXT NOT NULL,
  error_text TEXT,
  started_at TEXT NOT NULL,
  completed_at TEXT
);

CREATE TABLE IF NOT EXISTS events (
  event_id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  source TEXT NOT NULL,
  subject TEXT NOT NULL,
  payload TEXT NOT NULL,
  resolution_status TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cases (
  case_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  trigger_event_id TEXT NOT NULL REFERENCES events(event_id),
  subject TEXT NOT NULL,
  status TEXT NOT NULL,
  materiality TEXT,
  opened_at TEXT NOT NULL,
  closed_at TEXT,
  version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS evidence (
  evidence_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES cases(case_id),
  source TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  fact TEXT NOT NULL,
  provenance TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_fingerprints (
  case_id TEXT NOT NULL REFERENCES cases(case_id),
  fingerprint TEXT NOT NULL,
  evidence_id TEXT NOT NULL REFERENCES evidence(evidence_id),
  PRIMARY KEY (case_id, fingerprint)
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
  snapshot_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES cases(case_id),
  as_of TEXT NOT NULL,
  source TEXT NOT NULL,
  snapshot TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS risk_assessments (
  assessment_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES cases(case_id),
  snapshot_id TEXT NOT NULL REFERENCES portfolio_snapshots(snapshot_id),
  policy_version TEXT NOT NULL,
  result TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS institutional_positions (
  position_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES cases(case_id),
  office TEXT NOT NULL,
  stance TEXT NOT NULL,
  rationale TEXT NOT NULL,
  evidence_refs TEXT NOT NULL,
  supersedes_id TEXT REFERENCES institutional_positions(position_id),
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS challenges (
  challenge_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES cases(case_id),
  thesis_challenged TEXT NOT NULL,
  counter_thesis TEXT NOT NULL,
  unresolved INTEGER NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS committee_packages (
  package_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES cases(case_id),
  proposed_action TEXT NOT NULL,
  unresolved_questions TEXT NOT NULL,
  package_json TEXT NOT NULL,
  generated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decisions (
  decision_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES cases(case_id),
  action TEXT NOT NULL,
  founder_note TEXT NOT NULL,
  decided_at TEXT NOT NULL,
  supersedes_id TEXT REFERENCES decisions(decision_id)
);

CREATE TABLE IF NOT EXISTS decision_plans (
  plan_id TEXT PRIMARY KEY,
  decision_id TEXT NOT NULL REFERENCES decisions(decision_id),
  timing_mode TEXT NOT NULL,
  condition_text TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS execution_records (
  execution_id TEXT PRIMARY KEY,
  plan_id TEXT NOT NULL REFERENCES decision_plans(plan_id),
  mode TEXT NOT NULL CHECK(mode = 'SIMULATED'),
  status TEXT NOT NULL,
  details TEXT NOT NULL,
  executed_at TEXT
);

CREATE TABLE IF NOT EXISTS review_schedules (
  review_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES cases(case_id),
  horizon_days INTEGER NOT NULL,
  due_at TEXT NOT NULL,
  status TEXT NOT NULL,
  outcome TEXT
);

CREATE TABLE IF NOT EXISTS ledger_events (
  ledger_id INTEGER PRIMARY KEY AUTOINCREMENT,
  aggregate_type TEXT NOT NULL,
  aggregate_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  previous_hash TEXT,
  event_hash TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS founder_briefing_queue (
  case_id TEXT PRIMARY KEY REFERENCES cases(case_id),
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS founder_desk (
  case_id TEXT PRIMARY KEY REFERENCES cases(case_id),
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


MIGRATIONS = [
    (
        1,
        "durable_work_order_leases",
        (
            """CREATE TABLE work_order_leases (
              work_order_id TEXT PRIMARY KEY REFERENCES work_orders(work_order_id) ON DELETE CASCADE,
              employee_id TEXT NOT NULL REFERENCES employees(employee_id),
              worker_id TEXT NOT NULL,
              lease_token TEXT NOT NULL UNIQUE,
              generation INTEGER NOT NULL,
              claimed_at TEXT NOT NULL,
              heartbeat_at TEXT NOT NULL,
              expires_at TEXT NOT NULL
            )""",
            """CREATE INDEX idx_work_order_leases_expiry
               ON work_order_leases(expires_at)""",
        ),
    ),
    (
        2,
        "challenge_office_provenance",
        (
            """ALTER TABLE challenges
               ADD COLUMN office TEXT NOT NULL DEFAULT 'ARU'""",
        ),
    ),
    (
        3,
        "employee_eval_harness",
        (
            """CREATE TABLE eval_tasks (
              eval_task_id TEXT PRIMARY KEY,
              suite TEXT NOT NULL,
              title TEXT NOT NULL,
              objective TEXT NOT NULL,
              fixture_json TEXT NOT NULL,
              success_criteria_json TEXT NOT NULL,
              hidden_checks_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            )""",
            """CREATE TABLE eval_trials (
              trial_id TEXT PRIMARY KEY,
              eval_task_id TEXT NOT NULL REFERENCES eval_tasks(eval_task_id),
              treatment TEXT NOT NULL,
              provider TEXT NOT NULL,
              model TEXT NOT NULL,
              harness TEXT NOT NULL,
              seed_label TEXT,
              work_order_id TEXT,
              status TEXT NOT NULL,
              started_at TEXT NOT NULL,
              completed_at TEXT,
              metrics_json TEXT NOT NULL,
              notes_json TEXT NOT NULL
            )""",
            """CREATE TABLE eval_assertions (
              assertion_id INTEGER PRIMARY KEY AUTOINCREMENT,
              trial_id TEXT NOT NULL REFERENCES eval_trials(trial_id) ON DELETE CASCADE,
              grader TEXT NOT NULL,
              assertion_name TEXT NOT NULL,
              passed INTEGER NOT NULL,
              observed_json TEXT NOT NULL
            )""",
            """CREATE INDEX idx_eval_trials_task
               ON eval_trials(eval_task_id,treatment,provider,model)""",
        ),
    ),
    (
        4,
        "model_call_usage_telemetry",
        (
            """ALTER TABLE model_calls
               ADD COLUMN usage_json TEXT NOT NULL DEFAULT '{}'""",
            """ALTER TABLE model_calls
               ADD COLUMN input_context_chars INTEGER NOT NULL DEFAULT 0""",
        ),
    ),
]


def apply_migrations(conn: sqlite3.Connection) -> None:
    """Apply forward-only SQLite migrations exactly once.

    SCHEMA remains the legacy bootstrap for now. Every structural change after
    Epoch A is versioned here so an existing QuanTrade database can be upgraded
    instead of silently depending on CREATE TABLE IF NOT EXISTS.
    """
    applied = {
        row["version"]
        for row in conn.execute("SELECT version FROM schema_migrations")
    }
    for version, name, statements in MIGRATIONS:
        if version in applied:
            continue
        with conn:
            for statement in statements:
                conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_migrations(version,name) VALUES (?,?)",
                (version, name),
            )


def schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(version),0) AS version FROM schema_migrations"
    ).fetchone()
    return int(row["version"])


def connect(path: str = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    apply_migrations(conn)
    return conn
