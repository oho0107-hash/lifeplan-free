import unittest
from cost_research import (
    strip_html, focused_text, selected_sources, verify_ai_records,
    extract_table_fees, fee_completeness, annual_cost_preview,
)

KA = '''<h1>学費</h1><p>2026年度の学費</p><h2>中学校</h2>
<table><tr><td>(1) 入学金<br>(2) 施設拡充資金</td><td>320,000 円<br>120,000 円</td><td>入学手続時に納入</td></tr>
<tr><td>(3) 授業料 (月額)<br>(4) 施設維持費 (月額)<br>(5) 実験実習料 (月額)</td>
<td>44,000 円<br>8,000 円<br>8,000 円</td><td>月額</td></tr></table>
<p>学級費（学年旅行費・教材費等、第1学年160,000円）</p>
<h2>高等学校</h2><table><tr><td>授業料 (月額)</td><td>44,000円</td></tr><tr><td>指定端末</td><td>30,000円</td></tr></table>'''
SH = '''<h1>学費</h1><h2>渋谷教育学園幕張中学校納入金</h2>
<h3>入学納入金</h3><p>入学手続時に納入</p>
<table><tr><td>入学金</td><td>300,000円</td></tr></table>
<h3>施設拡充費</h3><p>入学後に納入して頂きます。</p>
<table><tr><td>施設拡充費</td><td>150,000円</td></tr></table>
<h3>毎月の納入金</h3><table><tr><td>授業料</td><td>39,000円</td></tr>
<tr><td>施設費</td><td>17,000円</td></tr>
<tr><td>維持費</td><td>2,500円</td></tr>
<tr><td>計</td><td>62,500円</td></tr></table>
<h2>渋谷教育学園幕張高等学校納入金</h2><h3>入学納入金</h3>
<table><tr><td>入学金</td><td>200,000円</td></tr></table>'''
IC = '''<h1>中学 授業料等納付金</h1><h4>2026年度 中学校納付金</h4>
<h4>入学手続時納付金</h4><table><tr><td>入学金</td><td>330,000円</td></tr></table>
<h4>授業料等納付金（2026年度の月額）</h4>
<table><tr><td>授業料</td><td>39,000円</td></tr>
<tr><td>施設整備・運営費</td><td>16,000円</td></tr>
<tr><td>生徒会費</td><td>800円</td></tr>
<tr><td>合計</td><td>57,800円〔年額693,600円〕</td></tr></table>'''


def snap(html, sid, stage='junior_high'):
    rows=extract_table_fees(html,stage)
    # Same structural evidence serialization as the real fetcher.
    lines=['[HTML料金表] '+r['section']+' | '+r['quote']+' | '+r['period'] for r in rows]
    return {'id':sid,'school':'テスト校','stage':stage,'year':2026,
            'url':'https://school.example/official','fetched_at':'2026-10-17',
            'status':'ok','evidence_rows':rows,'full_text':'\n'.join(lines)+'\n'+strip_html(html)}


def from_candidate(candidate, sid):
    return dict(source_id=sid,cost_name=candidate['cost_name'],cost_type=candidate['cost_type'],
                quote=candidate['quote'],amount_yen=candidate['amount_yen'],
                period=candidate['period'],required=candidate['required'],
                course_or_grade='中学全学年')


