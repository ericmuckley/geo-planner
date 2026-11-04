from pathlib import Path
import random
import tempfile
import unittest

from coarse_osm_country_wire_v4 import framed_records
from coarse_osm_native_smoke import STATE
from coarse_osm_projector_v1 import reference_seal
from coarse_osm_water_census_v2_test import CAPS, way
from coarse_osm_water_union_v1 import WaterUnion
from coarse_timing_input import PilotError

ARTIFACT=None


def oracle(rows, ids):
    ways={r['id']:r for r in rows if r['type']=='way'}
    tagged={i for i,r in ways.items() if r['tags'].get('natural')=='water' or r['tags'].get('waterway')=='riverbank' or r['tags'].get('landuse')=='reservoir'}
    members=set(ids)&ways.keys();union=tagged|members
    def refs(keys):return sum(len(ways[i]['nodes']) for i in keys)
    return {'unionWays':len(union),'unionReferences':refs(union),
            'closedUnionWays':sum(ways[i]['nodes'][0]==ways[i]['nodes'][-1] for i in union),
            'openUnionWays':sum(ways[i]['nodes'][0]!=ways[i]['nodes'][-1] for i in union),
            'taggedWays':len(tagged),'taggedReferences':refs(tagged),'memberWaysFound':len(members),'memberWayReferences':refs(members),
            'taggedMemberOverlapWays':len(tagged&members),'taggedMemberOverlapReferences':refs(tagged&members),
            'memberOnlyWays':len(members-tagged),'memberOnlyReferences':refs(members-tagged),
            'maximumUnionWayReferences':max((len(ways[i]['nodes']) for i in union),default=0),
            'unionEncodedBytes':sum(len(framed_records([ways[i]]))-4 for i in union),'missingMemberWays':len(set(ids)-ways.keys()),
            'firstUnionWayId':min(union,default=0),'lastUnionWayId':max(union,default=0),'requestedMemberWays':len(ids),'complete':1,'reserved19':0}


class Tests(unittest.TestCase):
    def engine(self, ids=()):
        if ARTIFACT is None:self.skipTest('Explicit compiled union target artifact required')
        return WaterUnion(*ARTIFACT,member_ids=ids)

    def compare(self,rows,ids=(),proof=False):
        engine=self.engine(ids);engine.begin()
        try:
            receipt=engine.validate_frames(framed_records(rows),STATE,CAPS,proof=proof)
            actual=engine.finish()
            self.assertEqual(actual['union'],oracle(rows,ids))
            self.assertEqual(actual['missingMemberWayIds'],sorted(set(ids)-{r['id'] for r in rows if r['type']=='way'}))
            self.assertEqual(receipt['semanticSha256'],reference_seal(rows))
            return actual
        finally:engine.release()

    def test_tagged_and_untagged_member_union(self):
        self.compare([way(10,{'natural':'water'}),way(20,{}),way(30,{'landuse':'reservoir'}),way(40,{'water':'lake'})],[10,20,40])

    def test_missing_before_between_and_after_source_ways(self):
        self.compare([way(10,{}),way(20,{}),way(30,{})],[1,10,15,30,99])

    def test_empty_requested_set_equals_tagged_water(self):
        self.compare([way(10,{'waterway':'riverbank'}),way(20,{})])

    def test_only_nodes_and_empty_stream_keep_missing_ids(self):
        node={'type':'node','id':1,'version':1,'timestamp':STATE,'visible':True,'tags':{'natural':'water'},'lon':0.,'lat':0.}
        self.compare([node],[1,2]);self.compare([],[1])

    def test_one_hundred_generated_unfiltered_sets(self):
        rng=random.Random(20261104)
        for _ in range(100):
            rows=[way(i,{'natural':'water'} if rng.randrange(3)==0 else {},[1,2,3,1] if rng.randrange(2) else [1,2]) for i in range(10,50,2)]
            ids=sorted(rng.sample(range(1,60),rng.randrange(30)))
            self.compare(rows,ids)

    def test_proof_mode_counters_and_source_seal_match(self):
        rows=[way(10,{'natural':'water'}),way(20,{})]
        self.assertEqual(self.compare(rows,[20]),self.compare(rows,[20],True))

    def test_semantic_frame_crosses_one_megabyte_chunks(self):
        self.compare([way(10,{'natural':'water','note':'x'*1200000})],[10])

    def test_source_failure_and_finish_lifecycle_fail_closed(self):
        engine=self.engine([10]);other=self.engine();engine.begin()
        try:
            with self.assertRaises(PilotError):engine.finish()
            with self.assertRaises(PilotError):other.begin()
            with self.assertRaises(PilotError):engine.validate_frames(framed_records([way(10,{},[1,0])]),STATE,CAPS)
            with self.assertRaises(PilotError):engine.finish()
        finally:engine.release()

    def test_python_and_native_member_order_domain_guards(self):
        engine=self.engine()
        for ids in ([1,1],[2,1],[0],[-1],[2**63],[1.5],[True]):
            with self.subTest(ids=ids),self.assertRaises(PilotError):self.engine(ids)
        import ctypes
        for ids in ([1,1],[2,1],[0],[2**63]):
            values=(ctypes.c_uint64*len(ids))(*ids)
            self.assertNotEqual(engine.library.gp_water_union_begin(values,len(ids)),0)
        engine.begin();engine.release()

    def test_actual_tiny_pbf_full_pipeline_and_member_union(self):
        engine=self.engine()
        import hashlib
        import osmium
        from coarse_osm_native_smoke import fixture_records, write_xml
        from coarse_osm_water_scan_v1 import collect
        rows=fixture_records();ways=[r for r in rows if r['type']=='way'];ways[0]['tags']['natural']='water'
        ids=sorted([ways[0]['id'],ways[-1]['id'],max(r['id'] for r in ways)+1])
        engine=self.engine(ids)
        with tempfile.TemporaryDirectory() as directory:
            xml,pbf=Path(directory)/'tiny.osm',Path(directory)/'tiny.pbf';write_xml(xml,rows)
            header=osmium.io.Header();header.set('osmosis_replication_timestamp',STATE)
            with osmium.SimpleWriter(str(pbf),header=header,bufsz=65536) as writer:
                for obj in osmium.FileProcessor(str(xml)):writer.add(obj)
            raw=pbf.read_bytes();source={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'md5':hashlib.md5(raw).hexdigest()}
            actual=collect(engine,pbf,STATE,CAPS,source,{'node':4,'way':3,'relation':2},reference_seal(rows),lambda:None)
            self.assertEqual(actual['water']['union'],oracle(rows,ids))
            self.assertEqual(actual['receipt']['pythonProjectionFrames'],0)


if __name__=='__main__':unittest.main()
