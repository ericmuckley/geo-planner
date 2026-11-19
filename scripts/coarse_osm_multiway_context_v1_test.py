from pathlib import Path
import struct
import unittest

from coarse_osm_car_packed_audit_v1 import unpack24
from coarse_osm_context_records_v1 import u24
import coarse_osm_context_records_v1_test as fixtures
from coarse_osm_multiway_context_v1 import build


class MultiContext(unittest.TestCase):
    def setUp(self):
        self.base=fixtures.Controls('test_complete_bytes_native_state_exit_trigger_identity_and_union')
        self.base.setUp();self.addCleanup(self.base.doCleanups)
        self.multi=self.base.root/'multi.u32'

    def produce(self,entries,add_final=True):
        b=self.base
        self.multi.write_bytes(b''.join(struct.pack('<II',*pair) for pair in entries))
        if add_final:
            # Independent fixture source/pre -> CSR -> spatial mapping.
            closed={n[0] for n in struct.iter_unpack('<Q',(b.source/'closures-0000.bin').read_bytes())}
            active=sorted((i for i,a in enumerate(b.arcs) if b.ids[a[2]] not in closed),key=lambda i:(b.arcs[i][0],i))
            native={pre:i for i,pre in enumerate(active)}
            permutation=list(struct.unpack('<'+'I'*len(active),b.permutation.read_bytes()))
            final=list(unpack24(b.final.read_bytes()));pairs=set(zip(final[::2],final[1::2]))
            pairs.update((permutation[native[a]],permutation[native[c]]) for a,c in entries if a in native and c in native)
            b.final.write_bytes(u24(n for pair in sorted(pairs) for n in pair))
        return build(b.source,b.rules,b.decisions,b.entries,self.multi,b.offsets,b.targets,b.permutation,
                     b.supported,b.final,b.output,b.dimensions)

    def test_multi_ban_overlapping_history_entry_stays_static(self):
        report,fields=self.produce([(0,1)])
        self.assertEqual(report['supportedSourceTurnPairs'],1)
        self.assertEqual(report['retainedStaticForbiddenPairs'],2)
        pairs=list(unpack24(fields['routing/forbidden-turns.u24']))
        self.assertEqual(set(zip(pairs[::2],pairs[1::2])),{(5,1),(3,5)})
        self.assertEqual(report['activeMultiEntryPairs'],1)

    def test_nonoverlapping_multi_ban_and_native_permutation(self):
        self.base.write_graph(permutation=range(6))
        report,fields=self.produce([(2,3)])
        self.assertEqual(report['retainedStaticForbiddenPairs'],2)
        self.assertEqual(report['independentAudit']['allRetainedStaticForbiddenPairsChecked'],2)
        self.assertEqual(len(fields['context/triggers.u24']),18)

    def test_other_closure_drops_pair_without_losing_source_bans(self):
        self.base.write_graph(closed=[50])
        report,_=self.produce([(5,1)])
        self.assertEqual(report['activeMultiEntryPairs'],0)
        self.assertEqual(report['multiEntryPairsDroppedByOtherClosures'],1)
        self.assertEqual(report['retainedStaticForbiddenPairs'],1)

    def test_cross_junction_or_duplicate_pre_pairs_refused(self):
        for entries in [[(0,3)],[(0,1),(0,1)]]:
            with self.assertRaises(AssertionError):self.produce(entries)

    def test_missing_static_union_refused(self):
        with self.assertRaises(AssertionError):self.produce([(2,3)],add_final=False)

    def test_empty_multi_set_keeps_exact_qualified_context_fields(self):
        _,fields=self.produce([])
        self.assertEqual(fields['routing/forbidden-turns.u24'],u24([5,1]))


if __name__=='__main__':unittest.main()
