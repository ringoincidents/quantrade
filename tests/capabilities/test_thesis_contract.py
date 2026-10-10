import unittest

from quantrade.capabilities.thesis_contract import (
    Assumption,
    CounterClaim,
    FalsificationCondition,
    Inference,
    Observation,
    SourceKind,
    ThesisClaim,
    ThesisContractError,
    ThesisContractInput,
    compile_thesis_contract,
)
from quantrade.capabilities.thesis_contract_evaluation import (
    reference_thesis_contracts,
)


class ThesisContractTests(unittest.TestCase):
    def _valid_contract(self):
        return ThesisContractInput(
            case_id="CASE-THESIS-1",
            as_of="2026-10-05T12:00:00+09:00",
            observations=(
                Observation(
                    observation_id="OBS-1",
                    statement="Verified filing fact.",
                    source_ref="fixture://filing/1",
                    source_kind=SourceKind.EXTERNAL_EVIDENCE.value,
                    observed_at="2026-10-04T09:00:00+09:00",
                ),
                Observation(
                    observation_id="OBS-2",
                    statement="Contradicting verified fact.",
                    source_ref="fixture://filing/2",
                    source_kind=SourceKind.RUNTIME_VERIFIED.value,
                    observed_at="2026-10-04T10:00:00+09:00",
                ),
            ),
            assumptions=(
                Assumption(
                    assumption_id="ASM-1",
                    statement="The observed improvement persists.",
                    rationale="Explicit forecast assumption.",
                ),
            ),
            inferences=(
                Inference(
                    inference_id="INF-1",
                    statement="Persistence would raise forward economics.",
                    input_refs=("OBS-1", "ASM-1"),
                ),
            ),
            thesis_claims=(
                ThesisClaim(
                    thesis_id="TH-1",
                    statement="Forward value may be understated.",
                    support_refs=("INF-1",),
                ),
            ),
            counter_claims=(
                CounterClaim(
                    counter_id="CTR-1",
                    thesis_id="TH-1",
                    statement="The improvement may reverse.",
                    basis_refs=("OBS-2",),
                ),
            ),
            falsification_conditions=(
                FalsificationCondition(
                    condition_id="FAL-1",
                    thesis_id="TH-1",
                    statement="Observed economics reverse below baseline.",
                    observable="verified_operating_metric",
                    evaluation_horizon="next_two_quarters",
                ),
            ),
        )

    def test_valid_contract_is_structured_but_non_authoritative(self):
        artifact = compile_thesis_contract(self._valid_contract())
        self.assertEqual(1, artifact.completeness["thesis_count"])
        self.assertTrue(
            artifact.completeness["all_theses_evidence_backed"]
        )
        self.assertTrue(
            artifact.completeness["all_theses_have_counter_research"]
        )
        self.assertTrue(artifact.completeness["all_theses_falsifiable"])
        assessment = artifact.thesis_assessments[0]
        self.assertTrue(assessment["evidence_backed"])
        self.assertEqual(
            ("OBS-1",),
            assessment["eligible_evidence_observation_refs"],
        )
        self.assertEqual(("ASM-1",), assessment["assumption_refs"])
        self.assertFalse(artifact.authority["thesis_truth_validated"])
        self.assertFalse(
            artifact.authority["portfolio_proposal_created"]
        )
        self.assertFalse(artifact.authority["execution_authorized"])

    def test_model_artifact_is_not_counted_as_evidence(self):
        contract = ThesisContractInput(
            case_id="CASE-MODEL-ONLY",
            as_of="2026-10-05T12:00:00+09:00",
            observations=(
                Observation(
                    observation_id="OBS-M",
                    statement="Model output.",
                    source_ref="fixture://model",
                    source_kind=SourceKind.MODEL_ARTIFACT.value,
                    observed_at="2026-10-05T10:00:00+09:00",
                ),
            ),
            thesis_claims=(
                ThesisClaim(
                    thesis_id="TH-M",
                    statement="Model-only thesis.",
                    support_refs=("OBS-M",),
                ),
            ),
            falsification_conditions=(
                FalsificationCondition(
                    condition_id="FAL-M",
                    thesis_id="TH-M",
                    statement="Verified future data contradicts it.",
                    observable="future_verified_data",
                    evaluation_horizon="before_promotion",
                ),
            ),
        )
        artifact = compile_thesis_contract(contract)
        assessment = artifact.thesis_assessments[0]
        self.assertFalse(assessment["evidence_backed"])
        self.assertEqual(
            ("OBS-M",),
            assessment["non_evidence_observation_refs"],
        )
        self.assertFalse(
            artifact.completeness["all_theses_evidence_backed"]
        )

    def test_client_fact_is_not_market_thesis_evidence(self):
        contract = ThesisContractInput(
            case_id="CASE-CLIENT-FACT",
            as_of="2026-10-05T12:00:00+09:00",
            observations=(
                Observation(
                    observation_id="CLIENT-FACT",
                    statement="Client has a liquidity requirement.",
                    source_ref="fixture://client-fact",
                    source_kind=SourceKind.CLIENT_FACT.value,
                    observed_at="2026-10-04T00:00:00+09:00",
                ),
            ),
            thesis_claims=(
                ThesisClaim(
                    thesis_id="TH-CLIENT",
                    statement="Client context alone does not prove market edge.",
                    support_refs=("CLIENT-FACT",),
                ),
            ),
            falsification_conditions=(
                FalsificationCondition(
                    condition_id="FAL-CLIENT",
                    thesis_id="TH-CLIENT",
                    statement="Verified market evidence is required.",
                    observable="verified_market_evidence",
                    evaluation_horizon="before_research_handoff",
                ),
            ),
        )
        artifact = compile_thesis_contract(contract)
        assessment = artifact.thesis_assessments[0]
        self.assertFalse(assessment["evidence_backed"])
        self.assertEqual(
            ("CLIENT-FACT",),
            assessment["non_evidence_observation_refs"],
        )

    def test_assumption_is_not_evidence(self):
        contract = ThesisContractInput(
            case_id="CASE-ASSUMPTION",
            as_of="2026-10-05T12:00:00+09:00",
            assumptions=(
                Assumption(
                    assumption_id="ASM",
                    statement="Growth persists.",
                    rationale="Forecast assumption.",
                ),
            ),
            thesis_claims=(
                ThesisClaim(
                    thesis_id="TH",
                    statement="Value is understated.",
                    support_refs=("ASM",),
                ),
            ),
            falsification_conditions=(
                FalsificationCondition(
                    condition_id="FAL",
                    thesis_id="TH",
                    statement="Growth fails to persist.",
                    observable="growth",
                    evaluation_horizon="next_year",
                ),
            ),
        )
        artifact = compile_thesis_contract(contract)
        assessment = artifact.thesis_assessments[0]
        self.assertFalse(assessment["evidence_backed"])
        self.assertEqual(("ASM",), assessment["assumption_refs"])

    def test_future_observation_is_rejected(self):
        contract = self._valid_contract()
        bad = ThesisContractInput(
            case_id=contract.case_id,
            as_of=contract.as_of,
            observations=(
                Observation(
                    observation_id="OBS-FUTURE",
                    statement="Future fact.",
                    source_ref="fixture://future",
                    source_kind=SourceKind.EXTERNAL_EVIDENCE.value,
                    observed_at="2026-10-06T00:00:00+09:00",
                ),
            ),
            thesis_claims=(
                ThesisClaim(
                    thesis_id="TH-F",
                    statement="Bad future thesis.",
                    support_refs=("OBS-FUTURE",),
                ),
            ),
            falsification_conditions=(
                FalsificationCondition(
                    condition_id="FAL-F",
                    thesis_id="TH-F",
                    statement="Condition.",
                    observable="metric",
                    evaluation_horizon="later",
                ),
            ),
        )
        with self.assertRaisesRegex(
            ThesisContractError,
            "after case as_of",
        ):
            compile_thesis_contract(bad)

    def test_duplicate_ids_across_node_types_are_rejected(self):
        contract = ThesisContractInput(
            case_id="CASE-DUP",
            as_of="2026-10-05T12:00:00+09:00",
            observations=(
                Observation(
                    observation_id="SAME",
                    statement="Fact.",
                    source_ref="fixture://fact",
                    source_kind=SourceKind.EXTERNAL_EVIDENCE.value,
                    observed_at="2026-10-04T00:00:00+09:00",
                ),
            ),
            assumptions=(
                Assumption(
                    assumption_id="SAME",
                    statement="Assumption.",
                    rationale="Reason.",
                ),
            ),
        )
        with self.assertRaisesRegex(
            ThesisContractError,
            "duplicate node id",
        ):
            compile_thesis_contract(contract)

    def test_unknown_support_ref_is_rejected(self):
        contract = ThesisContractInput(
            case_id="CASE-UNKNOWN",
            as_of="2026-10-05T12:00:00+09:00",
            thesis_claims=(
                ThesisClaim(
                    thesis_id="TH",
                    statement="Claim.",
                    support_refs=("DOES-NOT-EXIST",),
                ),
            ),
            falsification_conditions=(
                FalsificationCondition(
                    condition_id="FAL",
                    thesis_id="TH",
                    statement="Condition.",
                    observable="metric",
                    evaluation_horizon="later",
                ),
            ),
        )
        with self.assertRaisesRegex(
            ThesisContractError,
            "unknown node",
        ):
            compile_thesis_contract(contract)

    def test_inference_cycle_is_rejected(self):
        contract = ThesisContractInput(
            case_id="CASE-CYCLE",
            as_of="2026-10-05T12:00:00+09:00",
            inferences=(
                Inference(
                    inference_id="I1",
                    statement="One.",
                    input_refs=("I2",),
                ),
                Inference(
                    inference_id="I2",
                    statement="Two.",
                    input_refs=("I1",),
                ),
            ),
            thesis_claims=(
                ThesisClaim(
                    thesis_id="TH",
                    statement="Claim.",
                    support_refs=("I1",),
                ),
            ),
            falsification_conditions=(
                FalsificationCondition(
                    condition_id="FAL",
                    thesis_id="TH",
                    statement="Condition.",
                    observable="metric",
                    evaluation_horizon="later",
                ),
            ),
        )
        with self.assertRaisesRegex(
            ThesisContractError,
            "dependency cycle",
        ):
            compile_thesis_contract(contract)

    def test_every_thesis_requires_falsification(self):
        contract = ThesisContractInput(
            case_id="CASE-NO-FALSIFICATION",
            as_of="2026-10-05T12:00:00+09:00",
            observations=(
                Observation(
                    observation_id="OBS",
                    statement="Fact.",
                    source_ref="fixture://fact",
                    source_kind=SourceKind.EXTERNAL_EVIDENCE.value,
                    observed_at="2026-10-04T00:00:00+09:00",
                ),
            ),
            thesis_claims=(
                ThesisClaim(
                    thesis_id="TH",
                    statement="Claim.",
                    support_refs=("OBS",),
                ),
            ),
        )
        with self.assertRaisesRegex(
            ThesisContractError,
            "requires at least one falsification",
        ):
            compile_thesis_contract(contract)

    def test_counter_claim_must_target_existing_thesis(self):
        contract = ThesisContractInput(
            case_id="CASE-COUNTER",
            as_of="2026-10-05T12:00:00+09:00",
            observations=(
                Observation(
                    observation_id="OBS",
                    statement="Fact.",
                    source_ref="fixture://fact",
                    source_kind=SourceKind.EXTERNAL_EVIDENCE.value,
                    observed_at="2026-10-04T00:00:00+09:00",
                ),
            ),
            counter_claims=(
                CounterClaim(
                    counter_id="CTR",
                    thesis_id="MISSING",
                    statement="Counter.",
                    basis_refs=("OBS",),
                ),
            ),
        )
        with self.assertRaisesRegex(
            ThesisContractError,
            "unknown thesis",
        ):
            compile_thesis_contract(contract)

    def test_counter_research_can_be_missing_without_fabrication(self):
        contract = self._valid_contract()
        no_counter = ThesisContractInput(
            case_id=contract.case_id,
            as_of=contract.as_of,
            observations=contract.observations,
            assumptions=contract.assumptions,
            inferences=contract.inferences,
            thesis_claims=contract.thesis_claims,
            counter_claims=(),
            falsification_conditions=contract.falsification_conditions,
        )
        artifact = compile_thesis_contract(no_counter)
        self.assertFalse(
            artifact.completeness["all_theses_have_counter_research"]
        )
        self.assertFalse(
            artifact.thesis_assessments[0]["counter_research_present"]
        )
        self.assertFalse(artifact.authority["thesis_truth_validated"])

    def test_reference_harness_preserves_evidence_boundary(self):
        result = reference_thesis_contracts()
        backed = result["cases"]["evidence_backed"]
        model_only = result["cases"]["model_only"]
        self.assertTrue(
            backed["completeness"]["all_theses_evidence_backed"]
        )
        self.assertFalse(
            model_only["completeness"]["all_theses_evidence_backed"]
        )
        self.assertFalse(
            result["authority"]["canonical_evidence_created"]
        )
        self.assertFalse(
            result["authority"]["thesis_truth_validated"]
        )
        self.assertFalse(result["authority"]["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
