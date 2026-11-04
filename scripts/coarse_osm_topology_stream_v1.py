"""Bounded fixed-record spools for the exact major-road topology census."""
from array import array
import hashlib
from pathlib import Path

from coarse_timing_input import require

CAPS={'references':48163649,'ways':4227238,'taggedNodes':48142518,'relationNodes':1201443,'relationWays':13455382,
      'presenceMaxNodeID':14319708500,'chunkReferences':2000000,'fileBytes':67108864,'ownedBytes':2147483648}
NAMES={10:'tagged',11:'refs',12:'relation-nodes',13:'relation-ways'}


class Streams:
    def __init__(self,root,kernel,caps,check=lambda:None):
        self.root=Path(root);self.kernel=kernel;self.caps=dict(caps);self.check=check
        require(not self.root.exists(),'Topology fresh stream root');self.root.mkdir()
        self.counts=dict.fromkeys(NAMES,0);self.hashes={k:hashlib.sha256() for k in NAMES};self.roster={};self.refs=bytearray();self.parts={k:[] for k in NAMES};self.written=0
        self.open_files={};self.file_sizes={}
    def write(self,name,raw):
        self.check();path=self.root/name
        require(path.parent==self.root and not path.exists() and len(raw)<=self.caps['fileBytes'] and self.written+len(raw)<=self.caps['ownedBytes']-16777216,'Topology bounded fresh file')
        with path.open('xb') as stream:stream.write(raw)
        path.chmod(0o444);self.written+=len(raw);self.roster[name]={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()};return path
    def ref_part(self,raw):
        self.kernel.sort(raw);path=self.write('refs-'+str(len(self.parts[11])).zfill(4)+'.bin',raw);self.parts[11].append(path)
    def close_part(self,event):
        stream=self.open_files.pop(event,None)
        if stream is None:return
        stream.close();path=self.parts[event][-1];path.chmod(0o444)
        with path.open('rb') as f:pin=hashlib.file_digest(f,'sha256').hexdigest()
        self.roster[path.name]={'bytes':self.file_sizes[event],'sha256':pin}
    def accept(self,event,raw):
        self.check();require(event in NAMES and isinstance(raw,bytes) and 0<len(raw)<=1048576 and len(raw)%(24 if event==11 else 8)==0,'Topology callback chunk')
        width=24 if event==11 else 8;self.counts[event]+=len(raw)//width;self.hashes[event].update(raw)
        key={10:'taggedNodes',11:'references',12:'relationNodes',13:'relationWays'}[event]
        require(self.counts[event]<=self.caps[key],'Topology exact emitted row cap')
        if event==11:
            self.refs.extend(raw);size=24*self.caps['chunkReferences']
            while len(self.refs)>=size:
                part=self.refs[:size];del self.refs[:size];self.ref_part(part)
            return
        position=0
        while position<len(raw):
            if event not in self.open_files:
                path=self.root/(NAMES[event]+'-'+str(len(self.parts[event])).zfill(4)+'.bin')
                self.open_files[event]=path.open('xb');self.parts[event].append(path);self.file_sizes[event]=0
            size=min(len(raw)-position,self.caps['fileBytes']-self.file_sizes[event])
            require(self.written+size<=self.caps['ownedBytes']-16777216,'Topology emitted output byte cap')
            self.open_files[event].write(raw[position:position+size]);self.written+=size;self.file_sizes[event]+=size;position+=size
            if self.file_sizes[event]==self.caps['fileBytes']:self.close_part(event)
    def finish(self):
        if self.refs:self.ref_part(self.refs);self.refs=bytearray()
        for event in tuple(self.open_files):self.close_part(event)
        for event,key in ((10,'taggedNodes'),(11,'references'),(12,'relationNodes'),(13,'relationWays')):require(self.counts[event]==self.caps[key],'Topology complete emitted count')
        metadata=[]
        for event in (12,13):
            raw=bytearray()
            for path in self.parts[event]:self.check();raw.extend(path.read_bytes())
            self.kernel.sort(raw,ids=True)
            for offset in range(0,len(raw),self.caps['fileBytes']):self.write('sorted-'+NAMES[event]+'-'+str(offset//self.caps['fileBytes']).zfill(4)+'.bin',raw[offset:offset+self.caps['fileBytes']])
            ids=array('Q');require(ids.itemsize==8,'Topology metadata word width');ids.frombytes(raw);metadata.append(ids)
        result=self.kernel.count(self.parts[11],self.parts[10],metadata[0],metadata[1],references=self.caps['references'],ways=self.caps['ways'],tagged_nodes=self.caps['taggedNodes'])
        return {'counts':result,'streams':{NAMES[k]:{'rows':self.counts[k],'wireSha256':self.hashes[k].hexdigest(),'parts':len(self.parts[k])} for k in NAMES},'artifacts':self.roster,'writtenBytes':self.written,'modelChanged':False,'graphAllocated':False,'carPolicyReviewed':False,'etaQualified':False,'vercelQualified':False}
    def close(self):
        for stream in self.open_files.values():stream.close()
        self.open_files.clear()
