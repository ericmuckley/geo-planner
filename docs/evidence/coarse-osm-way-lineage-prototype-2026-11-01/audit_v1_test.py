"""Independent virtual-query overlay versus raw chains/cycles, including zero arcs."""
import math,unittest
from audit_v1 import Linked,shortest,point_distance

class Tests(unittest.TestCase):
    def test_all_point_queries_on_chains_and_cycles(self):
        for closed in (False,True):
            for n in (2,3,7,12):
                sequence=[*range(n),*([0] if closed else [])];lengths=[float(i%3) for i in range(len(sequence)-1)];total=math.fsum(lengths)
                vertices={0:0} if closed else {0:0,n-1:1};used={i:i for i in range(n)};raw=Linked(n);compact=Linked(len(vertices));compact.edge(0,0 if closed else 1,total)
                for a,b,length in zip(sequence,sequence[1:],lengths):raw.edge(a,b,length)
                alias=[-1 if i in vertices else 0 for i in range(n)];prefix=[0. if i in vertices else math.fsum(lengths[:i]) for i in range(n)];suffix=[0. if i in vertices else math.fsum(lengths[i:]) for i in range(n)]
                fields=dict(vertex_map=vertices,used_map=used,edge_data=[(1,0,len(sequence)-1,0,0 if closed else 1,total)],alias=alias,prefix=prefix,suffix=suffix,positions=list(range(n)),edge_lengths=[lengths])
                for a in range(n):
                    for b in range(n):
                        expected=shortest(raw.neighbors,a,b,[0]);actual=point_distance(compact.neighbors,a,b,settles=[0],**fields)
                        self.assertAlmostEqual(actual,expected,places=9)
    def test_distinct_source_components_do_not_connect_through_aliases(self):
        graph=Linked(4);graph.edge(0,1,2.);graph.edge(2,3,2.)
        fields=dict(vertex_map={0:0,2:1,3:2,5:3},used_map={i:i for i in range(6)},edge_data=[(1,0,2,0,1,2.),(2,0,2,2,3,2.)],alias=[-1,0,-1,-1,1,-1],prefix=[0,1,0,0,1,0],suffix=[0,1,0,0,1,0],positions=[0,1,0,0,1,0],edge_lengths=[[1.,1.],[1.,1.]])
        self.assertIsNone(point_distance(graph.neighbors,1,4,settles=[0],**fields))

if __name__=='__main__':unittest.main()
