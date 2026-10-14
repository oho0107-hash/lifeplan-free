import unittest
from education_cost_budget import preview,quote_key,NeedsApproval


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.a={'source_id':'a','stage':'junior_high','school':'架空校','year':2026,
                'source_url':'https://example.edu.jp/tuition','cost_name':'入学金','cost_type':'admission',
                'amount_yen':300000,'period':'once','required':True,'quote':'入学金 300,000 円'}
        self.b={**self.a,'cost_name':'授業料','cost_type':'tuition','amount_yen':50000,
                'period':'monthly','quote':'授業料 50,000 円'}
        self.sel={'approved_by_user':True,'double_count_reviewed':True,'source_id':'a','school':'架空校',
                  'stage':'junior_high','observed_fee_year':2026,'forecast_year':2026,
                  'approved_inflation_rate_pct':0,'fee_charges':[{'quote_key':quote_key(self.a),'is_first_year':True},
                                                                   {'quote_key':quote_key(self.b),'months':12}]}

    def test_only_explicit_rows_are_summed(self):
        result=preview([self.a,self.b],self.sel)
        self.assertEqual(result['documented_subtotal_observed_yen'],900000)
        self.assertFalse(result['is_full_education_cost'])

    def test_quote_must_be_selected(self):
        with self.assertRaises(NeedsApproval):preview([self.a],self.sel)

    def test_must_approve_selection(self):
        with self.assertRaises(NeedsApproval):preview([self.a,self.b],{**self.sel,'approved_by_user':False})

    def test_inflation_no_silent_addition(self):
        with self.assertRaises(NeedsApproval):preview([self.a,self.b],{**self.sel,'forecast_year':2036,
                                                                    'approved_inflation_rate_pct':3})

    def test_future_projection_only_if_authorized(self):
        r=preview([self.a,self.b],{**self.sel,'forecast_year':2027,'approved_inflation_rate_pct':2,
                                   'inflation_assumption_approved':True})
        self.assertEqual(r['documented_subtotal_forecast_yen'],918000)

    def test_must_review_double_count(self):
        with self.assertRaises(NeedsApproval):preview([self.a,self.b],{**self.sel,'double_count_reviewed':False})

    def test_not_add_optional_without_approval(self):
        c={**self.a,'required':False}
        with self.assertRaises(NeedsApproval):preview([c],{**self.sel,'fee_charges':[{'quote_key':quote_key(c),'is_first_year':True}]})

if __name__ == '__main__':unittest.main()
