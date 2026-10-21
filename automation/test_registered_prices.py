import unittest
from cost_research import registry
class RegistryCoverageTests(unittest.TestCase):
    def test_secondary_and_university_sources_exist_but_not_assumed_complete(self):
        stages={}
        for source in registry()['sources']:
            stages.setdefault(source['stage'],[]).append(source)
            self.assertTrue(source['url'].startswith('https://'))
            self.assertEqual(source['host'],source['url'].split('/')[2])
        self.assertGreaterEqual(len(stages.get('junior_high',[])),3)
        self.assertGreaterEqual(len(stages.get('high_school',[])),2)
        self.assertGreaterEqual(len(stages.get('university',[])),2)
if __name__=='__main__':unittest.main()
