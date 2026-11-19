"""Independent native/reference price and unchanged-topology controls."""
from array import array
import random
import unittest

from coarse_osm_car_cost_math_v1 import NativeCosts
from coarse_osm_car_cost_math_v1_test import reference
from coarse_osm_tagged_timing_v1 import MAX_MS,estimated_way,reprice_arcs

ARTIFACT=None


class PythonKernel:
    def __init__(self):self.calls=0
    def costs(self,xy,speeds,same):
        self.calls+=1
        return array('Q',(reference(xy[4*i:4*i+4],speed,same[i]) for i,speed in enumerate(speeds)))


class Controls(unittest.TestCase):
    def setUp(self):
        self.kernel=NativeCosts(*ARTIFACT) if ARTIFACT else PythonKernel()
        self.xy=[0,0,10000,0,20000,0,20000,10000];self.anchors=[0,1,2,3]
        self.geometry=[0,1,2,2,3,0,3];self.ways=[(10,50.,60.,11,5),(20,0.,40.,2,7)]
        rows=[]
        for first,last,tail,head in [(0,1,0,1),(1,2,1,2),(3,4,2,3)]:
            for d in (1,-1):rows.append((tail if d==1 else head,head if d==1 else tail,0,first,last,d))
        rows.append((3,0,1,0,1,-1));self.arcs=[(*a,self.price(a,False)) for a in rows]
    def price(self,a,proposed):
        _,_,way,first,last,d=a[:6];r=self.ways[way];start=0 if way==0 else self.ways[way-1][4];i=1 if d==1 else 2
        speed=r[i]
        if proposed and not r[3]&(1<<(i+1)):speed*=9/10
        return sum(reference([*self.xy[2*self.geometry[start+p]:2*self.geometry[start+p]+2],*self.xy[2*self.geometry[start+p+1]:2*self.geometry[start+p+1]+2]],speed,self.geometry[start+p]==self.geometry[start+p+1]) for p in range(first,last))
    def run_prices(self,**kw):
        stats={};out=list(reprice_arcs(self.ways,self.geometry,self.xy,self.anchors,self.arcs,self.kernel,stats,**kw));return out,stats
    def test_estimated_metadata_preserves_original_legal_speeds_defaults_direction_flags(self):
        original=self.ways.copy();row=estimated_way(self.ways[0]);self.assertEqual(row,(10,45.,60.,11,5));self.assertEqual(self.ways,original)
        self.assertEqual(estimated_way((30,0.,0.,6<<8,0)),(30,0.,0.,6<<8,0))
    def test_every_bidirectional_price_matches_independent_coordinate_reference(self):
        out,stats=self.run_prices();self.assertEqual([a[:6] for a in out],[a[:6] for a in self.arcs])
        self.assertEqual([a[6] for a in out],[self.price(a,True) for a in self.arcs]);self.assertEqual(stats['defaultArcsChecked'],3)
        self.assertTrue(all(b[6]>=a[6] for a,b in zip(self.arcs,out)));self.assertEqual(stats['arcsChecked'],7)
    def test_batch_boundaries_preserve_all_costs_and_no_buffer_aliases(self):
        expected,_=self.run_prices();out,stats=self.run_prices(primitive_limit=2,arc_limit=1);self.assertEqual(out,expected);self.assertEqual(stats['nativeBatches'],7)
        repeated,_=self.run_prices(primitive_limit=2,arc_limit=2);self.assertEqual(repeated,out)
    def test_seeded_multi_point_geometry_and_directional_default_combinations(self):
        rng=random.Random(20261106);self.ways=[];self.geometry=[];self.xy=[];self.anchors=[];self.arcs=[]
        for w in range(120):
            count=rng.randrange(2,7);first=len(self.geometry);start=len(self.xy)//2
            for p in range(count):
                self.xy.extend((w*10000+p*700,rng.randrange(-30000,30000)));self.geometry.append(start+p);self.anchors.append(start+p)
            flags=3|rng.choice([0,4,8,12]);self.ways.append((w+10,rng.choice([30.,50.,80.,100.]),rng.choice([40.,60.,100.]),flags,len(self.geometry)))
            for d in (1,-1):
                a=(start if d==1 else start+count-1,start+count-1 if d==1 else start,w,0,count-1,d);self.arcs.append((*a,self.price(a,False)))
        out,_=self.run_prices(primitive_limit=64,arc_limit=9);self.assertEqual([a[6] for a in out],[self.price(a,True) for a in self.arcs])
    def test_forged_original_source_price_fails_before_output(self):
        a=self.arcs[0];self.arcs[0]=(*a[:6],a[6]+1)
        with self.assertRaises(AssertionError):self.run_prices()
    def test_foreign_endpoints_geometry_and_inconsistent_source_direction_fail(self):
        for index,value in [(0,3),(2,2),(3,-1),(4,7),(5,0),(6,True)]:
            old=self.arcs.copy();a=list(self.arcs[0]);a[index]=value;self.arcs[0]=tuple(a)
            with self.assertRaises(AssertionError):self.run_prices()
            self.arcs=old
        for row in [(10,50.,60.,10,5),(10,float('nan'),60.,11,5),(10,161.,60.,11,5)]:
            with self.assertRaises(AssertionError):estimated_way(row)
    def test_cancellation_prevents_any_kernel_execution_or_yield(self):
        k=PythonKernel()
        def cancel():raise RuntimeError('cancelled')
        with self.assertRaisesRegex(RuntimeError,'cancelled'):list(reprice_arcs(self.ways,self.geometry,self.xy,self.anchors,self.arcs,k,{},cancel))
        self.assertEqual(k.calls,0)
    def test_macro_overflow_is_rejected_without_clipping(self):
        class Overflow:
            def costs(self,xy,speeds,same):return array('Q',(MAX_MS+(s<50) for s in speeds))
        self.arcs=[(*self.arcs[0][:6],MAX_MS)]
        with self.assertRaises(AssertionError):list(reprice_arcs(self.ways,self.geometry,self.xy,self.anchors,self.arcs,Overflow(),{}))


if __name__=='__main__':unittest.main()
