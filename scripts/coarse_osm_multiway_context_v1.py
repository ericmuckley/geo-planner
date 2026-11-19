"""Build single-via history records while retaining multi-via entry bans."""
from array import array
from bisect import bisect_left
from collections import Counter
from pathlib import Path
import struct
import time

from coarse_osm_car_packed_audit_v1 import ARC, rows, unpack24
from coarse_osm_context_records_v1 import build as build_contexts, u24
from coarse_osm_context_records_audit_v1 import audit as audit_contexts
from coarse_osm_entry_graph_audit_v1 import pairs


def build(source, rules, decisions, single_entries, multi_entries, offsets_path, targets_path,
          permutation, source_turns, final_turns, output, dimensions, check=lambda:None):
    began = time.monotonic()
    way_count, vertices, pre_count, post_count, _ = dimensions
    multi = pairs(multi_entries,4)
    assert len(multi) <= 200000 and all(max(pair) < pre_count for pair in multi)
    wanted = {value for pair in multi for value in pair}
    identities = array('Q',(r[0] for r in rows(source,'ways',struct.Struct('<Q24x'))))
    assert len(identities) == way_count and all(a < b for a,b in zip(identities,identities[1:]))
    blocked = bytearray(way_count)
    for identity, in rows(source,'closures',struct.Struct('<Q')):
        at=bisect_left(identities,identity)
        if at < way_count and identities[at] == identity:blocked[at]=1
    offsets=unpack24(Path(offsets_path).read_bytes());targets=unpack24(Path(targets_path).read_bytes())
    assert len(offsets)==vertices+1 and offsets[0]==0 and offsets[-1]==post_count
    assert len(targets)==post_count and all(a<=b for a,b in zip(offsets,offsets[1:]))
    cursor=array('I',offsets[:-1]);selected={};pre=retained=0
    for tail,head,way,*_ in rows(source,'arcs',ARC):
        assert pre < pre_count and tail < vertices and head < vertices and way < way_count
        arc=None
        if not blocked[way]:
            arc=cursor[tail]
            assert arc < offsets[tail+1] and targets[arc]==head
            cursor[tail]+=1;retained+=1
        if pre in wanted:selected[pre]=(arc,tail,head)
        pre+=1
        if pre%65536==0:check()
    assert pre==pre_count and retained==post_count and cursor==array('I',offsets[1:]) and selected.keys()==wanted
    mapped=set();dropped=0
    for before,after in multi:
        a,b=selected[before],selected[after]
        assert a[2]==b[1]
        if a[0] is None or b[0] is None:dropped+=1
        else:mapped.add((a[0],b[0]))
    supported=set(pairs(source_turns,3));static=sorted(supported|mapped)
    # Temporary CSR file belongs to this new owned root. Its semantics are
    # source-supported bans PLUS conservative multi-via entry bans.
    output=Path(output);output.mkdir()
    static_path=output/'retained-static-csr.u24'
    static_path.write_bytes(u24(value for pair in static for value in pair))
    # Release dense temporary mapping before the separately qualified builder.
    wanted_tails={tail for _,tail,_ in selected.values()}
    del identities,blocked,offsets,targets,cursor,selected
    report,fields=build_contexts(source,rules,decisions,single_entries,offsets_path,targets_path,
                               permutation,static_path,final_turns,dimensions,check)
    for name,raw in fields.items():
        path=output/name;path.parent.mkdir(exist_ok=True);path.write_bytes(raw)
    proof=audit_contexts(source,rules,decisions,single_entries,offsets_path,permutation,
                         static_path,final_turns,output,dimensions,check)
    # Independently source-map every selected pre-arc by CSR rank within its
    # native tail, using sparse counters instead of the constructor's cursors.
    # Read the emitted CSR targets only through the new source pass; every
    # selected source endpoint and non-closed status must reconstruct exactly.
    wanted_arcs={};ranks=Counter();pre=0
    from coarse_osm_entry_resolution_audit_v1 import fixed
    source_ids=array('Q',(r[0] for r in rows(source,'ways',struct.Struct('<Q24x'))))
    closed={r[0] for r in rows(source,'closures',struct.Struct('<Q'))}
    starts=unpack24(Path(offsets_path).read_bytes())
    for tail,head,way,*_ in rows(source,'arcs',ARC):
        allowed=source_ids[way] not in closed
        if pre in wanted:
            wanted_arcs[pre]=(starts[tail]+ranks[tail] if allowed else None,tail,head)
        if allowed and tail in wanted_tails:ranks[tail]+=1
        pre+=1
        if pre%65536==0:check()
    assert pre==pre_count and wanted_arcs.keys()==wanted
    assert {tail for _,tail,_ in wanted_arcs.values()}==wanted_tails
    independently_mapped=set()
    for a,b in fixed(multi_entries,struct.Struct('<II'),200000):
        incoming,tail,head=wanted_arcs[a];following,other_tail,_=wanted_arcs[b]
        assert head==other_tail
        if incoming is not None and following is not None:independently_mapped.add((incoming,following))
    assert independently_mapped==mapped and set(pairs(static_path,3))==set(pairs(source_turns,3))|independently_mapped
    report['retainedStaticForbiddenPairs']=report.pop('supportedTurnPairsRetained')
    report['staticForbiddenBytes']=report.pop('sourceOnlyForbiddenBytes')
    report['finalForbiddenUnionPairsChecked']=report.pop('oldFinalForbiddenUnionPairsChecked')
    proof['allRetainedStaticForbiddenPairsChecked']=proof.pop('allSupportedTurnPairsRetained')
    proof['scope']='Complete independent history state/exit/trigger source audit;static forbidden means all source-supported bans plus multi-via entry bans. Static union single-via triggers equals final conservative turn set. No runtime/query/app admission.'
    report.update(status='multiway_static_bans_and_single_via_context_records_source_audited',
                  supportedSourceTurnPairs=len(supported),multiPreEntryPairs=len(multi),
                  activeMultiEntryPairs=len(mapped),multiEntryPairsDroppedByOtherClosures=dropped,
                  independentMultiEntryCsrMappingsChecked=len(wanted),independentAudit=proof,
                  requiresTurnContextSearch=True,workerOperationSecondsIncludingAllSourceAudits=time.monotonic()-began,
                  scope='Single-via histories on NEW physical IDs. All source-supported and conservative multi-via entry bans remain static;only single-via entry bans become history triggers. Complete independent source audits and a separate sparse CSR-rank mapping verify both. No speed/geometry/flags/closure change,query/ETA/app admission.')
    return report,fields
