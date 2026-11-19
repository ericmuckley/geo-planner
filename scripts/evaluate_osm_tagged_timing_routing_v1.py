"""Bounded captured packed/history/paid-endpoint consumer of derived time costs."""
import argparse
from array import array
import gzip
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

from coarse_osm_context_turns_v1 import ContextQueryGraph
from coarse_osm_entry_graph_v1 import QueryGraph
from coarse_osm_multiway_entry_v1 import plan_multiway,audit_raw_multiway_path
from coarse_osm_packed_capture_v1 import ARC,TURN,WAY,encode
from evaluate_osm_conditional_capture_v1 import SourceReplay,arc_dict,packed_arcs,unpack24


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def run(recipe,pin):
    began=time.monotonic();repo=Path(__file__).resolve().parents[1]
    assert sha(recipe)==pin;plan=json.loads(recipe.read_bytes())
    assert plan['output']=='data/coarse-quality/us-osm-tagged-timing-routing-capture-v1'
    assert plan['hostSeconds']==600 and plan['maxOwnedBytes']==67108864 and plan['controlsPassed']==72
    assert plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+plan['maxOwnedBytes']<72*1024**3
    for name,expected in plan['bindings'].items():assert sha(repo/name)==expected,name
    root=repo/plan['output'];root.mkdir();(root/'execution-plan.json').write_bytes(recipe.read_bytes())
    source_stats={}
    def check():
        assert time.monotonic()-began<600
        assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)<4*1024**3
    def save(name,value):
        raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode();assert len(raw)<=1048576
        with (root/name).open('xb') as stream:stream.write(raw)
    def read(name,expected):
        path=repo/name;assert path.is_file() and not path.is_symlink() and path.stat().st_size==expected['bytes']<=16*1048576
        st=path.stat();source_stats[name]=(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)
        assert sha(path)==expected['sha256'];check();return path.read_bytes()
    def field(prefix,code=None,shape=None,derived=False):
        rows=plan['derivedFiles'] if derived else plan['sourceFiles']
        selected=[r for name,r in sorted(rows.items()) if Path(name).name.startswith(prefix+'-')]
        assert selected
        raw=b''.join(read(r['source'],r) for r in selected);assert len(raw)<=16*1048576
        if shape:return list(shape.iter_unpack(raw))
        if code:
            out=array(code);out.frombytes(raw);return out
        return raw
    try:
        assert sum(r['bytes'] for r in plan['sourceFiles'].values())<=16*1048576
        ids,xy,anchors,flags=field('ids','Q'),field('xy','i'),field('anchors','I'),field('flags')
        geometry,ways,raw_arcs=field('geometry','I'),field('ways',shape=WAY),field('arcs',shape=ARC)
        proposed_ways,proposed_arcs,proposed_flags=field('ways',shape=WAY,derived=True),field('arcs',shape=ARC,derived=True),field('flags',derived=True)
        assert len(ids)==143560 and len(anchors)==46881 and len(ways)==len(proposed_ways)==28995
        assert len(raw_arcs)==len(proposed_arcs)==79148 and flags==proposed_flags
        for before,after in zip(ways,proposed_ways,strict=True):
            assert (before[0],before[3],before[4])==(after[0],after[3],after[4])
            for index in (1,2):assert after[index]==before[index]*(1.0 if before[3]&(1<<(index+1)) else 0.9)
        for before,after in zip(raw_arcs,proposed_arcs,strict=True):assert before[:6]==after[:6] and after[6]>=before[6]
        original_closed=set(field('closures','Q'));turns=field('turns',shape=TURN)
        elements=[json.loads(line)['element'] for line in (repo/plan['relations']).read_text().splitlines()]
        cases=json.loads((repo/plan['originalReport']).read_bytes())['queries']
        assert len(elements)==4900 and len(cases)==82
        proposal=plan_multiway(elements,[arc_dict(a,ways) for a in raw_arcs],len(raw_arcs))
        assert proposal['oldClosed']==original_closed and len(proposal['closed'])==506 and len(proposal['contextRules'])==295
        def graph(cost_ways,cost_arcs):
            fields,fixtures,counts=encode(ids,xy,anchors,flags,geometry,cost_ways,cost_arcs,proposal['closed'],turns,cases)
            active=packed_arcs(cost_arcs,cost_ways,proposal['closed']);index={tuple(a[:6]):i for i,a in enumerate(active)}
            values=unpack24(fields['forbidden-turns.u24']);supported=set(zip(values[::2],values[1::2]))
            extra={(index[tuple(cost_arcs[a][:6])],index[tuple(cost_arcs[b][:6])]) for a,b in proposal['multiPairs']
                   if tuple(cost_arcs[a][:6]) in index and tuple(cost_arcs[b][:6]) in index}
            overflow=dict(zip(unpack24(fields['cost-overflow-arcs.u24']),array('I',fields['cost-overflow-ticks.u32'])))
            words=array('H');words.frombytes(fields['costs.u16']);assert len(words)==len(active)
            physical=[]
            for i,a in enumerate(active):
                ticks=overflow[i] if words[i]==65535 else words[i];assert ticks==(a[6]+124)//125
                record=arc_dict(a,cost_ways);record['ms']=ticks*125;physical.append(record)
            return fields,fixtures,active,physical,ContextQueryGraph(QueryGraph(physical,flags,supported|extra),proposal['contextRules'])
        old_fields,old_fixtures,old_active,_,baseline=graph(ways,raw_arcs)
        fields,fixtures,active,physical,candidate=graph(proposed_ways,proposed_arcs)
        cost_fields={'costs.u16','cost-overflow-arcs.u24','cost-overflow-ticks.u32'}
        unchanged=[name for name in fields if name not in cost_fields]
        assert len(unchanged)==8 and all(fields[n]==old_fields[n] for n in unchanged)
        assert len(active)==len(old_active)==77459
        assert all(a[:6]==b[:6] and b[6]>=a[6] for a,b in zip(old_active,active,strict=True))
        saved=json.loads((repo/plan['baselineReport']).read_bytes());assert saved['candidateFinite']==81 and len(saved['rows'])==82
        replay=SourceReplay(ids,xy,anchors,geometry,proposed_ways,active,elements,proposal['closed'],proposal['converted'])
        present={a['way'] for a in physical};rows=[];finite=increased=unchanged_totals=0
        def paid_domain(old,new):
            assert old.get('vertex')==new.get('vertex')
            before,after=old.get('partials',[]),new.get('partials',[]);assert len(before)==len(after)
            for a,b in zip(before,after,strict=True):assert a['arc']==b['arc'] and b['ticks']>=a['ticks']
        for ordinal,(fixture,old,prior_row) in enumerate(zip(fixtures,old_fixtures,saved['rows'],strict=True)):
            check();assert fixture['sourceNodeIds']==old['sourceNodeIds']==prior_row['sourceNodeIds']
            assert fixture['windowId']==old['windowId']==prior_row['windowId']
            paid_domain(old['source'],fixture['source']);paid_domain(old['target'],fixture['target'])
            assert (old['directTicks'] is None)==(fixture['directTicks'] is None)
            if old['directTicks'] is not None:assert fixture['directTicks']>=old['directTicks']
            previous=baseline.query(old['source'],old['target'],old['directTicks'],check);assert previous['ticks']==prior_row['candidateTicks']
            result=candidate.query(fixture['source'],fixture['target'],fixture['directTicks'],check)
            candidate.replay(fixture['source'],fixture['target'],fixture['directTicks'],result)
            audit_raw_multiway_path(elements,proposal['multiConverted'],physical,result,present)
            witness=replay.audit(fixture,result,flags)
            assert (previous['ticks'] is None)==(result['ticks'] is None),'All old feasible captured endpoints retain'
            if result['ticks'] is not None:
                assert result['ticks']>=previous['ticks'],'Nondecreasing exact costs cannot create a cheaper optimum'
                finite+=1;increased+=result['ticks']>previous['ticks'];unchanged_totals+=result['ticks']==previous['ticks']
            fixture['expectedTicks']=result['ticks']
            raw=json.dumps({'fixture':fixture,'result':result,'sourceWitness':witness},separators=(',',':')).encode()
            packed=gzip.compress(raw,mtime=0);assert len(raw)<=16*1048576 and len(packed)<=2*1048576
            name=f'query-{ordinal:02d}.json.gz'
            with (root/name).open('xb') as stream:stream.write(packed)
            rows.append(dict(index=ordinal,windowId=fixture['windowId'],sourceNodeIds=fixture['sourceNodeIds'],baselineTicks=previous['ticks'],candidateTicks=result['ticks'],sourceReplayed=witness is not None,pathSteps=len(result['steps']),asset={'file':name,'bytes':len(packed),'sha256':hashlib.sha256(packed).hexdigest()}))
        assert finite==81 and len(rows)==82 and increased+unchanged_totals==81
        (root/'routing').mkdir()
        for name,raw in fields.items():
            with (root/'routing'/name).open('xb') as stream:stream.write(raw)
        save('query-fixtures.json',fixtures)
        for name,before in source_stats.items():
            st=(repo/name).stat();assert before==(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)
        assert sum(p.stat().st_size for p in root.rglob('*') if p.is_file())<plan['maxOwnedBytes']
        report=dict(status='complete_captured_tagged_timing_packed_history_paid_routing_source_replay_passed',recipeSha256=pin,
                    originalCases=82,baselineFinite=81,candidateFinite=finite,candidateUnavailable=1,costsIncreased=increased,costsUnchanged=unchanged_totals,
                    unchangedPhysicalPackedFields=len(unchanged),physicalArcs=77459,preArcsChecked=79148,nodeFlagsChanged=0,
                    singleViaContextRules=295,closedWays=506,allOldOptimaReproduced=True,allNewFinitePathsSourceReplayed=True,
                    allPaidEndpointDomainsAndNondecreasingPricesChecked=True,routingQueries=164,sourcePbfReads=0,providerRequests=0,applicationDbReads=0,
                    originalLegalSpeedSourceModified=False,countryCostOrRuntimeBuilt=False,accuracyOrAppAccepted=False,
                    hostSecondsIncludingBindingEncodingPaidRebuildSearchSourceAuditAndWrites=time.monotonic()-began,rows=rows,
                    scope='Complete bounded captured packed-cost consumer. Eight physical/node/source-supported-turn fields stay byte-identical;all cost words decode to exact derived source prices. Rebuilt paid native prefixes/direct options preserve source endpoints. Every old optimum reproduces;every finite new path independently raw-source geometry/cost/node/via-node/single-history/multi-entry replayed. Same fixed9/10 explicit-speed rule/defaults unchanged. Original legal-speed source stays read-only. No national/83ETA/maps/localgrid/accuracy/app admission. Host RSS/deadline checks are not cgroup/CPU/swap/cloud measurements.')
        save('report.json',report);print(json.dumps({k:report[k] for k in ['status','candidateFinite','candidateUnavailable','costsIncreased','costsUnchanged','hostSecondsIncludingBindingEncodingPaidRebuildSearchSourceAuditAndWrites']}))
    except BaseException as error:save('failure.json',{'error':repr(error),'hostSeconds':time.monotonic()-began});raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe',type=Path);parser.add_argument('pin');args=parser.parse_args();run(args.recipe,args.pin)
