import json
from pathlib import Path
import struct
import tempfile
import unittest

from coarse_osm_car_packed_audit_v1 import ARC
from coarse_osm_multiway_country_v1 import resolve
from coarse_osm_multiway_entry_v1_test import relation


class Country(unittest.TestCase):
    def prepared(self, root, elements=None, arcs=None):
        source = root/'facts';source.mkdir()
        identities = [1,2,3,4,5,10,11,12]
        arcs = arcs if arcs is not None else [(i,i+1,i,0,1,1,b'\0'*3,125) for i in range(8)]
        elements = elements or [relation(), {'id':2,'tags':{'type':'restriction','restriction':'no_left_turn'},
                              'members':[{'type':'way','role':role,'ref':value} for role,value in [('from',10),('via',11),('to',12)]]}]
        baseline = set()
        for element in elements:
            if element['id'] != 2:baseline.update(m['ref'] for m in element['members'] if m['type']=='way')
        (source/'ways-0000.bin').write_bytes(b''.join(struct.pack('<QddII',w,50,50,0,1) for w in identities))
        (source/'arcs-0000.bin').write_bytes(b''.join(ARC.pack(*a) for a in arcs))
        paths = [root/name for name in ['metadata.jsonl','decisions.bin','closures.bin','pairs.bin']]
        paths[0].write_text(''.join(json.dumps(e)+'\n' for e in elements))
        paths[1].write_bytes(struct.pack('<QII',2,0,1))
        paths[2].write_bytes(b''.join(struct.pack('<Q',w) for w in sorted(baseline)))
        paths[3].write_bytes(b'')
        old_post = sum(identities[a[2]] not in baseline for a in arcs)
        dims=[len(identities),9,len(arcs),old_post,len(elements),1]
        return source,paths,dims

    def run_case(self, elements=None, arcs=None, change=lambda p,d:None):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);source,paths,dims=self.prepared(root,elements,arcs);change(paths,dims)
            report=resolve(source,*paths,root/'output',dims)
            return report,{p.name:p.read_bytes() for p in (root/'output').iterdir()}

    def test_complete_baseline_and_independent_join(self):
        report,fields=self.run_case()
        self.assertEqual(report['newMultiEntryPairs'],1)
        self.assertEqual(report['newClosureIds'],0)
        self.assertEqual(report['proposedPostArcs'],8)
        self.assertEqual(list(struct.iter_unpack('<II',fields['multi-entry-pairs-pre.u32'])),[(0,1)])

    def test_missing_leg_uses_complete_pre_arcs(self):
        arcs=[(i,i+1,i,0,1,1,b'\0'*3,125) for i in range(8) if i!=2]
        report,_=self.run_case(arcs=arcs)
        self.assertEqual(report['inactiveMissingMemberMultiRules'],1)
        self.assertEqual(report['newMultiEntryPairs'],0)
        self.assertEqual(report['newClosureIds'],0)

    def test_no_join_keeps_full_contribution(self):
        arcs=[(i,i,i,0,1,1,b'\0'*3,125) for i in range(8)]
        report,_=self.run_case(arcs=arcs)
        self.assertEqual(report['noJoinMultiFallbackRules'],1)
        self.assertEqual(report['newClosureIds'],4)

    def test_other_relation_overlap_is_never_subtracted(self):
        raw=relation(3,'only_left_turn')
        report,_=self.run_case(elements=[relation(),{'id':2,'tags':{'type':'restriction','restriction':'no_left_turn'},'members':[{'type':'way','role':r,'ref':w} for r,w in [('from',10),('via',11),('to',12)]]},raw])
        self.assertEqual(report['newClosureIds'],4)
        self.assertEqual(report['proposedPostArcs'],4)

    def test_lost_baseline_union_refused(self):
        with self.assertRaises(AssertionError):
            self.run_case(change=lambda p,d:p[2].write_bytes(struct.pack('<Q',1)))

    def test_incomplete_pre_count_refused(self):
        def change(paths,dims):dims[2]+=1
        with self.assertRaises(AssertionError):self.run_case(change=change)

    def test_old_single_decision_identity_or_status_refused(self):
        for identity,status in [(99,0),(2,1),(2,9)]:
            with self.assertRaises((AssertionError,KeyError)):
                self.run_case(change=lambda p,d:p[1].write_bytes(struct.pack('<QII',identity,status,0)))

    def test_cancel_before_source_selection(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);source,paths,dims=self.prepared(root)
            def stop():raise RuntimeError('cancel')
            with self.assertRaisesRegex(RuntimeError,'cancel'):resolve(source,*paths,root/'output',dims,stop)
            self.assertFalse((root/'output').exists())


if __name__ == '__main__':unittest.main()
