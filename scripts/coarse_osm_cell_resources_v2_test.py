"""Retained allocation, files, namespace and write ownership are independent limits."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import coarse_osm_cell_resources_v2 as cell
from coarse_timing_input import PilotError


class Tests(unittest.TestCase):
    def test_both_stopped_index_and_prefix_are_included_in_retained_reservation(self):
        self.assertEqual(cell.RETAINED,55406628967);self.assertEqual(cell.OWNED,13044412313)
        self.assertEqual(cell.RETAINED+cell.OWNED+cell.TMP,cell.TOTAL)

    def resource(self,root):
        tmp=root/'tmp';tmp.mkdir();return cell.CellResources(root,tmp=tmp)

    def test_physical_projected_allocation_cannot_spend_retained_bytes(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);resources=self.resource(root)
            with patch.object(cell,'resource_metrics',return_value={}):
                resources.check(force=True)
                with self.assertRaises(PilotError):resources.check(force=True,projected=cell.OWNED)

    def test_tmp_and_namespace_caps_remain_separate(self):
        with tempfile.TemporaryDirectory() as name:
            resources=self.resource(Path(name));normal={'logicalBytes':0,'allocatedBytes':0,'entries':1,'conservativeAllocatedBytes':1048576}
            for tmp in [normal|{'allocatedBytes':cell.TMP+1},normal|{'entries':4096}]:
                with patch.object(cell,'owned_usage',side_effect=[normal,tmp]):
                    with self.assertRaises(PilotError):resources.check(force=True)

    def test_storage_refuses_outside_paths_and_existing_output(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);resources=self.resource(root);storage=cell.CellStorage(root,resources)
            with patch.object(cell,'resource_metrics',return_value={}):
                storage.write(root/'owned',b'bounded')
                with self.assertRaises(PilotError):storage.write(root/'owned',b'overwrite')
                with self.assertRaises(PilotError):storage.write(root.parent/'outside',b'not owned')

    def test_expired_worker_deadline_fails_before_metrics(self):
        with tempfile.TemporaryDirectory() as name:
            resources=self.resource(Path(name));resources.began-=resources.seconds+1
            with self.assertRaises(PilotError):resources.check(force=True)
