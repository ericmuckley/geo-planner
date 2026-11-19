"""Captured explicit-lane graph comparison with unchanged restriction policy."""
import argparse
from array import array
import gzip
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

from coarse_osm_conditional_graph_v1 import augment as conditional_augment
from coarse_osm_context_turns_v1 import ContextQueryGraph
from coarse_osm_entry_graph_v1 import QueryGraph
from coarse_osm_explicit_lanes_graph_v1 import augment
from coarse_osm_multiway_entry_v1 import plan_multiway, audit_raw_multiway_path
from coarse_osm_packed_capture_v1 import ARC, TURN, WAY, encode
from evaluate_osm_conditional_capture_v1 import SourceReplay, arc_dict, packed_arcs, sha, unpack24


def run(recipe,pin):
    began=time.monotonic();repo=Path(__file__).resolve().parents[1]
    assert sha(recipe)==pin
    plan=json.loads(recipe.read_bytes())
    assert plan['output']=='data/coarse-quality/us-osm-explicit-lanes-graph-capture-v1'
    assert plan['controlsPassed']==52 and plan['expectedPreArcs']==79118
    assert plan['expectedActiveArcs']==77429 and plan['hostSeconds']==600
    assert plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+plan['maxOwnedBytes']<72*1024**3
    for name,expected in plan['bindings'].items():assert sha(repo/name)==expected,name
    root=repo/plan['output'];root.mkdir();(root/'execution-plan.json').write_bytes(recipe.read_bytes())
    def check():
        assert time.monotonic()-began<600
        assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)<4*1024**3
    def save(name,value):
        raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode();assert len(raw)<=1048576
        with (root/name).open('xb') as stream:stream.write(raw)
    try:
        source=repo/plan['source'];roster=json.loads((repo/plan['sourceClosed']).read_bytes())['roster']
        assert sum(p['bytes'] for n,p in roster.items() if n.startswith('cost-facts/'))<=16*1048576
        def field(prefix,code=None,shape=None):
            raw=bytearray()
            for name in sorted(roster):
                if name.startswith('cost-facts/'+prefix+'-'):
                    check();path=source/name
                    assert path.stat().st_size==roster[name]['bytes'] and sha(path)==roster[name]['sha256']
                    raw.extend(path.read_bytes())
            if shape:return list(shape.iter_unpack(raw))
            if code:
                values=array(code);values.frombytes(raw);return values
            return raw
        ids,xy,anchors,flags=field('ids','Q'),field('xy','i'),field('anchors','I'),field('flags')
        geometry,ways,raw_arcs=field('geometry','I'),field('ways',shape=WAY),field('arcs',shape=ARC)
        original_closed,turns=set(field('closures','Q')),field('turns',shape=TURN)
        elements=[json.loads(line)['element'] for line in (source/'deferred-relations.jsonl').read_text().splitlines()]
        cases=json.loads((repo/plan['originalReport']).read_bytes())['queries']
        assert len(cases)==82 and len(elements)==4900
        records=json.loads((repo/plan['conditionalRecords']).read_bytes())['records'];assert len(records)==109
        ways,raw_arcs,changed=conditional_augment(ids,xy,anchors,geometry,ways,raw_arcs,records,check)
        assert len(changed)==108 and len(raw_arcs)==plan['expectedPreArcs']
        old_proposal=plan_multiway(elements,[arc_dict(a,ways) for a in raw_arcs],len(raw_arcs))
        assert old_proposal['oldClosed']==original_closed
        old_fields,old_fixtures,old_counts=encode(ids,xy,anchors,flags,geometry,ways,raw_arcs,old_proposal['closed'],turns,cases)
        old_active=packed_arcs(raw_arcs,ways,old_proposal['closed'])
        old_index={tuple(a[:6]):i for i,a in enumerate(old_active)}
        def entry_pairs(proposal,raw,index):
            return {(index[tuple(raw[a][:6])],index[tuple(raw[b][:6])]) for a,b in proposal['multiPairs']
                    if tuple(raw[a][:6]) in index and tuple(raw[b][:6]) in index}
        old_values=unpack24(old_fields['forbidden-turns.u24'])
        old_supported=set(zip(old_values[::2],old_values[1::2]));old_entries=entry_pairs(old_proposal,raw_arcs,old_index)
        old_physical=[arc_dict(a,ways) for a in old_active]
        baseline=ContextQueryGraph(QueryGraph(old_physical,flags,old_supported|old_entries),old_proposal['contextRules'])
        old_report=json.loads((repo/plan['multiwayBaseline']/'report.json').read_bytes())
        assert old_report['candidateFinite']==81 and len(old_report['rows'])==82
        assert old_counts['arcs']==plan['expectedActiveArcs']==77429
        lane_records=json.loads((repo/plan['laneRecords']).read_bytes());assert len(lane_records)==32
        old_ways,old_raw=ways,raw_arcs
        ways,raw_arcs,lane_changed=augment(ids,xy,anchors,geometry,ways,raw_arcs,lane_records,check)
        assert len(lane_changed)==28 and raw_arcs[:len(old_raw)]==old_raw
        changed_ids={row['way'] for row in lane_changed}
        for before,after in zip(old_ways,ways,strict=True):
            if before[0] not in changed_ids:assert before==after
        pre_arcs=[arc_dict(a,ways) for a in raw_arcs]
        proposal=plan_multiway(elements,pre_arcs,len(raw_arcs))
        fields,fixtures,counts=encode(ids,xy,anchors,flags,geometry,ways,raw_arcs,proposal['closed'],turns,cases)
        active=packed_arcs(raw_arcs,ways,proposal['closed']);index={tuple(a[:6]):i for i,a in enumerate(active)}
        assert len(index)==len(active)
        mapping={before:index[tuple(a[:6])] for before,a in enumerate(old_active) if tuple(a[:6]) in index}
        for before,after in mapping.items():assert old_active[before]==active[after]
        entries=entry_pairs(proposal,raw_arcs,index);values=unpack24(fields['forbidden-turns.u24'])
        supported=set(zip(values[::2],values[1::2]));physical=[arc_dict(a,ways) for a in active]
        candidate=ContextQueryGraph(QueryGraph(physical,flags,supported|entries),proposal['contextRules'])
        # Newly present roads can activate restrictions. Measure transition/path
        # changes rather than assuming graph-superset monotonicity.
        allowed=removed_transitions=0
        for before,a in enumerate(old_physical):
            for after in baseline.source.outgoing[a['head']]:
                delay=baseline.source.delay(before,after)
                if delay is None:continue
                allowed+=1
                if before not in mapping or after not in mapping or candidate.source.delay(mapping[before],mapping[after])!=delay:
                    removed_transitions+=1
        replay=SourceReplay(ids,xy,anchors,geometry,ways,active,elements,proposal['closed'],proposal['converted'])
        rows=[];finite=improved=recovered=regressed=0
        for ordinal,(fixture,old_fixture,old_row) in enumerate(zip(fixtures,old_fixtures,old_report['rows'],strict=True)):
            check();assert fixture['sourceNodeIds']==old_fixture['sourceNodeIds']==old_row['sourceNodeIds']
            assert fixture['windowId']==old_fixture['windowId']==old_row['windowId']
            prior=baseline.query(old_fixture['source'],old_fixture['target'],old_fixture['directTicks'],check)
            assert prior['ticks']==old_row['candidateTicks']
            result=candidate.query(fixture['source'],fixture['target'],fixture['directTicks'],check)
            candidate.replay(fixture['source'],fixture['target'],fixture['directTicks'],result)
            audit_raw_multiway_path(elements,proposal['multiConverted'],physical,result,set(a['way'] for a in pre_arcs))
            witness=replay.audit(fixture,result,flags)
            if prior['ticks'] is not None:
                improved+=result['ticks'] is not None and result['ticks']<prior['ticks']
                regressed+=result['ticks'] is None or result['ticks']>prior['ticks']
            else:recovered+=result['ticks'] is not None
            finite+=witness is not None
            raw=json.dumps({'fixture':fixture,'result':result,'sourceWitness':witness},separators=(',',':')).encode()
            compressed=gzip.compress(raw,mtime=0);assert len(raw)<=16*1048576 and len(compressed)<=2*1048576
            name=f'query-{ordinal:02d}.json.gz'
            with (root/name).open('xb') as stream:stream.write(compressed)
            rows.append({'index':ordinal,'windowId':fixture['windowId'],'sourceNodeIds':fixture['sourceNodeIds'],
                         'baselineTicks':prior['ticks'],'candidateTicks':result['ticks'],'pathSteps':len(result['steps']),
                         'sourceReplayed':witness is not None,'witness':{'filename':name,'bytes':len(compressed),'sha256':hashlib.sha256(compressed).hexdigest()}})
        assert sum(p.stat().st_size for p in root.rglob('*') if p.is_file())<plan['maxOwnedBytes']
        report={'status':'captured_explicit_lane_graph_and_source_replay_complete','recipeSha256':pin,
                'originalCases':82,'baselineFinite':81,'candidateFinite':finite,'candidateStillUnreachable':82-finite,
                'previousFailuresRecovered':recovered,'previousFiniteImproved':improved,'previousFiniteRegressed':regressed,
                'oldPreArcs':len(old_raw),'newPreArcs':len(raw_arcs),'oldPhysicalArcs':len(old_active),'newPhysicalArcs':len(active),
                'oldPhysicalArcsRetained':len(mapping),'oldRetainedArcPricesExact':True,
                'oldAllowedPhysicalTransitionsChecked':allowed,'oldAllowedPhysicalTransitionsRemoved':removed_transitions,
                'oldSupportedTurnPairs':len(old_supported),'supportedSourceTurnPairs':len(supported),
                'oldContextRules':len(old_proposal['contextRules']),'newContextRules':len(proposal['contextRules']),
                'oldClosedWays':len(old_proposal['closed']),'newClosedWays':len(proposal['closed']),
                'changedWays':lane_changed,'newPreClosureArcs':len(raw_arcs)-len(old_raw),
                'maximumCapturedQueryStates':candidate.maximum_states,'rows':rows,
                'routingQueries':164,'sourcePbfReads':0,'nativeConstructorExecutions':0,'providerRequests':0,
                'applicationDbReads':0,'hostSeconds':time.monotonic()-began,'appActivated':False,
                'scope':'Captured source-only explicit ordinary-car lane eligibility experiment. All old source rows/prices/directions retained except28formerly lane-rejected policies/normalized flags;new geometry pays every primitive. Recompute all source restrictions:absent-member decisions,single-via histories,multi-entry bans,and other closure contributors. All82previous optima reproduced;every finite new winner independently source geometry/price/node/turn/single-via/raw multi-entry replayed. Added roads may activate restrictions;regressions measured,not assumed absent. No lane-to-lane simulation,native cost parity,country feasibility,83ETA/maps/accuracy/app admission,cost fit or place exception. HostRSS/deadline are not cgroup/CPU/swap/cloud admission.'}
        save('report.json',report)
        print(json.dumps({k:report[k] for k in ('status','candidateFinite','candidateStillUnreachable','previousFailuresRecovered','previousFiniteImproved','previousFiniteRegressed','oldPhysicalArcs','newPhysicalArcs','newPreClosureArcs','hostSeconds')}))
    except BaseException as error:
        save('failure.json',{'error':repr(error),'hostSeconds':time.monotonic()-began});raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe',type=Path);parser.add_argument('pin')
    args=parser.parse_args();run(args.recipe,args.pin)
