import ctypes
import gzip
import hashlib
from pathlib import Path
import random
import struct
import tempfile
import unittest
from unittest.mock import patch

from coarse_osm_country_wire_v4 import CALLBACK, field_frame, framed_records, reference_seal
from coarse_osm_native_smoke import STATE
from coarse_osm_water_census_v2_test import CAPS
from coarse_osm_water_coordinate_codec_v1 import encode_rows,decode_rows,typed_rows
from coarse_osm_water_coordinate_store_v1 import CoordinateStore
from coarse_osm_water_coordinates_v1 import WaterCoordinates,audit_store
from coarse_osm_water_reference_store_v1 import Reader

ARTIFACT=None


def node(identity,x=0,y=0,**tags):
    return {'type':'node','id':identity,'version':1,'timestamp':STATE,'visible':True,'tags':tags,'lon':x/10000000,'lat':y/10000000}


def chunks(ids):
    raw=b''.join(struct.pack('<Q',i) for i in ids)
    return lambda:(raw[i:i+65536] for i in range(0,len(raw),65536))


def read_all(root,report):
    with Reader(root,report) as reader:
        parts=[]
        while raw:=reader.read(1048576):parts.append(raw)
        return b''.join(parts)


def replace_stream(root,report,raw):
    part=report['parts'][0];path=root/part['name'];packed=gzip.compress(raw,mtime=0);path.write_bytes(packed)
    part.update(rawBytes=len(raw),rawSha256=hashlib.sha256(raw).hexdigest(),bytes=len(packed),sha256=hashlib.sha256(packed).hexdigest())
    report.update(rawBytes=len(raw),rawSha256=part['rawSha256'],compressedBytes=len(packed))


