from __future__ import annotations

import sqlite3


SCHEMA = """
PRAGMA foreign_keys = ON;

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
"""


def connect(path: str = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn
