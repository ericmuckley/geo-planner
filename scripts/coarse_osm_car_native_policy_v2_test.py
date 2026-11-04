"""Reuse all original controls and exercise generic invalid-source isolation."""
import unittest

import coarse_osm_car_native_policy_v1_test as legacy
from coarse_osm_car_native_policy_v2 import NativePolicy
from coarse_osm_car_policy_v1 import restriction_policy as legacy_restriction
from coarse_osm_car_policy_v2 import restriction_policy
from coarse_timing_input import PilotError

ARTIFACT = None
WireTests = legacy.WireTests


class NativeTests(legacy.NativeTests):
    @classmethod
    def setUpClass(cls):
        if ARTIFACT is None:
            raise unittest.SkipTest('Run with the protected compiled V2 artifact')
        cls.native = NativePolicy(*ARTIFACT)

    def relation(self, props, members):
        expected = restriction_policy({'id': 1, 'tags': props, 'members': members})
        actual = self.native.classify('relation', props, members)
        for key in ('status', 'kind', 'fromWay', 'via', 'toWay', 'reason'):
            self.assertEqual(actual[key], expected.get(key, 0 if key in ('fromWay', 'via', 'toWay') else None))

    def test_unlocatable_unsupported_restriction_fails(self):
        # Override the V1 refusal expectation; preserve that producer/test unchanged.
        for members in ([], [{'type': 'relation', 'ref': 91, 'role': 'via'}]):
            tags = {'type': 'restriction', 'restriction': 'unknown'}
            record = {'id': 7, 'tags': tags, 'members': members}
            with self.assertRaises(PilotError):
                legacy_restriction(record)
            result = restriction_policy(record)
            self.assertEqual(result['status'], 'invalid-unlocatable')
            self.assertEqual((result['sourceTags'], result['sourceMembers']), (tags, members))
            self.relation(tags, members)

    def test_every_direct_node_or_way_keeps_conservative_closure(self):
        for kind in ('node', 'way'):
            for role in ('', 'from', 'via', 'to', 'unknown'):
                members = [{'type': 'relation', 'ref': 91, 'role': 'from'}, {'type': kind, 'ref': 72, 'role': role}]
                record = {'id': 8, 'tags': {'type': 'restriction', 'restriction': 'unknown'}, 'members': members}
                self.assertEqual(restriction_policy(record), legacy_restriction(record))
                self.assertEqual(restriction_policy(record)['status'], 'closed-unsupported')
                self.relation(record['tags'], members)

    def test_mode_exceptions_and_unrelated_empty_records_stay_unchanged(self):
        for tags in ({'type': 'route'}, {'type': 'restriction:bicycle'},
                     {'type': 'restriction', 'except': 'motorcar'}, {'type': 'restriction', 'restriction:bicycle': 'no_left_turn'}):
            record = {'id': 8, 'tags': tags, 'members': []}
            self.assertEqual(restriction_policy(record), legacy_restriction(record))
            self.relation(tags, [])

    def test_invalid_member_and_truncated_relation_wire_still_reject(self):
        from coarse_osm_car_native_policy_v1 import frame
        raw = frame('relation', {'type': 'restriction'}, [{'type': 'relation', 'ref': 91, 'role': 'from'}])
        for broken in (raw[:-1], raw+b'x', raw.replace((91).to_bytes(8, 'little'), bytes(8))):
            with self.assertRaises(PilotError):
                self.native.decode(broken)
