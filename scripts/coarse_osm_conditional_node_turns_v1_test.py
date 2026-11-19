import copy
import itertools
import random
import unittest

from coarse_osm_car_policy_v1 import turn_allowed
from coarse_osm_conditional_node_turns_v1 import BASE_KEYS,CONDITIONAL_KEYS,KINDS,classify,conditional_values


def relation(**tags):
    return {'type':'relation','id':99,'tags':{'type':'restriction','restriction:conditional':'no_left_turn @ (Mo-Fr 07:00-09:00)'}|tags,
            'members':[{'type':'way','ref':10,'role':'from'},{'type':'node','ref':30,'role':'via'},{'type':'way','ref':20,'role':'to'}]}


class Tests(unittest.TestCase):
    def test_supported_base_and_conditional_keys_produce_one_static_maneuver(self):
        for kind,key in itertools.product(KINDS,CONDITIONAL_KEYS):
            element=relation();element['tags']={'type':'restriction',key:kind+' @ wet'}
            before=copy.deepcopy(element);rule=classify(element)['rule']
            self.assertEqual((rule.from_way,rule.via_node,rule.to_way,rule.kind),(10,30,20,kind))
            self.assertEqual(element,before)
        for key in BASE_KEYS:
            self.assertIsNotNone(classify(relation(**{key:'no_left_turn'}))['rule'])

    def test_static_ban_is_a_subset_of_every_condition_state_without_closing_roads(self):
        rule=classify(relation())['rule'];static={'fromWay':rule.from_way,'toWay':rule.to_way,'kind':rule.kind}
        for condition,outgoing,incoming in itertools.product((False,True),(20,40),(10,50)):
            proposed=turn_allowed(incoming,outgoing,False,[static] if incoming==static['fromWay'] else [])
            actual=turn_allowed(incoming,outgoing,False,[static] if condition and incoming==static['fromWay'] else [])
            if proposed:self.assertTrue(actual)
            if incoming==10 and outgoing==20:self.assertFalse(proposed)
            else:self.assertTrue(proposed)

    def test_top_level_clauses_parentheses_unicode_and_admin_bounds(self):
        self.assertEqual(conditional_values('no_left_turn @ (Mo-Fr; PH off); no_left_turn @ 雪'),('no_left_turn','no_left_turn'))
        self.assertIsNotNone(conditional_values('no_left_turn @ '+'('*8+'wet'+')'*8))
        self.assertIsNone(conditional_values('no_left_turn @ '+'('*9+'wet'+')'*9))
        self.assertIsNotNone(conditional_values(';'.join(['no_left_turn @ wet']*64)))
        self.assertIsNone(conditional_values(';'.join(['no_left_turn @ wet']*65)))
        self.assertIsNone(conditional_values('no_left_turn @ '+'x'*65536))

    def test_malformed_unknown_mixed_only_and_relaxing_values_keep_fallback(self):
        for value in ('','no_left_turn','no_left_turn @','no_left_turn @ ()','no_left_turn @ (wet','no_left_turn @ wet)',
                      'no_left_turn @@ wet','no_left_turn @ "wet"','only_left_turn @ wet','none @ wet','no_entry @ wet',
                      'no_left_turn @ wet; no_right_turn @ snow','no_left_turn @ wet;'):
            self.assertIsNone(classify(relation(**{'restriction:conditional':value}))['rule'],value)
        self.assertIsNone(classify(relation(restriction='no_right_turn'))['rule'])

    def test_incomplete_complex_same_way_and_invalid_ids_never_convert(self):
        for change in ('missing','duplicate','via-way','same-way','bool-id'):
            element=relation()
            if change=='missing':element['members'].pop()
            elif change=='duplicate':element['members'][1]['role']='from'
            elif change=='via-way':element['members'][1]['type']='way'
            elif change=='same-way':element['members'][2]['ref']=10
            else:element['members'][0]['ref']=True
            self.assertIsNone(classify(element)['rule'],change)

    def test_mode_exemptions_and_unknown_qualifiers_do_not_disappear(self):
        for tags in ({'type':'restriction:bicycle'},{'except':'motorcar'},{'except':'car'},{'except':'bicycle|psv'},
                     {'restriction:bus:conditional':'no_right_turn @ wet'},{'restriction:forward':'no_left_turn'},
                     {'except:conditional':'motorcar @ wet'}):
            self.assertIsNone(classify(relation(**tags))['rule'],tags)
        self.assertIsNotNone(classify(relation(**{'except':'bicycle;psv'}))['rule'])

    def test_generated_member_order_and_condition_truth_do_not_select_places(self):
        rng=random.Random(20261107)
        for _ in range(1000):
            element=relation();rng.shuffle(element['members'])
            ids=rng.sample(range(1,1000000),3)
            for member,identity in zip(element['members'],ids):member['ref']=identity
            kind=rng.choice(sorted(KINDS));element['tags']['restriction:conditional']=kind+' @ (opaque condition)'
            got=classify(element)['rule'];self.assertIsNotNone(got)
            for member in element['members']:
                self.assertEqual(getattr(got,{'from':'from_way','via':'via_node','to':'to_way'}[member['role']]),member['ref'])

    def test_complete_static_or_noncar_forms_are_not_reinterpreted(self):
        element=relation();element['tags']={'type':'restriction','restriction':'no_left_turn'}
        self.assertIsNone(classify(element)['rule'])
        element['tags']['restriction:hgv:conditional']='no_left_turn @ wet'
        self.assertIsNone(classify(element)['rule'])
