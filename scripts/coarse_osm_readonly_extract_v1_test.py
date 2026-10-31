"""Tiny whole-source extraction revalidates an existing input without new fine writes."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import unittest

from coarse_osm_bulk import extract as reference_extract
from coarse_osm_country_screen_v1 import BoundedCodec,OwnedStorage
from coarse_osm_country_screen_v6 import NativeScreen
from coarse_osm_filtered_extract_v1 import extract
from coarse_osm_native_smoke import fixture_records,STATE
from coarse_osm_projector_v1 import EncodedIndex
import coarse_osm_projector_v1_test as prior
from coarse_osm_revalidated_index_v1 import SourceIndex
from coarse_osm_window_cells_v1 import Cells,SCALE
from coarse_osm_window_codec_v1 import Codec
from coarse_osm_window_masks_v1 import Masks

ARTIFACT=None
ENGINES=[]
CODECS=[]
CELL_CODECS=[]
MASKERS=[]


def configure_native(path,sha):
    global ARTIFACT
    ARTIFACT=path,sha


def pins(root):return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()}


class NativeTests(unittest.TestCase):
    setUp=prior.Tests.setUp
    directory=prior.Tests.directory
    pbf=prior.Tests.pbf

    def setup_input(self):
        if ARTIFACT is None:self.skipTest('Qualified native window-mask artifact required')
        root=self.directory();codec=BoundedCodec(*ARTIFACT,row_budget=2000000);CODECS.append(codec)
        index=EncodedIndex(root/'fine-input',OwnedStorage(root),codec=codec,index_limit=1048576)
        for row in fixture_records():
            if row['type']=='node':index.add_xy(row['id'],round(row['lon']*SCALE),round(row['lat']*SCALE))
        index.finish();index.close();return index.root,json.loads((index.root/'index.json').read_text())

    def run_readonly(self,path,source,manifest,**options):
        root=self.directory();engine=NativeScreen(*ARTIFACT);ENGINES.append(engine)
        grid=Cells(self.config['windows']);cells=Codec(*ARTIFACT,grid);masks=Masks(*ARTIFACT,grid);CELL_CODECS.append(cells);MASKERS.append(masks)
        views=[]
        def factory(output,storage,*,codec,index_limit,replacing=None):
            view=SourceIndex(source,codec,manifest,index_limit=index_limit,replacing=replacing);views.append(view);return view
        state=extract(path,self.config,root,engine=engine,cell_codec=cells,masker=masks,expected_counts={'node':4,'way':3,'relation':2},index_factory=factory,**options)
        return state,root,views

    def test_complete_output_equals_reference_and_all_input_bytes_remain_unchanged(self):
        source,manifest=self.setup_input();before=pins(source);path=self.pbf();state,root,views=self.run_readonly(path,source,manifest)
        self.assertEqual(state['status'],'passed_cell_filtered_extraction_prototype',state.get('error'))
        reference=self.directory();expected=reference_extract(lambda:iter(deepcopy(fixture_records())),self.config,reference,source_identity={'publisherStateUtc':STATE})
        self.assertEqual(expected['status'],'extracted_publisher_file_analysis_pending')
        self.assertEqual((root/'elements.jsonl').read_bytes(),(reference/'elements.jsonl').read_bytes())
        self.assertEqual(pins(source),before);self.assertEqual(len(views),2)
        self.assertTrue(all(view.finished and view.closed for view in views))
        self.assertEqual([view.report()['nodeRowsCompared'] for view in views],[4,4])
        self.assertEqual([view.report()['wholeFileVerificationPasses'] for view in views],[1,1])
        self.assertFalse((root/'primary-index').exists());self.assertFalse((root/'audit-index').exists())
        self.assertTrue(all(receipt['nativeEof'] for receipt in state['nativeReceipts']))

    def test_between_pass_input_drift_fails_without_repair_or_admission(self):
        source,manifest=self.setup_input();path=self.pbf();changed=[]
        def corrupt():
            part=source/'00000000.bin';before=part.stat();raw=bytearray(part.read_bytes());raw[-1]^=1;part.write_bytes(raw);os.utime(part,ns=(before.st_atime_ns,before.st_mtime_ns));changed.append(bytes(raw))
        state,root,views=self.run_readonly(path,source,manifest,before_second=corrupt)
        self.assertEqual(state['status'],'stopped');self.assertFalse(state['independentAuditComplete'])
        self.assertEqual((source/'00000000.bin').read_bytes(),changed[0]);self.assertFalse((root/'elements.jsonl').exists())

    def test_bad_non_node_source_record_prevents_whole_source_qualification(self):
        source,manifest=self.setup_input();before=pins(source);rows=fixture_records();rows[4]['timestamp']='2027-01-01T00:00:00Z'
        state,root,_=self.run_readonly(self.pbf(rows),source,manifest)
        self.assertEqual(state['status'],'stopped');self.assertFalse(state['independentAuditComplete'])
        self.assertEqual(pins(source),before);self.assertFalse((root/'elements.jsonl').exists())
