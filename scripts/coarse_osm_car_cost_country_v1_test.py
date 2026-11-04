"""Required-input regressions before any expensive source or coordinate I/O."""
from copy import deepcopy
import unittest

from coarse_osm_car_cost_country_v1 import ARTIFACT_SHA, COMPARISONS, EXPECTED, REFERENCES, RELATION_NODES, SCAN, SOURCE, TAGS, required_mounts, validate
from coarse_timing_input import PilotError


class Tests(unittest.TestCase):
    def plan(self):
        return {'phase': 'national_native_car_cost_facts_v1', 'sourceDescription': deepcopy(SOURCE), 'scanCaps': deepcopy(SCAN),
                'artifactSha256': ARTIFACT_SHA, 'topology': {'references': list(REFERENCES), 'tags': list(TAGS),
                'relationNodes': RELATION_NODES, 'expected': dict(EXPECTED)}, 'mounts': required_mounts(),
                'hostFiles': {name: '0'*64 for name in required_mounts() if name != SOURCE['path']}}

    def test_complete_plan_has_all32_streams_and_reference_inputs(self):
        plan = self.plan();validate(plan)
        self.assertEqual(len(REFERENCES)+len(TAGS)+1, 32)

    def test_every_comparison_input_is_required_before_source(self):
        for name in COMPARISONS:
            plan = self.plan();del plan['mounts'][name]
            with self.assertRaises(PilotError):validate(plan)

    def test_every_typed_stream_binding_and_seal_is_required(self):
        for name in REFERENCES+TAGS+[RELATION_NODES]:
            for field in ('mounts', 'hostFiles'):
                plan = self.plan();del plan[field][name]
                with self.assertRaises(PilotError):validate(plan)

    def test_wrong_source_description_or_caps_rejects(self):
        for field, key in (('sourceDescription', 'sha256'), ('sourceDescription', 'state'), ('scanCaps', 'scanNodesPerPass')):
            plan = self.plan();plan[field][key] = 'wrong'
            with self.assertRaises(PilotError):validate(plan)

    def test_wrong_native_artifact_or_topology_denominator_rejects(self):
        plan = self.plan();plan['artifactSha256'] = '0'*64
        with self.assertRaises(PilotError):validate(plan)
        plan = self.plan();plan['topology']['expected']['selected'] -= 1
        with self.assertRaises(PilotError):validate(plan)

    def test_country_mount_and_no_extra_host_pbf_hash_pass(self):
        plan = self.plan();del plan['mounts'][SOURCE['path']]
        with self.assertRaises(PilotError):validate(plan)
        plan = self.plan();plan['hostFiles'][SOURCE['path']] = SOURCE['sha256']
        with self.assertRaises(PilotError):validate(plan)
