"""Synthetic geometric union controls, including a separate brute-force oracle."""
from copy import deepcopy
import hashlib
import io
import math
import unittest

from coarse_osm_speed_opportunity_v1 import CAPS,KINDS,Samples,opportunity,tag_mask
from coarse_osm_records import canonical
from coarse_timing_input import PilotError

STATE='2026-10-25T21:21:21Z'
WINDOWS=[{'id':'outer','bbox':[0,0,.003,.003]},{'id':'inner','bbox':[.0005,.0005,.0025,.0025]}]


def source():
    return [{'windowId':w['id'],'arc':i,'sourceClassKph':85 if i==0 else 105,'sourceKm':weight,
             'sourceSpans':[[[lo,.0015],[hi,.0015],weight]]} for i,(w,lo,hi,weight) in enumerate(zip(WINDOWS,[.0001,.0006],[.0029,.0024],[7.,3.]))]


def fixture(tags=None,split=False):
    common={'version':1,'timestamp':'2026-10-20T00:00:00Z','visible':True}
    nodes=[common|{'type':'node','id':i+1,'tags':{},'lon':x,'lat':.0015} for i,x in enumerate((-.001,.0015,.004))]
    def record(e):return {'publisherStateUtc':STATE,'element':e,'elementSha256':hashlib.sha256(canonical(e)).hexdigest(),'windowIds':['outer','inner']}
    ways=[common|{'type':'way','id':i+1,'tags':{'highway':'primary',**(tags or {})},'nodes':refs} for i,refs in enumerate(([1,2],[2,3]) if split else ([1,3],))]
    result=[record(e) for e in nodes+ways]
    for row in result[3:]:row['geometryDependencySha256']=hashlib.sha256(canonical([STATE,[nodes[i-1] for i in row['element']['nodes']]])).hexdigest()
    return result


def run(rows=None,records=None,**options):
    return opportunity(io.BytesIO(b''.join(canonical(r)+b'\n' for r in (rows if rows is not None else fixture()))),source() if records is None else records,
                       snapshot=STATE,windows=WINDOWS,caps=CAPS|options.pop('caps',{}),**options)


