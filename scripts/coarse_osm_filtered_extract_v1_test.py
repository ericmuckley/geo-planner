"""Filtered two-pass output equals four-pass reference; no missing geometry shortcuts."""
from copy import deepcopy
import json
from collections import Counter
from coarse_osm_window_cells_v1 import Cells
from coarse_osm_window_codec_v1 import Codec
from coarse_osm_window_masks_v1 import Masks
import os
from pathlib import Path
import random
import unittest

from coarse_osm_bulk import extract as reference_extract
from coarse_osm_bulk_audit import crossing
from coarse_osm_filtered_extract_v1 import extract,primary_windows
from coarse_osm_country_screen_v6 import NativeScreen
from coarse_osm_native_smoke import fixture_records,STATE
import coarse_osm_projector_v1_test as prior
from coarse_osm_records import intersects

ARTIFACT=None
ENGINES=[]
MEMORY_CASES=[]
CODECS=[]
MASKERS=[]


def configure_native(path,sha):
    global ARTIFACT
    ARTIFACT=(path,sha)


class GeometryTests(unittest.TestCase):
    def test_conservative_envelope_never_discards_crossing_or_touching(self):
        rng=random.Random(69215)
        cases=[[[-1,.5],[2,.5]],[[-1,0],[2,0]],[[0,0],[0,1]],[[0,0],[0,0]]]
        cases += [[[rng.randint(-20,20)/10,rng.randint(-20,20)/10] for _ in range(rng.randint(2,6))] for _ in range(300)]
        windows=[{'id':1,'bbox':[0,0,1,1]},{'id':2,'bbox':[-1,-1,0,0]}]
        for points in cases:
            candidates=primary_windows(points,windows)
            for window in windows:
                if intersects(points,window['bbox']) or crossing(points,window['bbox']):self.assertIn(window,candidates)


