"""Bounded recursive source-ID closure of selected water relation members."""
from array import array
import gzip
import hashlib
import json
from pathlib import Path

from coarse_timing_input import require


def read_records(path, *, byte_cap=64*1048576, row_cap=70000):
    rows={};total=0
    with gzip.open(path,'rb') as stream:
        while raw:=stream.readline(8*1048576+1):
            total+=len(raw)
            require(raw.endswith(b'\n') and len(raw)<=8*1048576 and total<=byte_cap,'Water closure input cap')
            row=json.loads(raw)
            require(row['type']=='relation' and row['id'] not in rows and len(rows)<row_cap,'Water closure input relation identity/count')
            rows[row['id']]=row
    return rows


def targets(rows):
    return {m['ref'] for row in rows.values() for m in row['members'] if m['type']=='relation'}


def resolve(roots, fetch, *, max_rounds=4, max_new=10000, max_members=500000, check=lambda:None):
    known=dict(roots);children={};missing=set();rounds=[];members=0
    pending=targets(known)-known.keys()
    for _ in range(max_rounds):
        if not pending:break
        check()
        requested=set(pending)
        rows=fetch(requested)
        found=set()
        for row in rows:
            identity=row['id']
            require(identity in requested and identity not in found and identity not in known,'Water closure exact requested child IDs')
            found.add(identity);children[identity]=row;known[identity]=row
            members+=len(row['members'])
            require(len(children)<=max_new and members<=max_members,'Water closure descendant cap')
        absent=requested-found;missing.update(absent)
        rounds.append({'requestedIds':sorted(requested),'foundIds':sorted(found),'absentIds':sorted(absent)})
        pending=targets({i:children[i] for i in found})-known.keys()-missing
    edges={i:[m['ref'] for m in r['members'] if m['type']=='relation' and m['ref'] in known] for i,r in known.items()}
    colors={};back_edges=[]
    for identity in known:
        if colors.get(identity):continue
        colors[identity]=1;stack=[(identity,iter(edges[identity]))]
        while stack:
            current,children_iter=stack[-1]
            child=next(children_iter,None)
            if child is None:colors[current]=2;stack.pop();continue
            color=colors.get(child,0)
            if color==1:back_edges.append([current,child])
            elif color==0:colors[child]=1;stack.append((child,iter(edges[child])))
    ways=sorted({m['ref'] for r in known.values() for m in r['members'] if m['type']=='way'})
    return children,ways,{'rootRelations':len(roots),'descendantRelations':len(children),'descendantMembers':members,
                         'rounds':rounds,'sourceAbsentRelationIds':sorted(missing),'depthLimitedRelationIds':sorted(pending),
                         'cycleBackEdges':back_edges,'referenceClosureComplete':not missing and not pending,
                         'acyclic':not back_edges,'uniqueWayIds':len(ways)}


def save_way_ids(path, ways):
    values=array('Q',ways)
    import sys
    require(values.itemsize==8 and sys.byteorder=='little','Water closure index platform')
    with Path(path).open('xb') as stream:values.tofile(stream)
    with Path(path).open('rb') as stream:
        for identity in ways:require(stream.read(8)==identity.to_bytes(8,'little'),'Water closure index independent reopen')
        require(not stream.read(1),'Water closure index EOF')


def audit_saved(root, roots, stored, expected):
    """Reopen every descendant, then recompute closure without a source fetch."""
    root=Path(root)
    children=read_records(root/'water-relations.jsonl.gz',byte_cap=256*1048576,row_cap=10000)
    digest=hashlib.sha256();raw_bytes=0;members=0
    with gzip.open(root/'water-relations.jsonl.gz','rb') as stream:
        for raw in stream:digest.update(raw);raw_bytes+=len(raw)
    require(digest.hexdigest()==stored['rawJsonSha256'] and raw_bytes==stored['rawJsonBytes'],'Water closure exact saved JSON bytes')
    reached=set(roots);frontier=targets(roots);rounds=[];absent=set()
    while frontier:
        wanted=frontier-reached-absent
        if not wanted:break
        found=wanted & children.keys()
        absent.update(wanted-found);reached.update(found)
        rounds.append({'requestedIds':sorted(wanted),'foundIds':sorted(found),'absentIds':sorted(wanted-found)})
        frontier=targets({i:children[i] for i in found})
    require(reached-set(roots)==children.keys(),'Water closure no unreferenced descendant records')
    # A depth-limited run must not relabel its remaining IDs as source-absent.
    require(rounds[:len(expected['rounds'])]==expected['rounds'] and
            sorted(absent-set(expected['depthLimitedRelationIds']))==expected['sourceAbsentRelationIds'],'Water closure independent reachable/missing replay')
    all_rows=roots|children
    way_ids={m['ref'] for r in all_rows.values() for m in r['members'] if m['type']=='way'}
    with (root/'closure-member-way-ids.u64').open('rb') as stream:
        for identity in sorted(way_ids):require(stream.read(8)==identity.to_bytes(8,'little'),'Water closure all member-way IDs')
        require(not stream.read(1),'Water closure all member-way EOF')
    for row in children.values():members+=len(row['members'])
    require(len(children)==stored['counts']['relations']==expected['descendantRelations'] and members==expected['descendantMembers'] and len(way_ids)==expected['uniqueWayIds'],'Water closure saved dimensions')
    return {'allRootRelationsChecked':len(roots),'allDescendantsChecked':len(children),'allDescendantMemberOccurrencesChecked':members,
            'allUniqueWayIdsChecked':len(way_ids),'allSourceDerivedReachabilityAndMissingIdsChecked':True}