class Tests(unittest.TestCase):
    def test_full_weights_classes_windows_and_unreviewed_flags(self):
        report,arcs,masks=run(fixture({'maxspeed':'55 mph','access':'private','oneway':'yes','maxspeed:conditional':'20 @ wet'}))
        self.assertEqual(report['allWindows']['sourceKm'],10);self.assertEqual(report['types'],{'node':3,'way':1});self.assertEqual(report['memberships'],8)
        for kind in KINDS[:3]:self.assertEqual(report['allWindows']['unions'][kind]['alignedFraction'],1)
        self.assertEqual(report['allWindows']['unions']['unscopedNumeric']['alignedFraction'],0)
        self.assertEqual(set(masks),{7});self.assertEqual(len(arcs),2)
        for flag in ('sourceAdequacyQualified','carPermissionReviewed','uniqueMatchesQualified','usableLimitOrMatchingQualified','modelChanged'):self.assertFalse(report[flag])

    def test_symbolic_directional_annotation_and_numeric_categories(self):
        for tags,mask in [({},1),({'maxspeed':'US:urban'},3),({'maxspeed:forward':'55 mph'},3),({'maxspeed:type':'US:urban'},3),({'maxspeed':'50'},15),({'maxspeed':'50','maxspeed:lanes':'30|50'},7)]:
            self.assertEqual(tag_mask(tags),mask);report,_,masks=run(fixture(tags));self.assertEqual(set(masks),{mask})

    def test_split_way_union_is_not_a_unique_connected_match(self):
        report,_,_=run(fixture({'maxspeed':'50'},split=True));self.assertEqual(report['allWindows']['unions']['plainNumeric']['alignedFraction'],1);self.assertFalse(report['uniqueMatchesQualified'])

    def test_duplicate_geometry_does_not_double_count(self):
        rows=fixture({'maxspeed':'50'});extra=deepcopy(rows[-1]);extra['element']['id']=2;extra['elementSha256']=hashlib.sha256(canonical(extra['element'])).hexdigest();rows.append(extra)
        report,_,_=run(rows);self.assertEqual(report['allWindows']['unions']['plainNumeric']['alignedKm'],10)

    def test_distance_tangent_and_clipped_endpoint_are_enforced(self):
        samples=Samples(source(),WINDOWS)
        samples.segment([-.001,.002],[.004,.002],'outer',15)
        samples.segment([.0015,-.001],[.0015,.004],'outer',15)
        self.assertFalse(any(samples.masks))
        samples.segment([-.001,.0015],[.004,.0015],'outer',15)
        self.assertEqual(set(samples.masks[samples.arcs[0]['firstSample']:samples.arcs[0]['lastSample']]),{15})

    def test_reverse_bins_match_independent_forward_oracle(self):
        # Separate planar projection + haversine/acute-angle oracle, with both
        # orientations, cross-bin samples, near-threshold offsets and clipping.
        segments=[([0,.00165],[.003,.00165],1),([.001,.0015],[.002,.0015],15),([.003,.0018],[0,.0018],3),([.0015,0],[.0015,.003],7)]
        samples=Samples(source(),WINDOWS)
        for a,b,mask in segments:samples.segment(a,b,'outer',mask)
        expected=[]
        for point,sa,sb,_ in samples.points[:samples.arcs[0]['lastSample']]:
            mask=0
            for a,b,value in segments:
                # All oracle segments are already inside the outer rectangle.
                scale=math.cos(math.radians((sa[1]+sb[1]+a[1]+b[1])/4));u=((sb[0]-sa[0])*scale,sb[1]-sa[1]);v=((b[0]-a[0])*scale,b[1]-a[1])
                cosine=abs(u[0]*v[0]+u[1]*v[1])/(math.hypot(*u)*math.hypot(*v))
                if cosine<math.cos(math.radians(15)):continue
                s=math.cos(math.radians(point[1]));dx=(b[0]-a[0])*s;dy=b[1]-a[1];t=max(0,min(1,((point[0]-a[0])*s*dx+(point[1]-a[1])*dy)/(dx*dx+dy*dy)))
                q=[a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])];lat1,lat2=map(math.radians,(point[1],q[1]));h=math.sin((lat2-lat1)/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(math.radians(q[0]-point[0])/2)**2
                if 12742*math.atan2(math.sqrt(h),math.sqrt(1-h))<=.025:mask|=value
            expected.append(mask)
        self.assertEqual(list(samples.masks[:len(expected)]),expected)

    def test_every_finite_cap_and_external_deadline(self):
        for key in CAPS:
            with self.subTest(cap=key),self.assertRaises(PilotError):run(fixture({'maxspeed':'50'}),caps={key:1})
        def expired():raise PilotError('outer deadline')
        with self.assertRaisesRegex(PilotError,'outer deadline'):run(check=expired)

    def test_bad_fields_snapshot_missing_nodes_and_order_fail(self):
        for mode in ('field','snapshot','missing','order','precision','window'):
            rows=fixture()
            if mode=='field':rows[0]['elementSha256']='0'*64
            if mode=='snapshot':rows[0]['publisherStateUtc']='wrong'
            if mode=='missing':rows.pop(0)
            if mode=='order':rows[0],rows[1]=rows[1],rows[0]
            if mode=='window':rows[-1]['windowIds']=['unknown']
            if mode=='precision':rows[0]['element']['lon']=.123456789;rows[0]['elementSha256']=hashlib.sha256(canonical(rows[0]['element'])).hexdigest()
            with self.subTest(mode=mode),self.assertRaises(PilotError):run(rows)

    def test_changed_original_denominator_or_duplicate_identity_fails(self):
        records=source();records[0]['sourceKm']+=1
        with self.assertRaisesRegex(PilotError,'source km'):run(records=records)
        records=source();records.append(deepcopy(records[0]))
        with self.assertRaisesRegex(PilotError,'source identity'):run(records=records)

    def test_whole_arc_opportunity_is_generous_and_empty_window_remains(self):
        report,arcs,masks=run([]);self.assertEqual(report['allWindows']['sourceKm'],10);self.assertEqual(report['allWindows']['unions']['allGeometry']['alignedFraction'],0);self.assertEqual(len(report['windows']),2);self.assertFalse(any(masks))
