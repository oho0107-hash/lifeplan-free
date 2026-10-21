import unittest
from source_change_report import compare
class SourceWatchTests(unittest.TestCase):
    def test_initial_does_not_claim_change(self):
        new={'rows':[{'id':'school','url':'https://a.jp','status':'fetched','fee_excerpt_sha256':'x'}]}
        self.assertEqual(compare(None,new)['source_change_count'],0)
    def test_change_of_fee_excerpt_alerts_without_claiming_price_rise(self):
        a={'rows':[{'id':'school','url':'https://a.jp','status':'fetched','fee_excerpt_sha256':'x'}]}
        b={'rows':[{'id':'school','url':'https://a.jp','status':'fetched','fee_excerpt_sha256':'y'}]}
        self.assertEqual(compare(a,b)['changes'][0]['type'],'excerpt_changed')
    def test_freshness_unavailable_alert(self):
        a={'rows':[{'id':'school','url':'https://a.jp','status':'fetched','fee_excerpt_sha256':'x'}]}
        b={'rows':[{'id':'school','url':'https://a.jp','status':'needs_review','reason':'blocked'}]}
        self.assertEqual(compare(a,b)['changes'][0]['type'],'page_unavailable')
if __name__=='__main__':unittest.main()
