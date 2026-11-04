"""Describe topology of already-saved candidate paths; never change matches."""
from collections import Counter,defaultdict
import math

from coarse_timing_input import require

ROLES=set('motorway trunk primary secondary tertiary residential living_street unclassified service motorway_link trunk_link primary_link secondary_link tertiary_link'.split())


def family(record,bindings,weights):
    require(0<len(weights)<=20000 and all(type(w) in (int,float) and math.isfinite(w) and w>0 for w in weights),'Family positive original weights')
    require(len(weights)==record['sampleCount'] and math.isclose(math.fsum(weights),record['sourceKm'],rel_tol=1e-12,abs_tol=1e-9),'Family unchanged original denominator')
    candidates=record['candidates'];require(len(candidates)<=4096,'Family candidate cap')
    parts=set();mask=0;variants=0
    for candidate in candidates:
        path=candidate['nativeParts'];require(0<len(path)<=64 and len(path)==len(set(path)) and all(p in bindings for p in path),'Family bounded native parts')
        for a,b in zip(path,path[1:]):require(bool(set(bindings[a]['endpointIds'])&set(bindings[b]['endpointIds'])),'Family saved path missing real node-ID join')
        parts.update(path)
        for variant in candidate['variants']:
            variants+=1;require(variants<=4096,'Family variant cap');value=int(variant['coveredSampleMaskHex'],16);require(value>=0 and value.bit_length()<=len(weights),'Family sample mask cap');mask|=value
    require(len(parts)<=262144,'Family union part cap');adjacency=defaultdict(list)
    for part in parts:
        ends=bindings[part]['endpointIds'];require(len(ends)==2 and all(type(n) is int and n>0 for n in ends),'Family native endpoint identity')
        a,b=ends;adjacency[a].append((b,part));adjacency[b].append((a,part))
    remaining=set(adjacency);components=[]
    while remaining:
        stack=[min(remaining)];vertices=set();edges=set()
        while stack:
            node=stack.pop()
            if node in vertices:continue
            vertices.add(node);remaining.discard(node)
            for neighbor,part in adjacency[node]:edges.add(part);stack.append(neighbor)
        components.append({'nodes':len(vertices),'parts':len(edges),'branchNodes':sum(len(adjacency[n])>2 for n in vertices),'cycle':len(edges)>=len(vertices)})
    if record['searchCapped']:status='capped_original_search'
    elif not candidates:status='no_saved_candidate'
    elif any(c['branchNodes'] or c['cycle'] for c in components):status='branch_or_cycle_in_candidate_union'
    elif len(components)>1:status='multiple_disconnected_corridors'
    else:status='one_unbranched_candidate_corridor'
    unscoped=bool(parts) and all(bindings[p]['attributes']['unscopedNumeric'] for p in parts)
    supported=bool(parts) and all(bindings[p]['nativeTags'].get('highway') in ROLES for p in parts)
    union=math.fsum(w for i,w in enumerate(weights) if mask>>i&1)
    opportunity=union if status=='one_unbranched_candidate_corridor' and unscoped and supported else 0.
    return {k:record[k] for k in ('windowId','arc','sourceClassKph','sourceKm','sampleCount')}|{
        'originalStatus':record['status'],'familyStatus':status,'savedCandidatePaths':len(candidates),'savedCandidateVariants':variants,
        'nativePartsInCandidateUnion':len(parts),'components':components,'candidateUnionAlignedKm':union,'allUnscopedNumeric':unscoped,'allSupportedNativeRoles':supported,
        'unbranchedUnscopedSupportedOpportunityKm':opportunity,'rawAccessTagParts':sum(bool(bindings[p]['attributes']['accessTags']) for p in parts),
        'originalRejectedAlignedParts':len(record['unrepresentedParts']),'sourceAdequacyQualified':False,'physicalMatchQualified':False,'usableLimitOrMatchingQualified':False,'modelChanged':False}


def summary(records):
    source=math.fsum(r['sourceKm'] for r in records);opportunity=math.fsum(r['unbranchedUnscopedSupportedOpportunityKm'] for r in records)
    return {'arcWindowRecords':len(records),'sourceKm':source,'samples':sum(r['sampleCount'] for r in records),'familyStatusCounts':dict(Counter(r['familyStatus'] for r in records)),
            'familyStatusSourceKm':{status:math.fsum(r['sourceKm'] for r in records if r['familyStatus']==status) for status in sorted({r['familyStatus'] for r in records})},
            'unbranchedUnscopedSupportedOpportunityKm':opportunity,'unbranchedUnscopedSupportedOpportunityFraction':opportunity/source if source else None,
            'usableLimitOrMatchingQualified':False,'modelChanged':False}
