from pathlib import Path
import struct
import unittest
import coarse_osm_entry_graph_audit_v1_test as fixtures
from coarse_osm_incoming_entry_pairs_v1 import merge_incoming_pairs
from coarse_osm_packed_capture_v1 import pack24
from coarse_timing_input import PilotError


class Tests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.Controls();self.f.setUp();self.addCleanup(self.f.tmp.cleanup)
        self.combined = self.f.extra.parent/'combined.u32';self.output=self.f.extra.parent/'merged.u24'
        self.combined.write_bytes(struct.pack('<IIII',0,1,1,2))
        (self.f.original/'closures-0000.bin').write_bytes(struct.pack('<QQ',10,20))

    def merge(self):
        f=self.f
        return merge_incoming_pairs(f.original,f.view,f.routing,f.extra,self.combined,f.final,self.output,f.dims,f.counts)

    def test_closed_incoming_open_outgoing_maps_and_old_final_union_retains(self):
        counts,proof=self.merge()
        self.assertEqual(counts,[2,1,2,0,3,4])
        self.assertEqual(self.output.read_bytes(),pack24([0,1,1,2,3,1]))
        self.assertEqual(proof['allSourcePreArcsReplayed'],4)
        self.assertTrue(proof['allOriginalNativeFinalPairsRetained'])

    def test_open_incoming_cannot_remove_any_old_transition(self):
        self.combined.write_bytes(struct.pack('<IIII',0,1,3,1))
        with self.assertRaises(PilotError):self.merge()

    def test_nonjoining_source_pair_refuses(self):
        self.combined.write_bytes(struct.pack('<IIII',0,1,0,2))
        with self.assertRaises(PilotError):self.merge()

    def test_old_pair_loss_duplicate_or_partial_input_refuses(self):
        for raw in [struct.pack('<II',1,2),struct.pack('<IIII',0,1,0,1),b'x']:
            self.combined.write_bytes(raw)
            with self.assertRaises((PilotError,AssertionError)):self.merge()

    def test_independently_closed_endpoint_drops_new_pair(self):
        f=self.f
        (f.original/'closures-0000.bin').write_bytes(struct.pack('<QQQ',10,20,30))
        (f.view/'closures-0000.bin').write_bytes(struct.pack('<Q',30))
        (f.routing/'offsets.u24').write_bytes(pack24([0,1,2,2,2,3]))
        (f.routing/'targets.u24').write_bytes(pack24([1,2,1]))
        f.final.write_bytes(pack24([0,1,2,1]));f.dims[-2]=3;f.counts[-1]=3
        counts,proof=self.merge()
        self.assertEqual(counts,[2,1,1,1,2,3])
        self.assertEqual(proof['newDroppedPairs'],1)

    def test_forged_csr_correspondence_refuses(self):
        (self.f.routing/'targets.u24').write_bytes(pack24([2,2,3,1]))
        with self.assertRaises(PilotError):self.merge()

    def test_pair_domain_and_native_baseline_count_refuse(self):
        self.combined.write_bytes(struct.pack('<IIII',0,1,1,99))
        with self.assertRaises(PilotError):self.merge()
        self.combined.write_bytes(struct.pack('<IIII',0,1,1,2));self.f.counts[4]=1
        with self.assertRaises(PilotError):self.merge()


if __name__=='__main__':unittest.main()
