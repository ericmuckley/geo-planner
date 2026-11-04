"""Native junction/terminal/competitor/resource controls; no real data."""
from copy import deepcopy
import hashlib
import io
import unittest

from coarse_osm_match_v1 import CAPS,Index,attributes,match,read_nodes,read_window,summary
from coarse_osm_records import canonical
from coarse_timing_input import PilotError

STATE='2026-10-25T21:21:21Z';BOX=[0,-.001,.01,.001]


def fixture(points=None,ways=None):
    points=points or {1:[-.001,0],2:[.005,0],3:[.011,0]}
    ways=ways or [([1,2,3],{'highway':'primary','maxspeed':'55 mph'})]
    common={'version':1,'timestamp':'2026-10-20T00:00:00Z','visible':True}
    elements=[common|{'type':'node','id':i,'lon':p[0],'lat':p[1],'tags':{}} for i,p in sorted(points.items())]
    nodes={e['id']:e for e in elements};rows=[]
    for i,(refs,tags) in enumerate(ways):elements.append(common|{'type':'way','id':i+1,'nodes':refs,'tags':tags})
    for e in elements:
        r={'publisherStateUtc':STATE,'element':e,'elementSha256':hashlib.sha256(canonical(e)).hexdigest(),'windowIds':['a']}
        if e['type']=='way':r['geometryDependencySha256']=hashlib.sha256(canonical([STATE,[nodes[i] for i in e['nodes']]])).hexdigest()
        rows.append(r)
    return rows


def stream(rows):return io.BytesIO(b''.join(canonical(r)+b'\n' for r in rows))
def source():return {'windowId':'a','arc':1,'sourceClassKph':105,'sourceKm':7.,'sourceSpans':[[[0,0],[.01,0],7.]]}


def prepare(rows=None,caps=None):
    caps=CAPS|{'nodeCanonicalBytes':1048576}|(caps or {});rows=fixture() if rows is None else rows
    nodes,receipt=read_nodes(stream(rows),STATE,caps=caps);meta,lines,scan=read_window(stream(rows),nodes,'a',caps=caps)
    assert receipt['sha256']==scan['sha256']
    return meta,lines,Index(lines,BOX,caps=caps),caps


def run(rows=None,caps=None):
    meta,lines,index,caps=prepare(rows,caps);return match(source(),meta,lines,index,BOX,caps=caps)


