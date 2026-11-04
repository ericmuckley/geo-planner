"""Capture accounting, immutable banks, source closure and raw-output ledger."""
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import coarse_osm_disk_resources_v1 as resources
from coarse_osm_records import canonical
from coarse_timing_input import PilotError
import run_osm_disk_capture_v1 as capture


class Tests(unittest.TestCase):
    def test_retains_all_failures_and_qualifications_with_bounded_database_and_journal_space(self):
        self.assertEqual(resources.RETAINED,58226331751+2*64*1024**2)
        self.assertEqual(resources.RETAINED+resources.TMP+resources.OWNED_LIMIT,64*1024**3)
        self.assertLess(resources.WRITABLE_WORST_CASE,resources.OWNED_LIMIT)
        self.assertEqual(capture.RUN_CAPS['hostSeconds'],14400)
        self.assertEqual(capture.RUN_CAPS['passSeconds'],6900)

    def test_proposal_preserves_arbitrary_windows_and_input_values(self):
        base={'windows':[{'id':'any','bbox':[-5,1,-4,2]}],'proposedCaps':{}}
        saved=deepcopy(base);result=capture.proposal_for(base,'run',capture.RUN_CAPS)
        self.assertEqual(base,saved);self.assertEqual(result['windows'],base['windows'])
        self.assertEqual(result['proposedCaps']['workingBytesIncludingTmp'],resources.OWNED_LIMIT+resources.TMP)

    def test_accounted_output_cannot_spend_retained_or_tmp_capacity(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);tmp=root/'tmp';tmp.mkdir();guard=resources.FullResources(root,tmp=tmp)
            with patch.object(resources,'resource_metrics',return_value={}):
                guard.check(force=True)
                with self.assertRaises(PilotError):guard.check(force=True,projected=resources.OWNED_LIMIT)

    def test_bank_storage_rejects_duplicates_fine_index_writes_and_removal(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);tmp=root/'tmp';tmp.mkdir();guard=resources.FullResources(root,tmp=tmp);storage=resources.CaptureStorage(root,guard,{'0000.bin':{'bytes':4,'sha256':hashlib.sha256(b'part').hexdigest()}})
            bank=root/'all-highway-primary-selection-cells';bank.mkdir();fine=root/'primary-index';fine.mkdir()
            with patch.object(resources,'resource_metrics',return_value={}):
                storage.write(bank/'0000.bin',b'part')
                for path in [bank/'0000.bin',fine/'00000000.bin',bank/'unknown']:
                    with self.assertRaises(PilotError):storage.write(path,b'overwrite')
                with self.assertRaises(PilotError):storage.remove(bank/'0000.bin',4)
                self.assertEqual((bank/'0000.bin').read_bytes(),b'part')
                with self.assertRaises(PilotError):storage.complete()
                other=root/'all-highway-independent-materialization-cells';other.mkdir()
                with self.assertRaises(PilotError):storage.write(other/'0000.bin',b'fail')
                storage.write(other/'0000.bin',b'part');storage.complete()

    def receipt(self):
        plan={'source':{'counts':{'node':4,'way':3,'relation':2},'sha256':'source','md5':'md5','publisherState':'state','bytes':564},'semantic':'fields','highwayWays':2}
        receipt={'nativeEof':True,'counts':plan['source']['counts'],'visits':9,'semanticSha256':'fields','batchWays':2,'highwayWays':2,
                 'sourceIdentity':{'sourceSha256':'source','sourceMd5':'md5','publisherStateUtc':'state'},'postSourceHashBytes':564,'knownGuardReadBytes':1128}
        return receipt,plan

    def test_whole_source_and_every_highway_batch_are_required(self):
        good,plan=self.receipt();capture.check_receipt(good,plan)
        for key,value in [('nativeEof',False),('counts',{'node':4,'way':2,'relation':2}),('visits',8),('semanticSha256','drift'),('batchWays',1),('highwayWays',1),('postSourceHashBytes',563),('knownGuardReadBytes',1127)]:
            with self.assertRaises(PilotError):capture.check_receipt(good|{key:value},plan)

    def test_all_source_identity_fields_are_required(self):
        receipt,plan=self.receipt()
        for key in receipt['sourceIdentity']:
            damaged=deepcopy(receipt);damaged['sourceIdentity'][key]='drift'
            with self.assertRaises(PilotError):capture.check_receipt(damaged,plan)

    def ledger(self,rows):
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'output';path.write_bytes(b''.join(canonical(row)+b'\n' for row in rows))
            return capture.output_ledger(path,[{'id':'q','bbox':[0,0,1,1]}])

    def row(self):
        element={'type':'node','id':7,'lon':0,'lat':0,'tags':{'source':'raw'}}
        return {'element':element,'elementSha256':hashlib.sha256(canonical(element)).hexdigest(),'windowIds':['q']}

    def test_ledger_retains_raw_fields_and_counts_unique_memberships(self):
        row=self.row();result=self.ledger([row]);self.assertEqual(result['uniqueCounts'],{'node':1});self.assertEqual(result['windowOccurrences'],1)
        self.assertEqual(result['windows'][0]['status'],'complete_from_acquired_file_only')

    def test_ledger_rejects_field_digest_duplicate_ids_and_unknown_windows(self):
        row=self.row()
        for rows in [[row,row],[row|{'elementSha256':'drift'}],[row|{'windowIds':['unknown']}],[row|{'windowIds':['q','q']}]]:
            with self.assertRaises(PilotError):self.ledger(rows)

    def test_proposed_selection_caps_change_internal_allocation_only(self):
        result=capture.proposal_for({'windows':[],'proposedCaps':{}},'run',capture.RUN_CAPS)['proposedCaps']
        self.assertEqual((result['selectedUniqueTypedElements'],result['selectedWindowElementOccurrences']),(2000000,4000000))
        self.assertEqual(result['retainedNativeObjectBytes'],512*1024**2)
        self.assertEqual(result['normalizedExtractBytes'],1024**3)
        self.assertEqual(result['singleNormalizedElementBytes'],8*1024**2)

    def test_native_per_pass_cap_stays_one_complete_source(self):
        instance=object.__new__(resources.FullScreen)
        with patch('coarse_osm_country_screen_v7.NativeScreen.scan',return_value={}) as call:
            instance.scan('source','snapshot',{'scanObjectVisitsTotal':2*resources.MAX_VISITS})
            self.assertEqual(call.call_args.args[2]['scanObjectVisitsTotal'],resources.MAX_VISITS)

    def test_streaming_ledger_rejects_out_of_order_rows(self):
        row=self.row();other=self.row();other['element']=other['element']|{'id':6}
        other['elementSha256']=hashlib.sha256(canonical(other['element'])).hexdigest()
        with self.assertRaises(PilotError):self.ledger([row,other])
