import unittest
from education_cost_audit import report, checklist


class TestCoverageAudit(unittest.TestCase):
    def test_every_required_stage_exists(self):
        stages=set(checklist()['stages'])
        for stage in ('nursery','kindergarten','elementary','junior_high','high_school','university',
                      'cram_elementary','cram_junior_high','cram_high_school','prep_school',
                      'private_tutor','lessons','exam','housing'):
            self.assertIn(stage,stages)

    def test_unknown_never_automatically_zero(self):
        data=report([],[],selected=['high_school'])
        line=data['education_fee_stages'][0]
        self.assertEqual(line['state'],'requires_source_registration')
        self.assertIsNone(line['source_only_subtotal_yen'])
        self.assertTrue(line['unconfirmed_fee_types'])

    def test_school_differences_not_summed(self):
        data=report([{'stage':'university','amount_yen':1200000,'cost_type':'tuition'},
                     {'stage':'university','amount_yen':900000,'cost_type':'tuition'}],
                    [{'stage':'university','id':'a'}, {'stage':'university','id':'b'}],selected=['university'])
        self.assertIsNone(data['education_fee_stages'][0]['source_only_subtotal_yen'])
        self.assertEqual(data['education_fee_stages'][0]['registered_official_sources'],2)

    def test_unsupported_stage_rejected(self):
        with self.assertRaises(ValueError): report([],[],selected=['random'])

if __name__ == '__main__': unittest.main()
