"""Capacity recipe, source receipts, query derivation and original-window guards."""
from copy import deepcopy
import unittest

import run_osm_cell_census_v1 as cell
from coarse_timing_input import PilotError


def plan():
    fine=cell.FIXTURE+'/full-prototype/audit-index';catalog=fine+'/index.json'
    return {'stage':'controls','phase':'window_cell_capacity_v1','caps':deepcopy(cell.CONTROL_CAPS),'output':cell.OUTPUTS['controls'],
            'imageId':cell.IMAGE,'network':'none','artifact':{'path':cell.ARTIFACT,'sha256':cell.ARTIFACT_SHA},'site':cell.SITE,'runtime':cell.RUNTIME,
            'retainedReservationBytes':cell.RETAINED,'ownedWorkLimitBytes':cell.OWNED,
            'parentQualification':{'recipe':cell.REPORT+'/qualification-plan-v12.json','sha256':'d0be6ce2f68459e9aad0e76f3241e99bfe118c2e651e03789dddfb77370c2cec','tests':38,'skips':0},
            'source':{'path':cell.FIXTURE+'/full-fixture.pbf','counts':{'node':4,'way':3,'relation':2},'sha256':'source','md5':'md5','publisherState':'state','bytes':564},
            'fineInput':fine,'catalog':catalog,'semantic':'semantic','highwayWays':2,'windows':[{'id':'a','bbox':[0,0,1,1]},{'id':'b','bbox':[.25,.25,.75,.75]}],
            'queryIDs':[1,4],'mounts':{catalog:'/inputs/catalog.json'},'inputs':{catalog:'catalog',cell.ARTIFACT:cell.ARTIFACT_SHA},
            'workerFiles':{'/inputs/catalog.json':'catalog','/artifacts/helper.so':cell.ARTIFACT_SHA}}


class Tests(unittest.TestCase):
    def test_tiny_recipe_and_fixed_source_boundary_queries(self):
        cell.validate(plan())
        self.assertEqual(cell.queries({'shards':[{'first':1,'last':4},{'first':7,'last':7}]}),[1,4,7])

    def test_caps_accounting_source_path_and_artifact_drift_fail(self):
        for key,value in [('caps',cell.CONTROL_CAPS|{'bankBytes':cell.CONTROL_CAPS['bankBytes']+1}),
                          ('retainedReservationBytes',cell.RETAINED-1),('fineInput','old-failed.sqlite'),
                          ('artifact',{'path':cell.ARTIFACT,'sha256':'other'})]:
            damaged=plan();damaged[key]=value
            with self.assertRaises(PilotError):cell.validate(damaged)

    def test_invalid_duplicate_unsorted_or_missing_reference_queries_fail(self):
        for ids in [[],[True,4],[0,4],[4,1],[1,1],[1,2**63]]:
            damaged=plan();damaged['queryIDs']=ids
            with self.assertRaises(PilotError):cell.validate(damaged)

    def receipt(self):
        return {'nativeEof':True,'counts':{'node':4,'way':3,'relation':2},'visits':9,'semanticSha256':'semantic',
                'sourceIdentity':{'sourceSha256':'source','sourceMd5':'md5','publisherStateUtc':'state'},'postSourceHashBytes':564,'knownGuardReadBytes':1128,'highwayWays':2,'pythonProjectionFrames':0,'batchWays':0,
                'selectedNodeProjections':0,'restrictionProjections':0,'witnessRows':2}

    def test_whole_source_eof_fields_counts_projection_and_witnesses_are_mandatory(self):
        cell.check_receipt(self.receipt(),plan())
        for key,value in [('nativeEof',False),('counts',{'node':4,'way':2,'relation':2}),('visits',8),
                          ('semanticSha256','changed'),('sourceIdentity',{'sourceSha256':'changed','sourceMd5':'md5'}),
                          ('postSourceHashBytes',563),('knownGuardReadBytes',1127),('highwayWays',1),('pythonProjectionFrames',1),('batchWays',1),('witnessRows',1)]:
            damaged=self.receipt();damaged[key]=value
            with self.assertRaises(PilotError):cell.check_receipt(damaged,plan())

    def test_original_national_windows_cannot_be_changed(self):
        windows=[{'id':str(i),'bbox':[0,0,1,1]} for i in range(21)];p={'stage':'run','windows':windows}
        cell.check_windows(p,{'windows':deepcopy(windows)})
        proposal={'windows':deepcopy(windows)};proposal['windows'][0]['bbox'][0]=-.1
        with self.assertRaises(PilotError):cell.check_windows(p,proposal)

    def test_code_mount_escape_and_source_hash_closure_are_rejected(self):
        damaged=plan();damaged['inputs'][damaged['source']['path']]='source'
        with self.assertRaises(PilotError):cell.validate(damaged)
        damaged=plan();damaged['mounts']['scripts/../.env']='/code/config';damaged['inputs']['scripts/../.env']='bad'
        with self.assertRaises(PilotError):cell.validate(damaged)
