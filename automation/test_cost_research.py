import unittest
from cost_research import strip_html, focused_text, selected_sources, verify_ai_records


class TestOfficialCostAgent(unittest.TestCase):
    def test_html_not_executable(self):
        t=strip_html('<script>SECRET</script><h2>授業料</h2><p>月額39,000円</p>')
        self.assertIn('39,000円',t)
        self.assertNotIn('SECRET',t)
    def test_only_education_issues(self):
        reg={'sources':[{'id':'a','school':'開成','aliases':['kaisei']}]}
        self.assertEqual(selected_sources('背景色を変えて',reg),[])
        self.assertEqual(len(selected_sources('開成の学費を調べて',reg)),1)
    def test_new_stages_named_preparatory_school(self):
        reg={'sources':[{'id':'prep','school':'河合塾大学受験科','stage':'prep_school',
                         'aliases':['河合塾'],'url':'https://example.org','host':'example.org'},
                        {'id':'jhs','school':'開成中学校','stage':'junior_high',
                         'aliases':['開成'],'url':'https://example.org','host':'example.org'}]}
        self.assertEqual([x['id'] for x in selected_sources('河合塾の予備校費用を調査',reg)], ['prep'])
        self.assertEqual([x['id'] for x in selected_sources('予備校の費用を調査',reg)], ['prep'])

    def test_price_must_have_exact_evidence(self):
        s={'id':'a','school':'甲中学校','stage':'junior_high','year':2026,
           'url':'https://sample.example/price','status':'ok','fetched_at':'2026-10-15',
           'text':'入学金 300,000円','full_text':'入学金 300,000円'}
        r={'source_id':'a','cost_name':'入学金','amount_yen':300000,'period':'once',
           'required':True,'quote':'入学金 300,000円'}
        ok,bad=verify_ai_records([r,{**r,'amount_yen':400000}], [s])
        self.assertEqual(len(ok),1)
        self.assertEqual(len(bad),1)
    def test_no_partial_number_match(self):
        s={'id':'a','school':'甲中学校','stage':'junior_high','year':2026,
           'url':'https://sample.example/price','status':'ok','fetched_at':'2026-10-15',
           'text':'入学金 300,000円','full_text':'入学金 300,000円'}
        r={'source_id':'a','cost_name':'入学金','amount_yen':300,'period':'once',
           'required':True,'quote':'入学金 300,000円'}
        self.assertEqual(len(verify_ai_records([r],[s])[0]),0)

    def test_disallows_invented_source(self):
        s={'id':'a','school':'甲中学校','stage':'junior_high','year':2026,
           'url':'https://sample.example/price','status':'ok','fetched_at':'2026-10-15',
           'text':'入学金 300,000円','full_text':'入学金 300,000円'}
        r={'source_id':'z','cost_name':'入学金','amount_yen':300000,'period':'once','required':True,'quote':'入学金 300,000円'}
        self.assertEqual(len(verify_ai_records([r],[s])[0]),0)

if __name__=='__main__':unittest.main()
