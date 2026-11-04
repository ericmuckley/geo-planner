"""Inventory preserves every record/area and reports tag presence, never usability."""
from copy import deepcopy
import hashlib
import io
import unittest

from coarse_osm_attribute_inventory_v1 import CAPS,inventory,merged
from coarse_osm_records import canonical
from coarse_timing_input import PilotError

STATE='2026-10-25T21:21:21Z'
WINDOWS=[{'id':'outer','bbox':[0,0,1,1]},{'id':'inner','bbox':[.25,.25,.75,.75]}]


def record(element):
    return {'publisherStateUtc':STATE,'element':element,'elementSha256':hashlib.sha256(canonical(element)).hexdigest(),'windowIds':[w['id'] for w in WINDOWS]}


def fixture(tags=None):
    common={'version':1,'timestamp':'2026-10-20T00:00:00Z','visible':True}
    nodes=[record(common|{'type':'node','id':i,'tags':{'barrier':'gate'} if i==1 else {},'lon':x,'lat':.5}) for i,x in [(1,-1.),(2,2.)]]
    relation=record(common|{'type':'relation','id':1,'tags':{'type':'restriction'},'members':[{'type':'way','ref':999,'role':'to'}]})
    way=record(common|{'type':'way','id':1,'nodes':[1,2],'tags':{'highway':'primary','maxspeed':'55 mph','access':'private','maxspeed:conditional':'35 @ wet',**(tags or {})}})
    way['geometryDependencySha256']=hashlib.sha256(canonical([STATE,[r['element'] for r in nodes]])).hexdigest()
    return [*nodes,relation,way]


def run(rows,**options):
    caps=CAPS|{'nodeCanonicalBytes':1048576}|options.pop('caps',{})
    return inventory(io.BytesIO(b''.join(canonical(r)+b'\n' for r in rows)),snapshot=STATE,windows=options.pop('windows',WINDOWS),caps=caps,**options)


class Tests(unittest.TestCase):
    def test_all_records_scopes_raw_permissions_and_union_length(self):
        rows=fixture();result=run(rows);self.assertEqual(result['types'],{'node':2,'relation':1,'way':1});self.assertEqual(result['occurrences'],8)
        all_roads=result['allCapturedHighways'];outer,inner=[w['allCapturedHighways'] for w in result['windows']]
        self.assertEqual(all_roads['ways'],1);self.assertEqual(all_roads['plainNumericWays'],1);self.assertEqual(all_roads['unscopedNumericWays'],0)
        self.assertEqual(all_roads['accessTagWays'],1);self.assertGreater(all_roads['clippedMeters'],111180);self.assertLess(all_roads['clippedMeters'],111200)
        self.assertEqual(all_roads['clippedMeters'],outer['clippedMeters']);self.assertAlmostEqual(outer['clippedMeters'],2*inner['clippedMeters'],delta=.01)
        self.assertEqual(result['barrierTagNodes'],1);self.assertFalse(result['usableForTiming']);self.assertFalse(result['permissionsReviewed']);self.assertFalse(result['usableLimitOrMatchingGateQualified'])

    def test_numeric_presence_never_means_reviewed_private_access(self):
        rows=fixture();way=rows[-1];way['element']['tags'].pop('maxspeed:conditional');way['elementSha256']=hashlib.sha256(canonical(way['element'])).hexdigest()
        result=run(rows);self.assertEqual(result['allCapturedHighways']['unscopedNumericLengthFraction'],1);self.assertFalse(result['usableForTiming'])

    def test_missing_symbolic_units_and_unknown_roles_remain_present(self):
        for speed in [None,'US:urban','none','55 MPH']:
            rows=fixture({'highway':'custom'});tags=rows[-1]['element']['tags']
            if speed is None:tags.pop('maxspeed')
            else:tags['maxspeed']=speed
            rows[-1]['elementSha256']=hashlib.sha256(canonical(rows[-1]['element'])).hexdigest();result=run(rows)
            self.assertEqual(result['byRole']['other']['ways'],1);self.assertEqual(result['supportedRoadRoles']['ways'],0);self.assertEqual(result['allCapturedHighways']['plainNumericWays'],0)

    def test_changed_same_version_node_metadata_and_missing_geometry_fail(self):
        rows=fixture();rows[0]['element']['tags']['barrier']='bollard';rows[0]['elementSha256']=hashlib.sha256(canonical(rows[0]['element'])).hexdigest()
        with self.assertRaisesRegex(PilotError,'geometry dependency'):run(rows)
        with self.assertRaisesRegex(PilotError,'missing geometry'):run([fixture()[0],*fixture()[2:]])

    def test_field_snapshot_membership_and_sorted_identity_are_required(self):
        for mode in ['field','snapshot','window','duplicate','order']:
            rows=fixture()
            if mode=='field':rows[0]['elementSha256']='0'*64
            if mode=='snapshot':rows[0]['publisherStateUtc']='2026-10-24T00:00:00Z'
            if mode=='window':rows[0]['windowIds']=['unknown']
            if mode=='duplicate':rows.insert(1,deepcopy(rows[0]))
            if mode=='order':rows[0],rows[1]=rows[1],rows[0]
            with self.assertRaises(PilotError):run(rows)

    def test_every_resource_cap_and_external_check_remains_effective(self):
        for key in ['records','occurrences','inputBytes','recordBytes','wayReferences','nodeCanonicalBytes']:
            with self.assertRaises(PilotError):run(fixture(),caps={key:1})
        def expired():raise PilotError('outer deadline')
        with self.assertRaisesRegex(PilotError,'outer deadline'):run(fixture(),check=expired)

    def test_interval_merging_disjoint_empty_and_zero_length_cases(self):
        self.assertEqual(merged([(0,.5),(.25,.75),(.8,1)]),[(0,.75),(.8,1)]);self.assertEqual(merged([]),[])
        result=run([]);self.assertIsNone(result['allCapturedHighways']['plainNumericLengthFraction']);self.assertFalse(result['usableForTiming'])

    def test_duplicate_window_or_invalid_native_precision_is_rejected(self):
        with self.assertRaises(PilotError):run(fixture(),windows=[WINDOWS[0],WINDOWS[0]])
        rows=fixture();rows[0]['element']['lon']=.123456789;rows[0]['elementSha256']=hashlib.sha256(canonical(rows[0]['element'])).hexdigest()
        with self.assertRaisesRegex(PilotError,'native coordinate precision'):run(rows)
