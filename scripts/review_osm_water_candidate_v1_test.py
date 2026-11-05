"""Regression: missing routes cannot improve a reported fixed-set mean."""
import copy
import unittest
from review_osm_water_candidate_v1 import review


def fixture():
    return {'rows':[{'id':str(i),'set':'synthetic','referenceMinutes':10,'candidate':{'pointMinutes':12 if i<80 else None,'classification':'correct'}} for i in range(83)]}


class ReviewTests(unittest.TestCase):
    def test_recoveries_and_fixed_denominators(self):
        old=fixture();new=copy.deepcopy(old)
        for row in new['rows'][80:]:row['candidate']['pointMinutes']=10
        result=review(old,new)
        self.assertEqual(result['previousFinite'],80);self.assertEqual(result['currentFinite'],83)
        self.assertEqual(result['samePreviousFiniteSet']['current']['meanAbsoluteMinutes'],2)
        self.assertAlmostEqual(result['all83']['current']['meanAbsoluteMinutes'],160/83)
        self.assertIsNone(result['all83']['previous']['meanAbsoluteMinutes'])
        self.assertEqual(result['recoveredIds'],['80','81','82'])

    def test_lost_route_is_not_hidden_by_one_recovery(self):
        old=fixture();new=copy.deepcopy(old)
        new['rows'][0]['candidate']['pointMinutes']=None;new['rows'][80]['candidate']['pointMinutes']=10
        result=review(old,new)
        self.assertEqual(result['previousFinite'],result['currentFinite'])
        self.assertEqual(result['newlyUnavailableIds'],['0']);self.assertEqual(result['recoveredIds'],['80'])
        self.assertIsNone(result['samePreviousFiniteSet']['current']['meanAbsoluteMinutes'])
        self.assertEqual(result['bothFiniteDiagnosticOnly']['current']['requestedCases'],79)
        new['rows'][1]['referenceMinutes']=11
        with self.assertRaises(AssertionError):review(old,new)


if __name__=='__main__':unittest.main()
