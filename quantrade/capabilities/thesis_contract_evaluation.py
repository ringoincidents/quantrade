"""Synthetic reference harness for QuanTrade Thesis Contract.

The fixtures validate structural/provenance boundaries only. They do not
represent real investment research or recommendations.
"""
from __future__ import annotations

from dataclasses import asdict

from quantrade.capabilities.thesis_contract import (
    Assumption,
    CounterClaim,
    FalsificationCondition,
    Inference,
    Observation,
    SourceKind,
    ThesisClaim,
    ThesisContractInput,
    compile_thesis_contract,
)


def reference_thesis_contracts() -> dict:
    evidence_backed = ThesisContractInput(
        case_id="CASE-REFERENCE-THESIS-001",
        as_of="2026-10-05T12:00:00+09:00",
        observations=(
            Observation(
                observation_id="OBS-MARGIN",
                statement=(
                    "Synthetic filing observation: operating margin improved "
                    "versus the comparison period."
                ),
                source_ref="fixture://filing/margin",
                source_kind=SourceKind.EXTERNAL_EVIDENCE.value,
                observed_at="2026-10-04T09:00:00+09:00",
            ),
            Observation(
                observation_id="OBS-INVENTORY",
                statement=(
                    "Synthetic filing observation: inventory remains elevated."
                ),
                source_ref="fixture://filing/inventory",
                source_kind=SourceKind.RUNTIME_VERIFIED.value,
                observed_at="2026-10-04T09:00:00+09:00",
            ),
            Observation(
                observation_id="OBS-MODEL",
                statement=(
                    "Synthetic model artifact: pricing power may be improving."
                ),
                source_ref="fixture://model/artifact",
                source_kind=SourceKind.MODEL_ARTIFACT.value,
                observed_at="2026-10-05T10:00:00+09:00",
            ),
        ),
        assumptions=(
            Assumption(
                assumption_id="ASM-PERSISTENCE",
                statement="Margin improvement persists for two quarters.",
                rationale=(
                    "Synthetic assumption used only to demonstrate explicit "
                    "assumption separation."
                ),
                provenance_refs=("fixture://assumption-note",),
            ),
        ),
        inferences=(
            Inference(
                inference_id="INF-EARNINGS",
                statement=(
                    "If margin improvement persists, forward earnings can "
                    "exceed the static baseline."
                ),
                input_refs=("OBS-MARGIN", "ASM-PERSISTENCE"),
            ),
        ),
        thesis_claims=(
            ThesisClaim(
                thesis_id="THESIS-EDGE",
                statement=(
                    "The market may understate durable earnings improvement."
                ),
                support_refs=("INF-EARNINGS", "OBS-MODEL"),
            ),
        ),
        counter_claims=(
            CounterClaim(
                counter_id="COUNTER-INVENTORY",
                thesis_id="THESIS-EDGE",
                statement=(
                    "Elevated inventory may prevent the margin improvement "
                    "from persisting."
                ),
                basis_refs=("OBS-INVENTORY",),
            ),
        ),
        falsification_conditions=(
            FalsificationCondition(
                condition_id="FALSIFY-MARGIN",
                thesis_id="THESIS-EDGE",
                statement=(
                    "The thesis is weakened if reported operating margin "
                    "reverses below the pre-improvement baseline."
                ),
                observable="reported_operating_margin",
                evaluation_horizon="next_two_quarters",
            ),
        ),
    )

    model_only = ThesisContractInput(
        case_id="CASE-REFERENCE-THESIS-002",
        as_of="2026-10-05T12:00:00+09:00",
        observations=(
            Observation(
                observation_id="OBS-MODEL-ONLY",
                statement="Synthetic model-generated narrative.",
                source_ref="fixture://model/only",
                source_kind=SourceKind.MODEL_ARTIFACT.value,
                observed_at="2026-10-05T10:00:00+09:00",
            ),
        ),
        assumptions=(
            Assumption(
                assumption_id="ASM-ONLY",
                statement="Synthetic unsupported assumption.",
                rationale="Demonstrate that assumptions are not evidence.",
            ),
        ),
        thesis_claims=(
            ThesisClaim(
                thesis_id="THESIS-MODEL-ONLY",
                statement="A model-only thesis must not become evidence-backed.",
                support_refs=("OBS-MODEL-ONLY", "ASM-ONLY"),
            ),
        ),
        falsification_conditions=(
            FalsificationCondition(
                condition_id="FALSIFY-MODEL-ONLY",
                thesis_id="THESIS-MODEL-ONLY",
                statement="Future verified evidence contradicts the narrative.",
                observable="future_verified_evidence",
                evaluation_horizon="before_any_downstream_promotion",
            ),
        ),
    )

    compiled_backed = compile_thesis_contract(evidence_backed)
    compiled_model_only = compile_thesis_contract(model_only)

    return {
        "schema": "quantrade_thesis_contract_reference_evaluation_v1",
        "cases": {
            "evidence_backed": asdict(compiled_backed),
            "model_only": asdict(compiled_model_only),
        },
        "lessons": (
            "OBSERVATION_ASSUMPTION_INFERENCE_ARE_DISTINCT",
            "MODEL_ARTIFACT_IS_NOT_EVIDENCE",
            "THESIS_MUST_DEFINE_FALSIFICATION",
            "COUNTER_RESEARCH_REMAINS_SEPARATE",
            "STRUCTURAL_COMPLETENESS_IS_NOT_THESIS_TRUTH",
        ),
        "authority": {
            "model_called": False,
            "canonical_evidence_created": False,
            "thesis_truth_validated": False,
            "portfolio_proposal_created": False,
            "committee_decision_created": False,
            "execution_authorized": False,
        },
    }
