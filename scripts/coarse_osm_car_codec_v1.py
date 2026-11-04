"""Lossless u16 time ticks/u32 overflow and compact reverse-arc ordinals."""
from array import array
from bisect import bisect_left
import sys
from coarse_timing_input import require

TICK_MS=125;SENTINEL=65535;MAX_U32=2**32-1


def ticks(milliseconds):
    require(type(milliseconds) is int and milliseconds>=0,'Car nonnegative integer milliseconds')
    result=(milliseconds+TICK_MS-1)//TICK_MS
    require(result<=MAX_U32,'Car tick u32 overflow')
    return result


class Costs:
    def __init__(self,costs):
        require(sys.byteorder=='little','Car little-endian wire format')
        self.words=array('H');self.indices=array('I');self.values=array('I')
        require(self.words.itemsize==2 and self.indices.itemsize==4,'Car cost word widths')
        for i,cost in enumerate(costs):
            require(i<MAX_U32,'Car arc index overflow');value=ticks(cost);self.words.append(min(value,SENTINEL))
            if value>=SENTINEL:self.indices.append(i);self.values.append(value)
    def get(self,index):
        require(type(index) is int and 0<=index<len(self.words),'Car cost index')
        value=self.words[index]
        if value!=SENTINEL:return value
        i=bisect_left(self.indices,index);require(i<len(self.indices) and self.indices[i]==index,'Car missing overflow entry');return self.values[i]
    @property
    def bytes(self):return 2*len(self.words)+8*len(self.indices)


class Reverses:
    def __init__(self,arcs,offsets,vertex):
        self.words=bytearray();self.indices=array('I');self.values=array('I')
        for i,arc in enumerate(arcs):
            reverse=arc['reverse']
            if reverse is None:self.words.append(255);continue
            head=vertex[arc['head']];ordinal=reverse-offsets[head]
            require(0<=ordinal<offsets[head+1]-offsets[head] and arcs[reverse]['reverse']==i,'Car physical reverse pairing')
            if ordinal<254:self.words.append(ordinal)
            else:self.words.append(254);self.indices.append(i);self.values.append(reverse)
    def get(self,index,head,offsets):
        require(type(index) is int and 0<=index<len(self.words),'Car reverse index');value=self.words[index]
        if value==255:return None
        if value<254:return offsets[head]+value
        i=bisect_left(self.indices,index);require(i<len(self.indices) and self.indices[i]==index,'Car missing reverse overflow');return self.values[i]
    @property
    def bytes(self):return len(self.words)+8*len(self.indices)
