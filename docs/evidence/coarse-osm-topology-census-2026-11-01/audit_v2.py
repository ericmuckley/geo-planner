"""Independent baseline audit plus a separately stated way-lineage contraction diagnostic."""
from array import array
from bisect import bisect_left
from functools import lru_cache
import hashlib
import heapq
from itertools import groupby
import json
import os
from pathlib import Path
import stat
import struct
import sys
import time

REF=struct.Struct('<QQII');ID=struct.Struct('<Q')


def require(ok,message):
    if not ok:raise ValueError(message)
def load(path):return json.loads(Path(path).read_bytes())
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def audit(root,*,seconds=1200):
    root=Path(root);began=time.monotonic();deadline=began+seconds;receipt=load(root/'receipt.json');report=load(root/'topology.json');paths={};stats={};hashed=0
    def check():require(time.monotonic()<deadline,'Independent topology audit deadline')
    for name,pin in report['artifacts'].items():
        check();require(Path(name).name==name and name.endswith('.bin'),'Independent bounded input path')
        path=root/'streams'/name;s=path.lstat();require(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_size==pin['bytes']<=67108864,'Independent file type/size')
        require(sha(path)==pin['sha256'],'Independent spool checksum '+name);hashed+=s.st_size;paths[name]=path;stats[name]=(s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    require(hashed==report['writtenBytes']<=2147483648,'Independent retained spool accounting')
    def records(path,fmt):
        before=path.stat();width=fmt.size
        with path.open('rb') as stream:
            while raw:=stream.read(width*65536):
                check();require(len(raw)%width==0,'Independent truncated typed record')
                yield from fmt.iter_unpack(raw)
        after=path.stat();require((before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_size,after.st_mtime_ns,after.st_ctime_ns),'Independent input drift')
    def ids(prefix):
        for name,path in sorted(paths.items()):
            if name.startswith(prefix):
                for row in records(path,ID):
                    require(0<row[0]<2**63,'Independent typed member/tag ID');yield row[0]
    metadata=[]
    for prefix in ('relation-nodes-','relation-ways-'):
        expected=sorted(ids(prefix));actual=array('Q')
        require(actual.itemsize==8 and sys.byteorder=='little','Independent metadata word width')
        for name,path in sorted(paths.items()):
            if name.startswith('sorted-'+prefix):
                with path.open('rb') as stream:actual.frombytes(stream.read())
        require(len(expected)==len(actual) and all(a==b for a,b in zip(expected,actual)),'Independent exact raw/sorted metadata multiset')
        metadata.append(actual);del expected
    relation_nodes,relation_ways=metadata
    @lru_cache(maxsize=65536)
    def related_way(way):
        pos=bisect_left(relation_ways,way);return pos<len(relation_ways) and relation_ways[pos]==way
    def ref_rows(path):
        previous=None
        for row in records(path,REF):
            node,way,degree,flags=row;key=(node,way,flags,degree)
            require(0<node<=receipt['maxNodeId'] and 0<way<=receipt['maxWayId'] and flags in (0,1) and degree==(1 if flags else 2),'Independent reference fields')
            require(previous is None or previous<=key,'Independent sorted reference chunk');previous=key;yield row
    tag_iter=iter(ids('tagged-'));tag=next(tag_iter,None);last_tag=0;tagged_read=0
    def advance_tag():
        nonlocal tag,last_tag,tagged_read
        if tag is not None:
            require(tag>last_tag,'Independent tagged-node order');last_tag=tag;tagged_read+=1;tag=next(tag_iter,None)
    max_way=receipt['maxWayId'];require(0<max_way<=1571764908,'Independent finite native-way audit arenas')
    seen=bytearray((max_way+8)//8);ends=bytearray((max_way+4)//4);unique_ways=first_ends=second_ends=0
    counts={k:0 for k in report['counts']};relation_cursor=0;rows_seen=0;lineage_anchors=0
    parts=[ref_rows(path) for name,path in sorted(paths.items()) if name.startswith('refs-')]
    merged=heapq.merge(*parts,key=lambda row:(row[0],row[1],row[3],row[2]))
    for node,group in groupby(merged,key=lambda row:row[0]):
        degree=occurrences=internal=0;endpoint=relation_way=False
        for _,way,d,flag in group:
            rows_seen+=1;degree+=d;occurrences+=1;internal+=not flag;endpoint|=bool(flag);relation_way|=related_way(way)
            byte=way//8;mask=1<<(way%8)
            if not seen[byte]&mask:seen[byte]|=mask;unique_ways+=1
            if flag:
                byte=way//4;shift=2*(way%4);n=(ends[byte]>>shift)&3;require(n<2,'Independent more than two ends per source way')
                ends[byte]+=1<<shift
                if n==0:first_ends+=1
                else:second_ends+=1
            counts['references']+=1;counts['totalDegree']+=d;counts['endpointOccurrences']+=flag
            if rows_seen%1000000==0:check();print(json.dumps({'auditReferenceRows':rows_seen,'seconds':time.monotonic()-began}),flush=True)
        while tag is not None and tag<node:advance_tag()
        tagged=tag==node
        while relation_cursor<len(relation_nodes) and relation_nodes[relation_cursor]<node:relation_cursor+=1
        relation_node=relation_cursor<len(relation_nodes) and relation_nodes[relation_cursor]==node
        anchor=degree!=2 or endpoint or tagged or relation_node or relation_way
        lineage_anchors+=bool(degree!=2 or endpoint or tagged or relation_node)
        counts['uniqueNodes']+=1;counts['anchors']+=anchor;counts['taggedSelectedNodes']+=tagged;counts['relationNodeSelectedNodes']+=relation_node;counts['relationWaySelectedNodes']+=relation_way
        counts['degreeNotTwoNodes']+=degree!=2;counts['wayEndUniqueNodes']+=endpoint
        if anchor:counts['internalAnchorOccurrences']+=internal
        else:require(occurrences==1 and degree==2 and internal==1,'Independent removed node is exactly one internal degree-two occurrence')
    while tag is not None:advance_tag()
    counts['allTaggedNodeIds']=tagged_read
    require(unique_ways==first_ends==second_ends==receipt['topologyWays'],'Independent unique source ways and every two endpoints')
    counts['primitiveEdges']=counts['references']-unique_ways
    # Each removed degree-two internal vertex removes exactly one edge.
    # This is independent of the producer's per-way/internal-anchor formula.
    counts['contractedEdges']=counts['primitiveEdges']-(counts['uniqueNodes']-counts['anchors'])
    v=counts['anchors'];e=counts['contractedEdges'];n=counts['uniqueNodes'];p=counts['primitiveEdges']
    counts['routingArrayBytes']=12*v+24*e+4;counts['fullGeometryArrayBytes']=8*n+4*p+8*e+4;counts['combinedArrayBytes']=counts['routingArrayBytes']+counts['fullGeometryArrayBytes'];counts['complete']=1
    require(counts==report['counts'],'Independent every topology/count/storage field')
    for name,path in paths.items():
        s=path.stat();require(stats[name]==(s.st_size,s.st_mtime_ns,s.st_ctime_ns),'Independent final closed input drift')
    check()
    lineage_edges=p-(n-lineage_anchors)
    diagnostic={'anchors':lineage_anchors,'contractedEdges':lineage_edges,'routingMetersF64ArrayBytes':12*lineage_anchors+24*lineage_edges+4,
        'fullGeometryArrayBytes':8*n+4*p+8*lineage_edges+4,'hypotheticalU16CostRoutingArrayBytes':12*lineage_anchors+12*lineage_edges+4,
        'requiresFullWayLineageAndGeometryOffline':True,'contractedArtifactBuilt':False,'carSemanticsQualified':False,'compressedPackageMeasured':False,
        'rule':'Retain every selected-degree junction, source-way end, tagged node and explicit relation node. Interior nodes are not extra anchors solely because their source way appears in a relation; ordered full geometry and all source-way/relation metadata must remain traceable in edge provenance.',
        'scope':'Whole acquired-file count diagnostic, no continental-only or Vercel-fit admission. U16 costs are storage arithmetic only; no cost/quantization/overflow policy is selected.'}
    return {'status':'independent_derived_topology_audit_with_lineage_diagnostic_passed','wayLineageDiagnostic':diagnostic,'counts':counts,'sourceWaysIndependentlyCounted':unique_ways,'everySourceWayHasTwoEndpoints':True,
        'rawSortedMetadataExactMultisets':True,'authenticatedSpoolBytes':hashed,'spoolFiles':len(paths),'secondsIncludingHashesMetadataSortAndPythonIncidence':time.monotonic()-began,
        'receiptSha256':sha(root/'receipt.json'),'topologySha256':sha(root/'topology.json'),'sourcePbfReads':0,'nativeLibraryExecutions':0,'graphAllocated':False,'modelChanged':False,'etaQualified':False,'nationalCoverageQualified':False,'vercelQualified':False}


if __name__=='__main__':
    root=Path(sys.argv[1]);result=audit(root)
    if len(sys.argv)>2:
        with Path(sys.argv[2]).open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result,indent=2))
