"""Bridge Investment Office capability artifacts into InstitutionalKernel.

This module is deliberately schema-based rather than importing the newer
`quantrade.capabilities` package. The integration branch is stacked on the
institutional architecture line, while the Investment Office capability work
currently lives in a separate main-based Draft PR.

That separation is intentional:
- Investment Office capabilities own research-domain artifacts.
- InstitutionalKernel remains the single source of Case / Committee /
  Decision authority.

The bridge promotes only bounded, verified artifact types and never creates a
Founder Decision, DecisionPlan, PAPER authorization, or execution side effect.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
import hashlib
import json
from typing import Any, Mapping

from .service import InstitutionalKernel


class InvestmentOfficeBridgeError(ValueError):
    """Raised when an Investment Office handoff violates integration rules."""


EXPECTED_SCHEMAS = {
    "fundamental": "quantrade_fundamental_observation_query_v1",
    "thesis": "quantrade_thesis_contract_v1",
    "portfolio": "quantrade_portfolio_opportunity_v1",
    "risk": "quantrade_risk_opinion_v1",
}

EVIDENCE_SOURCE_KINDS = {
    "EXTERNAL_EVIDENCE",
    "RUNTIME_VERIFIED",
}


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_plain(v) for v in value]
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvestmentOfficeBridgeError(f"{field_name} is required")
    return value.strip()


def _require_schema(artifact: dict, expected: str, label: str) -> None:
    if artifact.get("schema") != expected:
        raise InvestmentOfficeBridgeError(
            f"{label} schema must be {expected}"
        )


def _assert_false(
    artifact: dict,
    field_name: str,
    label: str,
) -> None:
    authority = artifact.get("authority")
    if not isinstance(authority, dict):
        raise InvestmentOfficeBridgeError(
            f"{label} authority block is required"
        )
    if authority.get(field_name) is not False:
        raise InvestmentOfficeBridgeError(
            f"{label} must have {field_name}=false"
        )


def _canonical_hash(payload: dict) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


class InvestmentOfficeInstitutionalBridge:
    """Bind IO artifacts into the existing institutional Case substrate."""

    def __init__(self, kernel: InstitutionalKernel) -> None:
        self.kernel = kernel
        self.conn = kernel.conn

    def _existing_handoff(self, case_id: str, handoff_id: str) -> dict | None:
        rows = self.conn.execute(
            """SELECT payload FROM ledger_events
            WHERE aggregate_type='Case'
              AND aggregate_id=?
              AND event_type='INVESTMENT_OFFICE_HANDOFF_BOUND'
            ORDER BY ledger_id DESC""",
            (case_id,),
        ).fetchall()
        for row in rows:
            try:
                payload = json.loads(row["payload"])
            except (TypeError, json.JSONDecodeError):
                continue
            if payload.get("handoff_id") == handoff_id:
                result = payload.get("result")
                if isinstance(result, dict):
                    return result
        return None

    def _validate_artifacts(
        self,
        case_id: str,
        *,
        fundamental: dict,
        thesis: dict,
        portfolio: dict,
        risk: dict,
    ) -> None:
        self.kernel.get_case(case_id)

        _require_schema(
            fundamental,
            EXPECTED_SCHEMAS["fundamental"],
            "fundamental",
        )
        _require_schema(
            thesis,
            EXPECTED_SCHEMAS["thesis"],
            "thesis",
        )
        _require_schema(
            portfolio,
            EXPECTED_SCHEMAS["portfolio"],
            "portfolio",
        )
        _require_schema(
            risk,
            EXPECTED_SCHEMAS["risk"],
            "risk",
        )

        _assert_false(
            fundamental,
            "canonical_evidence_created",
            "fundamental",
        )
        _assert_false(fundamental, "execution_authorized", "fundamental")
        _assert_false(thesis, "canonical_evidence_created", "thesis")
        _assert_false(thesis, "thesis_truth_validated", "thesis")
        _assert_false(thesis, "execution_authorized", "thesis")
        _assert_false(
            portfolio,
            "portfolio_proposal_created",
            "portfolio",
        )
        _assert_false(portfolio, "target_weight_set", "portfolio")
        _assert_false(portfolio, "execution_authorized", "portfolio")
        _assert_false(risk, "committee_decision_created", "risk")
        _assert_false(risk, "execution_authorized", "risk")

        if thesis.get("case_id") != portfolio.get("case_id"):
            raise InvestmentOfficeBridgeError(
                "thesis and portfolio case_id must match"
            )
        if portfolio.get("case_id") != risk.get("case_id"):
            raise InvestmentOfficeBridgeError(
                "portfolio and risk case_id must match"
            )

        if portfolio.get("status") != "ELIGIBLE_FOR_PORTFOLIO_REVIEW":
            raise InvestmentOfficeBridgeError(
                "institutional handoff requires "
                "ELIGIBLE_FOR_PORTFOLIO_REVIEW"
            )

        risk_status = risk.get("status")
        if risk_status not in {
            "PASS",
            "PASS_WITH_LIMITS",
            "VETO",
            "REQUIRE_MORE_INFORMATION",
        }:
            raise InvestmentOfficeBridgeError(
                f"unsupported Risk status: {risk_status}"
            )

    def _bind_evidence(
        self,
        case_id: str,
        *,
        fundamental: dict,
        thesis: dict,
    ) -> list[str]:
        nodes = thesis.get("nodes")
        if not isinstance(nodes, dict):
            raise InvestmentOfficeBridgeError(
                "Thesis Contract nodes are required"
            )
        observations = nodes.get("observations")
        if not isinstance(observations, (list, tuple)):
            raise InvestmentOfficeBridgeError(
                "Thesis Contract observations must be a list"
            )

        fundamental_rows = fundamental.get("observations")
        if not isinstance(fundamental_rows, (list, tuple)):
            raise InvestmentOfficeBridgeError(
                "fundamental observations must be a list"
            )
        by_id = {
            str(item.get("observation_id")): item
            for item in fundamental_rows
            if isinstance(item, dict) and item.get("observation_id")
        }

        evidence_ids: list[str] = []
        for observation in observations:
            if not isinstance(observation, dict):
                raise InvestmentOfficeBridgeError(
                    "Thesis observation must be an object"
                )
            source_kind = str(observation.get("source_kind") or "")
            if source_kind not in EVIDENCE_SOURCE_KINDS:
                continue

            observation_id = _required_text(
                observation.get("observation_id"),
                "Thesis observation_id",
            )
            observed_at = _required_text(
                observation.get("observed_at"),
                "Thesis observation observed_at",
            )
            statement = _required_text(
                observation.get("statement"),
                "Thesis observation statement",
            )

            if source_kind == "EXTERNAL_EVIDENCE":
                source = by_id.get(observation_id)
                if source is None:
                    raise InvestmentOfficeBridgeError(
                        "external Thesis observation is absent from bound "
                        f"FundamentalQueryResult: {observation_id}"
                    )
                source_observed_at = _required_text(
                    source.get("published_at"),
                    "Fundamental published_at",
                )
                if source_observed_at != observed_at:
                    raise InvestmentOfficeBridgeError(
                        "Thesis observed_at must exactly match source "
                        f"published_at for {observation_id}"
                    )
                source_ref = _required_text(
                    source.get("source_ref"),
                    "Fundamental source_ref",
                )
                evidence_ref = _required_text(
                    source.get("evidence_ref"),
                    "Fundamental evidence_ref",
                )
                fact = {
                    "observation_id": observation_id,
                    "asset_id": source.get("asset_id"),
                    "metric_key": source.get("metric_key"),
                    "value": source.get("value"),
                    "unit": source.get("unit"),
                    "currency": source.get("currency"),
                    "fiscal_period_end": source.get("fiscal_period_end"),
                    "statement": statement,
                }
                provenance = {
                    "source_kind": source_kind,
                    "source_provider": source.get("source_provider"),
                    "source_document_id": source.get(
                        "source_document_id"
                    ),
                    "source_ref": source_ref,
                    "evidence_ref": evidence_ref,
                    "published_at": source_observed_at,
                    "retrieved_at": source.get("retrieved_at"),
                    "revision_id": source.get("revision_id"),
                    "revision_of": source.get("revision_of"),
                    "restated": source.get("restated"),
                    "normalization_method": source.get(
                        "normalization_method"
                    ),
                    "published_at_precision": source.get(
                        "published_at_precision"
                    ),
                }
                fingerprint = evidence_ref
            else:
                source_ref = _required_text(
                    observation.get("source_ref"),
                    "Runtime-verified source_ref",
                )
                fact = {
                    "observation_id": observation_id,
                    "statement": statement,
                }
                provenance = {
                    "source_kind": source_kind,
                    "source_ref": source_ref,
                    "observed_at": observed_at,
                }
                fingerprint = (
                    f"runtime-verified:{source_ref}:{observed_at}:"
                    f"{observation_id}"
                )

            evidence_id = self.kernel.add_evidence(
                case_id,
                source_ref,
                _json(fact),
                provenance,
                observed_at=observed_at,
                fingerprint=fingerprint,
            )
            evidence_ids.append(evidence_id)

        if not evidence_ids:
            raise InvestmentOfficeBridgeError(
                "institutional handoff requires at least one eligible "
                "Evidence-bearing Observation"
            )
        return list(dict.fromkeys(evidence_ids))

    def _bind_portfolio(
        self,
        case_id: str,
        *,
        portfolio: dict,
        evidence_ids: list[str],
    ) -> str:
        rationale = {
            "source_schema": portfolio["schema"],
            "reasons": portfolio.get("reasons") or [],
            "opportunity_cost": portfolio.get("opportunity_cost") or {},
            "capital_headroom": portfolio.get("capital_headroom") or {},
            "constraints": portfolio.get("constraints") or {},
            "target_weight_set": False,
        }
        return self.kernel.add_position(
            case_id,
            "SPMG",
            "ELIGIBLE_FOR_PORTFOLIO_REVIEW",
            _json(rationale),
            evidence_ids,
        )

    def _bind_risk(
        self,
        case_id: str,
        *,
        portfolio: dict,
        risk: dict,
        evidence_ids: list[str],
    ) -> tuple[str, str, str]:
        constraints = portfolio.get("constraints")
        if not isinstance(constraints, dict):
            raise InvestmentOfficeBridgeError(
                "Portfolio constraints are required for snapshot binding"
            )
        snapshot_as_of = _required_text(
            constraints.get("as_of"),
            "Portfolio constraints as_of",
        )
        snapshot_id = self.kernel.add_snapshot(
            case_id,
            {
                "schema": "quantrade_investment_office_portfolio_snapshot_v1",
                "portfolio_status": portfolio.get("status"),
                "opportunity_cost": portfolio.get("opportunity_cost"),
                "capital_headroom": portfolio.get("capital_headroom"),
                "constraints": constraints,
            },
            source="investment_office_capability_handoff",
            as_of=snapshot_as_of,
        )

        policy = risk.get("policy")
        if not isinstance(policy, dict):
            raise InvestmentOfficeBridgeError(
                "Risk policy object is required"
            )
        policy_version = _required_text(
            policy.get("policy_id"),
            "Risk policy_id",
        )
        assessment_id = self.kernel.add_risk_assessment(
            case_id,
            snapshot_id,
            risk,
            policy_version,
        )
        risk_position_id = self.kernel.add_position(
            case_id,
            "IPRO",
            _required_text(risk.get("status"), "Risk status"),
            _json(
                {
                    "reasons": risk.get("reasons") or [],
                    "limits": risk.get("limits") or {},
                    "policy": policy,
                    "state": risk.get("state") or {},
                    "risk_limit_changed": False,
                    "target_weight_set": False,
                }
            ),
            evidence_ids,
        )
        return snapshot_id, assessment_id, risk_position_id

    def _bind_counterclaims(
        self,
        case_id: str,
        *,
        thesis: dict,
    ) -> list[str]:
        nodes = thesis.get("nodes")
        assert isinstance(nodes, dict)
        thesis_rows = nodes.get("thesis_claims") or []
        counter_rows = nodes.get("counter_claims") or []
        thesis_by_id = {
            str(item.get("thesis_id")): item
            for item in thesis_rows
            if isinstance(item, dict) and item.get("thesis_id")
        }

        challenge_ids: list[str] = []
        for counter in counter_rows:
            if not isinstance(counter, dict):
                raise InvestmentOfficeBridgeError(
                    "CounterClaim must be an object"
                )
            target_id = _required_text(
                counter.get("thesis_id"),
                "CounterClaim thesis_id",
            )
            target = thesis_by_id.get(target_id)
            if target is None:
                raise InvestmentOfficeBridgeError(
                    f"CounterClaim target Thesis missing: {target_id}"
                )
            challenged = _required_text(
                target.get("statement"),
                "Thesis statement",
            )
            counter_statement = _required_text(
                counter.get("statement"),
                "CounterClaim statement",
            )
            challenge_ids.append(
                self.kernel.add_challenge(
                    case_id,
                    challenged,
                    counter_statement,
                    True,
                    office="ARU",
                )
            )
        return challenge_ids

    def bind(
        self,
        case_id: str,
        *,
        fundamental: object,
        thesis: object,
        portfolio: object,
        risk: object,
        enter_committee_when_ready: bool = True,
    ) -> dict:
        """Bind one Investment Office handoff into the existing Case.

        Committee entry is allowed only when:
        - existing InstitutionalKernel readiness passes; and
        - Risk is not REQUIRE_MORE_INFORMATION.

        A VETO is preserved as IPRO stance and may still enter Committee for
        governed resolution; this bridge never overrides or weakens it.
        """
        fundamental_dict = _plain(fundamental)
        thesis_dict = _plain(thesis)
        portfolio_dict = _plain(portfolio)
        risk_dict = _plain(risk)

        for label, value in (
            ("fundamental", fundamental_dict),
            ("thesis", thesis_dict),
            ("portfolio", portfolio_dict),
            ("risk", risk_dict),
        ):
            if not isinstance(value, dict):
                raise InvestmentOfficeBridgeError(
                    f"{label} artifact must compile to an object"
                )

        self._validate_artifacts(
            case_id,
            fundamental=fundamental_dict,
            thesis=thesis_dict,
            portfolio=portfolio_dict,
            risk=risk_dict,
        )

        handoff_payload = {
            "case_id": case_id,
            "fundamental": fundamental_dict,
            "thesis": thesis_dict,
            "portfolio": portfolio_dict,
            "risk": risk_dict,
        }
        handoff_id = _canonical_hash(handoff_payload)
        existing = self._existing_handoff(case_id, handoff_id)
        if existing is not None:
            return {
                **existing,
                "idempotent_replay": True,
            }

        evidence_ids = self._bind_evidence(
            case_id,
            fundamental=fundamental_dict,
            thesis=thesis_dict,
        )
        portfolio_position_id = self._bind_portfolio(
            case_id,
            portfolio=portfolio_dict,
            evidence_ids=evidence_ids,
        )
        (
            portfolio_snapshot_id,
            risk_assessment_id,
            risk_position_id,
        ) = self._bind_risk(
            case_id,
            portfolio=portfolio_dict,
            risk=risk_dict,
            evidence_ids=evidence_ids,
        )
        challenge_ids = self._bind_counterclaims(
            case_id,
            thesis=thesis_dict,
        )

        readiness = self.kernel.committee_readiness(case_id)
        risk_status = str(risk_dict.get("status"))
        blocked_by_risk_information = (
            risk_status == "REQUIRE_MORE_INFORMATION"
        )

        committee_entered = False
        if (
            enter_committee_when_ready
            and readiness["ready"]
            and not blocked_by_risk_information
        ):
            self.kernel.enter_committee(case_id)
            committee_entered = True

        result = {
            "schema": "quantrade_investment_office_institutional_handoff_v1",
            "handoff_id": handoff_id,
            "case_id": case_id,
            "evidence_ids": evidence_ids,
            "portfolio_position_id": portfolio_position_id,
            "portfolio_snapshot_id": portfolio_snapshot_id,
            "risk_assessment_id": risk_assessment_id,
            "risk_position_id": risk_position_id,
            "adversarial_challenge_ids": challenge_ids,
            "risk_status": risk_status,
            "risk_veto_preserved": risk_status == "VETO",
            "risk_information_block": blocked_by_risk_information,
            "committee_readiness": readiness,
            "committee_entered": committee_entered,
            "idempotent_replay": False,
            "authority": {
                "founder_decision_created": False,
                "decision_plan_created": False,
                "paper_authorized": False,
                "execution_authorized": False,
                "live_order_possible": False,
            },
        }

        self.kernel.record_activity(
            "Case",
            case_id,
            "INVESTMENT_OFFICE_HANDOFF_BOUND",
            {
                "handoff_id": handoff_id,
                "result": result,
            },
        )
        return result
