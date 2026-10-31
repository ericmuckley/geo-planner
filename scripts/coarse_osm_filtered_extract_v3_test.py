"""Native disk selection equals frozen four-pass output with separate audit state."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from coarse_osm_bulk import extract as reference_extract
from coarse_osm_country_screen_v1 import BoundedCodec,OwnedStorage
from coarse_osm_country_screen_v7 import NativeScreen
from coarse_osm_filtered_extract_v3 import extract
from coarse_osm_native_smoke import fixture_records,STATE
from coarse_osm_projector_v1 import EncodedIndex
import coarse_osm_projector_v1_test as prior
from coarse_osm_revalidated_index_v1 import SourceIndex
from coarse_osm_window_cells_v1 import Cells,SCALE
from coarse_osm_window_codec_v2 import Codec
from coarse_osm_window_masks_v1 import Masks

ARTIFACT=None
ENGINES=[]


def configure_native(path,sha):
    global ARTIFACT
    ARTIFACT=path,sha


def pins(path):return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in path.iterdir()}


class Tests(unittest.TestCase):
    def setUp(self):
        prior.Tests.setUp(self)
        self.config['proposedCaps']['pythonSelectionStateBytes']=64*1024**2
    directory=prior.Tests.directory
    pbf=prior.Tests.pbf

    def prepare(self):
        if ARTIFACT is None:self.skipTest('Compiled selected-ID V7target required')
        root=self.directory();codec=BoundedCodec(*ARTIFACT,row_budget=2000000);index=EncodedIndex(root/'fine',OwnedStorage(root),codec=codec,index_limit=1048576)
        for raw in fixture_records():
            if raw['type']=='node':index.add_xy(raw['id'],round(raw['lon']*SCALE),round(raw['lat']*SCALE))
        index.finish();index.close();return index.root,json.loads((index.root/'index.json').read_text())

    def run_native(self,*,source_rows=None,config=None,**options):
        fine,manifest=self.prepare();before=pins(fine);views=[];root=self.directory()
        engine=NativeScreen(*ARTIFACT);ENGINES.append(engine);proposal=deepcopy(self.config if config is None else config)
        grid=Cells(proposal['windows']);cells=Codec(*ARTIFACT,grid);masker=Masks(*ARTIFACT,grid)
        def factory(output,storage,*,codec,index_limit,replacing=None):
            view=SourceIndex(fine,codec,manifest,index_limit=index_limit,replacing=replacing);views.append(view);return view
        rows=list(fixture_records()) if source_rows is None else source_rows
        counts={kind:sum(r['type']==kind for r in rows) for kind in ['node','way','relation']}
        state=extract(self.pbf(rows),proposal,root,engine=engine,cell_codec=cells,masker=masker,expected_counts=counts,index_factory=factory,**options)
        self.assertEqual(pins(fine),before);self.assertFalse((root/'primary-index').exists());self.assertFalse((root/'audit-index').exists())
        return state,root,views

    def test_full_tiny_output_equals_frozen_four_pass_reference_and_inputs_are_preserved(self):
        state,root,views=self.run_native();self.assertEqual(state['status'],'passed_disk_selected_extraction_prototype',state.get('error'))
        reference=self.directory();old=reference_extract(lambda:iter(deepcopy(fixture_records())),self.config,reference,source_identity={'publisherStateUtc':STATE})
        self.assertEqual(old['status'],'extracted_publisher_file_analysis_pending')
        self.assertEqual((root/'elements.jsonl').read_bytes(),(reference/'elements.jsonl').read_bytes())
        self.assertEqual(hashlib.sha256((root/'elements.jsonl').read_bytes()).hexdigest(),'dd2315bf022fa0ebe4ac7db1fee38329d40fb5c87f2e236577627d73730d875c')
        self.assertEqual([v.report()['wholeFileVerificationPasses'] for v in views],[1,1])
        self.assertTrue(all(s['sealed'] and s['integrityOk'] and s['closed'] and s['objects']==4 for s in state['selectedStores']))

    def test_no_highway_source_still_gets_whole_fine_file_verification(self):
        rows=[r for r in fixture_records() if r['type']=='node'];state,root,views=self.run_native(source_rows=rows)
        self.assertEqual(state['status'],'passed_disk_selected_extraction_prototype',state.get('error'))
        self.assertEqual((root/'elements.jsonl').read_bytes(),b'');self.assertEqual([v.verification_passes for v in views],[1,1])

    def test_primary_way_digest_corruption_is_rejected(self):
        state,_,_=self.run_native(primary_hook=lambda s:s.set_way_hash(1,'0'*64))
        self.assertEqual(state['status'],'stopped');self.assertIn('way-field drift',state['error'])

    def test_materialized_raw_metadata_tampering_is_caught_by_independent_audit(self):
        def change(store):
            raw=store.raw(('way',1));raw['tags']['maxspeed']='99 mph';store.replace(('way',1),raw)
        state,_,_=self.run_native(materialized_hook=change)
        self.assertEqual(state['status'],'stopped');self.assertIn('independent output',state['error'])

    def test_extra_primary_hint_cannot_make_an_unselected_node_pass_audit(self):
        state,_,_=self.run_native(primary_hook=lambda s:s.add('a',('node',3)))
        self.assertEqual(state['status'],'stopped');self.assertIn('materialization count',state['error'])

    def test_selected_count_retained_bytes_and_output_caps_remain_hard_limits(self):
        for key,value in [('selectedUniqueTypedElements',2),('retainedNativeObjectBytes',1),('normalizedExtractBytes',1)]:
            config=deepcopy(self.config);config['proposedCaps'][key]=value
            state,_,_=self.run_native(config=config);self.assertEqual(state['status'],'stopped');self.assertFalse(state['independentAuditComplete'])