class TableEvidenceTest(unittest.TestCase):
    def test_university_faculty_prices_are_not_mixed(self):
        html=('<h1>大学 学納金</h1><h2>法学部</h2>'
              '<table><tr><td>授業料 (年額)</td><td>900,000円</td></tr></table>'
              '<h2>理工学部</h2>'
              '<table><tr><td>授業料 (年額)</td><td>1,450,000円</td></tr></table>')
        result=extract_table_fees(html,'university','明治大学 理工学部')
        self.assertEqual([r['amount_yen'] for r in result],[1450000])
        self.assertEqual(extract_table_fees(html,'university','明治大学 商学部'),[])

    def test_kaisei_multiline_and_middle_school_only(self):
        rows=extract_table_fees(KA,'junior_high')
        found={(r['cost_name'],r['amount_yen'],r['period']) for r in rows}
        self.assertIn(('入学金',320000,'once'),found)
        self.assertIn(('施設拡充資金',120000,'once'),found)
        self.assertIn(('授業料 (月額)',44000,'monthly'),found)
        self.assertIn(('施設維持費 (月額)',8000,'monthly'),found)
        self.assertFalse(any('指定端末' in r['cost_name'] for r in rows))

    def test_shibumaku_sections_and_skip_totals(self):
        rows=extract_table_fees(SH,'junior_high')
        amounts={(r['cost_name'],r['amount_yen'],r['period']) for r in rows}
        for key in [('入学金',300000,'once'),('施設拡充費',150000,'once'),
                    ('授業料',39000,'monthly'),('施設費',17000,'monthly')]:
            self.assertIn(key,amounts)
        self.assertNotIn(('入学金',200000,'once'),amounts)
        self.assertFalse(any(r['amount_yen']==62500 for r in rows))

    def test_ichikawa_annual_total_excluded(self):
        rows=extract_table_fees(IC,'junior_high')
        amounts={r['cost_name']:r['amount_yen'] for r in rows}
        self.assertEqual(amounts['入学金'],330000)
        self.assertEqual(amounts['授業料'],39000)
        self.assertEqual(amounts['施設整備・運営費'],16000)
        self.assertNotIn('合計',amounts)

    def test_verify_exacts_and_rejects_other_amount(self):
        s=snap(SH,'sh')
        record=from_candidate(next(r for r in s['evidence_rows'] if r['cost_name']=='授業料'),'sh')
        good,bad=verify_ai_records([record,{**record,'amount_yen':17000},
                                     {**record,'cost_name':'施設費'}],[s])
        self.assertEqual(len(good),1)
        self.assertEqual(len(bad),2)

    def test_missing_mandatory_fees_disallows_completeness(self):
        s=snap(KA,'kaisei')
        records=[from_candidate(next(r for r in s['evidence_rows'] if r['cost_name']=='入学金'),'kaisei')]
        ok,_=verify_ai_records(records,[s])
        audit=fee_completeness(ok,[s],required_labels={'kaisei':['入学金','施設拡充資金','授業料 (月額)']})
        self.assertEqual(audit['kaisei']['status'],'incomplete')
        self.assertIn('施設拡充資金',audit['kaisei']['missing_required'])
        self.assertEqual(fee_completeness(ok,[s])['kaisei']['status'],'incomplete')

    def test_preview_never_calls_partial_figure_full_budget(self):
        s=snap(SH,'sh');records=[from_candidate(r,'sh') for r in s['evidence_rows']]
        verified,_=verify_ai_records(records,[s])
        preview=annual_cost_preview(verified,source_id='sh',required_labels=['入学金','授業料'],year_count=3)
        self.assertEqual(preview['years'][0]['confirmed_subtotal_yen'],300000+39000*12)
        self.assertEqual(preview['years'][1]['confirmed_subtotal_yen'],39000*12)
        self.assertIsNone(preview['years'][0]['full_total_yen'])
        self.assertIsNone(preview['full_course_total_yen'])

    def test_old_text_verification_compatible(self):
        s={'id':'old','school':'甲中','stage':'junior_high','year':2026,
           'url':'https://example.org','fetched_at':'2026','status':'ok',
           'full_text':'入学金 300,000円','evidence_rows':[]}
        r={'source_id':'old','cost_name':'入学金','amount_yen':300000,'period':'once','required':True,'quote':'入学金 300,000円'}
        self.assertEqual(len(verify_ai_records([r],[s])[0]),1)

    def test_not_execute_script(self):
        self.assertNotIn('SECRET',strip_html('<script>SECRET</script><table><tr><td>授業料</td><td>50,000円</td></tr></table>'))



