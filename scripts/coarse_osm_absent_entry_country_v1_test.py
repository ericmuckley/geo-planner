from pathlib import Path
import struct
import tempfile
import unittest

from coarse_osm_absent_entry_country_v1 import resolve


class TypedAbsentEntryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.baseline = self.root/'facts', self.root/'baseline'
        self.source.mkdir(); self.baseline.mkdir()
        self.rules, self.fallback = self.root/'rules.bin', self.root/'fallback.u64'
        (self.source/'ways-0000.bin').write_bytes(b''.join(struct.pack('<QddII', n, 40, 40, 3, 2*(i+1)) for i, n in enumerate((10,20,30,40))))

    def fixture(self, members=(10,20,99), *, join=True, fallback=()):
        present = [10,20] + ([30] if members[2] == 30 else [])
        arcs = [(i, i+1 if join or i != 0 else 3, i, 0, 1, 1, 125) for i in range(len(present))]
        (self.source/'arcs-0000.bin').write_bytes(b''.join(struct.pack('<IIIIIb3xQ', *a) for a in arcs))
        self.rules.write_bytes(struct.pack('<QQQQ', 1, *members))
        self.fallback.write_bytes(b''.join(struct.pack('<Q', w) for w in fallback))
        all_closed = set(members) | set(fallback)
        (self.source/'closures-0000.bin').write_bytes(b''.join(struct.pack('<Q', w) for w in sorted(all_closed)))
        status = 1 if members[2] == 99 else 0 if join else 2
        closed = set(fallback) | (set(members) if status else set())
        pairs = [(0,1)] if status == 0 else []
        (self.baseline/'closures-0000.bin').write_bytes(b''.join(struct.pack('<Q', w) for w in sorted(closed)))
        (self.baseline/'entry-pairs-pre.u32').write_bytes(b''.join(struct.pack('<II', *a) for a in pairs))
        (self.baseline/'decisions.bin').write_bytes(struct.pack('<QII', 1, status, len(pairs)))
        count = lambda closed: sum(w not in closed for w in present)
        self.dimensions = [4,4,len(arcs),1,len(fallback)]
        self.native = [1,int(status==0),int(status==1),int(status==2),len(all_closed),len(closed),len(pairs),len(arcs),count(closed)]
        self.original_post = count(all_closed)

    def run_resolution(self):
        return resolve(self.source,self.rules,self.fallback,self.baseline,self.root/'resolved',self.dimensions,self.native,baseline_post=self.original_post)

    def test_absent_essential_member_reopens_only_its_contribution(self):
        self.fixture(); report = self.run_resolution()
        self.assertEqual(report['inactiveMissingMemberRules'],1)
        self.assertEqual(report['newClosureIds'],0)
        self.assertEqual(report['newFinalArcs'],2)
        self.assertEqual((self.root/'resolved/decisions.bin').read_bytes(),struct.pack('<QII',1,3,0))
        self.assertEqual((self.root/'resolved/inactive-members.bin').read_bytes(),struct.pack('<QB7x',1,4))

    def test_shared_other_contributor_keeps_its_road_closed(self):
        self.fixture(fallback=(20,)); report = self.run_resolution()
        self.assertEqual(report['newClosureIds'],1)
        self.assertEqual(report['newFinalArcs'],1)
        self.assertEqual((self.root/'resolved/closures-0000.bin').read_bytes(),struct.pack('<Q',20))

    def test_existing_real_entry_ban_and_pairs_are_unchanged(self):
        self.fixture((10,20,30)); report = self.run_resolution()
        self.assertEqual(report['inactiveMissingMemberRules'],0)
        self.assertEqual(report['retainedEntryRules'],1)
        self.assertTrue(report['entryPairsByteIdentical'])

    def test_present_members_without_join_keep_old_fallback(self):
        self.fixture((10,20,30),join=False); report = self.run_resolution()
        self.assertEqual(report['inactiveMissingMemberRules'],0)
        self.assertEqual(report['remainingNoJoinFallbackRules'],1)
        self.assertEqual(report['newFinalArcs'],0)

    def test_selected_member_with_zero_prearcs_is_distinct_from_missing_way(self):
        self.fixture(); self.rules.write_bytes(struct.pack('<QQQQ',1,10,20,30))
        for root in (self.source,self.baseline):
            (root/'closures-0000.bin').write_bytes(struct.pack('<QQQ',10,20,30))
        report = self.run_resolution()
        self.assertEqual(report['missingMemberOccurrencesOutsideSelectedWays'],0)
        self.assertEqual(report['missingMemberOccurrencesWithNoPreArcs'],1)

    def test_native_baseline_or_incomplete_preclosure_drift_refuses_output(self):
        self.fixture(); (self.baseline/'decisions.bin').write_bytes(struct.pack('<QII',1,1,1))
        with self.assertRaises(AssertionError): self.run_resolution()
        self.assertFalse((self.root/'resolved').exists())
        self.fixture(); self.dimensions[2] += 1
        with self.assertRaises(AssertionError): self.run_resolution()
        self.assertFalse((self.root/'resolved').exists())


if __name__ == '__main__':
    unittest.main()