class Tests(unittest.TestCase):
    def test_overhanging_native_way_keeps_raw_lineage_and_unreviewed_attributes(self):
        r=run();self.assertEqual(r['status'],'single_acquired_file_geometric_path');self.assertEqual(len(r['candidates']),1)
        self.assertAlmostEqual(r['candidates'][0]['maximumSupportedKm'],7);binding=r['alignedPartBindings'][0]
        self.assertEqual(binding['nativeWayId'],1);self.assertEqual(binding['firstNodeIndex'],0);self.assertEqual(binding['lastNodeIndex'],2)
        self.assertEqual(binding['attributes']['speed']['kmh'],88.51392);self.assertFalse(binding['attributes']['usableForTiming']);self.assertFalse(r['usableLimitOrMatchingQualified'])

    def test_shared_node_joins_split_ways_and_reversal(self):
        tags={'highway':'primary','maxspeed':'50'}
        for ways in ([([1,2],tags),([2,3],tags)],[([2,1],tags),([3,2],tags)]):
            r=run(fixture(ways=ways));self.assertEqual(r['status'],'single_acquired_file_geometric_path');self.assertEqual(len(r['candidates'][0]['nativeParts']),2)

    def test_interior_native_junction_splits_parent_way(self):
        tags={'highway':'primary'};points={1:[-.001,0],2:[.005,0],3:[.011,0],4:[.005,.0005]}
        meta,lines,_,_=prepare(fixture(points,[([1,2,3],tags),([2,4],tags)]))
        self.assertEqual([(m['nativeWayId'],m['firstNodeIndex'],m['lastNodeIndex']) for m in meta],[(1,0,1),(1,1,2),(2,0,1)])
        self.assertEqual(meta[0]['endpointIds'][1],meta[1]['endpointIds'][0]);self.assertEqual(meta[1]['endpointIds'][0],meta[2]['endpointIds'][0])

    def test_coincident_coordinates_without_shared_identity_never_join(self):
        tags={'highway':'primary'};points={1:[-.001,0],2:[.005,0],3:[.011,0],4:[.005,0]}
        r=run(fixture(points,[([1,2],tags),([4,3],tags)]));self.assertFalse(r['candidates']);self.assertEqual(r['status'],'no_path_under_fragment_rules')

    def test_parallel_competitors_and_grade_context_remain_visible(self):
        points={1:[-.001,0],2:[.011,0],3:[-.001,.0001],4:[.011,.0001]};tags={'highway':'primary','maxspeed':'50'}
        r=run(fixture(points,[([1,2],tags),([3,4],tags|{'layer':'1','bridge':'yes'})]))
        self.assertEqual(r['status'],'multiple_acquired_file_geometric_paths');self.assertEqual(len(r['candidates']),2);self.assertEqual(r['alignedPartBindings'][1]['attributes']['structureTags']['layer'],'1');self.assertFalse(r['uniquePhysicalMatchQualified'])

    def test_unknown_role_alternative_blocks_a_unique_geometric_claim(self):
        r=run(fixture(ways=[([1,2,3],{'highway':'primary'}),([1,2,3],{'highway':'unknown'})]));self.assertEqual(r['status'],'unresolved_aligned_alternatives');self.assertTrue(r['unrepresentedParts'])

    def test_speed_access_scope_and_oneway_tags_are_preserved_without_permission(self):
        tags={'highway':'primary','maxspeed':'55 mph','maxspeed:conditional':'20 @ wet','motorcar':'yes','access':'private','oneway':'-1','layer':'-1'}
        a=attributes(tags);self.assertEqual(a['speedScopeTags'],{'maxspeed:conditional':'20 @ wet'});self.assertEqual(a['accessTags'],{'motorcar':'yes','access':'private'});self.assertEqual(a['directionTags'],{'oneway':'-1'});self.assertFalse(a['unscopedNumeric']);self.assertEqual(a['carPermission'],'unreviewed')
        self.assertEqual(tags['maxspeed'],'55 mph');self.assertFalse(a['usableForTiming'])

    def test_changed_node_under_same_way_version_breaks_dependency(self):
        rows=fixture();rows[0]['element']['tags']['barrier']='gate';rows[0]['elementSha256']=hashlib.sha256(canonical(rows[0]['element'])).hexdigest()
        with self.assertRaisesRegex(PilotError,'geometry dependency'):prepare(rows)
        with self.assertRaises(PilotError):prepare(fixture()[1:])

    def test_barrier_node_context_is_retained(self):
        rows=fixture();rows[1]['element']['tags']['barrier']='gate';rows[1]['elementSha256']=hashlib.sha256(canonical(rows[1]['element'])).hexdigest();rows[-1]['geometryDependencySha256']=hashlib.sha256(canonical([STATE,[r['element'] for r in rows[:-1]]])).hexdigest()
        r=run(rows);self.assertEqual(r['alignedPartBindings'][0]['attributes']['barrierNodeIds'],[2]);self.assertFalse(r['carPermissionReviewed'])

    def test_read_index_and_membership_caps_fail_closed(self):
        for cap in ('nodeCanonicalBytes','geometryReferences','inputBytes','rowBytes','records','windowWays','windowReferences','parts','indexSegments','binEntries','comparisons','arcSamples','sampleMemberships'):
            with self.subTest(cap=cap),self.assertRaises(PilotError):run(fixture(ways=[([1,2],{'highway':'primary'}),([2,3],{'highway':'primary'})]),{cap:1})

    def test_search_and_projection_caps_keep_original_denominator(self):
        rows=fixture(ways=[([1,2],{'highway':'primary'}),([2,3],{'highway':'primary'})])
        for caps in ({'searchRows':1},{'searchStates':1},{'projectionComparisons':1}):
            r=run(rows,caps);self.assertTrue(r['searchCapped']);self.assertEqual(r['sourceKm'],7);self.assertFalse(r['usableLimitOrMatchingQualified'])

    def test_source_weight_drift_and_external_deadline_are_rejected(self):
        meta,lines,index,caps=prepare();s=source();s['sourceKm']+=1
        with self.assertRaisesRegex(PilotError,'denominator'):match(s,meta,lines,index,BOX,caps=caps)
        def expired():raise PilotError('deadline')
        with self.assertRaisesRegex(PilotError,'deadline'):read_nodes(stream(fixture()),STATE,expired,caps)

    def test_zero_candidate_still_preserves_source_class_window_and_km(self):
        r=run(fixture(ways=[([1,2,3],{'highway':'footway'})]));report=summary([r]);self.assertEqual(report['arcWindowRecords'],1);self.assertEqual(report['sourceKm'],7);self.assertEqual(report['singlePathUnscopedNumericSupportedKm'],0)

    def test_typed_identity_snapshot_field_and_native_precision_are_validated(self):
        for mode in ('snapshot','field','order','precision'):
            rows=fixture()
            if mode=='snapshot':rows[0]['publisherStateUtc']='wrong'
            if mode=='field':rows[0]['elementSha256']='0'*64
            if mode=='order':rows[0],rows[1]=rows[1],rows[0]
            if mode=='precision':rows[0]['element']['lat']=.123456789;rows[0]['elementSha256']=hashlib.sha256(canonical(rows[0]['element'])).hexdigest()
            with self.subTest(mode=mode),self.assertRaises(PilotError):prepare(rows)

    def test_reused_fragment_enumeration_matches_separate_reference(self):
        from coarse_timing_fragments_audit import reference_fragments,reference_search,equivalent
        from coarse_timing_chains import make_nodes
        from coarse_timing_fragments import make_fragments,search_fragments
        for rows in (fixture(),fixture(ways=[([1,2],{'highway':'primary'}),([2,3],{'highway':'primary'})])):
            meta,lines,index,caps=prepare(rows);samples,points,tangents,weights=index.support(source()['sourceSpans']);full,_=make_nodes(meta,samples,points,BOX)
            args=meta,lines,samples,points,tangents,BOX,list(full.values())
            actual=make_fragments(*args);expected=reference_fragments(*args)
            for a,b in zip(actual,expected):equivalent(a,b)
            equivalent(search_fragments(actual[0],weights),reference_search(expected[0],weights,64,4096))
