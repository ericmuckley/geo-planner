"""Epoch changes must rederive restrictions rather than transplant old indices."""
import json
from pathlib import Path
import struct
import tempfile
import unittest

from coarse_osm_car_entry_native_v1 import NativeEntries
from coarse_osm_car_packed_audit_v1 import ARC
from coarse_osm_car_policy_v1 import restriction_policy
from coarse_osm_lane_restrictions_v1 import conservative_post,relation_inputs,resolve
from coarse_osm_restriction_entry_v1 import entry_restriction

ARTIFACT=None


def relation(identity,members,kind='no_left_turn'):
    return {'id':identity,'tags':{'type':'restriction','restriction':kind},
            'members':[{'type':'way','role':role,'ref':value} for role,value in members]}


def fixture(root,*,missing=(),extra=(),no_multi_join=False):
    source=root/'facts';source.mkdir();identities=[10,20,30,40,50,60]
    arcs=[(i,i+1,i,0,1,1,b'\0'*3,125) for i in range(6) if identities[i] not in missing]
    if no_multi_join:arcs=[(a[0],99,*a[2:]) if a[2]==3 else a for a in arcs]
    (source/'ways-0000.bin').write_bytes(b''.join(struct.pack('<QddII',w,40.,0.,1,2*i+2) for i,w in enumerate(identities)))
    (source/'arcs-0000.bin').write_bytes(b''.join(ARC.pack(*a) for a in arcs))
    elements=[relation(1,[('from',10),('via',20),('to',30)]),
              relation(2,[('from',40),('via',50),('via',60),('to',10)]),*extra]
    original=set();constant=set();singles=[]
    for element in elements:
        policy=restriction_policy(element);original.update(policy['memberWays']);rule=entry_restriction(element)
        if rule:singles.append((rule.identity,rule.from_way,rule.via_way,rule.to_way))
        else:constant.update(policy['memberWays'])
    (source/'closures-0000.bin').write_bytes(b''.join(struct.pack('<Q',w) for w in sorted(original)))
    metadata=root/'metadata.jsonl';metadata.write_text(''.join(json.dumps(e)+'\n' for e in elements))
    rules=root/'rules.bin';rules.write_bytes(b''.join(struct.pack('<QQQQ',*r) for r in singles))
    fallback=root/'fallback.u64';fallback.write_bytes(b''.join(struct.pack('<Q',w) for w in sorted(constant)))
    return source,metadata,rules,fallback,[6,100,len(arcs),len(singles),len(constant)],len(elements)


class InputTests(unittest.TestCase):
    def test_original_baseline_and_raw_rule_union_are_rederived(self):
        with tempfile.TemporaryDirectory() as tmp:
            source,metadata,rules,fallback,dims,count=fixture(Path(tmp))
            self.assertEqual(conservative_post(source,dims),0)
            r=relation_inputs(source,metadata,rules,fallback,count)
            self.assertEqual(r['singleViaRules'],1);self.assertEqual(r['originalClosureIds'],6)

    def test_incomplete_source_count_and_lost_raw_union_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            source,metadata,rules,fallback,dims,count=fixture(Path(tmp))
            with self.assertRaises(AssertionError):conservative_post(source,[6,100,dims[2]+1])
            (source/'closures-0000.bin').write_bytes(struct.pack('<Q',10))
            with self.assertRaises(AssertionError):relation_inputs(source,metadata,rules,fallback,count)

    def test_mismatched_rule_members_or_fallback_cannot_reuse_old_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            source,metadata,rules,fallback,dims,count=fixture(Path(tmp))
            rules.write_bytes(struct.pack('<QQQQ',1,10,20,60))
            with self.assertRaises(AssertionError):relation_inputs(source,metadata,rules,fallback,count)

    def test_cancel_before_creating_native_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=fixture(Path(tmp));out=Path(tmp)/'out'
            def cancel():raise RuntimeError('cancel epoch')
            with self.assertRaisesRegex(RuntimeError,'cancel epoch'):resolve(None,*args[:4],out,args[4],args[5],cancel)
            self.assertFalse(out.exists())


class PipelineTests(unittest.TestCase):
    def engine(self):
        if ARTIFACT is None:self.skipTest('Explicit qualified native entry artifact required')
        return NativeEntries(*ARTIFACT)

    def run_case(self,**options):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);args=fixture(root,**options)
            report=resolve(self.engine(),*args[:4],root/'out',args[4],args[5])
            fields={p.name:p.read_bytes() for p in (root/'out/final').iterdir()}
            return report,fields

    def test_complete_native_baseline_then_single_and_multi_join_audits(self):
        report,fields=self.run_case()
        self.assertEqual(report['multiVia']['newClosureIds'],0)
        self.assertEqual(list(struct.iter_unpack('<II',fields['entry-pairs-pre.u32'])),[(0,1),(3,4)])
        self.assertFalse(report['oldNumericArcIdsReused']);self.assertFalse(report['previousLaneGraphMonotonicityAssumed'])

    def test_new_essential_leg_activates_previously_inactive_rule(self):
        before,old=self.run_case(missing=(30,));after,new=self.run_case()
        self.assertEqual(before['singleVia']['inactiveMissingMemberRules'],1)
        self.assertEqual(after['singleVia']['inactiveMissingMemberRules'],0)
        self.assertNotIn((0,1),list(struct.iter_unpack('<II',old['entry-pairs-pre.u32'])))
        self.assertIn((0,1),list(struct.iter_unpack('<II',new['entry-pairs-pre.u32'])))

    def test_overlapping_fallback_is_not_removed_when_multi_leg_is_missing(self):
        extra=(relation(3,[('from',50),('via',60),('to',10)],'only_left_turn'),)
        report,fields=self.run_case(missing=(60,),extra=extra)
        self.assertEqual(report['multiVia']['inactiveMissingMemberMultiRules'],1)
        self.assertEqual(set(r[0] for r in struct.iter_unpack('<Q',fields['closures-0000.bin'])),{10,50,60})

    def test_no_join_keeps_full_member_closure_contribution(self):
        report,fields=self.run_case(no_multi_join=True)
        self.assertEqual(report['multiVia']['noJoinMultiFallbackRules'],1)
        self.assertEqual(set(r[0] for r in struct.iter_unpack('<Q',fields['closures-0000.bin'])),{10,40,50,60})