class ProseFeeTest(unittest.TestCase):
    def test_kaisei_class_fee_and_second_year_contribution(self):
        html='''<h2>中学校</h2><p>※上記以外に、学級費（学年旅行費・教材費等、2026年度第1学年は160,000円）をお預かりします。</p>
        <p>※第2学年から毎年、施設拡充資金を年額70,000円申し受けます。</p>'''
        rows=extract_table_fees(html,'junior_high')
        self.assertTrue(any(r['cost_name']=='学級費' and r['amount_yen']==160000 and r['period']=='annual' for r in rows))
        self.assertTrue(any(r['cost_name']=='施設拡充資金' and r['amount_yen']==70000 and r['period']=='annual' for r in rows))

    def test_preserve_duplicate_admission_in_school_tables(self):
        rows=extract_table_fees(SH,'high_school')
        self.assertIn(200000,[r['amount_yen'] for r in rows if r['cost_name']=='入学金'])
        self.assertNotIn(300000,[r['amount_yen'] for r in rows if r['cost_name']=='入学金'])


class LegacyCompatibilityTests(unittest.TestCase):
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


class FetchIntegrationTest(unittest.TestCase):
    def test_approved_html_fetch_adds_fee_lines_and_maintains_year(self):
        from cost_research import fetch_source
        from email.message import Message
        class FakeResponse:
            def __init__(self):
                self.headers=Message();self.headers['Content-Type']='text/html; charset=utf-8'
            def geturl(self):return 'https://school.example/official'
            def read(self,n):return KA.encode('utf-8')[:n]
            def __enter__(self):return self
            def __exit__(self,*args):return None
        def opener(request,timeout):return FakeResponse()
        src={'id':'kaisei','school':'開成中学校','stage':'junior_high',
             'year':2026,'url':'https://school.example/official','host':'school.example'}
        data=fetch_source(src,opener=opener)
        self.assertEqual(data['year'],2026)
        self.assertIn('[HTML料金表]',data['text'])
        self.assertIn('入学金 320,000 円',data['full_text'])
        self.assertTrue(any(e['cost_name']=='入学金' for e in data['evidence_rows']))

    def test_unsupported_host_fails_before_network(self):
        from cost_research import fetch_source
        src={'id':'evil','school':'X','stage':'junior_high',
             'year':2026,'url':'http://127.0.0.1/','host':'example.com'}
        with self.assertRaises(ValueError):fetch_source(src,opener=lambda *a,**kw:None)


class DuplicateFeeNameTest(unittest.TestCase):
    def test_repeated_same_name_does_not_silently_override_payment(self):
        rows=[{'source_id':'ka','cost_name':'施設拡充資金','amount_yen':120000,
               'period':'once','required':True,'course_or_grade':'中学1年'},
              {'source_id':'ka','cost_name':'施設拡充資金','amount_yen':70000,
               'period':'annual','required':True,'grade_scope':'from_second_year'}]
        out=annual_cost_preview(rows,source_id='ka',required_labels=['施設拡充資金'])
        self.assertIsNone(out['years'][0]['full_total_yen'])
        self.assertEqual(out['years'][0]['confirmed_subtotal_yen'],0)
        self.assertTrue(out['years'][0]['unresolved'])

class ScopedAgentBudgetTest(unittest.TestCase):
    def test_parser_fix_keeps_relevant_independent_reviewers(self):
        from agent_runner import review_plan
        names = [name for name, _ in review_plan(True)]
        self.assertEqual(names, ['教育制度', 'プライバシー', 'QA'])
        self.assertEqual(len(review_plan(False)), 6)

    def test_parser_fix_reviews_parser_not_unchanged_household_engine(self):
        from agent_runner import review_code_context
        base = {'engine.js': 'unrelated_sensitive_engine',
                'automation/cost_research.py': 'parser_code',
                'automation/test_cost_research.py': 'parser_tests'}
        ctx = review_code_context(True, base)
        self.assertIn('parser_code', ctx)
        self.assertIn('parser_tests', ctx)
        self.assertNotIn('unrelated_sensitive_engine', ctx)
        self.assertIn('unrelated_sensitive_engine', review_code_context(False, base))

    def test_call_limit_still_stops_before_request_and_preserves_secret(self):
        import agent_runner
        from unittest.mock import patch
        with patch.object(agent_runner, 'KEY', 'test-secret'), patch.object(agent_runner, '_calls', agent_runner.MAX_CALLS):
            with self.assertRaisesRegex(RuntimeError, 'safety limit reached') as raised:
                agent_runner.ask('テスト担当', 'test', 'payload')
        self.assertNotIn('test-secret', str(raised.exception))


if __name__ == '__main__':
    unittest.main()
