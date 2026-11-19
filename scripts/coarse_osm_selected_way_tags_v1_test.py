"""Selected raw tags equal independent source fields; no policy inference."""
import hashlib
from pathlib import Path
import random
import tempfile
import unittest

from coarse_osm_conditional_census_v1_test import CAPS, STATE, node as other, way as chosen
from coarse_osm_conditional_records_v1 import read_records
from coarse_osm_country_wire_v4 import framed_records
from coarse_osm_projector_v1 import reference_seal
from coarse_osm_selected_way_tags_v1 import SelectedWayTags
from coarse_timing_input import PilotError

ARTIFACT = None


class Tests(unittest.TestCase):
    def engine(self):
        if ARTIFACT is None:
            self.skipTest('Compiled selected-way-tag artifact required')
        return SelectedWayTags(*ARTIFACT)

    def compare(self, rows, selected, proof=False):
        rows = sorted(rows, key=lambda r: ({'node':0,'way':1,'relation':2}[r['type']],r['id']))
        expected = [{k:r[k] for k in ('type','id','tags')} for r in rows if r['type']=='way' and r['id'] in selected]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'tags.bin'
            engine = self.engine()
            engine.begin(output, selected)
            try:
                receipt = engine.validate_frames(framed_records(rows), STATE, CAPS, proof=proof)
                counts = engine.finish()
                self.assertEqual(receipt['semanticSha256'], reference_seal(rows))
                self.assertEqual(list(read_records(output)), expected)
                self.assertEqual(counts['selectedRecords'], len(selected))
                self.assertEqual(counts['requestedWays'], len(selected))
                self.assertEqual(counts['encodedBytes'], output.stat().st_size)
                self.assertEqual(counts['tagUtf8Bytes'], sum(len(k.encode())+len(v.encode()) for r in expected for k,v in r['tags'].items()))
                self.assertEqual(counts['lastSelectedId'], selected[-1] if selected else 0)
                self.assertEqual(receipt['pythonProjectionFrames'], len(rows) if proof else 0)
                self.assertEqual(counts['complete'], 1)
                return counts, output.read_bytes()
            finally:
                engine.release()

    def test_full_unicode_unknown_and_empty_original_tags(self):
        self.compare([chosen(1,{}),chosen(2,{'barrier':'gate','note':'雪 😀','motorcar':'yes'}),chosen(3,{'anything':'unrecognized'})],[1,2,3])

    def test_sparse_selection_and_other_types_with_same_ids(self):
        self.compare([chosen(i,{'name':str(i)}) for i in range(1,8)]+[other(1,{'highway':'primary'})],[2,6])

    def test_empty_selection_and_empty_source(self):
        self.compare([],[])
        self.compare([chosen(1,{}),other(1,{'highway':'primary'})],[])

    def test_generated_mixed_streams_equal_independent_raw_fields(self):
        rng=random.Random(20261107)
        for _ in range(30):
            rows=[chosen(i,{'name':str(rng.randrange(1000)),'barrier':'gate'} if i%3 else {}) for i in range(1,101)]
            rows += [other(i,{'highway':'primary'}) for i in range(1,5)]
            self.compare(rows, sorted(rng.sample(range(1,101),30)))

    def test_large_raw_record_across_semantic_callback_boundaries(self):
        self.compare([chosen(1,{'note':'雪'*400000})],[1])

    def test_integer_identity_above_double_precision_stays_exact(self):
        self.compare([chosen(2**53+1,{'name':'large native id'})],[2**53+1])

    def test_summary_and_full_proof_mode_bytes_equal(self):
        rows=[chosen(1,{}),chosen(3,{'barrier':'gate'}),other(1,{'highway':'primary'})]
        self.assertEqual(self.compare(rows,[3]),self.compare(rows,[3],True))

    def test_invalid_selection_and_output_bounds_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for values in ([2,1],[1,1],[0],[-1],[True],[2**63],list(range(1,250002))):
                with self.assertRaises(PilotError):
                    self.engine().begin(Path(tmp)/'out',values)
            with self.assertRaises(PilotError):
                self.engine().begin(Path(tmp)/'out',[1],output_bytes=48*1048576+1)

    def test_missing_selection_never_completes(self):
        for selected in ([1],[3]):
            with tempfile.TemporaryDirectory() as tmp:
                engine=self.engine();engine.begin(Path(tmp)/'out',selected)
                try:
                    try:
                        engine.validate_frames(framed_records([chosen(2,{})]),STATE,CAPS)
                    except PilotError:
                        pass
                    with self.assertRaises(PilotError):engine.finish()
                finally:engine.release()

    def test_source_failure_and_output_cap_never_complete(self):
        for cap in (20,48*1048576):
            with tempfile.TemporaryDirectory() as tmp:
                engine=self.engine();engine.begin(Path(tmp)/'out',[1],output_bytes=cap)
                rows=[other(1,{'highway':'primary'}),chosen(1,{'barrier':'gate'})]
                if cap>20:rows[-1]['nodes']=[1,0]
                try:
                    with self.assertRaises(PilotError):engine.validate_frames(framed_records(rows),STATE,CAPS)
                    with self.assertRaises(PilotError):engine.finish()
                finally:engine.release()

    def test_exclusive_lifecycle_cancellation_and_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine=self.engine();other=self.engine();output=Path(tmp)/'out';engine.begin(output,[1])
            try:
                with self.assertRaises(PilotError):engine.finish()
                with self.assertRaises(PilotError):other.begin(Path(tmp)/'other',[1])
                calls=0
                def cancel():
                    nonlocal calls
                    calls+=1
                    if calls>=2:raise RuntimeError('selected-way cancellation')
                with self.assertRaisesRegex(RuntimeError,'selected-way cancellation'):
                    engine.validate_frames(framed_records([chosen(1,{})]),STATE,CAPS,check=cancel)
                with self.assertRaises(PilotError):engine.finish()
            finally:engine.release()
            with self.assertRaises(PilotError):engine.begin(output,[1])
            engine.begin(Path(tmp)/'fresh',[])
            try:
                engine.validate_frames(framed_records([]),STATE,CAPS);engine.finish()
                with self.assertRaises(PilotError):engine.finish()
            finally:engine.release()

    def test_actual_tiny_pbf_and_wrong_source_guard(self):
        import osmium
        from coarse_osm_native_smoke import fixture_records,write_xml
        rows=fixture_records()
        selected=[1,3]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);xml=root/'tiny.osm';pbf=root/'tiny.pbf';write_xml(xml,rows)
            header=osmium.io.Header();header.set('osmosis_replication_timestamp',STATE)
            with osmium.SimpleWriter(str(pbf),header=header,bufsz=65536) as writer:
                for obj in osmium.FileProcessor(str(xml)):writer.add(obj)
            raw=pbf.read_bytes()
            source={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'md5':hashlib.md5(raw).hexdigest()}
            for wrong in (False,True):
                engine=self.engine();output=root/('wrong' if wrong else 'tags');engine.begin(output,selected)
                try:
                    if wrong:
                        with self.assertRaisesRegex(PilotError,'source identity'):
                            engine.scan(pbf,STATE,CAPS,source=source|{'sha256':'0'*64})
                        with self.assertRaises(PilotError):engine.finish()
                    else:
                        receipt=engine.scan(pbf,STATE,CAPS,source=source)
                        counts=engine.finish()
                        self.assertEqual(receipt['semanticSha256'],reference_seal(rows))
                        self.assertEqual(receipt['pythonProjectionFrames'],0)
                        self.assertEqual(counts['selectedRecords'],2)
                        self.assertEqual(list(read_records(output)),[{k:r[k] for k in ('type','id','tags')} for r in rows if r['type']=='way' and r['id'] in selected])
                finally:engine.release()
