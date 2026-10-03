from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .employee_agent import EmployeeAgent, ModelProvider
from .organization import OrganizationRuntime
from .service import InstitutionalKernel
from .tools import ToolDefinition, ToolRegistry


ProviderFactory = Callable[[str, str], ModelProvider]


class DepartmentalReviewError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReviewEmployees:
    research: str
    portfolio: str
    risk: str
    adversarial: str


class BoundedDepartmentalReview:
    """Run role-separated institutional review behind deterministic gates.

    Models may submit only role-specific artifacts. Portfolio/risk calculations
    that must be deterministic are injected by runtime code rather than invented
    by the model. The returned summary intentionally excludes private Client
    constraints and model rationales.
    """

    def __init__(
        self,
        kernel: InstitutionalKernel,
        provider_factory: ProviderFactory,
        *,
        max_iterations: int = 4,
    ) -> None:
        self.kernel = kernel
        self.org = OrganizationRuntime(kernel)
        self.tools = ToolRegistry(kernel)
        self.provider_factory = provider_factory
        self.max_iterations = max_iterations
        self.conn = kernel.conn

    def _create_employees(self) -> ReviewEmployees:
        common = {
            "live_orders": False,
            "change_policy": False,
            "increase_risk_limit": False,
        }
        return ReviewEmployees(
            research=self.org.create_employee(
                "IID",
                "Evidence Research Analyst",
                "Collect sourced facts and identify evidence limitations.",
                authority={**common, "submit_evidence": True},
            ),
            portfolio=self.org.create_employee(
                "SPMG",
                "Portfolio Manager",
                "Interpret evidence in portfolio context and submit a bounded stance.",
                authority={**common, "submit_portfolio_position": True},
            ),
            risk=self.org.create_employee(
                "IPRO",
                "Risk Officer",
                "Interpret deterministic risk outputs and submit a bounded risk stance.",
                authority={**common, "submit_risk_position": True},
            ),
            adversarial=self.org.create_employee(
                "ARU",
                "Adversarial Reviewer",
                "Challenge the current thesis and preserve unresolved dissent.",
                authority={**common, "submit_challenge": True},
            ),
        )

    def _evidence_refs_for_case(self, case_id: str, refs: list[str]) -> list[str]:
        unique = list(dict.fromkeys(str(ref) for ref in refs if ref))
        if not unique:
            raise ValueError("at least one evidence reference is required")
        rows = self.conn.execute(
            "SELECT evidence_id FROM evidence WHERE case_id=?",
            (case_id,),
        ).fetchall()
        allowed = {str(row["evidence_id"]) for row in rows}
        if any(ref not in allowed for ref in unique):
            raise ValueError("evidence reference is not attached to this Case")
        return unique

    def _install_research_tool(self, employee_id: str, case_id: str) -> None:
        definition = ToolDefinition(
            "case.submit_research_evidence",
            "Submit one sourced fact to the bound Case. No trade or decision authority.",
            {"required": ["source", "fact", "provenance"]},
            True,
            "ARTIFACT_WRITE",
        )

        def submit(args: dict) -> dict:
            source = str(args["source"]).strip()
            fact = str(args["fact"]).strip()
            provenance = args["provenance"]
            if not source or not fact or not isinstance(provenance, dict):
                raise ValueError("research evidence requires source, fact and provenance")
            evidence_id = self.kernel.add_evidence(
                case_id,
                source,
                fact,
                provenance,
            )
            return {"evidence_id": evidence_id, "case_id": case_id}

        self.tools.register(definition, submit)
        self.tools.grant(employee_id, definition.name)

    def _install_portfolio_tool(self, employee_id: str, case_id: str) -> None:
        definition = ToolDefinition(
            "case.submit_portfolio_position",
            "Submit SPMG stance with Case-bound evidence references.",
            {"required": ["stance", "rationale", "evidence_refs"]},
            True,
            "ARTIFACT_WRITE",
        )

        def submit(args: dict) -> dict:
            refs = self._evidence_refs_for_case(
                case_id,
                list(args.get("evidence_refs") or []),
            )
            position_id = self.kernel.add_position(
                case_id,
                "SPMG",
                str(args["stance"]).strip(),
                str(args["rationale"]).strip(),
                refs,
            )
            return {"position_id": position_id, "office": "SPMG"}

        self.tools.register(definition, submit)
        self.tools.grant(employee_id, definition.name)

    def _install_risk_tool(
        self,
        employee_id: str,
        case_id: str,
        *,
        portfolio_snapshot: dict[str, Any],
        deterministic_risk_result: dict[str, Any],
        risk_policy_version: str,
    ) -> None:
        definition = ToolDefinition(
            "case.submit_risk_position",
            (
                "Submit IPRO interpretation of runtime-supplied deterministic risk "
                "results. The model cannot alter the bound snapshot or risk metrics."
            ),
            {"required": ["stance", "rationale", "evidence_refs"]},
            True,
            "ARTIFACT_WRITE",
        )
        persisted: dict[str, str] = {}

        def submit(args: dict) -> dict:
            refs = self._evidence_refs_for_case(
                case_id,
                list(args.get("evidence_refs") or []),
            )
            if not persisted:
                snapshot_id = self.kernel.add_snapshot(
                    case_id,
                    portfolio_snapshot,
                    source="runtime_deterministic_snapshot",
                )
                assessment_id = self.kernel.add_risk_assessment(
                    case_id,
                    snapshot_id,
                    deterministic_risk_result,
                    risk_policy_version,
                )
                persisted.update(
                    {
                        "snapshot_id": snapshot_id,
                        "assessment_id": assessment_id,
                    }
                )
            position_id = self.kernel.add_position(
                case_id,
                "IPRO",
                str(args["stance"]).strip(),
                str(args["rationale"]).strip(),
                refs,
            )
            return {
                **persisted,
                "position_id": position_id,
                "office": "IPRO",
            }

        self.tools.register(definition, submit)
        self.tools.grant(employee_id, definition.name)

    def _install_adversarial_tool(self, employee_id: str, case_id: str) -> None:
        definition = ToolDefinition(
            "case.submit_adversarial_challenge",
            "Submit an ARU counter-thesis. Unresolved dissent survives Committee entry.",
            {"required": ["thesis", "counter_thesis"]},
            True,
            "ARTIFACT_WRITE",
        )

        def submit(args: dict) -> dict:
            challenge_id = self.kernel.add_challenge(
                case_id,
                str(args["thesis"]).strip(),
                str(args["counter_thesis"]).strip(),
                bool(args.get("unresolved", True)),
                office="ARU",
            )
            return {"challenge_id": challenge_id, "office": "ARU"}

        self.tools.register(definition, submit)
        self.tools.grant(employee_id, definition.name)

    def _run_employee(
        self,
        *,
        employee_id: str,
        office: str,
        case_id: str,
        objective: str,
        constraints: dict[str, Any],
    ) -> dict[str, Any]:
        work_order_id = self.org.create_work_order(
            issuer_type="SYSTEM",
            issuer_id="QT-LIVE-003",
            recipient_office=office,
            recipient_employee_id=employee_id,
            objective=objective,
            constraints=constraints,
            urgency="NORMAL",
            linked_case_id=case_id,
            authority_scope={
                "research": True,
                "trade": False,
                "policy_change": False,
                "risk_limit_change": False,
            },
            budget={"max_tool_calls": 1},
        )
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
        )
        return {
            "work_order_id": work_order_id,
            "status": result.get("status"),
            "iterations": result.get("iterations"),
        }

    def run(
        self,
        *,
        precheck: dict[str, Any],
        private_strategy_envelope: dict[str, Any],
        portfolio_snapshot: dict[str, Any],
        deterministic_risk_result: dict[str, Any],
        risk_policy_version: str,
    ) -> dict[str, Any]:
        if precheck.get("schema") != "quantrade_institutional_case_precheck_v1":
            raise DepartmentalReviewError("unsupported precheck schema")
        client_context = precheck.get("client_context") or {}
        if not client_context.get("strategy_ready"):
            raise DepartmentalReviewError("Client Strategy Gate is not READY")
        if precheck.get("next_stage") != "BOUNDED_AI_REVIEW":
            raise DepartmentalReviewError(
                "precheck did not request BOUNDED_AI_REVIEW"
            )
        if (
            private_strategy_envelope.get("schema")
            != "quantrade_private_strategy_envelope_v1"
        ):
            raise DepartmentalReviewError("private Strategy Envelope is required")
        if not isinstance(portfolio_snapshot, dict) or not portfolio_snapshot:
            raise DepartmentalReviewError("deterministic portfolio snapshot is required")
        if not isinstance(deterministic_risk_result, dict) or not deterministic_risk_result:
            raise DepartmentalReviewError("deterministic risk result is required")
        if not risk_policy_version.strip():
            raise DepartmentalReviewError("risk policy version is required")

        market_state = precheck.get("market_state") or {}
        strategy_directive = precheck.get("strategy_directive") or {}
        symbol = str(market_state.get("symbol") or "UNKNOWN")

        event = self.kernel.ingest_event(
            "MATERIAL_REVIEW_REQUIRED",
            "QT-LIVE-003",
            symbol,
            {
                "precheck_run_id": precheck.get("run_id"),
                "market_timestamp": market_state.get("timestamp"),
                "mode": "PAPER",
            },
            title=f"QT-LIVE-003 bounded review: {symbol}",
        )
        case_id = event.get("case_id")
        if not case_id:
            raise DepartmentalReviewError("institutional Case was not opened")

        employees = self._create_employees()
        self._install_research_tool(employees.research, case_id)
        self._install_portfolio_tool(employees.portfolio, case_id)
        self._install_risk_tool(
            employees.risk,
            case_id,
            portfolio_snapshot=portfolio_snapshot,
            deterministic_risk_result=deterministic_risk_result,
            risk_policy_version=risk_policy_version,
        )
        self._install_adversarial_tool(employees.adversarial, case_id)

        common_public = {
            "market_state": market_state,
            "strategy_directive": strategy_directive,
            "mode": "PAPER_REVIEW",
            "live_orders_forbidden": True,
        }
        research = self._run_employee(
            employee_id=employees.research,
            office="IID",
            case_id=case_id,
            objective=(
                "Submit one decision-relevant sourced fact for this Case, state "
                "limitations, then finish. Do not recommend or execute a trade."
            ),
            constraints=common_public,
        )

        evidence_rows = self.conn.execute(
            "SELECT evidence_id,source,fact FROM evidence WHERE case_id=? ORDER BY created_at",
            (case_id,),
        ).fetchall()
        if not evidence_rows:
            raise DepartmentalReviewError("Research produced no canonical Evidence")
        evidence_refs = [str(row["evidence_id"]) for row in evidence_rows]

        portfolio = self._run_employee(
            employee_id=employees.portfolio,
            office="SPMG",
            case_id=case_id,
            objective=(
                "Submit one SPMG portfolio stance grounded in the attached Case "
                "evidence, then finish. No order or policy change."
            ),
            constraints={**common_public, "evidence_refs": evidence_refs},
        )

        private_risk = dict(private_strategy_envelope.get("risk_capacity") or {})
        risk = self._run_employee(
            employee_id=employees.risk,
            office="IPRO",
            case_id=case_id,
            objective=(
                "Interpret the bound deterministic risk result and submit one "
                "IPRO stance grounded in Case evidence, then finish."
            ),
            constraints={
                **common_public,
                "evidence_refs": evidence_refs,
                "private_risk_capacity": private_risk,
                "deterministic_risk_result": deterministic_risk_result,
                "risk_policy_version": risk_policy_version,
            },
        )

        portfolio_position = self.kernel._latest_current_position(case_id, "SPMG")
        risk_position = self.kernel._latest_current_position(case_id, "IPRO")
        adversarial = self._run_employee(
            employee_id=employees.adversarial,
            office="ARU",
            case_id=case_id,
            objective=(
                "Challenge the current investment thesis and submit one counter-thesis. "
                "Preserve unresolved dissent unless the challenge is genuinely resolved."
            ),
            constraints={
                **common_public,
                "portfolio_stance": (
                    portfolio_position["stance"] if portfolio_position else None
                ),
                "risk_stance": (
                    risk_position["stance"] if risk_position else None
                ),
            },
        )

        readiness = self.kernel.committee_readiness(case_id)
        if not readiness["ready"]:
            raise DepartmentalReviewError(
                "Committee artifact gate is incomplete: "
                + ", ".join(readiness["missing"])
            )
        self.kernel.enter_committee(case_id)

        model_call_count = self.conn.execute(
            """SELECT COUNT(*) c FROM model_calls
            WHERE work_order_id IN (?,?,?,?)""",
            (
                research["work_order_id"],
                portfolio["work_order_id"],
                risk["work_order_id"],
                adversarial["work_order_id"],
            ),
        ).fetchone()["c"]

        return {
            "schema": "quantrade_bounded_departmental_review_v1",
            "case_id": case_id,
            "status": "COMMITTEE",
            "mode": "PAPER_REVIEW",
            "departments": {
                "research": research,
                "portfolio": portfolio,
                "risk": risk,
                "adversarial": adversarial,
            },
            "artifacts": readiness["artifacts"],
            "unresolved_challenge_ids": readiness[
                "unresolved_challenge_ids"
            ],
            "model_call_count": int(model_call_count),
            "private_strategy_values_persisted_publicly": False,
            "live_execution_authorized": False,
        }
