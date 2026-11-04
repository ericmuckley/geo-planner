"""Independent compact-array decoder/query check, for offline qualification only.

This reader does not import the graph producer, cost/reverse codecs or turn policy.
Point fragments are paid partial arcs from preserved source geometry; no free snap.
"""
from array import array
from bisect import bisect_left
import heapq
import math
import sys

from coarse_timing_input import require


class Payload:
    def __init__(self,read):
        require(sys.byteorder=='little','Payload little-endian wire format')
        def load(name,code):
            a=array(code);a.frombytes(read(name));return a
        self.xy=load('xy.i32','i');self.offsets=load('offsets.u32','I');self.targets=load('targets.u32','I');self.words=load('costs.u16','H')
        self.cost_keys=load('cost-overflow-arcs.u32','I');self.cost_values=load('cost-overflow-ticks.u32','I')
        self.reverse=read('reverse.u8');self.reverse_keys=load('reverse-overflow-arcs.u32','I');self.reverse_values=load('reverse-overflow-targets.u32','I')
        self.flags=read('node-flags.u8');pairs=load('forbidden-turns.u32','I');self.forbidden=set(zip(pairs[::2],pairs[1::2]))
        self.vertices=len(self.flags);self.arcs=len(self.targets);self.work=0
        require(len(self.xy)==2*self.vertices and len(self.offsets)==self.vertices+1 and self.offsets[0]==0 and self.offsets[-1]==self.arcs,'Payload vertex/CSR shape')
        require(len(self.words)==len(self.reverse)==self.arcs and all(a<=b for a,b in zip(self.offsets,self.offsets[1:])) and all(t<self.vertices for t in self.targets),'Payload arc ranges')
        for keys,values in ((self.cost_keys,self.cost_values),(self.reverse_keys,self.reverse_values)):
            require(len(keys)==len(values) and all(a<b for a,b in zip(keys,keys[1:])) and all(k<self.arcs for k in keys),'Payload sorted overflow')
        require(set(self.cost_keys)=={i for i,w in enumerate(self.words) if w==65535} and all(v>=65535 for v in self.cost_values),'Payload lossless cost overflow')
        require(set(self.reverse_keys)=={i for i,w in enumerate(self.reverse) if w==254},'Payload reverse overflow identity')
        require(len(pairs)%2==0 and list(zip(pairs[::2],pairs[1::2]))==sorted(self.forbidden) and all(a<self.arcs and b<self.arcs for a,b in self.forbidden),'Payload sparse forbidden pairs')
        self.tails=array('I',(v for v in range(self.vertices) for _ in range(self.offsets[v],self.offsets[v+1])))
        for i in range(self.arcs):
            reverse=self.reverse_arc(i)
            require(reverse is None or reverse<self.arcs and self.tails[reverse]==self.targets[i] and self.targets[reverse]==self.tails[i] and self.reverse_arc(reverse)==i,'Payload physical reverse symmetry')
        require(all(self.targets[a]==self.tails[b] for a,b in self.forbidden),'Payload turn continuity')

    @staticmethod
    def overflow(keys,values,index):
        pos=bisect_left(keys,index);require(pos<len(keys) and keys[pos]==index,'Payload overflow missing');return values[pos]

    def cost_ms(self,index):
        word=self.words[index];return (word if word<65535 else self.overflow(self.cost_keys,self.cost_values,index))*125

    def reverse_arc(self,index):
        word=self.reverse[index]
        if word==255:return None
        if word==254:return self.overflow(self.reverse_keys,self.reverse_values,index)
        start,end=self.offsets[self.targets[index]:self.targets[index]+2];require(start+word<end,'Payload reverse ordinal range');return start+word

    def query(self,source,target,*,check=lambda:None):
        """Points: vertex int, or {arc: paid partial milliseconds} for internal points.

        A caller checks direct same-edge travel separately. A target partial arc is
        entered through its normal turn; a source partial arc has no pretrip history.
        """
        if isinstance(source,int) and isinstance(target,int) and source==target:return 0
        seeds={i:self.cost_ms(i) for i in range(self.offsets[source],self.offsets[source+1])} if isinstance(source,int) else source
        stops={} if isinstance(target,int) else target;best=math.inf;labels={};queue=[]
        for arc,cost in seeds.items():
            if isinstance(source,int) and arc in stops:best=min(best,stops[arc])
            labels[arc]=cost;heapq.heappush(queue,(cost,arc))
        while queue:
            cost,arc=heapq.heappop(queue)
            if labels[arc]!=cost:continue
            if cost>best:break
            self.work+=1;require(self.work<=40000000,'Payload query settle cap')
            if self.work%1024==0:check()
            head=self.targets[arc]
            if isinstance(target,int) and head==target:best=min(best,cost)
            flag=self.flags[head]
            if flag&1:continue
            reverse=self.reverse_arc(arc)
            for following in range(self.offsets[head],self.offsets[head+1]):
                reversal=following==reverse
                if reversal and not flag&4 or (arc,following) in self.forbidden:continue
                delay=(5000 if flag&2 else 0)+(20000 if reversal else 0)
                if following in stops:best=min(best,cost+delay+stops[following])
                candidate=cost+delay+self.cost_ms(following)
                if candidate<labels.get(following,math.inf) and candidate<=best:
                    labels[following]=candidate;heapq.heappush(queue,(candidate,following));require(len(queue)<=1000000,'Payload query heap cap')
        return None if math.isinf(best) else best


def point(graph,node,source):
    """Offline adapter only: full geometry/aliases are excluded from runtime totals."""
    if node in graph.vertex:return graph.vertex[node]
    edge,pos=graph.alias[node];fragment=graph.fragments[edge];out={}
    for direction,arc in fragment['arcs'].items():
        p=fragment['prefix'][direction];prefix=p[pos] if direction==1 else p[-1]-p[pos]
        ms=p[-1]-prefix if source else prefix;out[arc]=((ms+124)//125)*125
    return out


def query_native(payload,graph,source,target,check=lambda:None):
    if source==target:return 0
    result=payload.query(point(graph,source,True),point(graph,target,False),check=check)
    if source not in graph.vertex and target not in graph.vertex:
        edge,pos=graph.alias[source];end_edge,end=graph.alias[target]
        if edge==end_edge:
            fragment=graph.fragments[edge]
            for direction in fragment['arcs']:
                if direction==1 and end>=pos or direction==-1 and end<=pos:
                    prefix=fragment['prefix'][direction];direct=((abs(prefix[end]-prefix[pos])+124)//125)*125
                    result=direct if result is None else min(result,direct)
    return result
