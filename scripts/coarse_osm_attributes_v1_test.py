"""Native units, scope retention, metadata/geometry identity and unknown permissions."""
from copy import deepcopy
import hashlib
import unittest

from coarse_osm_attributes_v1 import numeric_speed,way_facts
from coarse_osm_records import canonical
from coarse_timing_input import PilotError

STATE='2026-10-25T21:21:21Z'


def record(element):
    return {'publisherStateUtc':STATE,'element':element,'elementSha256':hashlib.sha256(canonical(element)).hexdigest(),'windowIds':['arbitrary']}


def fixture(tags=None):
    nodes={i:record({'type':'node','id':i,'version':1,'timestamp':'2026-10-20T00:00:00Z','visible':True,
                     'tags':{'barrier':'gate'} if i==1 else {},'lon':i/100,'lat':0.25}) for i in (1,2)}
    way=record({'type':'way','id':9,'version':3,'timestamp':'2026-10-21T00:00:00Z','visible':True,
                'nodes':[2,1,2],'tags':{'highway':'primary','maxspeed':'55 mph',**(tags or {})},'extraSourceField':'preserved'})
    way['geometryDependencySha256']=hashlib.sha256(canonical([STATE,[nodes[i]['element'] for i in way['element']['nodes']]])).hexdigest()
    return way,nodes


class Tests(unittest.TestCase):
    def test_native_default_kmh_explicit_units_and_fractional_values(self):
        for raw,expected,unit in [('90',90,'km/h'),('90 km/h',90,'km/h'),('55 mph',88.51392,'mph'),('12.5 mph',20.1168,'mph')]:
            parsed=numeric_speed(raw);self.assertEqual(parsed['status'],'plain_numeric');self.assertAlmostEqual(parsed['kmh'],expected)
            self.assertEqual(parsed['sourceUnit'],unit);self.assertEqual(parsed['raw'],raw);self.assertFalse(parsed['usableForTiming'])

    def test_special_symbolic_variable_and_malformed_values_remain_unknown(self):
        for raw in ['none','walk','signals','variable','US:urban','30;50','50 @ wet','50|60','55 MPH',' 50','+50','1e2','NaN','Infinity','10 knots','9'*257]:
            result=numeric_speed(raw);self.assertEqual(result['status'],'unrecognized');self.assertIsNone(result['kmh']);self.assertEqual(result['raw'],raw)
        self.assertEqual(numeric_speed(None)['status'],'missing')
        self.assertEqual(numeric_speed('0')['status'],'nonpositive_or_nonfinite')
        for raw in [True,50,{},[]]:
            with self.assertRaises(PilotError):numeric_speed(raw)

    def test_all_raw_fields_ordered_geometry_and_duplicate_nodes_are_retained(self):
        way,nodes=fixture();saved=deepcopy(way);result=way_facts(way,nodes,snapshot=STATE)
        self.assertEqual(result['sourceRecord'],way);self.assertEqual(result['coordinates'],[[.02,.25],[.01,.25],[.02,.25]])
        self.assertEqual(result['orderedNodeElementSha256'],[nodes[i]['elementSha256'] for i in [2,1,2]])
        self.assertEqual(result['barrierNodeIds'],[1]);self.assertEqual(way,saved)
        way['element']['extraSourceField']='mutated afterwards';self.assertEqual(result['sourceRecord'],saved)

    def test_conditional_directional_lane_vehicle_and_unknown_scopes_are_not_flattened(self):
        scopes={'maxspeed:conditional':'35 @ wet','maxspeed:forward':'65 mph','maxspeed:backward':'45 mph','maxspeed:lanes':'45|55','maxspeed:hgv':'40','maxspeed:custom':'unknown'}
        way,nodes=fixture(scopes);result=way_facts(way,nodes,snapshot=STATE)
        self.assertEqual(result['speedScopeTags'],scopes);self.assertFalse(result['plainNumericWithoutSpeedScopes']);self.assertFalse(result['usableForTiming'])

    def test_source_annotations_are_retained_without_inventing_a_scope(self):
        way,nodes=fixture({'maxspeed:type':'sign','maxspeed:reason':'local text','source:maxspeed':'signage'})
        result=way_facts(way,nodes,snapshot=STATE);self.assertTrue(result['plainNumericWithoutSpeedScopes'])
        self.assertEqual(result['sourceRecord']['element']['tags'],way['element']['tags']);self.assertFalse(result['usableForTiming'])

    def test_access_direction_and_structure_are_facts_without_permissions(self):
        tags={'access':'yes','motor_vehicle':'private','motorcar:conditional':'yes @ permit','oneway':'-1','oneway:conditional':'yes @ wet','layer':'-1','tunnel':'yes','junction':'roundabout'}
        way,nodes=fixture(tags);result=way_facts(way,nodes,snapshot=STATE)
        self.assertEqual(result['accessTags'],{k:v for k,v in tags.items() if k.startswith(('access','motor_')) or k.startswith('motorcar')})
        self.assertEqual(result['directionTags'],{'oneway':'-1','oneway:conditional':'yes @ wet'})
        self.assertEqual(result['carPermission'],'unreviewed');self.assertFalse(result['usableForTiming'])

    def test_missing_or_changed_same_version_node_geometry_and_metadata_fail(self):
        way,nodes=fixture()
        with self.assertRaises(PilotError):way_facts(way,{1:nodes[1]},snapshot=STATE)
        for field,value in [('lon',.4),('tags',{'barrier':'bollard'})]:
            damaged=deepcopy(nodes);damaged[1]['element'][field]=value
            damaged[1]['elementSha256']=hashlib.sha256(canonical(damaged[1]['element'])).hexdigest()
            with self.assertRaises(PilotError):way_facts(way,damaged,snapshot=STATE)

    def test_snapshot_field_seals_and_typed_references_are_required(self):
        for mode in ['snapshot','hash','bool','extraFutureTimestamp']:
            way,nodes=fixture()
            if mode=='snapshot':way['publisherStateUtc']='2026-10-24T00:00:00Z'
            if mode=='hash':way['elementSha256']='0'*64
            if mode=='bool':way['element']['nodes'][0]=True
            if mode=='extraFutureTimestamp':way['element']['timestamp']='2026-10-26T00:00:00Z'
            with self.assertRaises(PilotError):way_facts(way,nodes,snapshot=STATE)

    def test_arbitrary_roles_and_tags_have_no_place_specific_defaults(self):
        for role,supported in [('motorway_link',True),('primary',True),('footway',False),('construction',False),('custom',False)]:
            way,nodes=fixture({'highway':role,'maxspeed':'US:custom','name':'arbitrary'})
            result=way_facts(way,nodes,snapshot=STATE)
            self.assertEqual(result['roadRoleSupportedForLaterScreen'],supported);self.assertIsNone(result['speed']['kmh']);self.assertFalse(result['usableForTiming'])
