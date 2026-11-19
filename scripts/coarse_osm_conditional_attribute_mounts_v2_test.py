"""Regression for the preserved V1 nested fact-mount mismatch."""
import unittest
from coarse_osm_conditional_attribute_mounts_v2 import validate_fact_mounts


class MountLayoutTests(unittest.TestCase):
    def test_flat_complete_consumer_layout(self):
        validate_fact_mounts({str(i): '/facts/'+name for i, name in enumerate(['ways-0000.bin', 'ways-0001.bin', 'arcs-0000.bin', 'closures-0000.bin'])})

    def test_nested_missing_or_gapped_groups_refused(self):
        valid = {name: '/facts/'+name+'-0000.bin' for name in ['ways', 'arcs', 'closures']}
        for broken in [{k: v.replace('/facts/', '/facts/cost-facts/') for k, v in valid.items()},
                       {k: v for k, v in valid.items() if k != 'ways'},
                       valid | {'ways': '/facts/ways-0001.bin'}]:
            with self.assertRaises(ValueError):
                validate_fact_mounts(broken)


if __name__ == '__main__':
    unittest.main()
