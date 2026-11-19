import gzip
import json
from pathlib import Path
import struct
import tempfile
import unittest

from coarse_osm_blocked_node_ids_v1 import map_nodes, write_and_audit


class BlockedNodeIdsTests(unittest.TestCase):
    def test_nonidentity_mapping_preserves_exact_uint64_ids_and_source_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            report = write_and_audit(bytes([3,0,1]),[2,0,1],[0,2,1],[10,2**53+17,30],[0,1,3],directory)
            rows = json.loads(gzip.decompress((Path(directory)/'blocked-nodes.json.gz').read_bytes()))
            self.assertEqual([row['sourceNodeId'] for row in rows], [str(2**53+17),'30'])
            raw = (Path(directory)/'blocked-node-ids.u64').read_bytes()
            self.assertEqual(list(struct.unpack('<QQ',raw)),[30,2**53+17])
            self.assertEqual(report['allGraphToSourceFlagsCompared'],3)

    def test_wrong_or_duplicate_permutations_and_flag_mismatch_refuse(self):
        for permutation in ([0,0],[0,2],[1,0]):
            with self.assertRaises(AssertionError):
                map_nodes(bytes([0,1]),permutation,[0,1],[10,20],[0,1])

    def test_bad_source_indices_and_duplicate_ids_refuse(self):
        with self.assertRaises(AssertionError):
            map_nodes(bytes([1]),[0],[1],[10],[1])
        with self.assertRaises(AssertionError):
            map_nodes(bytes([1,1]),[0,1],[0,1],[10,10],[1,1])

    def test_empty_blocked_selection_has_complete_empty_representations(self):
        with tempfile.TemporaryDirectory() as directory:
            report = write_and_audit(bytes([0,2]),[0,1],[0,1],[10,20],[0,2],directory)
            self.assertEqual(report['blockedVertices'],0)
            self.assertEqual((Path(directory)/'blocked-node-ids.u64').read_bytes(),b'')


if __name__ == '__main__':
    unittest.main()
