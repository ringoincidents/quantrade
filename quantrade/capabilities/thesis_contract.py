"""Structured Thesis Contract for QuanTrade Investment Cases.

This module separates Observations, Assumptions, Inferences, Thesis Claims,
Counter-Claims, and Falsification Conditions before any downstream portfolio or
investment decision.

It is deterministic, dependency-free, and model-free.

Important authority boundary:
- it does not create canonical Evidence;
- it does not decide whether a thesis is true;
- it does not create a Portfolio Proposal, Risk Opinion, Committee Decision,
  PAPER authority, or execution authority.

External/verified sources may be *referenced* as evidence-bearing inputs, while
model artifacts remain explicitly non-evidence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable


class ThesisContractError(ValueError):
    """Raised when a Thesis Contract violates structural/provenance rules."""


class SourceKind(str, Enum):
    EXTERNAL_EVIDENCE = "EXTERNAL_EVIDENCE"
    RUNTIME_VERIFIED = "RUNTIME_VERIFIED"
    CLIENT_FACT = "CLIENT_FACT"
    MODEL_ARTIFACT = "MODEL_ARTIFACT"
    HUMAN_ANALYSIS = "HUMAN_ANALYSIS"


EVIDENCE_ELIGIBLE_SOURCE_KINDS = frozenset(
    {
        SourceKind.EXTERNAL_EVIDENCE.value,
        SourceKind.RUNTIME_VERIFIED.value,
    }
)

# Client facts can be valid governed inputs to Mandate / Portfolio / Risk, but
# they are not market evidence for an Investment Thesis merely because they are
# true about the Client. Keep the source kind representable without granting it
# thesis-evidence authority.


@dataclass(frozen=True)
class Observation:
    observation_id: str
    statement: str
    source_ref: str
    source_kind: str
    observed_at: str


@dataclass(frozen=True)
class Assumption:
    assumption_id: str
    statement: str
    rationale: str
    provenance_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Inference:
    inference_id: str
    statement: str
    input_refs: tuple[str, ...]


@dataclass(frozen=True)
class ThesisClaim:
    thesis_id: str
    statement: str
    support_refs: tuple[str, ...]


@dataclass(frozen=True)
class CounterClaim:
    counter_id: str
    thesis_id: str
    statement: str
    basis_refs: tuple[str, ...]


@dataclass(frozen=True)
class FalsificationCondition:
    condition_id: str
    thesis_id: str
    statement: str
    observable: str
    evaluation_horizon: str


@dataclass(frozen=True)
class ThesisContractInput:
    case_id: str
    as_of: str
    observations: tuple[Observation, ...] = ()
    assumptions: tuple[Assumption, ...] = ()
    inferences: tuple[Inference, ...] = ()
    thesis_claims: tuple[ThesisClaim, ...] = ()
    counter_claims: tuple[CounterClaim, ...] = ()
    falsification_conditions: tuple[FalsificationCondition, ...] = ()


@dataclass(frozen=True)
class ThesisContractArtifact:
    schema: str
    case_id: str
    as_of: str
    nodes: dict
    thesis_assessments: tuple[dict, ...]
    completeness: dict
    authority: dict


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ThesisContractError(f"{field_name} is required")
    return value.strip()


def _parse_time(value: str, field_name: str) -> datetime:
    raw = _required_text(value, field_name).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ThesisContractError(
            f"{field_name} must be valid ISO-8601"
        ) from exc
    if parsed.tzinfo is None:
        raise ThesisContractError(
            f"{field_name} must include timezone information"
        )
    return parsed.astimezone(timezone.utc)


def _validate_refs_nonempty(refs: Iterable[str], field_name: str) -> tuple[str, ...]:
    items = tuple(refs)
    for ref in items:
        _required_text(ref, field_name)
    return items


def _register_id(
    node_id: str,
    node_type: str,
    registry: dict[str, str],
) -> None:
    normalized = _required_text(node_id, f"{node_type} id")
    if normalized in registry:
        raise ThesisContractError(
            f"duplicate node id across contract: {normalized}"
        )
    registry[normalized] = node_type


def _validate_source_kind(value: str) -> str:
    normalized = _required_text(value, "observation source_kind")
    allowed = {item.value for item in SourceKind}
    if normalized not in allowed:
        raise ThesisContractError(
            f"unsupported observation source_kind: {normalized}"
        )
    return normalized


def _resolve_refs(
    refs: Iterable[str],
    *,
    allowed_types: frozenset[str],
    registry: dict[str, str],
    field_name: str,
) -> tuple[str, ...]:
    items = _validate_refs_nonempty(refs, field_name)
    for ref in items:
        if ref not in registry:
            raise ThesisContractError(
                f"{field_name} references unknown node: {ref}"
            )
        if registry[ref] not in allowed_types:
            raise ThesisContractError(
                f"{field_name} cannot reference {registry[ref]} node: {ref}"
            )
    return items


def _validate_inference_cycles(
    inferences: tuple[Inference, ...],
    registry: dict[str, str],
) -> None:
    graph: dict[str, tuple[str, ...]] = {}
    for inference in inferences:
        deps = tuple(
            ref
            for ref in inference.input_refs
            if registry.get(ref) == "INFERENCE"
        )
        if inference.inference_id in deps:
            raise ThesisContractError(
                f"inference cannot reference itself: {inference.inference_id}"
            )
        graph[inference.inference_id] = deps

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visited:
            return
        if node_id in visiting:
            raise ThesisContractError(
                f"inference dependency cycle detected at: {node_id}"
            )
        visiting.add(node_id)
        for dependency in graph.get(node_id, ()):
            visit(dependency)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in graph:
        visit(node_id)


def _support_leaf_refs(
    refs: Iterable[str],
    *,
    registry: dict[str, str],
    inference_map: dict[str, Inference],
) -> tuple[str, ...]:
    leaves: list[str] = []
    visited: set[str] = set()

    def walk(ref: str) -> None:
        if ref in visited:
            return
        visited.add(ref)
        node_type = registry[ref]
        if node_type == "INFERENCE":
            for dependency in inference_map[ref].input_refs:
                walk(dependency)
            return
        leaves.append(ref)

    for ref in refs:
        walk(ref)
    return tuple(leaves)


def compile_thesis_contract(
    contract: ThesisContractInput,
) -> ThesisContractArtifact:
    """Validate and compile a non-authoritative Investment Thesis structure."""
    _required_text(contract.case_id, "case_id")
    case_as_of = _parse_time(contract.as_of, "as_of")

    registry: dict[str, str] = {}
    for observation in contract.observations:
        _register_id(observation.observation_id, "OBSERVATION", registry)
    for assumption in contract.assumptions:
        _register_id(assumption.assumption_id, "ASSUMPTION", registry)
    for inference in contract.inferences:
        _register_id(inference.inference_id, "INFERENCE", registry)
    for thesis in contract.thesis_claims:
        _register_id(thesis.thesis_id, "THESIS", registry)
    for counter in contract.counter_claims:
        _register_id(counter.counter_id, "COUNTER", registry)
    for condition in contract.falsification_conditions:
        _register_id(condition.condition_id, "FALSIFICATION", registry)

    observation_map = {
        item.observation_id: item
        for item in contract.observations
    }
    assumption_map = {
        item.assumption_id: item
        for item in contract.assumptions
    }
    inference_map = {
        item.inference_id: item
        for item in contract.inferences
    }
    thesis_map = {
        item.thesis_id: item
        for item in contract.thesis_claims
    }

    for observation in contract.observations:
        _required_text(observation.statement, "observation statement")
        _required_text(observation.source_ref, "observation source_ref")
        _validate_source_kind(observation.source_kind)
        observed_at = _parse_time(
            observation.observed_at,
            "observation observed_at",
        )
        if observed_at > case_as_of:
            raise ThesisContractError(
                f"observation {observation.observation_id} is after case as_of"
            )

    for assumption in contract.assumptions:
        _required_text(assumption.statement, "assumption statement")
        _required_text(assumption.rationale, "assumption rationale")
        _validate_refs_nonempty(
            assumption.provenance_refs,
            "assumption provenance_ref",
        )

    support_types = frozenset({"OBSERVATION", "ASSUMPTION", "INFERENCE"})

    for inference in contract.inferences:
        _required_text(inference.statement, "inference statement")
        refs = _resolve_refs(
            inference.input_refs,
            allowed_types=support_types,
            registry=registry,
            field_name=f"inference {inference.inference_id} input_refs",
        )
        if not refs:
            raise ThesisContractError(
                f"inference {inference.inference_id} requires input_refs"
            )

    _validate_inference_cycles(contract.inferences, registry)

    for thesis in contract.thesis_claims:
        _required_text(thesis.statement, "thesis statement")
        refs = _resolve_refs(
            thesis.support_refs,
            allowed_types=support_types,
            registry=registry,
            field_name=f"thesis {thesis.thesis_id} support_refs",
        )
        if not refs:
            raise ThesisContractError(
                f"thesis {thesis.thesis_id} requires support_refs"
            )

    for counter in contract.counter_claims:
        _required_text(counter.statement, "counter statement")
        if counter.thesis_id not in thesis_map:
            raise ThesisContractError(
                f"counter {counter.counter_id} references unknown thesis: "
                f"{counter.thesis_id}"
            )
        refs = _resolve_refs(
            counter.basis_refs,
            allowed_types=support_types,
            registry=registry,
            field_name=f"counter {counter.counter_id} basis_refs",
        )
        if not refs:
            raise ThesisContractError(
                f"counter {counter.counter_id} requires basis_refs"
            )

    falsification_by_thesis: dict[str, list[FalsificationCondition]] = {
        thesis_id: [] for thesis_id in thesis_map
    }
    for condition in contract.falsification_conditions:
        if condition.thesis_id not in thesis_map:
            raise ThesisContractError(
                f"falsification {condition.condition_id} references unknown "
                f"thesis: {condition.thesis_id}"
            )
        _required_text(
            condition.statement,
            "falsification condition statement",
        )
        _required_text(
            condition.observable,
            "falsification observable",
        )
        _required_text(
            condition.evaluation_horizon,
            "falsification evaluation_horizon",
        )
        falsification_by_thesis[condition.thesis_id].append(condition)

    for thesis_id, conditions in falsification_by_thesis.items():
        if not conditions:
            raise ThesisContractError(
                f"thesis {thesis_id} requires at least one falsification "
                "condition"
            )

    counter_by_thesis: dict[str, list[CounterClaim]] = {
        thesis_id: [] for thesis_id in thesis_map
    }
    for counter in contract.counter_claims:
        counter_by_thesis[counter.thesis_id].append(counter)

    thesis_assessments: list[dict] = []
    evidence_backed_count = 0
    counter_present_count = 0
    model_only_or_assumption_only_count = 0

    for thesis in contract.thesis_claims:
        leaves = _support_leaf_refs(
            thesis.support_refs,
            registry=registry,
            inference_map=inference_map,
        )
        observation_refs = tuple(
            ref for ref in leaves
            if registry[ref] == "OBSERVATION"
        )
        assumption_refs = tuple(
            ref for ref in leaves
            if registry[ref] == "ASSUMPTION"
        )

        evidence_observations = tuple(
            ref
            for ref in observation_refs
            if observation_map[ref].source_kind
            in EVIDENCE_ELIGIBLE_SOURCE_KINDS
        )
        non_evidence_observations = tuple(
            ref
            for ref in observation_refs
            if observation_map[ref].source_kind
            not in EVIDENCE_ELIGIBLE_SOURCE_KINDS
        )
        evidence_backed = bool(evidence_observations)
        if evidence_backed:
            evidence_backed_count += 1

        counters = counter_by_thesis[thesis.thesis_id]
        if counters:
            counter_present_count += 1

        if not evidence_backed:
            model_only_or_assumption_only_count += 1

        thesis_assessments.append(
            {
                "thesis_id": thesis.thesis_id,
                "support_leaf_refs": leaves,
                "eligible_evidence_observation_refs": evidence_observations,
                "non_evidence_observation_refs": non_evidence_observations,
                "assumption_refs": assumption_refs,
                "evidence_backed": evidence_backed,
                "counter_claim_ids": tuple(
                    item.counter_id for item in counters
                ),
                "counter_research_present": bool(counters),
                "falsification_condition_ids": tuple(
                    item.condition_id
                    for item in falsification_by_thesis[thesis.thesis_id]
                ),
                "falsification_defined": True,
                "thesis_truth_validated": False,
                "investment_authority": False,
            }
        )

    observation_rows = []
    for observation in contract.observations:
        observation_rows.append(
            {
                **asdict(observation),
                "evidence_eligible_reference": (
                    observation.source_kind
                    in EVIDENCE_ELIGIBLE_SOURCE_KINDS
                ),
                "canonical_evidence_created": False,
            }
        )

    completeness = {
        "observation_count": len(contract.observations),
        "assumption_count": len(contract.assumptions),
        "inference_count": len(contract.inferences),
        "thesis_count": len(contract.thesis_claims),
        "counter_claim_count": len(contract.counter_claims),
        "falsification_condition_count": len(
            contract.falsification_conditions
        ),
        "theses_with_evidence_backing": evidence_backed_count,
        "theses_with_counter_research": counter_present_count,
        "theses_without_eligible_evidence": (
            model_only_or_assumption_only_count
        ),
        "all_theses_falsifiable": (
            len(contract.thesis_claims)
            == sum(
                1
                for thesis_id in thesis_map
                if falsification_by_thesis[thesis_id]
            )
        ),
        "all_theses_evidence_backed": (
            bool(contract.thesis_claims)
            and evidence_backed_count == len(contract.thesis_claims)
        ),
        "all_theses_have_counter_research": (
            bool(contract.thesis_claims)
            and counter_present_count == len(contract.thesis_claims)
        ),
    }

    return ThesisContractArtifact(
        schema="quantrade_thesis_contract_v1",
        case_id=contract.case_id,
        as_of=contract.as_of,
        nodes={
            "observations": tuple(observation_rows),
            "assumptions": tuple(
                asdict(item) for item in contract.assumptions
            ),
            "inferences": tuple(
                asdict(item) for item in contract.inferences
            ),
            "thesis_claims": tuple(
                asdict(item) for item in contract.thesis_claims
            ),
            "counter_claims": tuple(
                asdict(item) for item in contract.counter_claims
            ),
            "falsification_conditions": tuple(
                asdict(item)
                for item in contract.falsification_conditions
            ),
        },
        thesis_assessments=tuple(thesis_assessments),
        completeness=completeness,
        authority={
            "model_called": False,
            "canonical_evidence_created": False,
            "thesis_truth_validated": False,
            "portfolio_proposal_created": False,
            "position_size_set": False,
            "risk_opinion_created": False,
            "committee_decision_created": False,
            "decision_plan_created": False,
            "paper_authorized": False,
            "execution_authorized": False,
            "live_order_possible": False,
        },
    )
