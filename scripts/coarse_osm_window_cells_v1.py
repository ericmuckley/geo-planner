"""Conservative segment rejection oracle; no source/index reader or routing change."""
from bisect import bisect_left
import math

from coarse_timing_input import require

SCALE=10000000


def bound(value,upper=False):
    require(type(value) in (int,float) and math.isfinite(value),'Window finite bound')
    numerator,denominator=value.as_integer_ratio()
    numerator*=SCALE
    return -((-numerator)//denominator) if upper else numerator//denominator


class Cells:
    """At most85 axis slots: intervals and exact edges stay distinct, within u16."""
    def __init__(self,windows):
        require(1<=len(windows)<=21,'Window count bound')
        self.ids=[];self.boxes=[]
        for window in windows:
            identity=window['id'];box=window['bbox']
            require(isinstance(identity,str) and 0<len(identity)<=128 and identity not in self.ids,'Window unique ID')
            require(isinstance(box,list) and len(box)==4 and all(type(v) in (int,float) and math.isfinite(v) for v in box),'Window bbox schema')
            require(-180<=box[0]<=box[2]<=180 and -90<=box[1]<=box[3]<=90,'Window bbox range/order')
            self.ids.append(identity)
            self.boxes.append((bound(box[0]),bound(box[1]),bound(box[2],True),bound(box[3],True)))
        self.x=sorted({coordinate for box in self.boxes for coordinate in (box[0],box[2])})
        self.y=sorted({coordinate for box in self.boxes for coordinate in (box[1],box[3])})
        self.width=2*len(self.x)+1;self.height=2*len(self.y)+1
        self.count=self.width*self.height;require(self.count<=7225,'Window cell u16 bound')
        edges=[(2*self.x.index(a)+1,2*self.y.index(b)+1,2*self.x.index(c)+1,2*self.y.index(d)+1) for a,b,c,d in self.boxes]
        codes=bytearray()
        for y in range(self.height):
            for x in range(self.width):
                for left,bottom,right,top in edges:
                    codes.append(int(x<left)|2*int(x>right)|4*int(y<bottom)|8*int(y>top))
        self.codes=bytes(codes)
        require(len(self.codes)<=151725,'Window outcode table bound')

    @staticmethod
    def slot(edges,value):
        position=bisect_left(edges,value)
        return 2*position+int(position<len(edges) and edges[position]==value)

    def cell(self,x,y):
        require(type(x) is int and type(y) is int and -180*SCALE<=x<=180*SCALE and -90*SCALE<=y<=90*SCALE,'Window native XY')
        return self.slot(self.x,x)+self.width*self.slot(self.y,y)

    def outcodes(self,cell):
        require(type(cell) is int and 0<=cell<self.count,'Window cell identity')
        start=cell*len(self.ids)
        return self.codes[start:start+len(self.ids)]

    def candidates(self,cells):
        require(2<=len(cells)<=65536,'Window way reference count')
        rows=[self.outcodes(cell) for cell in cells]
        # A shared outside half-plane certifies that whole segment misses the
        # expanded rectangle. Any uncertain segment needs exact coordinates.
        return [identity for i,identity in enumerate(self.ids) if any(a[i]&b[i]==0 for a,b in zip(rows,rows[1:]))]
