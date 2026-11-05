"""Read authenticated fixed-width chunks and stream small fact overlays."""
from bisect import bisect_left,bisect_right
import hashlib
from itertools import groupby
import mmap
from pathlib import Path
import struct

CHUNK=16*1048576


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


class Rows:
    def __init__(self,root,roster,prefix,format,check=lambda:None):
        self.row=struct.Struct(format);self.parts=[];self.starts=[0];self.handles=[];self.check=check
        try:
            names=sorted(n for n in roster if n.startswith('cost-facts/'+prefix+'-'))
            for i,name in enumerate(names):
                check();path=Path(root)/name;pin=roster[name]
                assert path.is_file() and not path.is_symlink() and 0<path.stat().st_size<=CHUNK
                assert path.stat().st_size==pin['bytes'] and pin['bytes']%self.row.size==0
                assert i==len(names)-1 or pin['bytes']==CHUNK
                before=path.stat();assert sha(path)==pin['sha256']
                handle=path.open('rb');mapped=mmap.mmap(handle.fileno(),0,access=mmap.ACCESS_READ)
                self.handles.append((handle,mapped,path,(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns),pin['sha256']))
                self.parts.append(mapped);self.starts.append(self.starts[-1]+len(mapped)//self.row.size)
        except BaseException:self.close();raise
    def __len__(self):return self.starts[-1]
    def __getitem__(self,index):
        assert type(index) is int and 0<=index<len(self)
        part=bisect_right(self.starts,index)-1;result=self.row.unpack_from(self.parts[part],(index-self.starts[part])*self.row.size)
        return result[0] if len(result)==1 else result
    def bytes(self,first,last):
        assert 0<=first<=last<=len(self)
        cursor=first*self.row.size;end=last*self.row.size
        while cursor<end:
            part=bisect_right(self.starts,cursor//self.row.size)-1;offset=cursor-self.starts[part]*self.row.size
            count=min(end-cursor,len(self.parts[part])-offset,1048576)
            self.check();yield self.parts[part][offset:offset+count];cursor+=count
    def verify_unchanged(self):
        for _,_,path,before,pin in self.handles:
            self.check();s=path.stat();assert (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)==before and sha(path)==pin
    def close(self):
        for handle,mapped,*_ in self.handles:mapped.close();handle.close()
        self.handles=[];self.parts=[]


class Writer:
    def __init__(self,root,limit,check=lambda:None):
        self.root=Path(root);self.limit=limit;self.check=check;self.bytes=0;self.roster={}
        self.prefix=None;self.part=0;self.stream=None;self.size=0;self.digest=None
    def start(self,prefix):
        self.finish();assert self.prefix is None and prefix in ('ways','arcs','flags')
        self.prefix=prefix;self.part=0
    def append(self,raw):
        assert self.prefix and self.bytes+len(raw)<=self.limit
        at=0
        while at<len(raw):
            self.check()
            if self.stream is None:
                self.name=f'cost-facts/{self.prefix}-{self.part:04d}.bin';self.part+=1
                self.stream=(self.root/self.name).open('xb');self.size=0;self.digest=hashlib.sha256()
            count=min(CHUNK-self.size,len(raw)-at);view=memoryview(raw)[at:at+count]
            assert self.stream.write(view)==count;self.digest.update(view);at+=count;self.size+=count;self.bytes+=count
            if self.size==CHUNK:self._close()
    def _close(self):
        if self.stream is None:return
        self.stream.close();self.roster[self.name]={'bytes':self.size,'sha256':self.digest.hexdigest()};self.stream=None
    def finish(self):self._close();self.prefix=None


def replace_rows(source,changes,writer):
    previous=0
    for index,value in sorted(changes.items()):
        assert previous<=index<len(source)
        for raw in source.bytes(previous,index):writer.append(raw)
        writer.append(source.row.pack(*value) if isinstance(value,tuple) else source.row.pack(value));previous=index+1
    for raw in source.bytes(previous,len(source)):writer.append(raw)


def insert_arcs(source,added,writer):
    from coarse_osm_conditional_overlay_v1 import FieldColumn
    ways=FieldColumn(source,2);cursor=0;previous=-1;insertions=[];new_index=0
    for way,group in groupby(added,key=lambda a:a[2]):
        assert way>previous;previous=way;at=bisect_left(ways,way)
        assert cursor<=at and (at==len(source) or ways[at]!=way)
        for raw in source.bytes(cursor,at):writer.append(raw)
        new_index+=at-cursor;first=new_index;count=0
        for arc in group:writer.append(source.row.pack(*arc));count+=1;new_index+=1
        insertions.append({'way':way,'oldArcInsertion':at,'newArcFirst':first,'newArcCount':count});cursor=at
    for raw in source.bytes(cursor,len(source)):writer.append(raw)
    return insertions
