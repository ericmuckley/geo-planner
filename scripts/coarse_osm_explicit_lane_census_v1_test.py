"""Independent tag/counter oracle for the bounded native lane consumer."""
import random
from pathlib import Path
import tempfile
import unittest

import coarse_osm_car_conditional_speed_v1 as old
import coarse_osm_car_explicit_lanes_v1 as new
from coarse_osm_conditional_census_v1_test import CAPS, STATE, node, way, RecordTests
from coarse_osm_conditional_records_v1 import read_records
from coarse_osm_country_wire_v4 import framed_records
from coarse_osm_explicit_lane_census_v1 import COUNTERS, ExplicitLaneCensus
from coarse_osm_explicit_lane_scan_v1 import audit
from coarse_timing_input import PilotError

ARTIFACT=None


def oracle(rows):
    c={key:0 for key in COUNTERS};changed=[]
    reasons=[None,'outside-major-profile','vehicle-ferry','access','area-ford-driveway-parking','conditional-or-way-restriction','lane-access','unsupported-oneway','unsupported-speed','directional-access']
    for row in rows:
        kind,tags=row['type'],row['tags'];c[kind+'s']+=1
        if kind=='relation':continue
        if kind=='node':
            before,after=old.node_policy(tags),new.node_policy(tags)
            assert before==after;c['allNodeFlagsExact']+=1
            c['oldUnblockedNodes']+=not before['blocked'];c['oldUnblockedNodesExact']+=not before['blocked']
            c['oldBlockedNodes']+=before['blocked'];c['newBlockedNodes']+=after['blocked']
            c['taggedNodes']+=before['tagged'];c['signalNodes']+=before['signal'];continue
        before,after=old.way_policy(tags),new.way_policy(tags)
        c['oldWayReason'+str(reasons.index(before.reason))]+=1;c['newWayReason'+str(reasons.index(after.reason))]+=1
        if before.reason=='outside-major-profile':assert before==after;continue
        c['majorWays']+=1;c['allMajorWayPoliciesCompared']+=1;c['majorReferences']+=len(row['nodes'])
        c['oldEligibleWays']+=before.reason is None;c['newEligibleWays']+=after.reason is None
        c['laneRejectedWays']+=before.reason=='lane-access';c['laneFallbackWays']+=before.reason==after.reason=='lane-access'
        if before.reason is None:assert before==after;c['oldEligibleWaysExact']+=1
        elif after.reason is None:
            assert before.reason=='lane-access';c['newlyEligibleWays']+=1
            c['newLaneWaysWithSpeedConditional' if any(k in tags for k in old.SPEED_KEYS) else 'newLaneWaysWithoutSpeedConditional']+=1
            changed.append({key:row[key] for key in ('type','id','tags')})
        else:assert before==after;c['unchangedExcludedMajorWaysExact']+=1
    return c,changed


def lane(**extra):return {'highway':'motorway','oneway':'yes','lanes':'3','motor_vehicle:lanes':'no|yes|yes','hov:lanes':'designated|yes|yes'}|extra


