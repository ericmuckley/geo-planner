"""Independent Python policy/count/raw-tag oracle, synthetic target input only."""
import random
from pathlib import Path
import tempfile
import unittest
from coarse_osm_country_wire_v4 import framed_records
from coarse_osm_native_smoke import STATE
from coarse_osm_conditional_census_v1 import ConditionalCensus
from coarse_osm_conditional_records_v1 import read_records
import coarse_osm_car_policy_v2 as old
import coarse_osm_car_conditional_speed_v1 as new
from coarse_timing_input import PilotError

ARTIFACT=None
CAPS={'singleNormalizedElementBytes':4194304,'scanNodesPerPass':10000,'scanWaysPerPass':10000,'scanRelationsPerPass':10000,'scanObjectVisitsTotal':30000,'pbfHeaderBytesExclusiveMaximum':65536,'pbfUncompressedBlobBytesExclusiveMaximum':33554432}


def node(i,tags):return {'type':'node','id':i,'version':1,'timestamp':STATE,'visible':True,'tags':tags,'lon':0.,'lat':0.}
def way(i,tags):return {'type':'way','id':i,'version':1,'timestamp':STATE,'visible':True,'tags':tags,'nodes':[1,2,3]}


def oracle(rows):
    from coarse_osm_conditional_census_v1 import COUNTERS
    c={k:0 for k in COUNTERS};changed=[]
    for r in rows:
        kind,tags=r['type'],r['tags'];c[kind+'s']+=1
        conditional=any(k.endswith(':conditional') for k in tags)
        if kind=='relation':continue
        if kind=='node':
            a,b=old.node_policy(tags),new.node_policy(tags)
            c['nodesWithConditional']+=conditional;c['oldUnblockedNodes']+=not a['blocked'];c['oldUnblockedNodesExact']+=not a['blocked']
            c['oldBlockedNodes']+=a['blocked'];c['newBlockedNodes']+=b['blocked'];c['taggedNodes']+=a['tagged'];c['signalNodes']+=a['signal']
            if any(a[k]!=b[k] for k in ('blocked','signal','tagged')):c['changedNodeFlags']+=1;changed.append(r)
        else:
            a,b=old.way_policy(tags),new.way_policy(tags)
            reasons=[None,'outside-major-profile','vehicle-ferry','access','area-ford-driveway-parking','conditional-or-way-restriction','lane-access','unsupported-oneway','unsupported-speed','directional-access']
            c['oldWayReason'+str(reasons.index(a.reason))]+=1;c['newWayReason'+str(reasons.index(b.reason))]+=1
            if a.reason=='outside-major-profile':continue
            c['majorWays']+=1;c['majorReferences']+=len(r['nodes'])
            c['oldEligibleWays']+=a.reason is None;c['newEligibleWays']+=b.reason is None;c['oldEligibleWaysExact']+=a.reason is None
            speed=any(k in tags for k in new.SPEED_KEYS)
            c['majorWaysWithConditional']+=conditional;c['majorWaysWithSpeedConditional']+=speed
            c['speedConditionalStillExcludedWays']+=speed and b.reason is not None;c['oldExcludedConditionalWays']+=conditional and a.reason is not None
            c['majorIgnoredNonCarKeys']+=len(new.ignored_keys(tags))
            if a.reason is not None and b.reason is None:
                c['newlyEligibleWays']+=1;c['newSpeedConditionalWays' if speed else 'newNonCarScopedWays']+=1;changed.append(r)
    return c,[{k:r[k] for k in ('type','id','tags')} for r in changed]


