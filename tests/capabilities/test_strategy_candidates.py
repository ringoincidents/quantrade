import unittest

from quantrade.capabilities.strategy_candidates import (
    CandidateGenerationContext,
    CandidatePolicy,
    CandidateValidationError,
    StaticCandidateProvider,
    compile_position_signals,
    validate_formula,
)
from quantrade.capabilities.strategy_candidate_evaluation import (
    candidate_generation_experiment,
)
from quantrade.capabilities.strategy_research import CandidateStrategy, PriceBar


class StrategyCandidateTests(unittest.TestCase):
    def _bars(self, count=12):
        return [
            PriceBar(
                f"2026-01-{day:02d}T00:00:00+00:00",
                100.0 + day,
            )
            for day in range(1, count + 1)
        ]

    def _candidate(self, candidate_id="C1", formula=None):
        if formula is None:
            formula = {
                "op": "GT",
                "left": {"op": "SMA", "window": 3},
                "right": {"op": "SMA", "window": 5},
            }
        return CandidateStrategy(
            candidate_id,
            "fixture",
            "STATIC",
            "fixture://candidate",
            "TEST",
            "DAILY",
            formula_ast=formula,
        )

    def test_unknown_operator_is_rejected(self):
        with self.assertRaisesRegex(
            CandidateValidationError,
            "unsupported DSL operator",
        ):
            validate_formula(
                {
                    "op": "EXEC",
                    "code": "__import__('os').system('echo nope')",
                }
            )

    def test_depth_is_bounded(self):
        formula = {"op": "CLOSE"}
        for _ in range(5):
            formula = {"op": "REF", "value": formula, "periods": 1}
        formula = {
            "op": "GT",
            "left": formula,
            "right": {"op": "CONST", "value": 0},
        }
        with self.assertRaisesRegex(CandidateValidationError, "max_depth"):
            validate_formula(
                formula,
                CandidatePolicy(max_depth=3),
            )

    def test_window_is_bounded(self):
        with self.assertRaisesRegex(
            CandidateValidationError,
            "between 1 and 20",
        ):
            validate_formula(
                {
                    "op": "GT",
                    "left": {"op": "SMA", "window": 21},
                    "right": {"op": "CLOSE"},
                },
                CandidatePolicy(max_window=20),
            )

    def test_division_by_zero_is_deterministically_false(self):
        bars = self._bars()
        formula = {
            "op": "GT",
            "left": {
                "op": "DIV",
                "left": {"op": "CLOSE"},
                "right": {"op": "CONST", "value": 0},
            },
            "right": {"op": "CONST", "value": 1},
        }
        signals = compile_position_signals(
            self._candidate(formula=formula),
            bars,
        )
        self.assertEqual(
            [0.0] * (len(bars) - 1),
            [signal.target_position for signal in signals],
        )

    def test_candidate_count_is_bounded(self):
        candidates = [
            self._candidate(
                candidate_id=f"C{i}",
                formula={
                    "op": "GT",
                    "left": {"op": "RETURN", "window": 1},
                    "right": {"op": "CONST", "value": i / 100.0},
                },
            )
            for i in range(3)
        ]
        provider = StaticCandidateProvider(
            candidates,
            policy=CandidatePolicy(max_candidates=2),
        )
        with self.assertRaisesRegex(
            CandidateValidationError,
            "max_candidates=2",
        ):
            provider.generate(
                CandidateGenerationContext("TEST", "DAILY")
            )

    def test_duplicate_formula_is_rejected(self):
        provider = StaticCandidateProvider(
            [
                self._candidate("C1"),
                self._candidate("C2"),
            ]
        )
        with self.assertRaisesRegex(
            CandidateValidationError,
            "duplicate candidate formula",
        ):
            provider.generate(
                CandidateGenerationContext("TEST", "DAILY")
            )

    def test_provider_provenance_is_preserved(self):
        provider = StaticCandidateProvider([self._candidate()])
        generated = provider.generate(
            CandidateGenerationContext("TEST", "DAILY")
        )
        candidate = generated[0]
        self.assertEqual(
            "quantrade.static.strategy_candidates.v1",
            candidate.generator_provider["provider_id"],
        )
        self.assertTrue(
            candidate.generator_provider["deterministic"]
        )
        self.assertFalse(
            candidate.generator_provider["network_access"]
        )
        self.assertFalse(
            candidate.generator_provider["model_access"]
        )
        self.assertFalse(
            candidate.generator_provider["capital_effect"]
        )

    def test_extra_fields_cannot_smuggle_code(self):
        formula = {
            "op": "GT",
            "left": {"op": "CLOSE"},
            "right": {"op": "CONST", "value": 100},
            "python": "open('/tmp/x','w').write('bad')",
        }
        with self.assertRaisesRegex(
            CandidateValidationError,
            "unsupported keys",
        ):
            validate_formula(formula)

    def test_future_price_change_does_not_change_earlier_signal(self):
        bars = self._bars()
        candidate = self._candidate(
            formula={
                "op": "GT",
                "left": {"op": "SMA", "window": 3},
                "right": {"op": "SMA", "window": 5},
            }
        )
        first = compile_position_signals(candidate, bars)

        changed = list(bars)
        changed[-1] = PriceBar(
            changed[-1].observed_at,
            changed[-1].close * 100.0,
        )
        second = compile_position_signals(candidate, changed)

        self.assertEqual(
            [s.target_position for s in first[:-1]],
            [s.target_position for s in second[:-1]],
        )

    def test_static_provider_and_compiler_form_end_to_end_seam(self):
        bars = self._bars()
        provider = StaticCandidateProvider([self._candidate()])
        generated = provider.generate(
            CandidateGenerationContext("TEST", "DAILY")
        )
        signals = compile_position_signals(generated[0], bars)
        self.assertEqual(len(bars) - 1, len(signals))
        self.assertTrue(
            all(
                signal.information_cutoff == signal.effective_at
                for signal in signals
            )
        )
        self.assertTrue(
            all(
                signal.target_position in (0.0, 1.0)
                for signal in signals
            )
        )

    def test_end_to_end_candidate_experiment_stays_non_authoritative(self):
        artifact = candidate_generation_experiment()
        self.assertEqual(2, artifact["candidate_count"])
        self.assertEqual(
            [
                "STATIC_CANDIDATE_PROVIDER",
                "SAFE_AST_VALIDATION",
                "PAST_ONLY_SIGNAL_COMPILER",
                "DETERMINISTIC_STRATEGY_EVALUATOR",
            ],
            artifact["pipeline"],
        )
        self.assertFalse(artifact["authority"]["model_called"])
        self.assertFalse(
            artifact["authority"]["canonical_evidence_created"]
        )
        self.assertFalse(artifact["authority"]["strategy_approved"])
        self.assertFalse(artifact["authority"]["execution_authorized"])
        for result in artifact["results"]:
            self.assertTrue(
                result["formula_validation"]["safe_for_compilation"]
            )
            self.assertFalse(
                result["formula_validation"]["arbitrary_code_execution"]
            )
            self.assertFalse(
                result["signal_summary"]["future_information_required"]
            )
            self.assertFalse(
                result["evaluation"]["authority"]["execution_authorized"]
            )


if __name__ == "__main__":
    unittest.main()
