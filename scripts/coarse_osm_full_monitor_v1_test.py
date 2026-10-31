"""Reproduce checkpoint rename races without national input or Docker."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from coarse_osm_country_screen_v1 import owned_usage as legacy
from coarse_osm_full_monitor_v1 import owned_usage
from coarse_timing_input import PilotError


class Tests(unittest.TestCase):
    def test_atomic_checkpoint_disappearance_reproduces_old_monitor_failure(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);partial=root/'state.json.partial';partial.write_bytes(b'next')
            is_file=Path.is_file;is_dir=Path.is_dir
            with patch.object(Path,'is_file',lambda p:False if p==partial else is_file(p)),patch.object(Path,'is_dir',lambda p:False if p==partial else is_dir(p)):
                with self.assertRaisesRegex(PilotError,'Screen owned file kind'):legacy(root)

    def test_rename_during_one_metadata_snapshot_is_tolerated(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);target=root/'state.json';target.write_bytes(b'old');partial=root/'state.json.partial';partial.write_bytes(b'new')
            original=Path.lstat;moved=[]
            def snapshot(path,*args,**kwargs):
                if path==partial and not moved:partial.replace(target);moved.append(True)
                return original(path,*args,**kwargs)
            with patch.object(Path,'lstat',snapshot):usage=owned_usage(root)
            self.assertTrue(moved);self.assertEqual(target.read_bytes(),b'new');self.assertEqual(usage['logicalBytes'],3)
            self.assertGreaterEqual(usage['conservativeAllocatedBytes'],usage['allocatedBytes']+1048576)

    def test_stable_sample_matches_original_physical_and_logical_accounting(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);(root/'index').mkdir();(root/'index/00000000.bin').write_bytes(b'x'*32769)
            self.assertEqual(owned_usage(root),legacy(root))

    def test_special_symlink_and_hardlink_outputs_remain_rejected(self):
        for kind in ('symlink','hardlink','fifo'):
            with tempfile.TemporaryDirectory() as name:
                root=Path(name);source=root/'source';source.write_bytes(b'fixture');path=root/'special'
                if kind=='symlink':path.symlink_to(source)
                elif kind=='hardlink':os.link(source,path)
                else:os.mkfifo(path)
                with self.assertRaises(PilotError):owned_usage(root)

    def test_missing_owned_root_is_never_ignored(self):
        with tempfile.TemporaryDirectory() as name:
            with self.assertRaisesRegex(PilotError,'root disappeared'):owned_usage(Path(name)/'missing')
