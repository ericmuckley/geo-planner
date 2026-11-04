"""Continuous progress keeps original weights and true native connectivity."""
from copy import deepcopy
import unittest

from coarse_osm_continuous_match_v1 import CAPS,Index,Source,Work,GeometryRejected,match,read_nodes,read_window
from coarse_osm_match_v1_test import BOX,STATE,fixture,source,stream


def prepare(rows=None,caps=None):
    caps=CAPS|{'nodeCanonicalBytes':1048576}|(caps or {});rows=fixture() if rows is None else rows
    nodes,receipt=read_nodes(stream(rows),STATE,caps=caps);meta,lines,scan=read_window(stream(rows),nodes,'a',caps=caps);assert receipt['sha256']==scan['sha256']
    return meta,lines,Index(lines,BOX,caps=caps),caps


def run(rows=None,caps=None,record=None):
    meta,lines,index,caps=prepare(rows,caps);return match(source() if record is None else record,meta,lines,index,BOX,caps=caps)


def short_connector(join=True):
    # At24m lateral offset, the4.4m middle segment lies between the original
    # <=25m spaced weighted samples and aligns with none of them. It is still
    # a genuine corridor connection with two distinct native endpoint IDs.
    points={1:[-.001,.000215],2:[.00488,.000215],3:[.00492,.000215],4:[.011,.000215]}
    tags={'highway':'primary','maxspeed':'50'}
    ways=[([1,2],tags),([2,3],tags),([3,4],tags)]
    if not join:points[5]=points[3];ways[-1]=([5,4],tags)
    return fixture(points,ways)


