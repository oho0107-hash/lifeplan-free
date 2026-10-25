"""Offline orchestration contracts; no API or network request is made."""
import copy
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import agent_runner
from orchestration import requirements_contract, candidate_manifest, digest, unittest_outcomes

ROOT = Path(__file__).resolve().parents[1]


def requirement(financial=False):
    return {'summary': 'synthetic offline request', 'unknowns': [],
            'financial_rule_change': financial,
            'requirements': [{'name': 'synthetic requirement', 'purpose': 'exercise proposed change',
                'inputs': ['fabricated'], 'outputs': ['candidate'], 'rules': 'fixture only, never publish',
                'conditions': [], 'exceptions': [], 'sources': ['unverified synthetic fixture'],
                'target_year': None, 'unknowns': ['not a real policy change'], 'related_requirements': [],
                'acceptance_tests': [{'input': 'synthetic input', 'expected': 'candidate regression passes',
                                      'method': 'run Node regression in isolated temporary checkout'}]}]}


class ContractTests(unittest.TestCase):
    def test_requirements_and_acceptance_ids_are_assigned_locally(self):
        rows = requirements_contract(requirement())
        self.assertEqual(rows[0]['id'], 'REQ-001')
        self.assertEqual(rows[0]['acceptance_tests'][0]['id'], 'AT-001-01')
        self.assertEqual(rows[0]['final_verdict'], 'unverified')

    def test_missing_expected_value_is_rejected(self):
        payload = requirement()
        del payload['requirements'][0]['acceptance_tests'][0]['expected']
        with self.assertRaises(ValueError):
            requirements_contract(payload)

    def test_prose_or_empty_requirements_are_rejected(self):
        for rows in ([], ['looks good']):
            with self.assertRaises(ValueError):
                requirements_contract({'requirements': rows})

    def test_ai_unanimity_does_not_authorize_publication(self):
        manifest = candidate_manifest('fixture', requirements_contract(requirement()),
                                      {'engine.js': 'code'}, {'all': {'approved': True}}, [])
        self.assertFalse(manifest['publication_authorized'])
        self.assertFalse(manifest['auto_merge_eligible'])
        self.assertEqual(manifest['pr_mode'], 'draft')
        self.assertEqual(manifest['candidate_sha256']['engine.js'], digest('code'))

    def test_model_fallback_cannot_silently_spend_other_model_quota(self):
        self.assertIsNone(agent_runner.FALLBACK_MODEL)

    def test_skips_and_expected_failures_are_not_counted_as_passes(self):
        result = unittest_outcomes('Ran 4 tests in 0.001s\nOK (skipped=2, expected failures=1)')
        self.assertEqual(result['tests'], 4)
        self.assertEqual(result['skipped'], 2)
        self.assertEqual(result['expected_failures'], 1)
        self.assertEqual(result['failures'], 0)

    def test_issue_model_request_uses_persistent_codex_role_instructions(self):
        response = {'candidates': [{'content': {'parts': [{'text': '{"ok": true}'}]}}]}
        with patch.multiple(agent_runner, REPO=ROOT, KEY='synthetic-offline-fixture', _calls=0, _started=None), \
             patch.object(agent_runner.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(response).encode())) as http:
            self.assertEqual(agent_runner.ask('A02 要件検討エージェント', 'JSON only', 'synthetic request'), {'ok': True})
            payload = json.loads(http.call_args.args[0].data)
        text = payload['systemInstruction']['parts'][0]['text']
        self.assertIn('A02 要件定義', text)
        self.assertIn('一意の要件ID', text)
        self.assertIn('JSON-only model perspective', text)
        for prefix in agent_runner.MODEL_ROLES:
            self.assertTrue(agent_runner.persistent_role_context(prefix, ROOT).strip())


class OfflineEndToEndTests(unittest.TestCase):
    """Natural language -> mocked model -> guarded patch -> real regression.

    Provider responses are FIXTURES; this proves local wiring, not Gemini,
    GitHub permissions, live Issue delivery, PR creation or deployment.
    """
    def execute_candidate(self, financial):
        with tempfile.TemporaryDirectory(prefix='lifeplan-e2e-') as directory:
            root = Path(directory)
            output = root / 'candidate'
            request_file = root / 'request.txt'
            request_file.write_text('児童手当の仮想ルールを変更して検証してください' if financial
                                    else '画面の背景色だけを小さく変更してください', encoding='utf-8')
            if financial:
                changes = [{'file': 'engine.js', 'old': 'if(elder>=2)return 30000;',
                            'new': 'if(elder>=2)return 31000;'}]
            else:
                changes = [{'file': 'index.html', 'old': '--bg:#f2f5f5;', 'new': '--bg:#f2f6f5;'}]
            calls = []
            def fixture_ask(role, *args, **kwargs):
                calls.append(role)
                if '要件検討' in role:
                    return copy.deepcopy(requirement(financial))
                if role == '開発エージェント':
                    return {'changes': changes, 'explanation': 'offline fixture only', 'new_tests': []}
                if role == '独立品質ゲートエージェント':
                    return {'approved': True, 'issues': [], 'missing_tests': ['policy verification'],
                            'reasoning': 'model opinion is not evidence'}
                return {'findings': [], 'verdict': 'unverified'}
            with patch.multiple(agent_runner, REPO=ROOT, OUT=output, ISSUE_FILE=request_file), \
                 patch.object(agent_runner, 'ask', side_effect=fixture_ask), \
                 patch.object(agent_runner, 'collect', return_value=[]), \
                 patch.object(agent_runner, 'registry', return_value={'sources': []}):
                agent_runner.main()
            self.assertIn('C01 懐疑的レビュー', calls)
            manifest = json.loads((output / 'ORCHESTRATION.json').read_text())
            self.assertFalse(manifest['publication_authorized'])
            self.assertEqual(manifest['pr_mode'], 'draft')
            self.assertEqual(manifest['financial_rule_change'], financial)
            self.assertEqual(manifest['attempts'][0]['status'], 'model_review_accepted_tests_pending')
            self.assertEqual(manifest['objective_tests'], 'pending_isolated_verifier')
            # Execute actual generated HTML/engine with the repository's real
            # Node regression suite; do not replace it with a mock pass.
            (root / 'automation').mkdir()
            shutil.copy(ROOT / 'automation/test_smoke.cjs', root / 'automation/test_smoke.cjs')
            for name in ('index.html', 'engine.js'):
                shutil.copy(output / name, root / name)
            shutil.copy(ROOT / 'education-reserve.html', root / 'education-reserve.html')
            run = subprocess.run(['node', '--test', '--test-reporter=tap', 'automation/test_smoke.cjs'],
                                 cwd=root, capture_output=True, text=True, timeout=60)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('# tests 5', run.stdout)
            self.assertEqual((output / 'release.env').read_text().strip(),
                             'AUTO_CSS_ONLY=' + ('false' if financial else 'true'))
            if financial:
                self.assertTrue(manifest['human_approval_required'])
                self.assertEqual(manifest['independent_recalculation'], 'pending_for_affected_financial_rules')
            return len(calls)

    def test_cosmetic_request_produces_guarded_candidate_and_real_regression(self):
        self.assertGreater(self.execute_candidate(False), 3)

    def test_financial_request_stays_awaiting_evidence_and_human_approval(self):
        self.assertGreater(self.execute_candidate(True), 3)


if __name__ == '__main__':
    unittest.main()
