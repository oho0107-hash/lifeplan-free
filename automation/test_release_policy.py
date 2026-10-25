import unittest
from release_policy import classify
class ReleasePolicyTests(unittest.TestCase):
    def test_research_reports_auto_publishable(self):
        self.assertEqual(classify(['reviews/issue-5-run-123.md','costs/issue-5-run-123.json','costs/coverage-issue-5-run-123.json']),'evidence_only')
    def test_safe_reports_plus_code_not_auto(self):
        self.assertEqual(classify(['reviews/issue-5-run-123.md','automation/cost_research.py']),'human_required')
    def test_workflows_never_auto(self):
        self.assertEqual(classify(['.github/workflows/ai-dev.yml']),'human_required')
    def test_financial_data_never_auto(self):
        self.assertEqual(classify(['costs/official_sources.json']),'human_required')
    def test_run_evidence_and_orchestration_are_documentary(self):
        self.assertEqual(classify(['reviews/evidence-issue-5-run-123.json',
                                   'reviews/orchestration-issue-5-run-123.json']), 'evidence_only')
    def test_unrecognized_review_json_requires_human(self):
        self.assertEqual(classify(['reviews/policy.json']), 'human_required')
    def test_path_traversal_never_auto(self):
        self.assertEqual(classify(['reviews/../issue-5-run-123.md']), 'human_required')
    def test_empty_not_auto(self):
        self.assertEqual(classify([]),'human_required')
    def test_simple_css_only(self):
        self.assertEqual(classify(['index.html'],old_html='<style>a{color:red}</style>',new_html='<style>a{color:blue}</style>'),'cosmetic_only')
    def test_css_plus_documentary_report_can_be_auto(self):
        files=['index.html','reviews/issue-3-run-88.md','costs/issue-3-run-88.json']
        self.assertEqual(classify(files,old_html='<style>a{color:red}</style>',
                                  new_html='<style>a{color:blue}</style>'),'cosmetic_only')
    def test_script_with_css_not_auto(self):
        self.assertEqual(classify(['index.html'],old_html='<style>x{}</style>',new_html='<style>x{}</style><script>new()</script>'),'human_required')
if __name__=='__main__':unittest.main()
