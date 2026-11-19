"""Fresh-epoch restriction baselines using qualified native and audit helpers."""
from array import array
from bisect import bisect_left
import json
from pathlib import Path
import struct
import time

from coarse_osm_absent_entry_country_v1 import resolve as resolve_absent
from coarse_osm_car_packed_audit_v1 import rows
from coarse_osm_car_policy_v1 import restriction_policy
from coarse_osm_entry_resolution_audit_v1 import fixed
from coarse_osm_multiway_country_v1 import resolve as resolve_multi
from coarse_osm_restriction_entry_v1 import entry_restriction


def relation_inputs(source,metadata,rules,fallback,expected,check=lambda:None):
    original=set();constant=set();single=[];previous=seen=0
    with Path(metadata).open('rb') as stream:
        while line:=stream.readline(2097153):
            check();assert len(line)<=2097152 and line.endswith(b'\n')
            element=json.loads(line);assert type(element['id']) is int and previous<element['id']<2**63
            previous=element['id'];seen+=1;assert seen<=expected<=100000
            policy=restriction_policy(element);assert policy['status']=='closed-unsupported'
            original.update(policy['memberWays']);rule=entry_restriction(element)
            if rule is None:constant.update(policy['memberWays'])
            else:single.append((rule.identity,rule.from_way,rule.via_way,rule.to_way))
            assert len(original)<=200000 and len(constant)<=200000
    assert seen==expected and single==list(fixed(rules,struct.Struct('<QQQQ'),100000))
    assert sorted(constant)==[r[0] for r in fixed(fallback,struct.Struct('<Q'),200000)]
    assert sorted(original)==[r[0] for r in rows(source,'closures',struct.Struct('<Q'))]
    return {'unsupportedRelations':seen,'singleViaRules':len(single),'constantFallbackWayIds':len(constant),
            'originalClosureIds':len(original),'rawRelationRuleFallbackAndOriginalUnionExact':True}


def conservative_post(source,dimensions,check=lambda:None):
    way_count,vertices,pre_count=dimensions[:3]
    assert 0<way_count<=5000000 and 0<vertices<=0xffffff and 0<pre_count<=0xffffff
    identities=array('Q',(r[0] for r in rows(source,'ways',struct.Struct('<Q24x'))))
    assert len(identities)==way_count and 0<identities[0]<2**63 and all(a<b<2**63 for a,b in zip(identities,identities[1:]))
    counts=array('I',[0])*way_count;seen=0
    for tail,head,way in rows(source,'arcs',struct.Struct('<III20x')):
        assert tail<vertices and head<vertices and way<way_count and seen<pre_count
        counts[way]+=1;seen+=1
        if seen%65536==0:check()
    assert seen==pre_count
    blocked=0;previous=0
    for identity, in rows(source,'closures',struct.Struct('<Q')):
        assert previous<identity<2**63;previous=identity
        at=bisect_left(identities,identity)
        if at<way_count and identities[at]==identity:blocked+=counts[at]
    check();return pre_count-blocked


def resolve(native,source,metadata,rules,fallback,output,dimensions,metadata_count,check=lambda:None):
    began=time.monotonic();source=Path(source);output=Path(output)
    assert len(dimensions)==5 and dimensions[3]>0
    inputs=relation_inputs(source,metadata,rules,fallback,metadata_count,check)
    assert (inputs['singleViaRules'],inputs['constantFallbackWayIds'])==tuple(dimensions[3:])
    baseline_post=conservative_post(source,dimensions,check)
    output.mkdir();native_root=output/'native';native_root.mkdir()
    phase=time.monotonic();counts=native.resolve(source,rules,fallback,native_root,dimensions)
    native_seconds=time.monotonic()-phase;assert len(counts)==9 and counts[7]==dimensions[2]
    check();phase=time.monotonic()
    single=resolve_absent(source,rules,fallback,native_root,output/'single',dimensions,counts,
                          baseline_post=baseline_post,check=check)
    single_seconds=time.monotonic()-phase
    # The baseline is freshly constructed on this exact source epoch. The sealed
    # absent-member helper independently audits every native decision/pair before
    # deriving inactive rules; no old numeric IDs or old post-counts are supplied.
    phase=time.monotonic()
    multi=resolve_multi(source,metadata,output/'single/decisions.bin',output/'single/closures-0000.bin',
                        output/'single/entry-pairs-pre.u32',output/'final',
                        [*dimensions[:3],single['newFinalArcs'],metadata_count,dimensions[3]],check)
    return {'status':'fresh_source_epoch_single_and_multi_restrictions_independently_audited',
            'dimensions':dimensions,'relationInputAudit':inputs,'originalConservativePostArcs':baseline_post,
            'freshNativeCounts':counts,'singleVia':single,'multiVia':multi,
            'nativeSeconds':native_seconds,'singleResolutionAndCompleteNativeAuditSeconds':single_seconds,
            'multiResolutionAndIndependentJoinSeconds':time.monotonic()-phase,
            'secondsIncludingInputChecksAllResolutionsAndAudits':time.monotonic()-began,
            'oldNumericArcIdsReused':False,'previousLaneGraphMonotonicityAssumed':False,
            'sourceCostsFlagsOrPreArcsChanged':False,'sourcePbfReads':0,'coordinatesRead':0,
            'routingQueries':0,'runtimeGraphBuilt':False,'appActivated':False,
            'scope':'Raw metadata/rules/constant fallback/original closure union checked first. Fresh native single-entry baseline and conservative post-count derive only from this complete preclosure epoch;qualified absent-member helper exhaustively audits native output before inactive-leg conversion. Qualified multi-entry helper independently rereads source and sort-merges every join/decision/closure. Its parent-preservation statements refer only to this fresh single-via parent,not the previous graph epoch. Every other source constraint stays. No source constructor,coordinates,graph,query,ETA or app admission.'}