class Tests(unittest.TestCase):
    def engine(self):
        if ARTIFACT is None:self.skipTest('Explicit compiled conditional census target required')
        return ConditionalCensus(*ARTIFACT)

    def compare(self,rows,proof=False):
        expected,records=oracle(rows)
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'changed.bin';engine=self.engine();engine.begin(output)
            try:
                receipt=engine.validate_frames(framed_records(rows),STATE,CAPS,proof=proof);actual=engine.finish()
                for name,value in expected.items():
                    if name not in ('changedRecords','changedTagUtf8Bytes','changedEncodedBytes','maximumChangedRecordBytes','lastChangedNodeId','lastChangedWayId','complete'):self.assertEqual(actual[name],value,name)
                self.assertEqual(list(read_records(output)),records);self.assertEqual(actual['changedRecords'],len(records));self.assertEqual(actual['changedEncodedBytes'],output.stat().st_size)
                self.assertEqual(actual['changedTagUtf8Bytes'],sum(len(k.encode())+len(v.encode()) for r in records for k,v in r['tags'].items()))
                self.assertEqual(actual['complete'],1);self.assertEqual(receipt['pythonProjectionFrames'],len(rows) if proof else 0)
                return actual,output.read_bytes()
            finally:engine.release()

    def test_noncar_and_car_node_scopes_preserve_signals_and_tagged_anchors(self):
        self.compare([node(i+1,t) for i,t in enumerate([{}, {'hgv:conditional':'no @ night'},{'foot:conditional':'no @ night','highway':'traffic_signals'},{'motorcar:conditional':'no @ night'},{'barrier':'gate','motorcar':'yes','bicycle:conditional':'no @ night'},{'maxspeed:conditional':'20 @ wet'}])])

    def test_static_numeric_units_and_nested_clauses(self):
        self.compare([way(i+1,{'highway':'primary','maxspeed':'80','maxspeed:conditional':v}) for i,v in enumerate(['25 mph @ children_present','20 mph @ (Mo-Fr 07:00-17:00)','30 @ (Mo; Tu); 40 @ wet','none @ wet','25 mph'])])

    def test_all_old_positive_profiles_and_nonprofile_retained(self):
        self.compare([way(i+1,{'highway':role}) for i,role in enumerate([*old.POLICY['roles'],'residential','construction'])])

    def test_access_unknown_values_and_other_constraints_stay_closed(self):
        extra=[{'access':'private'},{'oneway:conditional':'yes @ night'},{'motorcar:conditional':'no @ night'},{'maxspeed:motorcar:conditional':'20 @ wet'},{'access:lanes':'yes|no'},{'route':'ferry'}]
        self.compare([way(i+1,{'highway':'primary','maxspeed:conditional':'20 @ wet'}|t) for i,t in enumerate(extra)])

    def test_directional_defaults_and_oneway_preserved(self):
        self.compare([way(i+1,{'highway':'secondary','oneway':v,'maxspeed:forward:conditional':'20 @ wet'}) for i,v in enumerate(['yes','no','-1'])])

    def test_generated_complete_mixed_policy_sets(self):
        rng=random.Random(20261105);choices=[{}, {'maxspeed:conditional':'20 @ wet'},{'hgv:conditional':'no @ night'},{'motorcar:conditional':'no @ night'},{'maxspeed:conditional':'signals @ wet'}]
        for _ in range(50):self.compare([node(i+1,dict(rng.choice(choices))) for i in range(10)]+[way(i+1,{'highway':rng.choice(['primary','motorway','residential'])}|rng.choice(choices)) for i in range(20)])

    def test_large_changed_frame_crosses_source_callback_boundaries(self):
        self.compare([way(1,{'highway':'primary','maxspeed:conditional':'20 @ wet','note':'x'*1200000})])

    def test_proof_and_summary_modes_emit_identical_changed_tags(self):
        rows=[node(1,{'hgv:conditional':'no @ night'}),way(1,{'highway':'primary','maxspeed:conditional':'20 @ wet'})]
        self.assertEqual(self.compare(rows),self.compare(rows,True))

    def test_finish_lifecycle_and_exclusive_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine=self.engine();other=self.engine();p=Path(tmp)/'out';engine.begin(p)
            try:
                with self.assertRaises(PilotError):engine.finish()
                with self.assertRaises(PilotError):other.begin(Path(tmp)/'other')
                engine.validate_frames(framed_records([]),STATE,CAPS);engine.finish()
                with self.assertRaises(PilotError):engine.finish()
            finally:engine.release()
            with self.assertRaises(PilotError):engine.begin(p)

    def test_source_failure_keeps_incomplete_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine=self.engine();engine.begin(Path(tmp)/'out')
            try:
                broken=way(1,{'highway':'primary','maxspeed:conditional':'20 @ wet'});broken['nodes']=[1,0]
                with self.assertRaises(PilotError):engine.validate_frames(framed_records([broken]),STATE,CAPS)
                with self.assertRaises(PilotError):engine.finish()
            finally:engine.release()

    def test_output_byte_and_record_caps_fail_before_complete(self):
        for options in ({'output_bytes':20},{'record_limit':1}):
            with tempfile.TemporaryDirectory() as tmp:
                engine=self.engine();engine.begin(Path(tmp)/'out',**options)
                try:
                    rows=[way(i+1,{'highway':'primary','maxspeed:conditional':'20 @ wet'}) for i in range(2)]
                    with self.assertRaises(PilotError):engine.validate_frames(framed_records(rows),STATE,CAPS)
                    with self.assertRaises(PilotError):engine.finish()
                finally:engine.release()

    def test_empty_and_relation_only_metadata_are_complete(self):
        self.compare([])
        self.compare([{'type':'relation','id':1,'version':1,'timestamp':STATE,'visible':True,'tags':{'type':'restriction','restriction:conditional':'no @ night'},'members':[]}])


class RecordTests(unittest.TestCase):
    @staticmethod
    def encoded(kind=1,identity=1,tags=(('maxspeed:conditional','20 @ 雪'),)):
        import struct
        body=b'CST1'+bytes([kind,0,0,0])+struct.pack('<QI',identity,len(tags))
        for key,value in tags:
            for text in (key,value):
                raw=text.encode();body+=struct.pack('<I',len(raw))+raw
        return struct.pack('<I',len(body))+body

    def test_exact_unicode_tags_without_coordinate_or_reference_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'records';p.write_bytes(self.encoded())
            self.assertEqual(list(read_records(p)),[{'type':'way','id':1,'tags':{'maxspeed:conditional':'20 @ 雪'}}])

    def test_corrupt_truncated_duplicate_unsorted_and_bad_identity_rejected(self):
        good=self.encoded()
        for raw in (good[:-1],good+b'x',b'\x00\x00\x00\x00',self.encoded(kind=2),self.encoded(identity=0),self.encoded(tags=(('a','1'),('a','2'))),self.encoded(tags=(('z','1'),('a','2'))),good+good,good.replace(b'CST1',b'bad!'),good.replace('雪'.encode(),b'\xff\xff\xff')):
            with tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp)/'records';p.write_bytes(raw)
                with self.assertRaises((AssertionError,UnicodeDecodeError)):list(read_records(p))

    def test_whole_file_cap_precedes_record_allocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'large'
            with p.open('wb') as stream:stream.truncate(48*1048576+1)
            with self.assertRaises(AssertionError):list(read_records(p))
