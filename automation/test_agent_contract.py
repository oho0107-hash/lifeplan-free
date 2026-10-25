"""Validate the persistent agent/requirement contract without any API calls."""
import json
from pathlib import Path
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AgentContractTests(unittest.TestCase):
    def test_all_23_roles_are_registered_and_have_complete_instructions(self):
        config = tomllib.loads((ROOT / '.codex/config.toml').read_text())
        roles = json.loads((ROOT / 'docs/agent-roles.json').read_text())['roles']
        expected = {f'{group}{i:02}' for group, count in [('A', 9), ('B', 9), ('C', 5)] for i in range(1, count + 1)}
        self.assertEqual({role['id'] for role in roles}, expected)
        self.assertEqual(len(roles), len(expected))
        registered = {name: entry for name, entry in config['agents'].items() if isinstance(entry, dict)}
        self.assertEqual(len(registered), 23)
        for role in roles:
            key = role['id'].lower() + '_' + role['role']
            self.assertIn(key, registered)
            path = ROOT / '.codex' / registered[key]['config_file']
            self.assertEqual(path.resolve().parent, (ROOT / '.codex/agents').resolve())
            layer = tomllib.loads(path.read_text())
            self.assertNotIn('model', layer, 'inherit existing model; do not introduce a paid provider')
            for field, label in [('responsibility', '責任'), ('knowledge', '必要知識'), ('deliverable', '成果物'), ('verification', '検証基準'), ('dependencies', '依存・協働')]:
                self.assertTrue(role[field])
                self.assertIn(label, layer['developer_instructions'])
            if role['id'] not in ('A04', 'A09'):
                self.assertEqual(layer['sandbox_mode'], 'read-only', 'reviewers must not edit the candidate')
        self.assertLessEqual(config['agents']['max_concurrent_threads_per_session'], 6)

    def test_requirements_have_traceability_and_do_not_claim_unrun_acceptance_passed(self):
        requirements = json.loads((ROOT / 'docs/requirements.json').read_text())['requirements']
        ids = {r['id'] for r in requirements}
        self.assertEqual(len(ids), len(requirements))
        fields = {'id', 'name', 'purpose', 'inputs', 'outputs', 'rules', 'conditions', 'exceptions', 'sources', 'target_year', 'unknowns', 'related_requirements', 'acceptance_tests', 'counter_review', 'final_verdict'}
        all_tests = []
        for requirement in requirements:
            self.assertTrue(fields <= requirement.keys())
            self.assertTrue(set(requirement['related_requirements']) <= ids)
            self.assertTrue(requirement['acceptance_tests'])
            for case in requirement['acceptance_tests']:
                self.assertTrue({'id', 'input', 'expected', 'method', 'status'} <= case.keys())
                self.assertEqual(case['status'], 'unrun', 'catalogue is not current run evidence')
                all_tests.append(case['id'])
        self.assertEqual(len(all_tests), len(set(all_tests)))

    def test_unverified_rule_sources_cannot_be_mistaken_for_verified_policy(self):
        rules = json.loads((ROOT / 'docs/rule-ledger.json').read_text())['rules']
        self.assertGreaterEqual(len(rules), 10)
        self.assertEqual(len(rules), len({r['id'] for r in rules}))
        for rule in rules:
            self.assertTrue(rule['unknowns'])
            self.assertIn('blocked', rule['publication'])
            for source in rule['sources']:
                self.assertTrue({'url', 'title', 'checked_on', 'target_year', 'status'} <= source.keys())
                if source['checked_on'] is None:
                    self.assertIn('unverified', source['status'])


if __name__ == '__main__':
    unittest.main()