class Tests(unittest.TestCase):
    def engine(self):
        if ARTIFACT is None:self.skipTest('Explicit compiled lane census artifact required')
        return ExplicitLaneCensus(*ARTIFACT)

    def compare(self,rows,proof=False):
        expected,records=oracle(rows)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'changed';engine=self.engine();engine.begin(path)
            try:
                receipt=engine.validate_frames(framed_records(rows),STATE,CAPS,proof=proof);actual=engine.finish()
                for key,value in expected.items():
                    if key not in ('changedRecords','changedTagUtf8Bytes','changedEncodedBytes','maximumChangedRecordBytes','lastChangedWayId','complete'):
                        self.assertEqual(actual[key],value,key)
                self.assertEqual(list(read_records(path)),records);self.assertEqual(actual['changedRecords'],len(records))
                self.assertEqual(actual['changedEncodedBytes'],path.stat().st_size)
                self.assertEqual(actual['lastChangedWayId'],records[-1]['id'] if records else 0)
                self.assertEqual(actual['complete'],1)
                self.assertEqual(receipt['pythonProjectionFrames'],len(rows) if proof else 0)
                independent=audit(path,actual,lambda:None)
                self.assertEqual(independent['counts']['ways'],len(records))
                return actual,path.read_bytes()
            finally:engine.release()

    def test_explicit_ordinary_lane_and_all_ambiguous_forms(self):
        changes=[{}, {'motor_vehicle:lanes':'|yes|yes'},{'oneway':'no'},{'hov:lanes':'designated|designated|designated'},
                 {'lanes':'03'},{'motorcar':'no'},{'access:lanes:forward':'yes|yes|yes'},{'hov:conditional':'designated @ night'}]
        self.compare([way(i+1,lane(**extra)) for i,extra in enumerate(changes)])

    def test_all_previous_eligible_and_other_excluded_policies_exact(self):
        tags=[{'highway':role} for role in (*old.POLICY['roles'],'residential','construction')]
        tags += [lane(**extra) for extra in ({'access':'private'},{'route':'ferry'},{'maxspeed':'bad'},{'motorcar:conditional':'no @ night'})]
        self.compare([way(i+1,t) for i,t in enumerate(tags)])

    def test_source_direction_defaults_and_current_conditional_speed_baseline(self):
        self.compare([way(i+1,lane(**extra)) for i,extra in enumerate(({}, {'oneway':'-1'}, {'maxspeed':'35 mph'},
                      {'maxspeed:conditional':'20 @ wet'},{'hgv:conditional':'no @ night'}, {'oneway:motorcar':'no'}))])

    def test_every_source_node_flag_stays_exact(self):
        self.compare([node(i+1,tags) for i,tags in enumerate(({}, {'hgv:conditional':'no @ night'},
                      {'highway':'traffic_signals'},{'motorcar:conditional':'no @ night'},{'barrier':'gate','motorcar':'yes'}))])

    def test_generated_complete_mixed_streams(self):
        rng=random.Random(20261106)
        choices=[lane(),lane(oneway='-1'),lane(oneway='no'),lane(**{'motor_vehicle:lanes':'|yes|yes'}),
                 {'highway':'primary','maxspeed:conditional':'20 @ wet'}, {'highway':'residential'},lane(access='private')]
        for _ in range(50):
            self.compare([node(i+1,{'highway':'traffic_signals'} if i%2 else {}) for i in range(4)]+
                         [way(i+1,dict(rng.choice(choices))) for i in range(30)])

    def test_large_changed_frame_crosses_source_callback_boundaries(self):
        self.compare([way(1,lane(note='雪'*400000))])

    def test_proof_and_summary_modes_match_exactly(self):
        rows=[node(1,{}),way(1,lane())]
        self.assertEqual(self.compare(rows),self.compare(rows,True))

    def test_finish_lifecycle_exclusive_output_and_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine=self.engine();other=self.engine();path=Path(tmp)/'out';engine.begin(path)
            try:
                with self.assertRaises(PilotError):engine.finish()
                with self.assertRaises(PilotError):other.begin(Path(tmp)/'other')
                engine.validate_frames(framed_records([]),STATE,CAPS);engine.finish()
                with self.assertRaises(PilotError):engine.finish()
            finally:engine.release()
            with self.assertRaises(PilotError):engine.begin(path)

    def test_source_failure_and_output_caps_never_complete(self):
        for options in ({},{'output_bytes':20},{'record_limit':1}):
            with tempfile.TemporaryDirectory() as tmp:
                engine=self.engine();engine.begin(Path(tmp)/'out',**options)
                try:
                    rows=[way(i+1,lane()) for i in range(2)]
                    if not options:rows[-1]['nodes']=[1,0]
                    with self.assertRaises(PilotError):engine.validate_frames(framed_records(rows),STATE,CAPS)
                    with self.assertRaises(PilotError):engine.finish()
                finally:engine.release()

    def test_empty_and_relation_only_streams(self):
        self.compare([])
        self.compare([{'type':'relation','id':1,'version':1,'timestamp':STATE,'visible':True,'tags':{'type':'restriction'},'members':[]}])

    def test_callback_cancellation_cannot_finish_and_release_allows_new_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine=self.engine();engine.begin(Path(tmp)/'cancelled');calls=0
            def cancel():
                nonlocal calls
                calls+=1
                if calls>=2:raise RuntimeError('cancel lane census callback')
            try:
                with self.assertRaisesRegex(RuntimeError,'cancel lane census callback'):
                    engine.validate_frames(framed_records([way(1,lane())]),STATE,CAPS,check=cancel)
                with self.assertRaises(PilotError):engine.finish()
            finally:engine.release()
            engine.begin(Path(tmp)/'fresh')
            try:
                engine.validate_frames(framed_records([]),STATE,CAPS)
                self.assertEqual(engine.finish()['changedRecords'],0)
            finally:engine.release()
