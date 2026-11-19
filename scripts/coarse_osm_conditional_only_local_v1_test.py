import copy
import unittest

from coarse_osm_conditional_only_local_v1 import local_candidates
from coarse_osm_conditional_only_overlay_v1_test import inputs
from coarse_timing_input import PilotError


class Tests(unittest.TestCase):
    def test_only_original_local_contributors_selected_and_outside_certificate_retained(self):
        args = inputs()
        metadata, ports = args[3], args[4]
        outside = copy.deepcopy(metadata[0])
        outside['source']['id'] = 9
        outside['derived']['identity'] = '9'
        outside_port = copy.deepcopy(ports[0])
        outside_port.update(sourceRelationId='9', status='from-way-outside-major-facts', forbiddenPreArcPairs=[])
        all_meta, all_ports = metadata + [outside], ports + [outside_port]
        before = copy.deepcopy([all_meta, all_ports])
        result = local_candidates([metadata[0]['source']], {}, {}, all_meta, all_ports)
        self.assertEqual(result['metadata'], metadata)
        self.assertEqual(result['ports'], ports)
        self.assertEqual(result['closingRelations'], [{'sourceRelation': 7, 'closedWays': ['10', '20']}])
        self.assertEqual(result['outside'], [{'sourceRelationId': '9', 'portStatus': 'from-way-outside-major-facts', 'presentInRawSource': False}])
        self.assertEqual([all_meta, all_ports], before)

    def test_supported_certificate_without_original_contribution_cannot_change_local_closures(self):
        args = inputs()
        result = local_candidates([], {}, {}, args[3], args[4])
        self.assertEqual(result['metadata'], [])
        self.assertEqual(result['closingRelations'], [])
        self.assertEqual(result['outside'][0]['portStatus'], 'source-ports-supported')

    def test_duplicate_forged_identity_or_different_original_source_refuses(self):
        args = inputs()
        source = args[3][0]['source']
        with self.assertRaises(PilotError):
            local_candidates([source, source], {}, {}, args[3], args[4])
        changed = copy.deepcopy(source)
        changed['tags']['restriction:conditional'] = 'only_right_turn @ snow'
        with self.assertRaises(PilotError):
            local_candidates([changed], {}, {}, args[3], args[4])
        ports = copy.deepcopy(args[4])
        ports[0]['sourceRelationId'] = '8'
        with self.assertRaises(PilotError):
            local_candidates([source], {}, {}, args[3], ports)


if __name__ == '__main__':
    unittest.main()
