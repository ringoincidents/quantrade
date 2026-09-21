import copy
import json
import unittest

from quantrade.institutional.e2a_runner import run_e2a_trial
from quantrade.institutional.e2a_suite import grade_e2a_trial, seed_e2a_tasks
from quantrade.institutional.employee_agent import ModelAction, ScriptedModelProvider
from quantrade.institutional.eval_harness import EmployeeEvalHarness
from quantrade.institutional.service import InstitutionalKernel


def issue(kind='THESIS_BREAK', refs=None):
    return dict(issue_type=kind, priority='HIGH', action='INVESTIGATE',
                reason='A material question needs investigation.',
                evidence_refs=refs if refs is not None else ['MEM-PD02'])


class GradingIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.kernel = InstitutionalKernel(':memory:')
        seed_e2a_tasks(EmployeeEvalHarness(self.kernel))
        self.counter = 0

    def tearDown(self):
        self.kernel.close()

    def run_summary(self, summary, case='E2A-PD-02', tools=()):
        self.counter += 1
        actions = [ModelAction('TOOL', dict(tool_name=name, arguments={})) for name in tools]
        actions.append(ModelAction('FINISH', {'summary': json.dumps(summary)}))
        return run_e2a_trial(self.kernel, eval_task_id=case,
            treatment='E2A_PLUS_DIAGNOSTICS_MEMORY',
            provider=ScriptedModelProvider(actions), seed_label=str(self.counter))

    def test_guessed_memory_reference_receives_no_credit(self):
        result = self.run_summary(dict(issues=[issue()], no_other_material_issues=True))
        self.assertFalse(result.passed)
        self.assertEqual(0, result.observed['material_issue_recall'])
        self.assertEqual(1, result.observed['false_research_count'])

    def test_retrieval_must_match_current_trial_and_cited_output(self):
        summary = dict(issues=[issue()], no_other_material_issues=True)
        first = self.run_summary(summary, tools=['e2.investment_memory'])
        self.assertTrue(first.passed)
        second = self.run_summary(summary)
        self.assertFalse(second.passed)
        wrong_ref = self.run_summary(dict(issues=[issue(refs=['FILING-SS'])],
            no_other_material_issues=True), tools=['e2.investment_memory'])
        self.assertFalse(wrong_ref.passed)
        with self.kernel.conn:
            self.kernel.conn.execute("UPDATE tool_invocations SET status='ERROR' WHERE work_order_id=?", (first.work_order_id,))
        regraded = grade_e2a_trial(EmployeeEvalHarness(self.kernel), first.trial_id)
        self.assertFalse(regraded['passed'])
        self.assertEqual(0, regraded['observed']['material_issue_recall'])

    def test_full_contract_rejects_missing_and_bad_fields(self):
        good = dict(issues=[issue()], no_other_material_issues=True)
        variants = [None, [], {'issues': []}, {'issues': [], 'no_other_material_issues': 'true'}]
        for key in good['issues'][0]:
            variant = copy.deepcopy(good)
            del variant['issues'][0][key]
            variants.append(variant)
        for key, value in [('priority', []), ('action', {}), ('issue_type', []),
                           ('reason', ''), ('evidence_refs', [42])]:
            variant = copy.deepcopy(good)
            variant['issues'][0][key] = value
            variants.append(variant)
        for summary in variants:
            with self.subTest(summary=summary):
                result = self.run_summary(summary, tools=['e2.investment_memory'])
                self.assertFalse(result.passed)
                self.assertFalse(result.checks['output_contract_valid'])
                self.assertEqual(0, result.observed['material_issue_recall'])

    def test_no_action_requires_explicit_complete_review(self):
        result = self.run_summary(dict(issues=[], no_other_material_issues=False), case='E2A-PD-06')
        self.assertFalse(result.passed)
        self.assertFalse(result.observed['appropriate_no_action'])

    def test_duplicate_type_cannot_hide_decoy(self):
        result = self.run_summary(dict(issues=[
            issue('FACTOR_CONCENTRATION', ['OBS-TECH']),
            issue('FACTOR_CONCENTRATION', ['NEWS-TINY'])], no_other_material_issues=True), case='E2A-PD-05')
        self.assertFalse(result.passed)
        self.assertTrue(result.observed['decoy_escalated'])

    def test_public_inference_does_not_require_unnecessary_tool(self):
        result = self.run_summary(dict(issues=[issue('CORRELATION_SHIFT', ['OBS-MACRO'])],
            no_other_material_issues=True), case='E2A-PD-04')
        self.assertTrue(result.passed)

    def test_unknown_reference_does_not_earn_credit(self):
        result = self.run_summary(dict(issues=[issue('FACTOR_CONCENTRATION', ['INVENTED'])],
            no_other_material_issues=True), case='E2A-PD-05')
        self.assertFalse(result.passed)
        self.assertEqual(0, result.observed['material_issue_recall'])

    def test_serialized_first_turn_contains_only_granted_capabilities(self):
        from quantrade.institutional.e2a_runner import TREATMENTS
        from quantrade.institutional.e2a_suite import E2A_CASES
        for case in E2A_CASES:
            for treatment in sorted(TREATMENTS):
                self.counter += 1
                result = run_e2a_trial(self.kernel, eval_task_id=case['eval_task_id'],
                    treatment=treatment, provider=ScriptedModelProvider([
                        ModelAction('FINISH', {'summary': json.dumps(dict(issues=[], no_other_material_issues=True))})
                    ]), seed_label=str(self.counter))
                row = self.kernel.conn.execute('SELECT input_context_json FROM model_calls WHERE work_order_id=?',
                    (result.work_order_id,)).fetchone()
                context = json.loads(row['input_context_json'])
                for hidden_key in ('material_issue_types', 'forbidden_false_positive_types', 'decoy_refs',
                                   'falsification_conditions', 'factor_exposures_pct'):
                    self.assertNotIn(hidden_key, row['input_context_json'])
                self.assertNotIn(case['title'], row['input_context_json'])
                self.assertNotIn(case['memory']['ref'], row['input_context_json'])
                self.assertNotIn(case['diagnostics']['ref'], row['input_context_json'])
                names = {t['name'] for t in context['available_tools']}
                expected = set() if treatment == 'E2A_SNAPSHOT_ONLY' else {'e2.portfolio_diagnostics'}
                if treatment == 'E2A_PLUS_DIAGNOSTICS_MEMORY':
                    expected.add('e2.investment_memory')
                self.assertEqual(expected, names)
