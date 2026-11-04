import ctypes
import gzip
import hashlib
from pathlib import Path
import random
import struct
import tempfile
import unittest
from unittest.mock import patch

from coarse_osm_country_wire_v4 import CALLBACK, framed_records, reference_seal
from coarse_osm_native_smoke import STATE
from coarse_osm_water_census_v2_test import CAPS, way
from coarse_osm_water_union_v1_test import oracle
from coarse_osm_water_reference_store_v1 import ReferenceStore, Reader
from coarse_osm_water_references_v1 import WaterReferences, audit_store
from coarse_timing_input import PilotError

ARTIFACT=None


def selected(rows,ids):
    return [r for r in rows if r['type']=='way' and (r['id'] in ids or r['tags'].get('natural')=='water' or
            r['tags'].get('waterway')=='riverbank' or r['tags'].get('landuse')=='reservoir')]


def contents(root,report):
    with Reader(root,report) as reader:
        chunks=[]
        while raw:=reader.read(1048576):chunks.append(raw)
        return b''.join(chunks)


class Tests(unittest.TestCase):
    def engine(self,store,rows,ids=(),**options):
        if ARTIFACT is None:self.skipTest('Explicit compiled reference target required')
        counts=oracle(rows,ids)
        return WaterReferences(*ARTIFACT,store=store,member_ids=ids,
                    expected_ways=options.get('ways',counts['unionWays']),expected_references=options.get('refs',counts['unionReferences']))

    def produce(self,root,rows,ids=(),audit=True,**options):
        wanted=selected(rows,ids);raw=framed_records(wanted);counts=oracle(rows,ids)
        with ReferenceStore(root,raw_way_bytes=len(raw),reference_count=counts['unionReferences']) as store:
            engine=self.engine(store,rows,ids,**options);engine.begin()
            try:
                receipt=engine.validate_frames(framed_records(rows),STATE,CAPS,proof=options.get('proof',False))
                measured=engine.finish()
                self.assertEqual(receipt['semanticSha256'],reference_seal(rows))
            finally:engine.release()
            if audit:
                proof=audit_store(engine,root,measured['referenceStore'],measured['referenceCapture'],measured['union'],ids)
                self.assertEqual(proof['allReferenceOccurrencesChecked'],counts['unionReferences'])
            self.assertEqual(contents(root,measured['referenceStore']['ways']),raw)
            ids_expected=sorted({n for r in wanted for n in r['nodes']})
            self.assertEqual(contents(root,measured['referenceStore']['nodes']),b''.join(struct.pack('<Q',i) for i in ids_expected))
            return engine,measured

    def test_exact_all_metadata_refs_and_untagged_members(self):
        with tempfile.TemporaryDirectory() as directory:
            rows=[way(10,{'natural':'water','name':'café 雪'},[1,2,3,1]),way(20,{},[4,3]),way(30,{})]
            self.produce(Path(directory),rows,[20,99])

    def test_empty_and_node_only_sources_have_empty_reference_storage(self):
        node={'type':'node','id':1,'version':1,'timestamp':STATE,'visible':True,'tags':{'natural':'water'},'lon':0.,'lat':0.}
        for rows in ([],[node]):
            with tempfile.TemporaryDirectory() as directory:self.produce(Path(directory),rows,[99])

    def test_one_hundred_generated_exact_streams_and_unique_sets(self):
        rng=random.Random(20261105)
        for _ in range(100):
            rows=[way(i,{'natural':'water'} if rng.randrange(3)==0 else {},[rng.randrange(1,100) for _ in range(rng.randrange(2,20))]) for i in range(10,30)]
            ids=sorted(rng.sample(range(1,35),10))
            with tempfile.TemporaryDirectory() as directory:self.produce(Path(directory),rows,ids)

    def test_frames_and_records_cross_output_and_shard_boundaries(self):
        with tempfile.TemporaryDirectory() as directory,patch('coarse_osm_water_reference_store_v1.PART_BYTES',65536):
            self.produce(Path(directory),[way(10,{'natural':'water','note':'x'*1200000})],[10])

    def test_proof_mode_keeps_exact_same_bytes_and_source_seal(self):
        with tempfile.TemporaryDirectory() as directory:self.produce(Path(directory),[way(10,{'natural':'water'})],proof=True)

    def test_frozen_wrong_dimensions_stop_without_complete_output(self):
        for change in ({'ways':0},{'refs':3},{'refs':5}):
            with tempfile.TemporaryDirectory() as directory,self.assertRaises(Exception):
                self.produce(Path(directory),[way(10,{'natural':'water'})],**change)

    def test_output_callback_failure_never_yields_source_eof(self):
        with tempfile.TemporaryDirectory() as directory:
            rows=[way(10,{'natural':'water'})]
            with ReferenceStore(directory,raw_way_bytes=len(framed_records(rows)),reference_count=4) as store:
                engine=self.engine(store,rows);engine.begin()
                try:
                    with patch.object(store,'way_chunk',side_effect=OSError('synthetic write failure')):
                        with self.assertRaises(Exception):engine.validate_frames(framed_records(rows),STATE,CAPS)
                    self.assertFalse(engine.last['nativeEof'])
                    with self.assertRaises(Exception):engine.finish()
                finally:engine.release()

    def test_invalid_source_reference_never_finishes_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            rows=[way(10,{'natural':'water'},[1,0])]
            with ReferenceStore(directory,raw_way_bytes=len(framed_records(rows)),reference_count=2) as store:
                engine=self.engine(store,rows);engine.begin()
                try:
                    with self.assertRaises(PilotError):engine.validate_frames(framed_records(rows),STATE,CAPS)
                    with self.assertRaises(PilotError):engine.finish()
                finally:engine.release()

    def test_independent_audit_rejects_resealed_wrong_node_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);engine,measured=self.produce(root,[way(10,{'natural':'water'})],audit=False)
            report=measured['referenceStore'];part=report['nodes']['parts'][0];path=root/part['name']
            raw=gzip.decompress(path.read_bytes());bad=struct.pack('<Q',99)+raw[8:];packed=gzip.compress(bad,mtime=0)
            path.write_bytes(packed);part.update(bytes=len(packed),sha256=hashlib.sha256(packed).hexdigest(),rawSha256=hashlib.sha256(bad).hexdigest())
            report['nodes']['rawSha256']=part['rawSha256']
            with self.assertRaises(Exception):audit_store(engine,root,report,measured['referenceCapture'],measured['union'],())

    def test_sorter_reentry_early_finish_append_and_repeated_finish_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            with ReferenceStore(directory,raw_way_bytes=0,reference_count=0) as store:
                engine=self.engine(store,[]);engine.begin();lib=engine.library
                try:self.assertNotEqual(lib.gp_water_refs_audit_begin(0),0)
                finally:engine.release()
                self.assertEqual(lib.gp_water_refs_audit_begin(2),0)
                try:
                    callback=CALLBACK(lambda *_:0);count=ctypes.c_uint64();values=(ctypes.c_uint64*2)(2,1)
                    self.assertNotEqual(lib.gp_water_refs_audit_finish(callback,None,ctypes.byref(count)),0)
                    self.assertEqual(lib.gp_water_refs_audit_append(values,2),0)
                    self.assertEqual(lib.gp_water_refs_audit_finish(callback,None,ctypes.byref(count)),0)
                    self.assertEqual(count.value,2)
                    self.assertNotEqual(lib.gp_water_refs_audit_append(values,2),0)
                    self.assertNotEqual(lib.gp_water_refs_audit_finish(callback,None,ctypes.byref(count)),0)
                finally:lib.gp_water_refs_audit_release()

    def test_native_input_caps_reject_before_reservation(self):
        with tempfile.TemporaryDirectory() as directory:
            with ReferenceStore(directory,raw_way_bytes=0,reference_count=0) as store:
                engine=self.engine(store,[]);lib=engine.library
                for ways,refs in ((4000001,0),(0,150000001)):
                    self.assertNotEqual(lib.gp_water_refs_begin(engine.member_ids,0,ways,refs),0)
                engine.begin();engine.release()

    def test_actual_tiny_pbf_pipeline_and_independent_audit(self):
        if ARTIFACT is None:self.skipTest('Explicit compiled reference target required')
        import osmium
        from coarse_osm_native_smoke import fixture_records,write_xml
        from coarse_osm_water_scan_v1 import collect
        rows=fixture_records();rows[4]['tags']['natural']='water';ids=[3]
        counts=oracle(rows,ids);raw=framed_records(selected(rows,ids))
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);xml,pbf=root/'tiny.osm',root/'tiny.pbf';write_xml(xml,rows)
            header=osmium.io.Header();header.set('osmosis_replication_timestamp',STATE)
            with osmium.SimpleWriter(str(pbf),header=header,bufsz=65536) as writer:
                for obj in osmium.FileProcessor(str(xml)):writer.add(obj)
            data=pbf.read_bytes();source={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'md5':hashlib.md5(data).hexdigest()}
            with ReferenceStore(root,raw_way_bytes=len(raw),reference_count=counts['unionReferences']) as store:
                engine=self.engine(store,rows,ids)
                measured=collect(engine,pbf,STATE,CAPS,source,{'node':4,'way':3,'relation':2},reference_seal(rows),lambda:None)['water']
                proof=audit_store(engine,root,measured['referenceStore'],measured['referenceCapture'],measured['union'],ids)
                self.assertEqual(proof['allWayRecordsAndFieldsDecoded'],2)


if __name__=='__main__':unittest.main()
