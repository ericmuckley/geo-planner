"""Inventory EOF, sample, equivalence and native-projection controls."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from coarse_osm_inventory import CAPS, scan, compare_sample, decision
from coarse_osm_native_smoke import fixture_records, write_xml, STATE
from coarse_osm_bulk_pbf import native_records
from coarse_osm_records import canonical, strict_json
from coarse_osm_validation_v4_test import proposal
from coarse_timing_input import PilotError

NATIVE = importlib.util.find_spec('osmium') is not None


class Tests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.source=self.root/'source';self.source.write_bytes(b'synthetic source bytes')
        self.caps=dict(CAPS,samplePerKind=2,checkpointEvery=2,countSeconds=10)

    def run_scan(self,rows=None,**options):
        rows=fixture_records() if rows is None else rows
        def apply(source,inventory):
            for row in rows: inventory.see(('node','way','relation').index(row['type']),deepcopy(row))
        return scan(self.source,self.root/'scan',self.caps,apply=options.pop('apply',apply),projector=lambda raw,limit:raw,**options)

    def test_fixed_first_objects_counts_eof_and_replay(self):
        result=self.run_scan()
        self.assertTrue(result['wholeSourceNativeEof'])
        self.assertEqual(result['counts'],{'node':4,'way':3,'relation':2})
        self.assertEqual(result['nativeCallbackVisits'],9)
        self.assertEqual(result['sampleCounts'],{'node':2,'way':2,'relation':2})
        rows=[strict_json(line) for line in (self.root/'scan/samples.jsonl').read_bytes().splitlines()]
        self.assertEqual([(r['type'],r['id']) for r in rows],[('node',1),('node',2),('way',1),('way',3),('relation',1),('relation',2)])
        compared=compare_sample(self.root/'scan/samples.jsonl',result,proposal(),self.root)
        self.assertTrue(compared['equivalent']);self.assertTrue(compared['allSampleRecordsAccepted'])
        self.assertFalse(compared['wholeSourceMetadataValidation'])

    def test_type_and_total_caps_leave_unqualified_partial_counts(self):
        for change in ({'nodeLimit':1},{'visitLimit':1}):
            with self.subTest(change=change):
                root=self.root/str(len(list(self.root.iterdir())))
                caps=dict(self.caps,**change)
                def apply(source,inv):
                    for row in fixture_records():inv.see(('node','way','relation').index(row['type']),row)
                result=scan(self.source,root,caps,apply=apply,projector=lambda row,limit:row)
                self.assertFalse(result['wholeSourceNativeEof']);self.assertEqual(result['nativeCallbackVisits'],2)
                self.assertIn('object cap',result['error']['message'])

    def test_decoder_failure_never_claims_eof(self):
        def broken(source,inv):
            inv.see(0,fixture_records()[0]);raise RuntimeError('synthetic decoder failure')
        result=self.run_scan(apply=broken)
        self.assertFalse(result['wholeSourceNativeEof']);self.assertEqual(result['counts']['node'],1)
        self.assertIn('decoder failure',result['error']['message'])
        self.assertEqual(self.source.read_bytes(),b'synthetic source bytes')

    def test_sample_byte_cap_preserves_prefix_and_stops(self):
        self.caps['sampleBytes']=len(canonical(fixture_records()[0]))
        result=self.run_scan()
        self.assertFalse(result['wholeSourceNativeEof']);self.assertEqual(result['sampleBytes'],0)
        self.assertEqual((self.root/'scan/samples.jsonl').read_bytes(),b'')
        self.assertIn('sample byte cap',result['error']['message'])

    def test_count_deadline_is_not_a_complete_inventory(self):
        now=[0.]
        def slow(source,inv):
            now[0]=20.;inv.see(0,fixture_records()[0])
        result=self.run_scan(apply=slow,clock=lambda:now[0])
        self.assertFalse(result['wholeSourceNativeEof']);self.assertIn('deadline',result['error']['message'])

    def test_source_change_refuses_eof_even_with_all_callbacks(self):
        def changed(source,inv):
            for row in fixture_records():inv.see(('node','way','relation').index(row['type']),row)
            Path(source).write_bytes(b'changed')
        result=self.run_scan(apply=changed)
        self.assertFalse(result['wholeSourceNativeEof']);self.assertIn('source changed',result['error']['message'])

    def test_both_rejections_are_equivalence_not_sample_admission(self):
        rows=fixture_records();rows[4]['nodes']=[1]
        result=self.run_scan(rows)
        compared=compare_sample(self.root/'scan/samples.jsonl',result,proposal(),self.root)
        self.assertTrue(compared['equivalent']);self.assertFalse(compared['allSampleRecordsAccepted'])
        chosen=decision(result,compared,self.forecast())
        self.assertIn('reference_and_prototype_reject_fixed_sample',chosen['reasons'])
        self.assertFalse(chosen['wholeExtractionAdmitted'])

    def test_modified_sample_is_not_replayed_as_verified(self):
        result=self.run_scan();path=self.root/'scan/samples.jsonl';path.write_bytes(path.read_bytes()+b'{}\n')
        with self.assertRaises(PilotError):compare_sample(path,result,proposal(),self.root)

    def forecast(self):
        return {'candidateNodeIndexMedianSeconds':1.7900979169644415,'nodeSampleCount':64000,'sampleIndexBytes':1748992,
            'workSeconds':14340,'sqliteIndexBytesEach':25769803776,'workingBytes':68719476736,'otherOriginalWorkingBytes':13730880848}

    def test_forecast_is_explicit_and_never_admits_a_full_import(self):
        inventory={'wholeSourceNativeEof':True,'counts':{'node':900000000,'way':1,'relation':1}}
        samples={'equivalent':True,'allSampleRecordsAccepted':True}
        chosen=decision(inventory,samples,self.forecast())
        self.assertEqual(chosen['decision'],'reject_current_all_node_four_pass_strategy')
        self.assertIn('node_index_time_screen',chosen['reasons'])
        self.assertFalse(chosen['wholeExtractionAdmitted'])
        self.assertIn('Extrapolation',chosen['forecast']['scope'])
        inventory['wholeSourceNativeEof']=False
        self.assertEqual(decision(inventory,samples,self.forecast())['decision'],'hold_incomplete_inventory')
        inventory['wholeSourceNativeEof']=True;samples['equivalent']=False
        self.assertEqual(decision(inventory,samples,self.forecast())['decision'],'reject_validator_equivalence')

    def fixture(self):
        import osmium
        xml=self.root/'tiny.osm';pbf=self.root/'tiny.osm.pbf'
        write_xml(xml,fixture_records())
        header=osmium.io.Header();header.set('osmosis_replication_timestamp',STATE)
        with osmium.SimpleWriter(str(pbf),bufsz=65536,header=header) as writer:
            for obj in osmium.FileProcessor(str(xml)):writer.add(obj)
        return pbf

    @unittest.skipUnless(NATIVE,'Qualified Linux native runtime required')
    def test_actual_native_callbacks_and_copied_samples_match_frozen_projector(self):
        pbf=self.fixture();result=scan(pbf,self.root/'native',CAPS)
        self.assertTrue(result['wholeSourceNativeEof']);self.assertEqual(result['counts'],{'node':4,'way':3,'relation':2})
        copied=[strict_json(line) for line in (self.root/'native/samples.jsonl').read_bytes().splitlines()]
        self.assertEqual(copied,list(native_records(pbf,CAPS['elementBytes'])))
        self.assertEqual(copied,fixture_records())

    @unittest.skipUnless(NATIVE,'Qualified Linux native runtime required')
    def test_actual_native_truncation_does_not_promote_partial_counts(self):
        pbf=self.fixture();broken=self.root/'broken.osm.pbf';broken.write_bytes(pbf.read_bytes()[:-1])
        result=scan(broken,self.root/'truncated',CAPS)
        self.assertFalse(result['wholeSourceNativeEof']);self.assertIsNotNone(result['error'])


if __name__=='__main__':unittest.main()
