"""Local safety checks. Run without internet, AI or GitHub secrets."""
import io
import json
import unittest
from unittest import mock
import urllib.error

from guard import apply_patches, apply_research_patches, is_auto_publish_safe, UnsafePatch, sync_engine

END="})(typeof window!=='undefined'?window:globalThis);"
HTML=f"<html><style>body{{color:red}}</style><script>/* LIFE Financial Studio\n(function(root){{}})({{}});\n{END}\n</script><p>TEST</p></html>"
ENGINE=f"/* LIFE Financial Studio\n(function(root){{}})({{}});\n{END}\n"

class TestGuard(unittest.TestCase):
    def setUp(self): self.old={'index.html':HTML,'engine.js':ENGINE}
    def test_auto_css_only(self):
        new=apply_patches(self.old,[{'file':'index.html','old':'color:red','new':'color:blue'}])
        self.assertTrue(is_auto_publish_safe(self.old,new))
    def test_css_external_network_is_manual(self):
        new=apply_patches(self.old,[{'file':'index.html','old':'color:red','new':'background:url(https://example.com)'}])
        self.assertFalse(is_auto_publish_safe(self.old,new))
    def test_financial_code_is_manual(self):
        new=apply_patches(self.old,[{'file':'engine.js','old':'(function(root){})','new':'(function(root){/* changed */})'}])
        self.assertFalse(is_auto_publish_safe(self.old,new))
        self.assertIn('/* changed */',new['index.html'])
    def test_no_workflow_edit(self):
        with self.assertRaises(UnsafePatch): apply_patches(self.old,[{'file':'.github/workflows/ai-dev.yml','old':'a','new':'b'}])
    def test_no_duplicate_search(self):
        with self.assertRaises(UnsafePatch): apply_patches(self.old,[{'file':'index.html','old':'<','new':'X'}])
    def test_no_engine_patch_in_html(self):
        with self.assertRaises(UnsafePatch): apply_patches(self.old,[{'file':'index.html','old':'(function(root){})','new':'evil'}])

class TestResearchPatchGuard(unittest.TestCase):
    def setUp(self):
        self.old={
            'automation/cost_research.py': 'def verify_price(value):\n    return int(value)\n',
            'automation/test_cost_research.py': 'def test_price():\n    assert verify_price("100") == 100\n',
            'index.html':HTML,'engine.js':ENGINE,
        }

    def test_allows_parser_and_test_together(self):
        edits=[
            {'file':'automation/cost_research.py','old':'return int(value)','new':'return int(value.replace(",", ""))'},
            {'file':'automation/test_cost_research.py','old':'verify_price("100")','new':'verify_price("1,000")'},
        ]
        result=apply_research_patches(self.old,edits)
        self.assertIn('value.replace',result['automation/cost_research.py'])
        self.assertEqual(result['index.html'],HTML)
        self.assertFalse(is_auto_publish_safe(self.old,result))

    def test_rejects_missing_regression_test(self):
        with self.assertRaises(UnsafePatch):
            apply_research_patches(self.old,[{'file':'automation/cost_research.py','old':'int(value)','new':'float(value)'}])

    def test_rejects_workflow_or_runner_edits(self):
        with self.assertRaises(UnsafePatch):
            apply_research_patches(self.old,[
                {'file':'automation/cost_research.py','old':'int(value)','new':'float(value)'},
                {'file':'.github/workflows/ai-dev.yml','old':'hi','new':'bye'},
            ])

    def test_rejects_unsafe_imports(self):
        with self.assertRaises(UnsafePatch):
            apply_research_patches(self.old,[
                {'file':'automation/cost_research.py','old':'def verify_price', 'new':'import subprocess\ndef verify_price'},
                {'file':'automation/test_cost_research.py','old':'def test_price', 'new':'def test_price_2'},
            ])

    def test_rejects_syntax_error(self):
        with self.assertRaises(UnsafePatch):
            apply_research_patches(self.old,[
                {'file':'automation/cost_research.py','old':'return int(value)','new':'return('},
                {'file':'automation/test_cost_research.py','old':'assert verify_price("100") == 100', 'new':'assert verify_price("100") == 101'},
            ])

class TestGeminiJSONRepair(unittest.TestCase):
    """No real network traffic, free API calls, or credentials are used."""

    def response(self, model_text):
        payload = {'candidates':[{'content':{'parts':[{'text': model_text}]}}]}
        return io.BytesIO(json.dumps(payload).encode('utf-8'))

    def test_invalid_regex_escape_is_repaired_without_changing_code(self):
        import agent_runner
        code = 'r"\\d+"'
        original = {'changes':[{'file':'automation/cost_research.py',
                                'old':'return 1','new':code}]}
        correct = json.dumps(original)
        broken = correct.replace('\\\\d', '\\d')
        with self.assertRaises(json.JSONDecodeError):
            json.loads(broken)
        with mock.patch.object(agent_runner, 'KEY', 'TEST_KEY_NOT_REAL'), \
             mock.patch.object(agent_runner, '_calls', 0), \
             mock.patch.object(agent_runner.urllib.request, 'urlopen', side_effect=[self.response(broken),self.response(correct)]) as call:
            result = agent_runner.ask('test', 'json', 'generate', limit=900)
            self.assertEqual(result, original)
            self.assertEqual(call.call_count, 2)
            self.assertEqual(agent_runner._calls, 2)

    def test_twice_invalid_repairs_stop_without_publishing(self):
        import agent_runner
        broken = r'{"changes":[{"old":"\d"}]}'
        with self.assertRaises(json.JSONDecodeError):
            json.loads(broken)
        with mock.patch.object(agent_runner, 'KEY', 'TEST_KEY_NOT_REAL'), \
             mock.patch.object(agent_runner, '_calls', 0), \
             mock.patch.object(agent_runner.urllib.request, 'urlopen',side_effect=lambda *args, **kwargs: self.response(broken)) as call:
            with self.assertRaisesRegex(RuntimeError,'after 2 syntax-repair attempts'):
                agent_runner.ask('test', 'json', 'generate', limit=1000)
            self.assertEqual(call.call_count, 3)

    def test_quota_error_during_repair_stops_immediately(self):
        import agent_runner
        broken = r'{"changes":[{"old":"\d"}]}'
        quota = urllib.error.HTTPError('https://example.invalid', 429, 'quota', {}, io.BytesIO(b'quota reached'))
        with mock.patch.object(agent_runner, 'KEY', 'TEST_KEY_NOT_REAL'), \
             mock.patch.object(agent_runner, '_calls', 0), \
             mock.patch.object(agent_runner.urllib.request, 'urlopen',side_effect=[self.response(broken),quota]) as call:
            with self.assertRaisesRegex(RuntimeError,'HTTP 429'):
                agent_runner.ask('test','json','generate',limit=1000)
            self.assertEqual(call.call_count, 2)

    def test_valid_payload_still_one_call(self):
        import agent_runner
        valid = json.dumps({'summary':'OK', 'changes':[]})
        with mock.patch.object(agent_runner,'KEY','TEST_KEY_NOT_REAL'), \
             mock.patch.object(agent_runner, '_calls', 0), \
             mock.patch.object(agent_runner.urllib.request,'urlopen',return_value=self.response(valid)) as call:
            self.assertEqual(agent_runner.ask('test','json','generate'), {'summary':'OK', 'changes':[]})
            self.assertEqual(call.call_count, 1)

if __name__=='__main__':unittest.main()