class Tests(unittest.TestCase):
    def engine(self,ids,store):
        if ARTIFACT is None:self.skipTest('Explicit compiled coordinate target required')
        return WaterCoordinates(*ARTIFACT,requested=len(ids),id_chunks=chunks(ids),store=store)

    def produce(self,root,rows,ids,*,audit=True,proof=False,chunk_bytes=1048576):
        with CoordinateStore(root,len(ids),encoded_budget=16*1048576,missing_budget=16*1048576) as store:
            engine=self.engine(ids,store);engine.begin()
            try:
                caps=CAPS|{'scanNodesPerPass':110000,'scanObjectVisitsTotal':130000}
                receipt=engine.validate_frames(framed_records(rows),STATE,caps,proof=proof)
                measured=engine.finish()
            finally:engine.release()
            wanted=set(ids)
            expected=[(r['id'],*struct.unpack('<ii',field_frame(r)[-8:])) for r in rows if r['type']=='node' and r['id'] in wanted]
            expected.sort()
            raw=read_all(root,measured['stored']['encoded'])
            self.assertEqual(raw,b''.join(encode_rows(expected)))
            self.assertEqual(list(decode_rows(raw[i:i+65536] for i in range(0,len(raw),65536))),expected)
            self.assertEqual(measured['stored']['sourceShadow']['sha256'],hashlib.sha256(b''.join(typed_rows(expected))).hexdigest())
            missing=sorted(set(ids)-{r['id'] for r in rows if r['type']=='node'})
            self.assertEqual(read_all(root,measured['stored']['missing']),b''.join(struct.pack('<Q',i) for i in missing))
            self.assertEqual(receipt['semanticSha256'],reference_seal(rows))
            if audit:
                checked=audit_store(engine,root,measured['stored'],measured['capture'],chunk_bytes=chunk_bytes)
                self.assertEqual(checked['presentCoordinatesIndependentlyDecoded'],len(expected))
            return engine,measured

    def test_known_extremes_metadata_and_missing_before_between_after(self):
        rows=[node(2,-1800000000,-900000000,name='café 雪'),node(4,1800000000,900000000),node(8,0,0)]
        with tempfile.TemporaryDirectory() as directory:self.produce(Path(directory),rows,[1,2,3,4,8,9])

    def test_empty_all_missing_and_real_zero_coordinates(self):
        for rows,ids in (([],[]),([],[1,2]),([node(1)],[1]),([node(2)],[1,3])):
            with tempfile.TemporaryDirectory() as directory:self.produce(Path(directory),rows,ids)

    def test_hundred_generated_exact_source_encoder_decoder_partitions(self):
        rng=random.Random(20261107)
        for _ in range(100):
            rows=[node(i,rng.randrange(-1800000000,1800000001),rng.randrange(-900000000,900000001)) for i in range(2,42,2)]
            ids=sorted(rng.sample(range(1,45),25))
            with tempfile.TemporaryDirectory() as directory:self.produce(Path(directory),rows,ids,chunk_bytes=rng.choice([1,2,3,7,17,31]))

    def test_large_source_frame_and_output_callback_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:self.produce(Path(directory),[node(1,note='x'*1200000)],[1])
        rng=random.Random(20261108)
        rows=[node(i,rng.randrange(-1800000000,1800000001),rng.randrange(-900000000,900000001)) for i in range(1,100001)]
        with tempfile.TemporaryDirectory() as directory:self.produce(Path(directory),rows,list(range(1,100001)))

    def test_proof_mode_has_same_exact_coordinate_bytes(self):
        with tempfile.TemporaryDirectory() as directory:self.produce(Path(directory),[node(1,-17,29)],[1,2],proof=True)

    def test_invalid_input_order_domain_and_incomplete_chunks_fail(self):
        for ids in ([1,1],[2,1],[0],[2**63]):
            with tempfile.TemporaryDirectory() as directory:
                with CoordinateStore(directory,len(ids),encoded_budget=1024,missing_budget=1024) as store:
                    engine=self.engine(ids,store)
                    with self.assertRaises(Exception):engine.begin()
        with tempfile.TemporaryDirectory() as directory:
            with CoordinateStore(directory,1,encoded_budget=1024,missing_budget=1024) as store:
                engine=self.engine([1],store);engine.id_chunks=lambda:iter(())
                with self.assertRaises(Exception):engine.begin()

    def test_source_and_output_failure_never_yield_complete_coordinates(self):
        for mode in ('source','output'):
            with tempfile.TemporaryDirectory() as directory:
                with CoordinateStore(directory,1,encoded_budget=1024,missing_budget=1024) as store:
                    engine=self.engine([1],store);engine.begin()
                    try:
                        raw=framed_records([node(1)])
                        if mode=='source':
                            with self.assertRaises(Exception):engine.validate_frames(raw[:-1],STATE,CAPS)
                        else:
                            with patch.object(store,'accept',side_effect=OSError('synthetic write stop')):
                                with self.assertRaises(Exception):engine.validate_frames(raw,STATE,CAPS)
                        self.assertFalse(engine.last['nativeEof'])
                        with self.assertRaises(Exception):engine.finish()
                    finally:engine.release()

    def test_independent_decoder_rejects_resealed_malformed_streams(self):
        bads=[b'WXY2',b'WXY1\x81\x00\x00\x00',b'WXY1'+b'\xff'*10,b'WXY1\x00\x00\x00',b'WXY1\x01\x00']
        for bad in bads:
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);engine,measured=self.produce(root,[node(1)],[1],audit=False)
                replace_stream(root,measured['stored']['encoded'],bad)
                with self.assertRaises(Exception):audit_store(engine,root,measured['stored'],measured['capture'])

    def test_resealed_wrong_missing_id_and_unknown_present_id_rejected(self):
        for mode in ('missing','present'):
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);engine,measured=self.produce(root,[node(1)],[1,2],audit=False)
                if mode=='missing':replace_stream(root,measured['stored']['missing'],struct.pack('<Q',99))
                else:replace_stream(root,measured['stored']['encoded'],b''.join(encode_rows([(99,0,0)])))
                with self.assertRaises(Exception):audit_store(engine,root,measured['stored'],measured['capture'])

    def test_changed_coordinate_or_source_shadow_rejected(self):
        for mode in ('coordinate','shadow'):
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);engine,measured=self.produce(root,[node(1)],[1],audit=False)
                if mode=='coordinate':replace_stream(root,measured['stored']['encoded'],b''.join(encode_rows([(1,1,0)])))
                else:measured['stored']['sourceShadow']['sha256']='0'*64
                with self.assertRaises(Exception):audit_store(engine,root,measured['stored'],measured['capture'])

    def test_capture_audit_lifecycle_and_native_capacity_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            with CoordinateStore(directory,1,encoded_budget=1024,missing_budget=1024) as store:
                engine=self.engine([1],store);lib=engine.library
                self.assertNotEqual(lib.gp_water_coords_begin(150000001),0)
                engine.begin()
                try:
                    self.assertNotEqual(lib.gp_water_coords_audit_begin(1),0)
                    with self.assertRaises(Exception):engine.begin()
                    with self.assertRaises(Exception):engine.finish()
                    self.assertNotEqual(lib.gp_water_coords_seal(),0)
                    engine.validate_frames(framed_records([node(1)]),STATE,CAPS);engine.finish()
                    with self.assertRaises(Exception):engine.finish()
                finally:engine.release()

    def test_actual_tiny_pbf_source_identity_and_complete_coordinate_audit(self):
        if ARTIFACT is None:self.skipTest('Explicit compiled coordinate target required')
        import osmium
        from coarse_osm_native_smoke import fixture_records,write_xml
        rows=fixture_records();ids=[1,2,3,4,99]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);xml,pbf=root/'tiny.osm',root/'tiny.pbf';write_xml(xml,rows)
            header=osmium.io.Header();header.set('osmosis_replication_timestamp',STATE)
            with osmium.SimpleWriter(str(pbf),header=header,bufsz=65536) as writer:
                for obj in osmium.FileProcessor(str(xml)):writer.add(obj)
            data=pbf.read_bytes();source={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'md5':hashlib.md5(data).hexdigest()}
            with CoordinateStore(root,len(ids),encoded_budget=1024,missing_budget=1024) as store:
                engine=self.engine(ids,store);engine.begin()
                try:
                    receipt=engine.scan(pbf,STATE,CAPS,source=source);measured=engine.finish()
                finally:engine.release()
                self.assertEqual(receipt['counts'],{'node':4,'way':3,'relation':2})
                self.assertEqual(receipt['semanticSha256'],reference_seal(rows))
                proof=audit_store(engine,root,measured['stored'],measured['capture'])
                self.assertEqual(proof['presentCoordinatesIndependentlyDecoded'],4)
                self.assertEqual(proof['missingIdsIndependentlyCompared'],1)


if __name__=='__main__':unittest.main()
