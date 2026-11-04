"""Typed catalog/source-byte/gather controls, synthetic saved data only."""
import hashlib
import random
import struct
import unittest

from coarse_osm_country_wire_v4 import field_frame
from coarse_osm_water_area_v1_test import ring,edges
from coarse_osm_water_catalog_v1 import WaterCatalog

ARTIFACT=None


def frame(identity,nodes,tags=None):
    return field_frame({'type':'way','id':identity,'version':1,'visible':True,
                         'timestamp':'2026-10-25T21:21:21Z','tags':tags or {},'nodes':nodes})


def source_way_bytes(identity,nodes,selected):
    return struct.pack('<QIB',identity,len(nodes),int(selected))+b''.join(struct.pack('<Q',i) for i in nodes)


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if ARTIFACT is None:raise unittest.SkipTest('Qualified Linux catalog artifact required')
        cls.engine=WaterCatalog(*ARTIFACT)

    def setUp(self):self.engine.release()
    def tearDown(self):self.engine.release()

    def load(self,points,ways):
        self.engine.begin(len(points),len(ways),sum(len(nodes) for _,nodes,_ in ways))
        raw=b''.join(struct.pack('<Qii',*p) for p in points)
        for cursor in range(0,len(raw),32):self.engine.append_points(raw[cursor:cursor+32])
        self.assertEqual(self.engine.seal('points'),{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
        expected=bytearray()
        for identity,nodes,tags in ways:
            self.engine.append_way(frame(identity,nodes,tags))
            selected=tags.get('natural')=='water' or tags.get('waterway')=='riverbank' or tags.get('landuse')=='reservoir'
            expected.extend(source_way_bytes(identity,nodes,selected))
        self.assertEqual(self.engine.seal('ways'),{'bytes':len(expected),'sha256':hashlib.sha256(expected).hexdigest()})

    def test_exact_coordinates_way_fields_roles_and_reverse_join(self):
        points=[(1,0,0),(2,10,0),(3,10,10),(4,0,10)]
        self.load(points,[(10,[1,2,3],{'natural':'water'}),(20,[1,4,3],{})])
        actual=self.engine.gather([(10,1),(20,-1)],5)
        self.assertEqual(actual,points+[points[0]])
        result=self.engine.assemble([(0,actual)]);self.assertTrue(result['accepted'])
        self.assertEqual(edges([(0,actual)]),edges([(r['role'],r['nodes']) for r in result['rings']]))
        self.assertEqual(self.engine.stats(),{'nodes':4,'ways':2,'references':6,'taggedWays':1,'coordinatesSealed':1,'waysSealed':1,'backingBytes':4*16+2*8+3*8+6*8+2,'failed':0})

    def test_water_selectors_are_generic_and_exact(self):
        tags=[{'natural':'water'},{'waterway':'riverbank'},{'landuse':'reservoir'},
              {'natural':'Water'},{'waterway':'river'},{'name':'water'},{'natural':'water','waterway':'riverbank'}]
        self.load([(1,0,0),(2,1,1)],[(i+1,[1,2],tag) for i,tag in enumerate(tags)])
        self.assertEqual(self.engine.stats()['taggedWays'],4)

    def test_generated_independent_source_bytes_and_gather(self):
        randomizer=random.Random(78244)
        for _ in range(100):
            self.engine.release();points=[(i*17+1,randomizer.randrange(-1800000000,1800000001),randomizer.randrange(-900000000,900000001)) for i in range(randomizer.randrange(4,60))]
            selected=randomizer.sample(points,randomizer.randrange(2,len(points)+1));nodes=[p[0] for p in selected]
            self.load(points,[(1,nodes,{'natural':'water'})])
            self.assertEqual(self.engine.gather([(1,1)],len(nodes)),selected)
            self.assertEqual(self.engine.gather([(1,-1)],len(nodes)),selected[::-1])

    def test_original_order_native_id_coordinates_and_missing_do_not_infer(self):
        self.load([(1,0,0),(2,0,0)],[(1,[1,2],{})])
        self.assertEqual(self.engine.gather([(1,1)],2),[(1,0,0),(2,0,0)])
        self.engine.release();self.load([(1,0,0),(2,10,0)],[(1,[1,3],{})])
        with self.assertRaisesRegex(Exception,'missing node'):self.engine.gather([(1,1)],2)

    def test_missing_way_broken_chain_and_capacity_stop(self):
        for chain,capacity in ( ([(999,1)],3), ([(1,1),(2,1)],5), ([(1,1)],1) ):
            self.engine.release();self.load([(1,0,0),(2,1,1),(3,2,2)],[(1,[1,2],{}),(2,[1,3],{})])
            with self.assertRaises(Exception):self.engine.gather(chain,capacity)
            self.assertEqual(self.engine.stats()['failed'],1)

    def test_point_order_range_truncation_and_complete_seals(self):
        for rows in ([(1,0,0),(1,1,1)],[(2,0,0),(1,1,1)],[(1,1800000001,0)],[(1,0,900000001)]):
            self.engine.release();self.engine.begin(len(rows),1,2)
            with self.assertRaises(Exception):self.engine.append_points(b''.join(struct.pack('<Qii',*p) for p in rows))
        self.engine.release();self.engine.begin(2,1,2);self.engine.append_points(struct.pack('<Qii',1,0,0))
        with self.assertRaises(Exception):self.engine.seal('points')
        with self.assertRaises(Exception):self.engine.append_points(b'bad')

    def test_bad_frame_poisoning_prevents_reuse_until_release(self):
        good=frame(1,[1,2],{'natural':'water'})
        for malformed in (good[:-1],b'BAD!'+good[4:],frame(1,[1,0]),good+b'x',frame(1,[1]),frame(1,[1]*2001)):
            self.engine.release();self.engine.begin(2,1,2);self.engine.append_points(struct.pack('<QiiQii',1,0,0,2,1,1));self.engine.seal('points')
            with self.assertRaises(Exception):self.engine.append_way(malformed)
            self.assertEqual(self.engine.stats()['failed'],1)
            with self.assertRaisesRegex(Exception,'failed state'):self.engine.append_way(good)

    def test_duplicate_way_and_incomplete_way_seal(self):
        self.engine.begin(2,2,4);self.engine.append_points(struct.pack('<QiiQii',1,0,0,2,1,1));self.engine.seal('points');self.engine.append_way(frame(1,[1,2]))
        with self.assertRaises(Exception):self.engine.append_way(frame(1,[1,2]))
        self.engine.release();self.engine.begin(2,2,4);self.engine.append_points(struct.pack('<QiiQii',1,0,0,2,1,1));self.engine.seal('points');self.engine.append_way(frame(1,[1,2]))
        with self.assertRaises(Exception):self.engine.seal('ways')

    def test_release_and_repeated_lifetimes(self):
        for _ in range(100):
            self.load([(1,0,0),(2,1,1)],[(1,[1,2],{})]);self.engine.release()
            self.assertEqual(self.engine.stats()['backingBytes'],0)
        with self.assertRaises(Exception):self.engine.begin(101738007,1,2)

    def test_full_country_backing_arithmetic(self):
        nodes,ways,refs=101738006,2829193,104806243
        tables=nodes*16+ways*8+(ways+1)*8+refs*8+ways
        self.assertEqual(tables,2514354329)
        self.assertLess(nodes*16+nodes*8,3*1024**3)
        self.assertLess(tables+1024**3,4*1024**3)


if __name__=='__main__':unittest.main()
