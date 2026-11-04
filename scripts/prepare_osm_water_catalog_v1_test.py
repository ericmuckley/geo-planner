"""Tiny complete saved-coordinate/GPF/chain/polygon controls, no real source."""
from array import array
import copy
import gzip
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

from analyze_osm_water_endpoints_v1 import analyze
from assemble_osm_water_polygons_v1 import assemble,audit_source_geometry,audit_saved,FEATURE,RING,POINT
from coarse_osm_country_wire_v4 import framed_records
from coarse_osm_water_catalog_v1 import WaterCatalog
from coarse_osm_water_catalog_v1_test import frame
from coarse_osm_water_coordinate_codec_v1 import encode_rows
from coarse_osm_water_reference_store_v1 import Budget,Shards
from prepare_osm_water_catalog_v1 import load_catalog

ARTIFACT=None
COORDINATE_ARTIFACT=None


def store(root,prefix,raw):
    writer=Shards(root,prefix,Budget(1048576))
    try:
        for p in range(0,len(raw),1048576):writer.write(raw[p:p+1048576])
        return writer.finish()
    finally:writer.close()


def fixture(root):
    points=[(1,0,0),(2,100,0),(3,100,100),(4,0,100),(5,20,20),(6,40,20),(7,40,40),(8,20,40),(9,200,0),(10,220,0),(11,200,20)]
    ways=[(10,[1,2,3,4,1],{'natural':'water'}),(20,[5,6,7,8,5],{'natural':'water'}),
          (30,[9,10,11,9],{'landuse':'reservoir'}),(40,[9,10],{'natural':'water'})]
    raw=b''.join(struct.pack('<I',len(b))+b for b in (frame(*row) for row in ways))
    way_report=store(root,'tiny-ways',raw);index_report=store(root,'tiny-ids',b''.join(struct.pack('<Q',p[0]) for p in points))
    encoded=b''.join(encode_rows(points));encoded_report=store(root,'tiny-coordinates',encoded)
    shadow=b''.join(struct.pack('<Qii',*p) for p in points)
    missing=store(root,'tiny-missing',b'')
    coordinates={'coordinates':{'capture':{'requested':11,'present':11,'missing':0,'encodedBytes':len(encoded),'canonicalBytes':176,'missingBytes':0,'complete':1,'reserved7':0},
                               'stored':{'encoded':encoded_report,'missing':missing,'sourceShadow':{'bytes':176,'sha256':hashlib.sha256(shadow).hexdigest()}}}}
    references={'water':{'referenceCapture':{'ways':4,'references':16},'referenceStore':{'ways':way_report,'nodes':index_report}}}
    roots=[{'id':100,'tags':{'type':'multipolygon'},'members':[{'type':'way','ref':10,'role':'outer'},{'type':'way','ref':20,'role':'inner'}]},
           {'id':102,'tags':{'type':'multipolygon'},'members':[{'type':'way','ref':999,'role':'outer'}]}]
    with gzip.open(root/'tiny-roots.gz','wb') as f:f.write(b''.join((json.dumps(r)+'\n').encode() for r in roots))
    with gzip.open(root/'tiny-desc.gz','wb') as f:f.write(b'')
    members=array('Q',[10,20,999]);endpoint_root=root/'endpoints';endpoint_root.mkdir()
    endpoints=analyze(endpoint_root,root,way_report,members,[(True,root/'tiny-roots.gz'),(False,root/'tiny-desc.gz')])
    return references,coordinates,members,endpoint_root,endpoints


class PipelineControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if ARTIFACT is None or COORDINATE_ARTIFACT is None:raise unittest.SkipTest('Qualified Linux catalog and coordinate artifacts required')
        cls.catalog=WaterCatalog(*ARTIFACT)

    def setUp(self):self.catalog.release()
    def tearDown(self):self.catalog.release()

    def test_complete_saved_data_to_polygon_pipeline_preserves_hole(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);references,coordinates,members,endroot,endpoints=fixture(root)
            loaded,ids,counts=load_catalog(self.catalog,COORDINATE_ARTIFACT,root,references,root,coordinates)
            self.assertEqual(loaded['statistics']['nodes'],11);self.assertTrue(loaded['coordinates']['independentDecoderReleasedBeforeWays'])
            out=root/'polygons';out.mkdir();result=assemble(out,self.catalog,ids,counts,members,endroot,endpoints)
            self.assertEqual((result['acceptedFeatures'],result['acceptedRings'],result['sourcePointsIndependentlyReplayed'],result['diagnosticsReopened']),(2,3,14,6))
            self.assertEqual(result['statusCounts']['1']['source_member_way_not_independent_water_polygon'],2)
            self.assertEqual(result['statusCounts']['2']['source_chain_missing_way_member'],1)

    def test_wrong_source_shadow_and_missing_coordinate_rejected(self):
        for mode in ('shadow','missing','way-count'):
            self.catalog.release()
            with tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);references,coordinates,*_=fixture(root)
                if mode=='shadow':coordinates['coordinates']['stored']['sourceShadow']['sha256']='0'*64
                elif mode=='missing':coordinates['coordinates']['capture']['missing']=1
                else:references['water']['referenceCapture']['ways']=5
                with self.assertRaises(Exception):load_catalog(self.catalog,COORDINATE_ARTIFACT,root,references,root,coordinates)

    def test_independent_output_replay_rejects_coordinate_edge_role_corruption(self):
        source=[(0,[(1,0,0),(2,20,0),(3,0,20),(1,0,0)])]
        valid=[{'role':0,'parent':0,'nodes':source[0][1]}]
        self.assertEqual(audit_source_geometry(source,valid),4)
        for mode in ('coordinate','edge','role','parent'):
            bad=copy.deepcopy(valid)
            if mode=='coordinate':bad[0]['nodes'][1]=(2,21,0)
            elif mode=='edge':bad[0]['nodes'].insert(2,(1,0,0))
            elif mode=='role':bad[0]['role']=1
            else:bad[0]['parent']=1
            with self.assertRaises(Exception):audit_source_geometry(source,bad)

    def test_saved_output_structure_and_shard_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            raw=FEATURE.pack(1,30,1)+RING.pack(0,1,4)+b''.join(POINT.pack(*p) for p in [(1,0,0),(2,10,0),(3,0,10),(1,0,0)])
            report=store(root,'bad-parent',raw)
            with self.assertRaises(Exception):audit_saved(root,report,1,1,4,lambda:None)
            path=root/report['parts'][0]['name'];path.write_bytes(path.read_bytes()[:-1])
            with self.assertRaises(Exception):audit_saved(root,report,1,1,4,lambda:None)

    def test_wrong_complete_id_partition_and_truncated_encoded_source_rejected(self):
        for mode in ('ids','coordinates'):
            self.catalog.release()
            with tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);references,coordinates,*_=fixture(root)
                if mode=='ids':references['water']['referenceStore']['nodes']=store(root,'wrong-ids',struct.pack('<11Q',*range(1,11),99))
                else:
                    report=coordinates['coordinates']['stored']['encoded'];path=root/report['parts'][0]['name'];path.write_bytes(path.read_bytes()[:-1])
                with self.assertRaises(Exception):load_catalog(self.catalog,COORDINATE_ARTIFACT,root,references,root,coordinates)


if __name__=='__main__':unittest.main()
