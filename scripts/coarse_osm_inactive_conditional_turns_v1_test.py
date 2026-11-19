import copy
import unittest

from coarse_osm_conditional_node_facts_v1_test import prepared, relation
from coarse_osm_conditional_node_ports_v1 import qualify
from coarse_osm_conditional_node_ports_v1_test import fixture, rule
from coarse_osm_inactive_conditional_turns_v1 import audit_effects, effects, relation_overlay
from coarse_timing_input import PilotError


def metadata_for(candidate):
    from dataclasses import asdict
    element=relation(candidate.identity,candidate.kind)
    element['members'][0]['ref']=candidate.from_way;element['members'][1]['ref']=candidate.via_node;element['members'][2]['ref']=candidate.to_way
    return [{'source':element,'derived':{k:str(v)if type(v)is int else v for k,v in asdict(candidate).items()}}]


class Tests(unittest.TestCase):
    def test_all_six_negative_incidence_shapes_are_independently_checked(self):
        probes=[rule(from_way=50),rule(to_way=50),rule(from_way=30),rule(to_way=30),rule(from_way=20,via_node=100,to_way=10),rule(via_node=100)]
        for candidate in probes:
            fields=fixture();metadata=metadata_for(candidate);ports=qualify(fields,[candidate]);before=copy.deepcopy(fields)
            proof=audit_effects(fields,metadata,ports)
            self.assertEqual(proof['inactiveRules'],1);self.assertEqual(fields,before)
    def test_represented_bans_stay_and_only_inactive_closure_contributors_leave(self):
        candidate=rule(identity=2,to_way=50);metadata=metadata_for(candidate);ports=qualify(fixture(),[candidate]);element=metadata[0]['source']
        out=relation_overlay([element],{},{},{10,50},metadata,ports['rows'])
        self.assertEqual(out['inactiveRelations'],{2});self.assertEqual(out['added'],{});self.assertEqual(out['closed'],set())
        meta,ports=prepared();out=relation_overlay([relation()],{},{},{10,20},meta,ports)
        self.assertEqual(len(out['added']),1);self.assertEqual(out['inactiveRelations'],set())
    def test_independent_shared_unknown_and_unrelated_restrictions_stay(self):
        candidate=rule(identity=2,to_way=50);meta=metadata_for(candidate);ports=qualify(fixture(),[candidate]);source=meta[0]['source']
        other=copy.deepcopy(source);other['id']=3;other['tags']['access:conditional']='no @ snow'
        out=relation_overlay([source,other],{},{},{10,50},meta,ports['rows'])
        self.assertEqual(out['closed'],{10,50});self.assertEqual(out['sharedClosedWaysRetained'],2)
    def test_missing_via_and_nonanchor_remain_fallback(self):
        for candidate in [rule(via_node=999),rule(via_node=400)]:
            meta=metadata_for(candidate);ports=qualify(fixture(),[candidate]);out=effects(meta,ports['rows'])
            self.assertFalse(out['inactive']);self.assertEqual(len(out['fallback']),1)
    def test_forged_status_ports_or_source_rows_fail_independent_audit(self):
        candidate=rule();meta=metadata_for(candidate);ports=qualify(fixture(),[candidate])
        altered=copy.deepcopy(ports);altered['rows'][0].update(status='no-directed-incoming-source-port',incomingPreArcIds=[])
        with self.assertRaises(PilotError):audit_effects(fixture(),meta,altered)
        altered=copy.deepcopy(ports);altered['rows'][0].update(status='to-way-outside-major-facts',toWayRow=None,incomingPreArcIds=[],outgoingPreArcIds=[])
        with self.assertRaises(PilotError):audit_effects(fixture(),meta,altered)
    def test_profile_change_invalidates_previous_absence_certificate(self):
        candidate=rule(to_way=50);meta=metadata_for(candidate);old=qualify(fixture(),[candidate]);changed=fixture()
        changed['ways'][2]=(50,50.,50.,3,6)
        changed['arcs'] += [(1,2,2,0,1,1,bytes(3),1000),(2,1,2,0,1,-1,bytes(3),1000)]
        with self.assertRaises(PilotError):audit_effects(changed,meta,old)
    def test_invalid_classifier_or_descriptor_identity_is_never_inferred(self):
        meta,ports=prepared();meta[0]['source']['tags']['restriction:conditional']='only_left_turn @ wet'
        with self.assertRaises(PilotError):effects(meta,ports)
        meta,ports=prepared();ports[0]['toWayId']='51'
        with self.assertRaises(PilotError):effects(meta,ports)
    def test_empty_or_outside_captured_local_source_never_invents_contribution(self):
        candidate=rule(to_way=50);meta=metadata_for(candidate);ports=qualify(fixture(),[candidate]);out=relation_overlay([],{},{},set(),meta,ports['rows'])
        self.assertFalse(out['inactiveRelations']);self.assertFalse(out['closed']);self.assertEqual(out['inactiveOutsideLocalMetadata'],1)


if __name__=='__main__':unittest.main()
