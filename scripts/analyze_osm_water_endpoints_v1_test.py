import gzip
import io
import json
from pathlib import Path
import tempfile
import unittest

from analyze_osm_water_endpoints_v1 import analyze,replay_chains
from coarse_osm_country_wire_v4 import framed_records
from coarse_osm_water_census_v2_test import way
from coarse_osm_water_endpoints_v1 import extract,relation_chains
from coarse_osm_water_reference_store_v1 import Budget,Shards


def relation(identity,members):return {'id':identity,'tags':{'type':'multipolygon','natural':'water'},'members':
                                       [{'type':'way','ref':i,'role':role} for i,role in members]}


class Controls(unittest.TestCase):
    def fixture(self,root,missing_input=False):
        inputs=root/'inputs';inputs.mkdir();outputs=root/'outputs';outputs.mkdir()
        raw=framed_records([way(10,{},[1,2,3]),way(20,{},[3,4,1]),way(30,{},[9,10,11,9])])
        writer=Shards(inputs,'ways',Budget());writer.write(raw);manifest=writer.finish()
        first=relation(1,[(10,'outer'),(20,'outer'),(30,'inner')])
        second=relation(2,[(99,'outer')])
        for name,row in [('roots.gz',first),('desc.gz',second)]:
            with gzip.open(inputs/name,'wt') as stream:stream.write(json.dumps(row)+'\n')
        ids=[10,20,30] if missing_input else [1,10,20,30,99]
        return outputs,inputs,manifest,ids,[(True,inputs/'roots.gz'),(False,inputs/'desc.gz')]

    def test_complete_saved_pipeline_roundtrip_audit_and_preserved_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            args=self.fixture(Path(directory));result=analyze(*args)
            self.assertEqual(result['captured']['sourceWayRecords'],3)
            self.assertEqual(result['captured']['sourceReferenceOccurrences'],10)
            self.assertEqual(result['captured']['missingMemberWayIds'],[1,99])
            self.assertEqual(result['rootStatusCounts'],{'explicit_role_degree2_closed_chains':1})
            self.assertEqual(result['additionalStatusCounts'],{'missing_way_member':1})
            self.assertEqual(result['explicitRoleChainMemberOccurrencesIndependentlyReplayed'],3)
            self.assertEqual(result['allRelationDiagnosticsReopened'],2)
            self.assertFalse(result['coordinatesExamined'] or result['polygonValidityEstablished'])

    def test_independent_chain_replay_rejects_wrong_direction_omission_and_role(self):
        raw=framed_records([way(10,{},[1,2,3]),way(20,{},[3,4,1])]);facts,_=extract(io.BytesIO(raw),[10,20])
        source=relation(1,[(10,'outer'),(20,'outer')])
        for mode in ('direction','omission','role'):
            result=relation_chains(source,facts)
            if mode=='direction':result['outer']['closedChains'][0][0][1]=-1
            elif mode=='omission':result['outer']['closedChains'][0].pop()
            else:result['inner']['closedChains']=result['outer']['closedChains'];result['outer']['closedChains']=[]
            with self.assertRaises(Exception):replay_chains(source,result,facts)

    def test_mismatched_complete_member_input_is_not_silently_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            args=self.fixture(Path(directory),True)
            with self.assertRaises(Exception):analyze(*args)


if __name__=='__main__':unittest.main()
