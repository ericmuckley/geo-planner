from importlib.util import find_spec
from pathlib import Path
import tempfile
import unittest

from sparse_select import close_parents, select_ids


class SparseSelectionTests(unittest.TestCase):
    def test_recursive_parent_closure_handles_cycles_and_reverse_order(self):
        self.assertEqual(close_parents({100}, {100: [99], 99: [98], 98: [100]}), {98, 99, 100})

    @unittest.skipUnless(find_spec("osmium"), "Pinned reader runs inside the sparse tools image")
    def test_any_node_boundary_membership_and_parent_restrictions_preserve_large_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, ids = Path(tmp) / "source.osm", Path(tmp) / "ids.txt"
            source.write_text('<osm version="0.6"><node id="1" lon="-2" lat="0"/><node id="14284658989" lon="0" lat="0"/>'
                '<way id="10"><nd ref="1"/><nd ref="14284658989"/><tag k="highway" v="residential"/></way>'
                '<relation id="99"><member type="relation" ref="100" role="via"/><tag k="type" v="restriction:motorcar"/></relation>'
                '<relation id="100"><member type="way" ref="10" role="from"/><tag k="type" v="restriction"/></relation></osm>')
            stats = select_ids(source, [-1, -1, 1, 1], ids)
            self.assertEqual(ids.read_text().splitlines(), ["w10", "r99", "r100"])
            self.assertEqual(stats["insideNodes"], 1)


if __name__ == "__main__": unittest.main()
