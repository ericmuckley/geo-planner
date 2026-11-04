"""Bounded lossless gzip shards for GPF ways and native u64 node IDs."""
import gzip
import hashlib
from pathlib import Path

from coarse_osm_bulk_pbf import stat_key
from coarse_timing_input import require

MIB=1048576
PART_BYTES=16*MIB


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


class Budget:
    def __init__(self, limit=480*MIB):self.limit=limit;self.closed=0
    def check(self, current=0):require(self.closed+current<=self.limit,'Water reference compressed output cap')


class Shards:
    def __init__(self,root,prefix,budget):
        self.root=Path(root);self.prefix=prefix;self.budget=budget
        self.parts=[];self.raw_bytes=0;self.digest=hashlib.sha256();self.closed=False
        self.file=self.stream=self.path=None

    def _open(self):
        require(len(self.parts)<256,'Water reference shard count cap')
        self.path=self.root/(self.prefix+f'-{len(self.parts):04d}.gz')
        self.file=self.path.open('xb')
        self.stream=gzip.GzipFile(filename='',mode='wb',fileobj=self.file,compresslevel=6,mtime=0)
        self.part_bytes=0;self.part_digest=hashlib.sha256()

    def _close_part(self):
        if self.stream is None:return
        try:self.stream.close()
        finally:self.file.close()
        size=self.path.stat().st_size
        self.budget.closed+=size;self.budget.check()
        require(size<64*MIB,'Water reference per-file cap')
        self.parts.append({'name':self.path.name,'rawBytes':self.part_bytes,'rawSha256':self.part_digest.hexdigest(),
                           'bytes':size,'sha256':sha(self.path)})
        self.file=self.stream=self.path=None

    def write(self,raw):
        require(not self.closed and 0<len(raw)<=MIB,'Water reference output chunk/state')
        cursor=0
        while cursor<len(raw):
            if self.stream is None:self._open()
            count=min(len(raw)-cursor,PART_BYTES-self.part_bytes);body=raw[cursor:cursor+count]
            self.stream.write(body);self.digest.update(body);self.part_digest.update(body)
            self.part_bytes+=count;self.raw_bytes+=count;cursor+=count
            self.budget.check(self.file.tell())
            if self.part_bytes==PART_BYTES:self._close_part()

    def finish(self):
        require(not self.closed,'Water reference repeated output finish')
        self._close_part();self.closed=True
        return {'parts':self.parts,'rawBytes':self.raw_bytes,'rawSha256':self.digest.hexdigest(),
                'compressedBytes':sum(p['bytes'] for p in self.parts)}

    def close(self):
        if self.stream is not None:
            try:self.stream.close()
            finally:self.file.close()
        self.stream=self.file=None;self.closed=True


class ReferenceStore:
    def __init__(self,root,*,raw_way_bytes,reference_count,budget=480*MIB):
        require(0<=raw_way_bytes<=2*1024**3 and 0<=reference_count<=150000000,'Water reference raw capacity')
        self.budget=Budget(budget);self.ways=Shards(root,'water-ways.gpf',self.budget)
        self.nodes=Shards(root,'node-ids.u64',self.budget)
        self.expected_way_bytes=raw_way_bytes;self.max_node_bytes=8*reference_count
        self.way_report=None;self.report=None

    def __enter__(self):return self
    def __exit__(self,*_):self.ways.close();self.nodes.close()

    def way_chunk(self,raw):
        require(self.way_report is None and self.ways.raw_bytes+len(raw)<=self.expected_way_bytes,'Water reference way byte cap/state')
        self.ways.write(raw)

    def prepare_nodes(self):
        require(self.way_report is None and self.ways.raw_bytes==self.expected_way_bytes,'Water reference exact source way bytes')
        self.way_report=self.ways.finish()

    def node_chunk(self,raw):
        require(self.way_report is not None and len(raw)%8==0 and self.nodes.raw_bytes+len(raw)<=self.max_node_bytes,'Water reference node byte cap/state')
        self.nodes.write(raw)

    def finish(self,unique_nodes):
        require(self.report is None and self.way_report is not None and self.nodes.raw_bytes==unique_nodes*8,'Water reference exact unique node bytes')
        self.report={'ways':self.way_report,'nodes':self.nodes.finish(),'compressedBytes':self.budget.closed,
                     'uniqueNodes':unique_nodes,'coordinatesRetained':False}
        return self.report


class Reader:
    """Read bounded chunks across lossless shards, checking every complete part."""
    def __init__(self,root,report):
        self.root=Path(root);self.report=report;self.cursor=0;self.stream=None
        self.total=0;self.digest=hashlib.sha256();self.finished=False
        require(len(report['parts'])<=256 and sum(p['rawBytes'] for p in report['parts'])==report['rawBytes'],'Water reference input roster')

    def __enter__(self):return self
    def __exit__(self,*_):
        if self.stream:self.stream.close()

    def _open(self):
        part=self.report['parts'][self.cursor];name=part['name'];path=self.root/name
        require(Path(name).name==name and name.endswith('.gz') and path.is_file() and not path.is_symlink() and
                0<part['rawBytes']<=PART_BYTES and path.stat().st_size==part['bytes']<64*MIB and sha(path)==part['sha256'],'Water reference shard identity/type/bound')
        self.before=stat_key(path);self.stream=gzip.open(path,'rb');self.part_total=0;self.part_digest=hashlib.sha256()

    def read(self,size):
        require(type(size) is int and 0<size<=8*MIB,'Water reference bounded read')
        pieces=[];remaining=size
        while remaining:
            if self.stream is None:
                if self.cursor==len(self.report['parts']):
                    require(self.total==self.report['rawBytes'] and self.digest.hexdigest()==self.report['rawSha256'],'Water reference complete input seal')
                    self.finished=True;break
                self._open()
            raw=self.stream.read(remaining)
            if raw:
                self.part_total+=len(raw);self.total+=len(raw)
                require(self.part_total<=self.report['parts'][self.cursor]['rawBytes'] and self.total<=self.report['rawBytes'],'Water reference decompression cap')
                self.part_digest.update(raw);self.digest.update(raw);pieces.append(raw);remaining-=len(raw)
            else:
                part=self.report['parts'][self.cursor]
                require(self.part_total==part['rawBytes'] and self.part_digest.hexdigest()==part['rawSha256'] and stat_key(self.root/part['name'])==self.before,'Water reference decoded part seal/stat')
                self.stream.close();self.stream=None;self.cursor+=1
        return b''.join(pieces)
