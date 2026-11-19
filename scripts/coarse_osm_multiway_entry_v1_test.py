import itertools
import unittest

from coarse_osm_multiway_entry_v1 import audit_raw_multiway_path, multiway_rule, plan_multiway


def relation(identity=1, kind='no_left_turn', via=(2,3)):
    return {'id':identity, 'tags':{'type':'restriction','restriction':kind},
            'members':[{'type':'way','role':role,'ref':ref} for role,ref in [('from',1),*[('via',v) for v in via],('to',4)]]}


ARCS = [{'way':i, 'tail':i-1, 'head':i} for i in (1,2,3,4)]


class Multiway(unittest.TestCase):
    def test_static_selector_and_order_independent_entry(self):
        for via in [(2,3),(3,2)]:
            result=plan_multiway([relation(via=via)],ARCS,4)
            self.assertEqual(result['closed'],set())
            self.assertEqual(result['multiPairs'],{(0,1)})
        self.assertEqual(multiway_rule(relation()).via_ways,(2,3))

    def test_each_missing_essential_leg_and_overlapping_contributor(self):
        for missing in (1,2,3,4):
            arcs=[a for a in ARCS if a['way']!=missing]
            result=plan_multiway([relation()],arcs,3)
            self.assertEqual(result['closed'],set())
            self.assertEqual(result['multiInactive'],[{'id':1,'absentEssentialWays':[missing]}])
        other=relation(2,'only_straight_on')
        result=plan_multiway([relation(),other],ARCS,4)
        self.assertEqual(result['closed'],{1,2,3,4})
        self.assertEqual(result['fallback'],[2])

    def test_unjoined_and_unsupported_shapes_keep_closures(self):
        disjoint=[{**a,'tail':100+a['tail'],'head':200+a['head']} for a in ARCS]
        self.assertEqual(plan_multiway([relation()],disjoint,4)['closed'],{1,2,3,4})
        cases=[relation(kind='only_left_turn'),relation(kind='unknown'),relation(via=(2,2)),relation(via=(1,2)),relation(via=tuple(range(10,75)))]
        conditional=relation();conditional['tags']['restriction:conditional']='no_left_turn @ (Mo-Fr)';cases.append(conditional)
        node=relation();node['members'][1]['type']='node';cases.append(node)
        duplicate=relation();duplicate['members'][-1]['role']='from';cases.append(duplicate)
        for raw in cases:
            self.assertIsNone(multiway_rule(raw))
        excepted=relation();excepted['tags']['except']='motorcar';self.assertIsNone(multiway_rule(excepted))

    def test_all_from_via_joins_block_complete_sequences(self):
        # Exhaustive walks include unrelated arrivals, loops, arbitrary via order,
        # prefixes/suffixes and a from-way that meets several distinct via roads.
        arcs=[{'way':way,'tail':0,'head':0} for way in (1,2,3,4,5)]
        result=plan_multiway([relation()],arcs,5)
        self.assertEqual(result['multiPairs'],{(0,1),(0,2)})
        for length in range(1,7):
            for path in itertools.product(range(5),repeat=length):
                allowed=all(pair not in result['multiPairs'] for pair in zip(path,path[1:]))
                ways=[arcs[i]['way'] for i in path]
                for via in ((2,3),(3,2)):
                    sequence=(1,*via,4)
                    complete=any(tuple(ways[i:i+4])==sequence for i in range(length-3))
                    self.assertFalse(allowed and complete)
        self.assertNotIn((4,1),result['multiPairs'])

    def test_raw_replay_does_not_trust_compiled_pairs(self):
        raw=relation();result=plan_multiway([raw],ARCS,4)
        converted=[{**r,'pairs':[]} for r in result['multiConverted']]
        with self.assertRaisesRegex(AssertionError,'Original multi-via'):
            audit_raw_multiway_path([raw],converted,ARCS,{'steps':[{'arc':0},{'arc':1}]},{1,2,3,4})
        audit_raw_multiway_path([raw],converted,ARCS,{'steps':[{'arc':1},{'arc':2}]},{1,2,3,4})

    def test_complete_preclosure_and_object_bounds(self):
        with self.assertRaisesRegex(ValueError,'Complete pre-relation'):
            plan_multiway([relation()],[],4)
        with self.assertRaisesRegex(ValueError,'bound'):
            plan_multiway([relation()]*10001,ARCS,4)


if __name__ == '__main__':
    unittest.main()
