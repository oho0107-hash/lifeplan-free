import unittest
from assurance_budget import calculate,BudgetError

BASE={'provider_id':'uni_demo','stage':'university','entry_year':2039,'years':4,
      'annual_growth_pct':2,'stress_growth_pct':5,'contingency_pct':10,
      'coverage_required':['admission','tuition','lab','transport'],'supplemental':[]}
ROWS=[{'provider_id':'uni_demo','stage':'university','year':2026,'cost_id':'tuition','cost_name':'授業料',
       'cost_type':'tuition','amount_yen':1400000,'period':'annual','grade_numbers':[1,2,3,4],
       'evidence_status':'verified','source_url':'https://example.ac.jp/fees','quote':'授業料 140万円', 'required':True},
      {'provider_id':'uni_demo','stage':'university','year':2026,'cost_id':'entry','cost_name':'入学金',
       'cost_type':'admission','amount_yen':300000,'period':'once','grade_numbers':[1],
       'evidence_status':'verified','source_url':'https://example.ac.jp/fees','quote':'入学金 30万円', 'required':True}]

class ReserveTests(unittest.TestCase):
    def test_partial_record_never_claims_sufficient(self):
        r=calculate(BASE,ROWS)
        self.assertEqual(r['readiness'],'incomplete')
        self.assertEqual(r['missing_categories'],['lab','transport'])
        self.assertFalse(r['safe_to_claim_guarantee'])
    def test_sourced_supplement_covers_categories_with_assumptions_visible(self):
        p={**BASE,'supplemental':[{'category':x,'amount_yen':60000,'grade_numbers':[1,2,3,4],
                                   'evidence_description':'比較可能な指定販売店の実額確認','period':'annual'} for x in ['lab','transport']]}
        r=calculate(p,ROWS)
        self.assertEqual(r['readiness'],'scenario_covered_not_guaranteed')
        self.assertGreater(r['reserve_total_yen'],r['baseline_total_yen'])
        self.assertGreater(r['reserve_total_yen'],r['stress_total_yen'])
        self.assertEqual([x['fee'] for x in r['years'][0]['lines']].count('入学金'),1)
        self.assertFalse(any(x['fee']=='入学金' for x in r['years'][1]['lines']))
    def test_unknown_cannot_be_zero_without_not_applicable(self):
        p={**BASE,'supplemental':[{'category':'lab','amount_yen':0,'grade_numbers':[1],
                                    'evidence_description':'不明'}]}
        with self.assertRaises(BudgetError):calculate(p,ROWS)
    def test_ignores_other_school(self):
        fake={**ROWS[0],'provider_id':'other','cost_id':'other-price','amount_yen':99000000}
        self.assertEqual(calculate(BASE,ROWS+[fake])['baseline_total_yen'],calculate(BASE,ROWS)['baseline_total_yen'])
    def test_never_add_bundled_totals_twice(self):
        dup={**ROWS[0],'cost_id':'official-summary','amount_yen':2500000,'included_in':'tuition'}
        self.assertEqual(calculate(BASE,ROWS+[dup])['baseline_total_yen'],calculate(BASE,ROWS)['baseline_total_yen'])
    def test_unsupported_grades_fail(self):
        with self.assertRaises(BudgetError):calculate(BASE,[{**ROWS[0],'grade_numbers':[5]},ROWS[1]])
    def test_stress_below_base_fails(self):
        with self.assertRaises(BudgetError):calculate({**BASE,'stress_growth_pct':1},ROWS)
    def test_does_not_accept_unsourced_verified_fee(self):
        with self.assertRaises(BudgetError):calculate(BASE,[{**ROWS[0],'source_url':'http://example.org'},ROWS[1]])
    def test_no_evidence_cannot_claim_ready(self):
        self.assertEqual(calculate(BASE,[])['readiness'],'incomplete')
    def test_benefits_not_silently_net_of_fees(self):
        self.assertNotIn('subsidies_deducted',calculate(BASE,ROWS))

if __name__=='__main__':unittest.main()
