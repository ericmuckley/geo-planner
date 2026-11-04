"""Owned streaming, finite caps and independent end-to-end typed spool controls."""
from pathlib import Path
import struct
import tempfile
import unittest

import coarse_osm_footprint_v1_test as prior
from coarse_osm_topology_kernel_v1 import Kernel,REF
from coarse_osm_topology_kernel_v1_test import occurrence_rows,oracle
from coarse_osm_topology_stream_v1 import Streams,CAPS
from coarse_timing_input import PilotError

ARTIFACT=None


class Tests(unittest.TestCase):
    def setUp(self):
        if ARTIFACT is None:self.skipTest('Explicit target topology artifact required')
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.kernel=Kernel(*ARTIFACT)
    def stream(self,**caps):
        c=dict(CAPS,references=8,ways=3,taggedNodes=10,relationNodes=2,relationWays=2,chunkReferences=2,fileBytes=64,ownedBytes=33554432)|caps
        return Streams(self.root/'streams',self.kernel,c)
    def test_exact_chunked_spools_match_independent_graph_partition(self):
        ways={1:[1,2,3],2:[3,4,5],3:[8,8]};tags=[1,2,6,7,8,10,11,12,13,999];s=self.stream()
        s.accept(10,struct.pack('<10Q',*tags));s.accept(11,b''.join(REF.pack(*r) for r in occurrence_rows(ways)));s.accept(12,struct.pack('<2Q',4,333));s.accept(13,struct.pack('<2Q',999,2))
        report=s.finish();self.addCleanup(s.close)
        for k,v in oracle(ways,tags,[4,333],[2,999]).items():self.assertEqual(report['counts'][k],v)
        self.assertEqual(report['streams']['refs']['parts'],4);self.assertEqual(report['streams']['tagged']['parts'],2)
        self.assertEqual(sum(v['bytes'] for v in report['artifacts'].values()),report['writtenBytes'])
    def test_emitted_count_cap_and_missing_final_counts_stop(self):
        s=self.stream(references=1)
        with self.assertRaises(PilotError):s.accept(11,REF.pack(1,1,1,1)*2)
        with self.assertRaises(PilotError):s.finish()
        s.close()
    def test_fresh_paths_escape_overwrite_and_owned_byte_cap(self):
        s=self.stream();s.write('one',b'ab')
        for name,raw in (('one',b'a'),('../escape',b'a'),('big',b'a'*65)):
            with self.assertRaises(PilotError):s.write(name,raw)
        with self.assertRaises(PilotError):Streams(s.root,self.kernel,s.caps)
        s.close()
    def test_invalid_wire_width_and_sorted_kernel_records_stop(self):
        s=self.stream()
        for event,raw in ((11,b'a'),(10,b'a'),(14,b'12345678')):
            with self.assertRaises(PilotError):s.accept(event,raw)
        with self.assertRaises(PilotError):s.accept(11,REF.pack(0,1,1,1)*2)
        s.close()
    def test_callback_deadline_stops_before_mutating_files(self):
        def expired():raise PilotError('stream deadline')
        s=Streams(self.root/'streams',self.kernel,dict(CAPS),expired)
        with self.assertRaisesRegex(PilotError,'stream deadline'):s.accept(10,struct.pack('<Q',1))
        self.assertEqual(list(s.root.iterdir()),[]);s.close()
    test_cleanup_refuses_unrelated_worker=prior.ControllerTests.test_cleanup_refuses_unrelated_worker
    test_exclusive_output_rejects_overwrite_escape_symlink_and_size=prior.ControllerTests.test_exclusive_output_rejects_overwrite_escape_symlink_and_size
    def test_new_controller_isolation_and_caps_are_finite(self):
        from run_osm_topology_v1 import CAPS as c,SOURCE,SCAN,FLAGS,IMAGE,OUTPUTS,ASSET_ROOT,HEADERS,validate
        plan={'stage':'build','phase':'native_national_topology_v1','caps':c,'source':SOURCE,'scanCaps':SCAN,'image':IMAGE,'flags':FLAGS,'output':OUTPUTS['build'],'network':'none','imagePull':'never','mounts':{},'inputs':{},'rootfs':{'path':ASSET_ROOT},'headers':{k:{'path':v} for k,v in HEADERS.items()}}
        validate(plan)
        with self.assertRaises(PilotError):validate(plan|{'caps':{}})
        self.assertLess(c['priorRetainedReserveBytes']+sum(c['ownedBytes'].values())+c['tmpBytes'],c['overallRetainedBytes'])