class NativeTests(unittest.TestCase):
    setUp=prior.Tests.setUp
    directory=prior.Tests.directory
    pbf=prior.Tests.pbf

    def engine(self):
        if ARTIFACT is None:self.skipTest('Compiled V6 target required')
        instance=NativeScreen(*ARTIFACT);ENGINES.append(instance);return instance

    def components(self):
        if ARTIFACT is None:self.skipTest('Compiled window mask target required')
        codec=Codec(*ARTIFACT,Cells(self.config['windows']));masker=Masks(*ARTIFACT,codec.cells)
        CODECS.append(codec);MASKERS.append(masker);return codec,masker

    def run_extract(self,rows=None,**kwargs):
        root=self.directory();path=self.pbf(rows)
        actual=rows if rows is not None else fixture_records()
        codec,masker=self.components()
        counts=Counter(row['type'] for row in actual)
        result=extract(path,self.config,root,engine=self.engine(),cell_codec=codec,masker=masker,expected_counts={kind:counts[kind] for kind in ('node','way','relation')},**kwargs)
        return result,root

    def test_complete_output_equals_independent_four_pass_reference(self):
        rows=fixture_records();result,root=self.run_extract(rows)
        reference_root=self.directory()
        expected=reference_extract(lambda:iter(deepcopy(rows)),self.config,reference_root,source_identity={'publisherStateUtc':STATE})
        self.assertEqual(expected['status'],'extracted_publisher_file_analysis_pending')
        self.assertEqual(result['status'],'passed_cell_filtered_extraction_prototype',result.get('error'))
        self.assertEqual((root/'elements.jsonl').read_bytes(),(reference_root/'elements.jsonl').read_bytes())
        self.assertEqual(result['scanObjectVisits'],18)
        self.assertEqual(result['nativeReceipts'][0]['selectedNodeProjections'],0)
        self.assertEqual(result['nativeReceipts'][1]['selectedNodeProjections'],2)
        self.assertFalse(list((root/'primary-index').glob('[0-9]*.bin')))
        self.assertEqual([row['fineReferences'] for row in result['coarseLookups']],[2,2])
        self.assertEqual([row['examinedReferences'] for row in result['coarseLookups']],[4,4])
        objects=[json.loads(line)['element'] for line in (root/'elements.jsonl').read_text().splitlines()]
        relation=next(row for row in objects if row['type']=='relation' and row['id']==1)
        self.assertEqual(relation['members'][-1]['ref'],999)

    def test_valid_large_transient_batch_does_not_consume_selected_retention_budget(self):
        base=fixture_records()[4];base['tags']=base['tags']|{f'foo{i}':'bar' for i in range(5)}
        rows=fixture_records()[:4]+[dict(base,id=i+1,nodes=[3,4]) for i in range(32768)]
        self.config['proposedCaps'].update(scanWaysPerPass=40000,retainedNativeObjectBytes=64*1024**2)
        result,root=self.run_extract(rows)
        self.assertEqual(result['status'],'passed_cell_filtered_extraction_prototype',result.get('error'))
        self.assertEqual(result['retainedElements'],0)
        self.assertEqual((root/'elements.jsonl').read_bytes(),b'')
        self.assertGreater(result['liveBatchConservativeHeapPeakBytes'],64*1024**2)
        self.assertLessEqual(result['liveBatchConservativeHeapPeakBytes'],128*1024**2)
        MEMORY_CASES.append({key:result[key] for key in ('liveBatchConservativeHeapPeakBytes','liveBatchHeapLimitBytes','retainedElements','scanObjectVisits')})

    def test_missing_extra_membership_and_way_hash_hints_fail(self):
        for damage in ('missing','extra','membership','hash'):
            def corrupt(primary):
                if damage=='missing':
                    primary.keys.remove(('node',2))
                    for members in primary.members.values():members.discard(('node',2))
                elif damage=='extra':primary.add('a',('node',3))
                elif damage=='membership':primary.members['a'].remove(('way',1))
                else:primary.ways[1]='not-the-field-hash'
            result,_=self.run_extract(primary_hook=corrupt)
            self.assertEqual(result['status'],'stopped',damage)
            self.assertFalse(result['independentAuditComplete'])

    def test_corrupt_old_shard_is_never_removed_during_rebuild(self):
        root=self.directory();path=self.pbf();old=root/'primary-index/00000000.bin'
        def corrupt():
            before=old.stat();raw=bytearray(old.read_bytes());raw[-1]^=1;old.write_bytes(raw)
            os.utime(old,ns=(before.st_atime_ns,before.st_mtime_ns))
        codec,masker=self.components()
        result=extract(path,self.config,root,engine=self.engine(),cell_codec=codec,masker=masker,expected_counts={'node':4,'way':3,'relation':2},before_second=corrupt)
        self.assertEqual(result['status'],'stopped');self.assertTrue(old.exists())

    def test_unselected_source_metadata_drift_is_detected(self):
        root=self.directory();path=self.pbf()
        def change():
            rows=fixture_records();rows[2]['tags']={'changed':'unselected'}
            other=self.pbf(rows);path.write_bytes(other.read_bytes())
        codec,masker=self.components()
        result=extract(path,self.config,root,engine=self.engine(),cell_codec=codec,masker=masker,expected_counts={'node':4,'way':3,'relation':2},before_second=change)
        self.assertEqual(result['status'],'stopped');self.assertIn('source byte drift',result['error'])

    def test_missing_road_geometry_stops_even_outside_windows(self):
        rows=fixture_records();rows[5]['nodes']=[3,999]
        result,_=self.run_extract(rows)
        self.assertEqual(result['status'],'stopped');self.assertIn('missing node',result['error'])

    def test_materialized_metadata_tamper_fails_independent_output(self):
        def corrupt(primary):primary.objects[('node',2)]['lon']=.75
        result,_=self.run_extract(materialized_hook=corrupt)
        self.assertEqual(result['status'],'stopped');self.assertIn('mismatch',result['error'])

    def test_bad_unselected_metadata_cannot_be_hidden(self):
        rows=fixture_records();rows[2]['timestamp']='2027-01-01T00:00:00Z'
        result,_=self.run_extract(rows)
        self.assertEqual(result['status'],'stopped');self.assertFalse(result['lastNativeReceipt']['nativeEof'])

    def test_independent_audit_detects_a_false_primary_rejection(self):
        root=self.directory();path=self.pbf();codec,masker=self.components()
        for i in range(len(masker.table)):masker.table[i]=15
        result=extract(path,self.config,root,engine=self.engine(),cell_codec=codec,masker=masker,expected_counts={'node':4,'way':3,'relation':2})
        self.assertEqual(result['status'],'stopped');self.assertFalse(result['independentAuditComplete'])

    def test_changed_bank_file_is_rejected_before_whole_capture_success(self):
        root=self.directory();path=self.pbf();codec,masker=self.components();damaged=[]
        def check():
            part=root/'all-highway-primary-selection-cells/0000.bin'
            if part.exists() and not damaged:
                raw=bytearray(part.read_bytes());raw[-1]^=1;part.write_bytes(raw);damaged.append(True)
        result=extract(path,self.config,root,engine=self.engine(),cell_codec=codec,masker=masker,expected_counts={'node':4,'way':3,'relation':2},check=check)
        self.assertTrue(damaged);self.assertEqual(result['status'],'stopped')

    def test_expected_counts_cannot_omit_unselected_source_objects(self):
        root=self.directory();path=self.pbf();codec,masker=self.components()
        result=extract(path,self.config,root,engine=self.engine(),cell_codec=codec,masker=masker,expected_counts={'node':4,'way':2,'relation':2})
        self.assertEqual(result['status'],'stopped');self.assertFalse(result['independentAuditComplete'])
