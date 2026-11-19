import copy
import unittest

from coarse_osm_conditional_node_ports_v1 import audit,qualify
from coarse_osm_conditional_node_turns_v2 import ConditionalNodeTurn
from coarse_timing_input import PilotError


def fixture():
    return {'ids':[100,200,300,400],'anchors':[0,1,2],
            'ways':[(10,50.,50.,3,2),(20,50.,50.,3,4),(30,0.,0.,3<<8,6)],
            'arcs':[(0,1,0,0,1,1,bytes(3),1000),(1,0,0,0,1,-1,bytes(3),1000),
                    (1,2,1,0,1,1,bytes(3),1000),(2,1,1,0,1,-1,bytes(3),1000)]}


def rule(identity=1,from_way=10,via_node=200,to_way=20,kind='no_left_turn'):
    return ConditionalNodeTurn(identity,from_way,via_node,to_way,kind)


class Tests(unittest.TestCase):
    def checked(self,fields,rules):
        before=copy.deepcopy(fields);result=qualify(fields,rules);proof=audit(fields,rules,result)
        self.assertEqual(fields,before)
        self.assertEqual(proof['allCandidateSourceDescriptorsIndependentlyReplayed'],len(rules))
        return result,proof

    def test_exact_native_ids_anchor_and_directed_pre_ports_independently_replay(self):
        result,proof=self.checked(fixture(),[rule(),rule(2,20,200,10)])
        self.assertEqual(result['rows'][0]['status'],'source-ports-supported')
        self.assertEqual(result['rows'][0]['incomingPreArcIds'],[0])
        self.assertEqual(result['rows'][0]['outgoingPreArcIds'],[2])
        self.assertEqual(result['rows'][1]['incomingPreArcIds'],[3])
        self.assertEqual(result['rows'][1]['outgoingPreArcIds'],[1])
        self.assertEqual(proof['supportedRules'],2)

    def test_every_missing_ineligible_and_nonanchor_scope_keeps_fallback(self):
        probes=[(rule(from_way=50),'from-way-outside-major-facts'),(rule(to_way=50),'to-way-outside-major-facts'),
                (rule(from_way=30),'from-way-base-ineligible'),(rule(to_way=30),'to-way-base-ineligible'),
                (rule(via_node=999),'via-node-not-in-selected-source'),(rule(via_node=400),'via-node-not-an-anchor'),
                (rule(from_way=20,via_node=100,to_way=10),'no-directed-incoming-source-port'),
                (rule(via_node=100),'no-directed-outgoing-source-port')]
        for candidate,reason in probes:
            result,_=self.checked(fixture(),[candidate]);self.assertEqual(result['rows'][0]['status'],reason)

    def test_full_node_anchor_way_and_arc_order_direction_and_cost_guards(self):
        for key,change in [('ids',[200,100,300,400]),('anchors',[0,1,1]),
                           ('ways',[(20,50.,50.,3,2),(10,50.,50.,3,4)]),('arcs',list(reversed(fixture()['arcs'])))]:
            fields=fixture();fields[key]=change
            with self.assertRaises(PilotError):qualify(fields,[rule()])
        for slot,value in ((0,3),(2,3),(4,2),(5,0),(6,b'bad'),(7,0)):
            fields=fixture();arc=list(fields['arcs'][0]);arc[slot]=value;fields['arcs'][0]=tuple(arc)
            with self.assertRaises(PilotError):qualify(fields,[rule()])
        fields=fixture();fields['ways'][0]=(10,0.,50.,3,2)
        with self.assertRaises(PilotError):qualify(fields,[rule()])

    def test_complete_selected_port_multiplicity_is_preserved(self):
        fields=fixture();fields['ways']=[(10,50.,50.,3,5),(20,50.,50.,3,7),(30,0.,0.,3<<8,9)]
        fields['arcs']=[(0,1,0,0,1,1,bytes(3),1000),(1,0,0,0,1,-1,bytes(3),1000),
                        (1,1,0,1,4,1,bytes(3),3000),(1,1,0,1,4,-1,bytes(3),3000),
                        (1,2,1,0,1,1,bytes(3),1000),(2,1,1,0,1,-1,bytes(3),1000)]
        result,_=self.checked(fields,[rule()])
        self.assertEqual(result['rows'][0]['incomingPreArcIds'],[0,2,3])
        self.assertEqual(result['rows'][0]['outgoingPreArcIds'],[4])

    def test_independent_audit_rejects_forged_ports_mapping_status_or_counts(self):
        fields=fixture();result=qualify(fields,[rule()])
        for key,value in [('incomingPreArcIds',[1]),('outgoingPreArcIds',[3]),('viaAnchor',0),('status','no-directed-incoming-source-port')]:
            altered=copy.deepcopy(result);altered['rows'][0][key]=value
            with self.assertRaises(PilotError):audit(fields,[rule()],altered)
        result['allSourceNodeIdsChecked']+=1
        with self.assertRaises(PilotError):audit(fields,[rule()],result)

    def test_uint64_identities_and_empty_candidate_set_remain_exact(self):
        fields=fixture();offset=2**53+1
        fields['ids']=[v+offset for v in fields['ids']]
        fields['ways']=[(row[0]+offset,*row[1:]) for row in fields['ways']]
        result,_=self.checked(fields,[rule(from_way=10+offset,via_node=200+offset,to_way=20+offset)])
        self.assertEqual(result['rows'][0]['viaNodeId'],str(200+offset))
        result,proof=self.checked(fixture(),[]);self.assertEqual(result['rows'],[]);self.assertEqual(proof['supportedRules'],0)

    def test_duplicate_forged_same_way_or_unknown_kind_rules_refuse(self):
        for rules in ([rule(),rule()],[rule(to_way=10)],[rule(kind='only_left_turn')],[rule(identity=True)]):
            with self.assertRaises(PilotError):qualify(fixture(),rules)
