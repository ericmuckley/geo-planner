"""Sample bounds, immutable source and output reconciliation controls."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from coarse_osm_bulk_test import pbf, frame, field
from coarse_osm_profile import CASES, copy_prefix, reconcile
from coarse_timing_input import PilotError


class Tests(unittest.TestCase):
    def paths(self, raw):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        source = Path(temp.name) / 'source.pbf'; source.write_bytes(raw)
        return source, source.with_name('sample.pbf')

    def test_copies_complete_frames_without_reading_the_tail(self):
        first = pbf(compressed=True)
        source, target = self.paths(first + b'not a frame')
        result = copy_prefix(source, target, frames=2, byte_limit=len(first))
        self.assertEqual(target.read_bytes(), first)
        self.assertEqual(source.read_bytes(), first + b'not a frame')
        self.assertEqual(result['sourcePrefixBytesRead'], len(first))
        self.assertFalse(result['wholePublisherFileEof'])

    def test_truncation_keeps_valid_prefix_and_source(self):
        first = pbf()
        source, target = self.paths(first[:-1])
        with self.assertRaises(PilotError): copy_prefix(source, target, frames=2)
        self.assertEqual(target.read_bytes(), first[:len(first)-len(frame(b'OSMData', field(1,b'')))])
        self.assertEqual(source.read_bytes(), first[:-1])

    def test_byte_limit_stops_before_copying_oversized_next_blob(self):
        raw = pbf()
        source, target = self.paths(raw)
        with self.assertRaises(PilotError): copy_prefix(source, target, frames=2, byte_limit=len(raw)-1)
        self.assertLess(target.stat().st_size, len(raw))

    def test_invalid_order_and_output_reuse_are_refused(self):
        source, target = self.paths(frame(b'OSMData', b''))
        with self.assertRaises(PilotError): copy_prefix(source, target, frames=1)
        with self.assertRaises(FileExistsError): copy_prefix(source, target, frames=1)

    def test_changed_source_is_not_admitted(self):
        source, target = self.paths(pbf())
        with patch('coarse_osm_profile.stat_key', side_effect=[(1,2,3,4,5),(1,2,3,4,6)]):
            with self.assertRaisesRegex(PilotError, 'source changed'): copy_prefix(source, target, frames=2)

    def test_reconciliation_rejects_count_hash_index_and_eof_drift(self):
        cases=[]
        for name,mode,implementation,profiled in CASES:
            cases.append({'name':name,'mode':mode,'implementation':implementation,'profiled':profiled,
                'counts':{'node':4},'projectedRecordsSha256':'a','indexSha256':'b' if mode=='index' else None,'indexBytes':8192 if mode=='index' else 0,
                'passes':[] if mode=='projection' else [{'status':'eof','counts':{'node':4}}],
                'secondsIncludingProjectionValidationHashAndIndexAsApplicable':2 if implementation=='reference' else 1})
        self.assertTrue(reconcile(cases)['performanceGatePassed'])
        for key,value in [('counts',{'node':3}),('projectedRecordsSha256','x'),('indexSha256','x'),('passes',[{'status':'running','counts':{'node':4}}])]:
            rows=deepcopy(cases);rows[3][key]=value
            with self.subTest(key=key):
                with self.assertRaises(PilotError): reconcile(rows)
        for row in cases: row['secondsIncludingProjectionValidationHashAndIndexAsApplicable']=1
        self.assertFalse(reconcile(cases)['performanceGatePassed'])


if __name__ == '__main__':
    unittest.main()
