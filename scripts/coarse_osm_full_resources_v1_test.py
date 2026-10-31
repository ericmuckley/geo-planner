"""Physical/source provenance and aggregate/per-pass boundary controls."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import coarse_osm_full_resources_v1 as full
from coarse_osm_country_screen_v6 import NativeScreen
from coarse_osm_records import canonical
from coarse_timing_input import PilotError


class Checks:
    def __init__(self):self.calls=[]
    def check(self,**kwargs):self.calls.append(kwargs)


class Tests(unittest.TestCase):
    def storage(self,root):
        raw=b'owned fixture';manifest={'shards':[{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}],
                                    'directory':{'bytes':3,'sha256':hashlib.sha256(b'dir').hexdigest()}}
        return full.BoundIndexStorage(root,Checks(),manifest),raw,manifest

    def test_aggregate_visit_budget_is_clamped_per_call_without_mutating_input(self):
        instance=object.__new__(full.FullScreen);caps={'scanObjectVisitsTotal':2*full.MAX_VISITS}
        with patch.object(NativeScreen,'scan',return_value='sentinel') as call:
            self.assertEqual(instance.scan('fixture','stamp',caps), 'sentinel')
        self.assertEqual(caps['scanObjectVisitsTotal'],2*full.MAX_VISITS)
        self.assertEqual(call.call_args.args[2]['scanObjectVisitsTotal'],full.MAX_VISITS)

    def test_expected_source_shard_and_catalog_are_enforced_before_write(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);(root/'primary-index').mkdir();storage,raw,manifest=self.storage(root)
            with self.assertRaises(PilotError):storage.write(root/'primary-index/00000000.bin',b'wrong')
            self.assertFalse((root/'primary-index/00000000.bin').exists())
            storage.write(root/'primary-index/00000000.bin',raw)
            with self.assertRaises(PilotError):storage.write(root/'primary-index/index.json',b'{}\n')
            storage.write(root/'primary-index/index.json',canonical(manifest)+b'\n')

    def test_missing_numbered_shards_and_wrong_namespace_are_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);(root/'primary-index').mkdir();(root/'other').mkdir();storage,raw,_=self.storage(root)
            for path in [root/'primary-index/00000001.bin',root/'other/00000000.bin',root.parent/'outside.bin']:
                with self.assertRaises(PilotError):storage.write(path,raw)

    def test_only_owned_primary_payloads_can_be_removed(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);(root/'primary-index').mkdir();(root/'audit-index').mkdir();storage,raw,_=self.storage(root)
            storage.write(root/'primary-index/00000000.bin',raw);storage.write(root/'audit-index/00000000.bin',raw)
            with self.assertRaises(PilotError):storage.remove(root/'audit-index/00000000.bin',len(raw))
            storage.remove(root/'primary-index/00000000.bin',len(raw));self.assertEqual(storage.shard_removals,1)

    def resource(self,root):
        (root/'tmp').mkdir();return full.FullResources(root,tmp=root/'tmp')

    def test_retained_reservation_cannot_be_reused_for_owned_output(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);resource=self.resource(root)
            with patch.object(full,'resource_metrics',return_value={}):
                resource.check(force=True)
                with self.assertRaises(PilotError):resource.check(force=True,projected=full.OWNED_LIMIT)
            self.assertEqual(full.OWNED_LIMIT+full.TMP+full.RETAINED,full.RETAINED_WORK_LIMIT)

    def test_namespace_overflow_and_temporary_allocation_are_guarded(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);resource=self.resource(root)
            normal={'logicalBytes':0,'allocatedBytes':0,'entries':1,'conservativeAllocatedBytes':1048576}
            too_many=normal|{'entries':4096};too_large=normal|{'allocatedBytes':full.TMP+1}
            for second in (too_many,too_large):
                with patch.object(full,'owned_usage',side_effect=[normal,second]):
                    with self.assertRaises(PilotError):resource.check(force=True)