class Tests(unittest.TestCase):
    def test_overhanging_single_path_and_positive_weight_roster_unchanged(self):
        r=run();self.assertEqual(r['status'],'single_acquired_file_geometric_path');self.assertEqual(r['sampleCount'],45);self.assertEqual(r['sourceKm'],7);self.assertAlmostEqual(r['candidates'][0]['maximumSupportedKm'],7);self.assertFalse(r['usableLimitOrMatchingQualified'])

    def test_zero_midpoint_short_connector_remains_a_real_path(self):
        r=run(short_connector());self.assertEqual(r['status'],'single_acquired_file_geometric_path');self.assertGreater(r['zeroOriginalSampleVariants'],0)
        self.assertEqual(len(r['candidates'][0]['nativeParts']),3);self.assertEqual(r['sampleCount'],45);self.assertAlmostEqual(r['candidates'][0]['maximumSupportedKm'],7)

    def test_nearby_coordinates_cannot_replace_a_missing_native_join(self):
        r=run(short_connector(False));self.assertFalse(r['candidates']);self.assertEqual(r['status'],'no_path_under_fragment_rules')

    def test_short_connector_orientation_reversal_preserves_support(self):
        rows=short_connector();ways=[]
        for r in rows:
            if r['element']['type']=='way':ways.append((r['element']['nodes'][::-1],r['element']['tags']))
        points={r['element']['id']:[r['element']['lon'],r['element']['lat']] for r in rows if r['element']['type']=='node'}
        forward,reverse=run(rows),run(fixture(points,ways));self.assertEqual(reverse['status'],forward['status']);self.assertAlmostEqual(reverse['candidates'][0]['maximumSupportedKm'],forward['candidates'][0]['maximumSupportedKm'])

    def test_parallel_unsupported_role_geometry_remains_a_competing_path(self):
        points={1:[-.001,0],2:[.011,0],3:[-.001,.0001],4:[.011,.0001]}
        r=run(fixture(points,[([1,2],{'highway':'primary','maxspeed':'50'}),([3,4],{'highway':'footway'})]));self.assertEqual(r['status'],'multiple_acquired_file_geometric_paths');self.assertEqual(len(r['candidates']),2);self.assertEqual(sum(c['allSupportedNativeRoles'] for c in r['candidates']),1)

    def test_rejected_side_branch_is_reported_without_physical_admission(self):
        points={1:[-.001,0],2:[.005,0],3:[.011,0],4:[.0055,0],5:[.006,.001]};tags={'highway':'primary','maxspeed':'50'}
        r=run(fixture(points,[([1,2,3],tags),([2,4,5],tags)]));self.assertEqual(r['status'],'single_acquired_file_geometric_path');self.assertTrue(r['rejectedAlignedGeometryRetained']);self.assertTrue(r['fragmentIssues']);self.assertFalse(r['uniquePhysicalMatchQualified']);self.assertIn('frozen continuous',r['candidateUniquenessScope'])

    def test_explicit_private_access_scopes_and_barriers_never_grant_permission(self):
        tags={'highway':'primary','maxspeed':'55 mph','motorcar':'yes','access':'private','maxspeed:conditional':'20 @ wet','oneway':'-1'}
        r=run(fixture(ways=[([1,2,3],tags)]));self.assertEqual(r['status'],'single_acquired_file_geometric_path');self.assertFalse(r['candidates'][0]['allUnscopedNumeric']);self.assertFalse(r['carPermissionReviewed']);self.assertEqual(r['alignedPartBindings'][0]['attributes']['directionTags'],{'oneway':'-1'})

    def test_source_projection_ties_across_different_progress_remain_ambiguous(self):
        s=Source([[[0,0],[.01,0],1.],[[.01,0],[0,0],1.]],Work(1000,lambda:None))
        with self.assertRaisesRegex(GeometryRejected,'ambiguous_source_progress'):s.project([.005,0],([0,0],[.01,0]))

    def test_shared_source_vertex_tangents_and_progress_are_consistent(self):
        s=Source([[[0,0],[.005,0],1.],[[.005,0],[.005,.005],1.]],Work(1000,lambda:None))
        self.assertAlmostEqual(s.project([.005,0],([0,0],[.005,0])),s.project([.005,0],([.005,0],[.005,.005])))

    def test_distance_and_tangent_gates_remain_fixed(self):
        s=Source([[[0,0],[.01,0],1.]],Work(1000,lambda:None))
        with self.assertRaisesRegex(GeometryRejected,'outside_source_corridor'):s.project([.005,.001],([0,0],[.01,0]))
        with self.assertRaisesRegex(GeometryRejected,'tangent'):s.project([.005,0],([.005,-.001],[.005,.001]))

    def test_continuous_projection_and_nearby_part_caps_preserve_denominator(self):
        for caps in ({'projectionComparisons':1},{'nearbyParts':1},{'curveSamples':1}):
            r=run(short_connector(),caps);self.assertTrue(r['searchCapped']);self.assertEqual(r['sourceKm'],7);self.assertEqual(r['sampleCount'],45);self.assertFalse(r['usableLimitOrMatchingQualified'])

    def test_search_row_and_state_caps_still_keep_all_original_weight(self):
        for caps in ({'searchRows':1},{'searchStates':1}):
            r=run(short_connector(),caps);self.assertTrue(r['searchCapped']);self.assertEqual(r['sourceKm'],7)

    def test_closed_native_parts_remain_explicitly_unresolved(self):
        points={1:[0,0],2:[.01,0],3:[.01,.0001]};r=run(fixture(points,[([1,2,3,1],{'highway':'primary'})]));self.assertFalse(r['candidates']);self.assertTrue(any('closed_native_part_unresolved' in i.get('reasons',[]) for i in r['fragmentIssues']))

    def test_source_weight_changes_and_external_deadline_are_rejected(self):
        from coarse_timing_input import PilotError
        s=source();s['sourceKm']+=1
        with self.assertRaises(PilotError):run(record=s)
        meta,lines,index,caps=prepare()
        def expired():raise PilotError('deadline')
        with self.assertRaisesRegex(PilotError,'deadline'):match(source(),meta,lines,index,BOX,expired,caps)

    def test_no_geometry_keeps_original_samples_and_no_candidate(self):
        meta,lines,index,caps=prepare([]);r=match(source(),meta,lines,index,BOX,caps=caps);self.assertFalse(r['candidates']);self.assertEqual(r['sourceKm'],7);self.assertEqual(r['sampleCount'],45)

    def test_independent_straight_source_graph_oracle_includes_zero_weight_links(self):
        import math
        from collections import defaultdict
        from coarse_path_features import distance_km
        cases=[fixture(),short_connector(),short_connector(False)]
        points={1:[-.001,0],2:[.011,0],3:[-.001,.0001],4:[.011,.0001]}
        cases.append(fixture(points,[([1,2],{'highway':'primary'}),([3,4],{'highway':'footway'})]))
        for rows in cases:
            meta,lines,index,caps=prepare(rows);actual=match(source(),meta,lines,index,BOX,caps=caps)
            n=45;weights=[7/n]*n;oracle={}
            for ordinal,(m,line) in enumerate(zip(meta,lines)):
                # These fixtures have horizontal native parts; this separate
                # oracle clips directly in x and never calls Source/fragments.
                a,b=line[0],line[-1];left,right=sorted((a,b));lo=max(0,left[0]);hi=min(.01,right[0])
                if hi<=lo:continue
                mask=0
                for i in range(n):
                    p=[(i+.5)*.01/n,0];q=[max(lo,min(hi,p[0])),left[1]]
                    x,y=map(math.radians,(p[1],q[1]));h=math.sin((y-x)/2)**2+math.cos(x)*math.cos(y)*math.sin(math.radians(q[0]-p[0])/2)**2
                    if 12742*math.atan2(math.sqrt(h),math.sqrt(1-h))<=.025:mask|=1<<i
                direction=int(a[0]>b[0]);oracle[ordinal]=(None if lo>left[0] else m['endpointIds'][direction],None if hi<right[0] else m['endpointIds'][1-direction],lo,hi,mask)
            paths=set()
            def covers(path):
                mask=0
                for ordinal in path:mask|=oracle[ordinal][4]
                return math.fsum(w for i,w in enumerate(weights) if mask>>i&1)/7>=.8-1e-12
            def visit(path):
                if covers(path):
                    if len(path)==1 or not covers(path[1:]) and not covers(path[:-1]):paths.add(min(path,path[::-1]))
                    return
                previous=oracle[path[-1]]
                for ordinal,native in oracle.items():
                    if ordinal not in path and previous[1] is not None and previous[1]==native[0] and native[2]>=previous[2] and native[3]>previous[3]:visit(path+(ordinal,))
            for ordinal in oracle:visit((ordinal,))
            self.assertEqual({tuple(c['nativeParts']) for c in actual['candidates']},paths)
