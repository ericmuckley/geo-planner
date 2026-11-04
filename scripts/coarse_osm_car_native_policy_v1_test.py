"""Native policy equivalence and malformed-boundary controls; synthetic input only."""
from dataclasses import asdict
import random
import struct
import unittest

from coarse_osm_car_native_policy_v1 import NativePolicy, frame
from coarse_osm_car_policy_v1 import POLICY, node_policy, restriction_policy, way_policy
from coarse_timing_input import PilotError

ARTIFACT = None


class WireTests(unittest.TestCase):
    def test_deterministic_sorted_input(self):
        self.assertEqual(frame('way', {'b': '2', 'a': '1'}), frame('way', {'a': '1', 'b': '2'}))
    def test_input_bounds(self):
        for kind, tags in [('other', {}), ('way', {'a': 3}), ('way', {'a': 'x' * 4194304})]:
            with self.assertRaises(PilotError):
                frame(kind, tags)


class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if ARTIFACT is None:
            raise unittest.SkipTest('Run with the protected compiled native artifact')
        cls.native = NativePolicy(*ARTIFACT)

    def way(self, props):
        self.assertEqual(self.native.classify('way', props), asdict(way_policy(props)), props)

    def node(self, props):
        expected = node_policy(props)
        self.assertEqual(self.native.classify('node', props), {key: expected[key] for key in ('blocked', 'signal', 'tagged')}, props)

    def relation(self, props, members):
        expected = restriction_policy({'id': 1, 'tags': props, 'members': members})
        actual = self.native.classify('relation', props, members)
        for key in ('status', 'kind', 'fromWay', 'via', 'toWay', 'reason'):
            self.assertEqual(actual[key], expected.get(key, 0 if key in ('fromWay', 'via', 'toWay') else None), (props, members, key))

    def test_every_role_and_default(self):
        for role in [*POLICY['roles'], 'residential', 'construction', '']:
            self.way({'highway': role})
        self.way({})

    def test_oneway_roundabout_circular_and_mode_precedence(self):
        for role in POLICY['roles']:
            for key in ('oneway', 'oneway:motor_vehicle', 'oneway:motorcar'):
                for value in ('yes', 'no', '1', '0', 'true', 'false', '-1', '', 'reversible', 'alternating', 'Yes'):
                    self.way({'highway': role, key: value})
            for junction in ('roundabout', 'circular', 'mini_roundabout'):
                self.way({'highway': role, 'junction': junction})
        self.way({'highway': 'motorway', 'oneway': 'yes', 'oneway:motor_vehicle': 'no', 'oneway:motorcar': '-1'})

    def test_speed_units_precedence_and_missing_defaults(self):
        for value in ('55', '55 mph', '40.5km/h', '0030.50 kph', ' 50 ', '\u200350\u00a0mph\u3000', '50\x1cmph', '0.000000000000000000000000001', '0' * 8192 + '55'):
            for key in ('maxspeed', 'maxspeed:forward', 'maxspeed:backward'):
                self.way({'highway': 'primary', key: value})
        self.way({'highway': 'primary', 'maxspeed': 'bad', 'maxspeed:forward': '50', 'maxspeed:backward': '60 mph'})

    def test_unsupported_zero_extreme_and_decimal_speeds(self):
        for value in ('', ' ', '0', '0 mph', '-1', '+1', '.5', '1.', '1e2', 'NaN', 'inf', '161', '100 mph', '60 MPH', '30;50', 'signals', '５０', '1' * 8192, '0.' + '0' * 8192 + '1', '55\x00mph'):
            self.way({'highway': 'primary', 'maxspeed': value})

    def test_general_directional_access_precedence(self):
        keys = ('motorcar', 'motor_vehicle', 'vehicle', 'access')
        for key in keys:
            for value in ('yes', 'permissive', 'designated', 'no', 'private', 'destination', '', 'YES'):
                self.way({'highway': 'primary', key: value})
                self.way({'highway': 'primary', key + ':forward': value})
                self.way({'highway': 'primary', key + ':backward': value})
        for props in ({'access': 'no', 'motorcar': 'yes'}, {'access': 'yes', 'motorcar:forward': 'no'},
                      {'access': 'private', 'motorcar:forward': 'yes'}, {'motor_vehicle': 'no', 'motorcar:backward': 'yes'},
                      {'motorcar': 'yes', 'access:forward': 'no'}):
            self.way({'highway': 'primary'} | props)

    def test_road_exclusions_and_ferry_scope(self):
        for key, values in {'ferry': ('', 'yes', 'primary', 'no', 'false', '0'), 'route': ('ferry', 'road'),
                            'ford': ('no', 'yes', ''), 'area': ('yes', 'no'), 'service': ('driveway', 'parking_aisle', 'alley'),
                            'maxspeed:conditional': ('', '50 @ Mo'), 'restriction:hgv': ('no_left_turn',),
                            'motorcar:lanes:forward': ('yes|no',), 'access:lanes': ('yes',), 'reversible': ('no',)}.items():
            for value in values:
                self.way({'highway': 'primary', key: value})

    def test_barrier_types_permissions_and_precedence(self):
        for barrier in ('gate', 'lift_gate', 'toll_booth', 'border_control', 'bollard', 'yes', ''):
            for access in ({}, {'motorcar': 'yes'}, {'access': 'designated'}, {'access': 'yes'}, {'motorcar': 'no', 'access': 'yes'}):
                self.node({'barrier': barrier} | access)

    def test_barrier_qualifiers_dimensions_locked_and_opening_hours(self):
        for key, values in {'motorcar:forward': ('yes',), 'oneway': ('no',), 'reversible': ('no',), 'restriction': ('no',),
                            'maxheight': ('4', ''), 'maxweight:forward': ('20',), 'width': ('4',), 'height': ('4',),
                            'access:conditional': ('yes @ Mo',), 'locked': ('yes', '', 'no'), 'opening_hours': ('Mo-Fr', '24/7', '')}.items():
            for value in values:
                self.node({'barrier': 'gate', 'motorcar': 'yes', key: value})
        self.node({'highway': 'traffic_signals'})
        self.node({})
        self.node({'access': 'no'})

    def test_turn_types_modes_and_exceptions(self):
        members = [{'type': 'way', 'ref': 1, 'role': 'from'}, {'type': 'node', 'ref': 2, 'role': 'via'}, {'type': 'way', 'ref': 3, 'role': 'to'}]
        for typ in ('restriction', 'restriction:motorcar', 'restriction:motor_vehicle', 'restriction:vehicle', 'restriction:bicycle', 'route', 'restriction:'):
            for kind in ('no_left_turn', 'no_right_turn', 'no_straight_on', 'no_u_turn', 'no_entry', 'no_exit', 'only_left_turn', 'only_right_turn', 'only_straight_on', 'only_u_turn', 'unknown'):
                self.relation({'type': typ, 'restriction': kind}, members)
        for value in ('motorcar', 'bus; motorcar', '\u2003vehicle\u3000', 'bicycle', ''):
            self.relation({'type': 'restriction', 'restriction': 'no_left_turn', 'except': value}, members)

    def test_via_way_conditions_repeated_and_unknown_members(self):
        members = [{'type': 'way', 'ref': 1, 'role': 'from'}, {'type': 'way', 'ref': 2, 'role': 'via'}, {'type': 'way', 'ref': 3, 'role': 'to'}]
        for tags in ({'restriction': 'no_left_turn'}, {'restriction:conditional': 'no_right_turn @ Mo'}, {'restriction:bicycle': 'no_left_turn'}, {}):
            self.relation({'type': 'restriction'} | tags, members)
        for kind in ('no_left_turn', 'no_u_turn', 'no_straight_on', 'only_u_turn', 'only_straight_on'):
            same = [members[0], {'type': 'node', 'ref': 2, 'role': 'via'}, members[2] | {'ref': 1}]
            self.relation({'type': 'restriction', 'restriction': kind}, same)

    def test_unlocatable_unsupported_restriction_fails(self):
        tags = {'type': 'restriction', 'restriction': 'unknown'}
        with self.assertRaises(PilotError):
            self.native.classify('relation', tags, [])
        with self.assertRaises(PilotError):
            self.native.classify('relation', tags, [{'type': 'relation', 'ref': 1, 'role': 'via'}])

    def test_malformed_frames_reject_and_clear_output(self):
        import ctypes
        valid = frame('way', {'highway': 'primary'})
        def text(value):
            return struct.pack('<I', len(value)) + value
        duplicate = b'GCP1\x01' + struct.pack('<I', 2) + (text(b'highway') + text(b'primary')) * 2
        unsorted = b'GCP1\x01' + struct.pack('<I', 2) + text(b'z') + text(b'1') + text(b'a') + text(b'1')
        for raw in (b'', b'wrong', valid[:-1], valid + b'x', valid[:4] + bytes([3]) + valid[5:], valid[:5] + struct.pack('<I', 65537) + valid[9:],
                    duplicate, unsorted,
                    b'GCP1\x01' + struct.pack('<I', 1) + struct.pack('<I', 1) + b'\xff' + struct.pack('<I', 0)):
            with self.assertRaises(PilotError):
                self.native.decode(raw)
            output = (ctypes.c_uint64 * 8)(*([999] * 8))
            error = ctypes.create_string_buffer(512)
            self.assertNotEqual(self.native.call(raw, len(raw), output, 8, error, len(error)), 0)
            self.assertEqual(list(output), [0] * 8)

    def test_seeded_way_metadata_combinations(self):
        rng = random.Random(20261102)
        fields = {'oneway': ('yes', 'no', '-1', 'bad'), 'motorcar': ('yes', 'no', 'designated'), 'access:forward': ('yes', 'no'),
                  'maxspeed': ('45 mph', '60', '0', 'signals'), 'maxspeed:backward': ('30', '40 kph', 'bad'),
                  'motor_vehicle:lanes': ('yes|no',), 'access:conditional': ('yes @ Mo',), 'ferry': ('yes', 'no'), 'ford': ('', 'no')}
        for _ in range(5000):
            props = {'highway': rng.choice(POLICY['roles'])}
            for key, values in fields.items():
                if rng.randrange(6) == 0:
                    props[key] = rng.choice(values)
            self.way(props)

    def test_seeded_node_metadata_combinations(self):
        rng = random.Random(20261103)
        fields = {'barrier': ('gate', 'bollard', 'lift_gate', ''), 'motorcar': ('yes', 'no', 'designated'), 'access': ('yes', 'no', 'designated'),
                  'highway': ('traffic_signals', 'crossing'), 'locked': ('yes', 'no'), 'width': ('4',), 'motor_vehicle:forward': ('yes', 'no')}
        for _ in range(1000):
            props = {key: rng.choice(values) for key, values in fields.items() if rng.randrange(3) == 0}
            self.node(props)
