import copy
import unittest

from coarse_osm_blocked_node_causes_v1 import node_cause
from coarse_osm_passable_node_overlay_v1 import audit_overlay,build_overlay
from coarse_timing_input import PilotError


def fixture():
    flags=bytes([0,5,1,7,4])
    rows=[{'vertex':i,'sourceNodeId':str(100+i),'flags':flags[i]} for i in (1,2,3)]
    tags={1:{'barrier':'cattle_grid'},2:{'barrier':'gate'},3:{'highway':'traffic_signals'}}
    evidence={row['sourceNodeId']:node_cause(int(row['sourceNodeId']),row['flags'],{'type':'node','id':int(row['sourceNodeId']),'tags':tags[row['vertex']]},[90] if row['vertex']==3 else []) for row in rows}
    return flags,rows,evidence


class Tests(unittest.TestCase):
    def test_only_qualified_block_bit_opens_and_every_source_cause_replays(self):
        flags,rows,evidence=fixture();before=copy.deepcopy((rows,evidence))
        output,changed=build_overlay(flags,rows,evidence)
        self.assertEqual(output,bytes([0,4,1,7,4]))
        self.assertEqual([r['vertex'] for r in changed],[1])
        self.assertEqual((rows,evidence),before)
        proof=audit_overlay(flags,output,rows,evidence)
        self.assertEqual(proof['changedVertices'],[1])
        self.assertTrue(proof['signalsAndReversalBitsExact'])

    def test_partial_duplicate_wrong_native_flags_and_missing_raw_tag_sets_refused(self):
        flags,rows,evidence=fixture()
        for mapping,records in ((rows[:-1],evidence),(rows+[rows[0]],evidence),(rows,evidence|{'999':evidence['101']})):
            with self.assertRaises(PilotError):build_overlay(flags,mapping,records)
        rows[0]['flags']=1
        with self.assertRaises(PilotError):build_overlay(flags,rows,evidence)

    def test_forged_original_cause_or_signal_is_rejected(self):
        flags,rows,evidence=fixture();evidence['101']['rawTags']={}
        with self.assertRaises(PilotError):build_overlay(flags,rows,evidence)

    def test_independent_byte_audit_refuses_extra_opening_or_flag_changes(self):
        flags,rows,evidence=fixture();output,_=build_overlay(flags,rows,evidence)
        for vertex in range(len(flags)):
            tampered=bytearray(output);tampered[vertex]^=1
            with self.assertRaises(PilotError):audit_overlay(flags,bytes(tampered),rows,evidence)
        tampered=bytearray(output);tampered[1]^=2
        with self.assertRaises(PilotError):audit_overlay(flags,bytes(tampered),rows,evidence)
