"""Read only saved selected relations and explicit missing IDs; no source scan."""
import argparse
from collections import Counter, defaultdict, deque
import gzip
import hashlib
import json
from pathlib import Path
import struct
import time

from coarse_timing_input import require


def summarize(records,missing_ways,missing_relations):
    known=set();roots=set();types={True:Counter(),False:Counter()}
    for root,row in records():
        identity=row['id'];require(identity not in known,'Water gap relation uniqueness')
        known.add(identity)
        if root:roots.add(identity)
        types[root][row['tags'].get('type','')]+=1
    parents=defaultdict(set);direct={};roles={kind:Counter() for kind in ('way','node','relation')}
    used_ways=set();used_relations=set()
    for _,row in records():
        identity=row['id'];flags=0
        for member in row['members']:
            kind,target,role=member['type'],member['ref'],member['role']
            require(kind in roles,'Water gap member type');roles[kind][role]+=1
            if kind=='way' and target in missing_ways:flags|=1;used_ways.add(target)
            if kind=='relation':
                if target in known:parents[target].add(identity)
                else:flags|=2;used_relations.add(target)
        if flags:direct[identity]=flags
    require(used_ways==set(missing_ways) and used_relations==set(missing_relations),'Water gap exact preserved missing-ID parity')
    propagated=dict(direct);queue=deque(direct)
    while queue:
        child=queue.popleft()
        for parent in parents[child]:
            flags=propagated.get(parent,0)|propagated[child]
            if flags!=propagated.get(parent,0):propagated[parent]=flags;queue.append(parent)
    affected=sorted([identity,flags] for identity,flags in propagated.items() if identity in roots)
    return {'rootRelations':len(roots),'additionalRelations':len(known)-len(roots),
            'rootTypeCounts':dict(types[True]),'additionalTypeCounts':dict(types[False]),
            'memberRoleCounts':{k:dict(v) for k,v in roles.items()},
            'sourceMissingWayIds':sorted(missing_ways),'sourceMissingRelationIds':sorted(missing_relations),
            'directRootSourceGapCount':sum(i in roots for i in direct),
            'rootsDependingOnMissingWays':sum(bool(flags&1) for _,flags in affected),
            'rootsDependingOnMissingRelations':sum(bool(flags&2) for _,flags in affected),
            'rootsDependingOnAnyKnownSourceGap':len(affected),'affectedRootsAndReasonBits':affected,
            'reasonBits':{'1':'At least one missing way in the descendant chain.','2':'At least one missing relation in the descendant chain.'},
            'eligibilityPolygonOrGeographicImpactEstablished':False,'nodeCoordinatesAudited':False}


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def run(recipe,pin):
    repo=Path(__file__).resolve().parents[1];recipe=Path(recipe).resolve();began=time.monotonic()
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe)==pin,'Water gap recipe binding')
    plan=json.loads(recipe.read_bytes())
    for name,pin in plan['inputs'].items():require(sha(repo/name)==pin,'Water gap input binding')
    def records():
        for root,name in ((True,plan['roots']),(False,plan['descendants'])):
            total=count=0
            with gzip.open(repo/name,'rb') as stream:
                while raw:=stream.readline(8*1048576+1):
                    total+=len(raw);count+=1
                    require(raw.endswith(b'\n') and len(raw)<=8*1048576 and total<=64*1048576 and count<=70000,'Water gap selected metadata cap')
                    yield root,json.loads(raw)
    raw=(repo/plan['missingWays']).read_bytes();require(len(raw)==136,'Water gap original missing-way record size')
    ways={r[0] for r in struct.iter_unpack('<Q',raw)};require(len(ways)==17,'Water gap unique missing-way count')
    closure=json.loads((repo/plan['closureReport']).read_bytes())['closure']
    result=summarize(records,ways,closure['sourceAbsentRelationIds'])
    require(result['rootRelations']==68734 and result['additionalRelations']==17,'Water gap complete original selected relations')
    result.update(status='saved_water_source_gap_dependencies_complete',recipeSha256=sha(recipe),
                  sourcePbfReads=0,nativeProducerExecutions=0,routingQueries=0,providerRequests=0,
                  hostSecondsIncludingBindingsSelectedRecordDecodeAndAnalysis=time.monotonic()-began)
    output=repo/plan['output'];raw=(json.dumps(result,indent=2,allow_nan=False)+'\n').encode()
    require(output.is_relative_to(repo/'docs/evidence') and len(raw)<=2*1048576,'Water gap output scope/cap')
    with output.open('xb') as stream:stream.write(raw)
    print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe');parser.add_argument('pin')
    args=parser.parse_args();run(args.recipe,args.pin)
