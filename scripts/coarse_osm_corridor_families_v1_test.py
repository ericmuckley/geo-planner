"""Saved path-family classification preserves all original weighted cases."""
from copy import deepcopy
import unittest

from coarse_osm_corridor_families_v1 import family,summary
from coarse_timing_input import PilotError


def binding(a,b,*,role='primary',numeric=True):return {'endpointIds':[a,b],'nativeTags':{'highway':role},'attributes':{'unscopedNumeric':numeric,'accessTags':{}}}
def candidate(parts,mask):return {'nativeParts':parts,'variants':[{'coveredSampleMaskHex':hex(mask)}]}
def record(paths,**extra):return {'windowId':'arbitrary','arc':1,'sourceClassKph':85,'sourceKm':10.,'sampleCount':10,'status':'multiple_acquired_file_geometric_paths' if len(paths)>1 else 'single_acquired_file_geometric_path' if paths else 'no_path_under_fragment_rules','candidates':paths,'searchCapped':False,'unrepresentedParts':[],**extra}


class Tests(unittest.TestCase):
    def test_overlapping_minimal_subpaths_form_one_native_corridor(self):
        r=record([candidate([1,2],255),candidate([2,3],1020)]);b={1:binding(1,2),2:binding(2,3),3:binding(3,4)};before=deepcopy(r)
        result=family(r,b,[1.]*10);self.assertEqual(result['familyStatus'],'one_unbranched_candidate_corridor');self.assertEqual(result['unbranchedUnscopedSupportedOpportunityKm'],10);self.assertEqual(result['nativePartsInCandidateUnion'],3);self.assertEqual(r,before);self.assertFalse(result['usableLimitOrMatchingQualified'])

    def test_parallel_or_coincident_geometry_with_different_ids_stays_multiple(self):
        r=record([candidate([1],1023),candidate([2],1023)]);b={1:binding(1,2),2:binding(3,4)}
        result=family(r,b,[1.]*10);self.assertEqual(result['familyStatus'],'multiple_disconnected_corridors');self.assertEqual(result['unbranchedUnscopedSupportedOpportunityKm'],0)

    def test_shared_road_prefix_with_real_branch_is_not_merged(self):
        r=record([candidate([1,2],1023),candidate([1,3],1023)]);b={1:binding(1,2),2:binding(2,3),3:binding(2,4)}
        result=family(r,b,[1.]*10);self.assertEqual(result['familyStatus'],'branch_or_cycle_in_candidate_union');self.assertEqual(result['components'][0]['branchNodes'],1)

    def test_loop_and_two_parallel_edges_between_same_nodes_remain_ambiguous(self):
        for b,paths in [({1:binding(1,1)},[candidate([1],1023)]),({1:binding(1,2),2:binding(1,2)},[candidate([1],1023),candidate([2],1023)])]:
            result=family(record(paths),b,[1.]*10);self.assertEqual(result['familyStatus'],'branch_or_cycle_in_candidate_union');self.assertTrue(result['components'][0]['cycle'])

    def test_unsupported_roles_and_speed_scopes_do_not_become_usable(self):
        for b in ({1:binding(1,2,role='footway')},{1:binding(1,2,numeric=False)}):
            result=family(record([candidate([1],1023)]),b,[1.]*10);self.assertEqual(result['unbranchedUnscopedSupportedOpportunityKm'],0);self.assertFalse(result['usableLimitOrMatchingQualified'])
        b={1:binding(1,2)};b[1]['attributes']['accessTags']={'access':'private'};result=family(record([candidate([1],1023)]),b,[1.]*10);self.assertEqual(result['rawAccessTagParts'],1);self.assertFalse(result['physicalMatchQualified'])

    def test_empty_capped_and_rejected_context_preserve_denominator(self):
        for r in (record([]),record([candidate([1],1023)],searchCapped=True,unrepresentedParts=[2])):
            result=family(r,{1:binding(1,2)},[1.]*10);self.assertEqual(result['sourceKm'],10);self.assertEqual(result['unbranchedUnscopedSupportedOpportunityKm'],0)
        report=summary([family(record([]),{},[1.]*10)]);self.assertEqual(report['arcWindowRecords'],1);self.assertEqual(report['samples'],10)

    def test_wrong_weight_missing_node_join_and_mask_overflow_fail(self):
        with self.assertRaises(PilotError):family(record([]),{},[1.]*9)
        with self.assertRaises(PilotError):family(record([candidate([1,2],1023)]),{1:binding(1,2),2:binding(3,4)},[1.]*10)
        with self.assertRaises(PilotError):family(record([candidate([1],2048)]),{1:binding(1,2)},[1.]*10)

    def test_reversal_and_independent_degree_oracle_agree(self):
        r=record([candidate([3,2,1],1023)]);b={1:binding(2,1),2:binding(3,2),3:binding(4,3)};result=family(r,b,[1.]*10)
        degrees={n:sum(n in ends['endpointIds'] for ends in b.values()) for n in {n for v in b.values() for n in v['endpointIds']}}
        self.assertEqual(sum(d==1 for d in degrees.values()),2);self.assertEqual(sum(d>2 for d in degrees.values()),0);self.assertEqual(result['familyStatus'],'one_unbranched_candidate_corridor')
