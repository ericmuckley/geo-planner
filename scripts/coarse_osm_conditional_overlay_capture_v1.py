"""Full small captured overlay audit; no country source or routing search."""
import hashlib
import json
from pathlib import Path
from coarse_osm_car_cost_math_v1 import NativeCosts
from coarse_osm_car_policy_v2 import restriction_policy
from coarse_osm_conditional_fact_io_v1 import Rows,Writer,replace_rows,insert_arcs
from coarse_osm_conditional_overlay_v1 import closed_relation_nodes,prepare
from coarse_osm_entry_graph_v1 import plan_entries
from coarse_osm_packed_capture_v1 import encode


def run(plan,root,check):
    source=Path('/facts/capture');roster=json.loads(Path('/inputs/capture-closed.json').read_bytes())['roster'];opened=[]
    def field(prefix,format,where=source,pins=roster):
        rows=Rows(where,pins,prefix,format,check);opened.append(rows);return rows
    writer=None
    try:
        ids,xy,anchors,flags,geometry,ways,arcs=[field(n,f) for n,f in [('ids','<Q'),('xy','<i'),('anchors','<I'),('flags','<B'),('geometry','<I'),('ways','<QddII'),('arcs','<IIIIIb3xQ')]]
        assert len(ids)==143560 and len(ways)==28995 and len(arcs)<200000 and len(geometry)<500000
        elements=[json.loads(line)['element'] for line in (source/'deferred-relations.jsonl').read_text().splitlines()];assert len(elements)==4900
        unsupported=[e for e in elements if restriction_policy(e)['status']=='closed-unsupported']
        closed_nodes,relation_count=closed_relation_nodes(unsupported,check)
        records=[{'type':r['kind'],'id':r['id'],'tags':r['tags']} for r in json.loads(Path('/inputs/conditional-records.json').read_bytes())['records'] if r['eligibilityGained']]
        assert len(records)==108
        kernel=NativeCosts('/artifacts/car-cost-math.so',plan['artifact']['sha256'])
        overlay=prepare(ids,xy,anchors,flags,geometry,ways,arcs,records,closed_nodes,kernel,check)
        assert len(overlay['wayRows'])==108 and not overlay['nodeFlags'] and len(overlay['arcs'])==307
        (root/'cost-facts').mkdir();writer=Writer(root,32*1048576,check)
        writer.start('ways');replace_rows(ways,overlay['wayRows'],writer)
        writer.start('flags');replace_rows(flags,overlay['nodeFlags'],writer)
        writer.start('arcs');insertions=insert_arcs(arcs,overlay['arcs'],writer);writer.finish()
        new_ways=field('ways','<QddII',root,writer.roster);new_flags=field('flags','<B',root,writer.roster);new_arcs=field('arcs','<IIIIIb3xQ',root,writer.roster)
        assert len(new_ways)==len(ways) and len(new_flags)==len(flags) and len(new_arcs)==len(arcs)+307
        for i in range(len(ways)):
            if i%2048==0:check()
            assert new_ways[i]==overlay['wayRows'].get(i,ways[i])
        for i in range(len(flags)):assert new_flags[i]==overlay['nodeFlags'].get(i,flags[i])
        cursor=shift=0
        for i in range(len(arcs)):
            if i%2048==0:check()
            while cursor<len(insertions) and insertions[cursor]['oldArcInsertion']<=i:shift+=insertions[cursor]['newArcCount'];cursor+=1
            assert new_arcs[i+shift]==arcs[i],'All original source arc costs/directions/parts retained exactly'
        at=0
        for group in insertions:
            for i in range(group['newArcCount']):assert new_arcs[group['newArcFirst']+i]==overlay['arcs'][at];at+=1
        assert at==307
        # Object expansion is limited to this complete <=200k-node capture.
        values=lambda rows:[rows[i] for i in range(len(rows))]
        ids,xy,anchors,geometry,flags,ways,arcs=map(values,(ids,xy,anchors,geometry,new_flags,new_ways,new_arcs))
        turns=values(field('turns','<QQQQB7x'));closures=set(values(field('closures','<Q')))
        cases=json.loads(Path('/inputs/original-report.json').read_bytes())['queries'];assert len(cases)==82
        arc_dict=lambda a:{'tail':a[0],'head':a[1],'way':ways[a[2]][0],'first':a[3],'last':a[4],'direction':a[5],'ms':a[6]}
        proposal=plan_entries(elements,[arc_dict(a) for a in arcs]);assert proposal['oldClosed']==closures
        fields,fixtures,_=encode(ids,xy,anchors,flags,geometry,ways,arcs,proposal['closed'],turns,cases)
        active=sorted((a for a in arcs if ways[a[2]][0] not in proposal['closed']),key=lambda a:(a[0],a[2],a[3],a[4],-a[5]));index={tuple(a[:6]):i for i,a in enumerate(active)}
        extra={(index[tuple(arcs[a][:6])],index[tuple(arcs[b][:6])]) for a,b in proposal['pairs'] if tuple(arcs[a][:6]) in index and tuple(arcs[b][:6]) in index}
        raw=fields['forbidden-turns.u24'];numbers=[int.from_bytes(raw[i:i+3],'little') for i in range(0,len(raw),3)]
        pairs=sorted(set(zip(numbers[::2],numbers[1::2]))|extra);fields['forbidden-turns.u24']=b''.join(i.to_bytes(3,'little') for pair in pairs for i in pair)
        target=json.loads(Path('/inputs/conditional-artifacts.json').read_bytes());assert set(target)=={'routing/'+n for n in fields}
        checks=[]
        for name,raw in fields.items():
            pin=target['routing/'+name];assert len(raw)==pin['bytes'] and hashlib.sha256(raw).hexdigest()==pin['sha256'],'Previous conditional packed graph byte identity'
            checks.append({'name':name,'bytes':len(raw),'sha256':pin['sha256']})
        expected=json.loads(Path('/inputs/conditional-fixtures.json').read_bytes());assert len(expected)==82
        for fixture,old in zip(fixtures,expected):fixture['expectedTicks']=old['expectedTicks']
        assert fixtures==expected
        for rows in opened:rows.verify_unchanged()
        return {'status':'complete_captured_conditional_overlay_native_merge_audit_passed','originalWaysChecked':len(ways),'originalFlagsChecked':len(flags),'originalArcsChecked':len(arcs)-307,'changedWayRows':108,'addedNativePricedArcs':307,'changedNodeFlags':0,'unsupportedSourceRelationsRead':relation_count,'relationClosedNodesRetained':len(closed_nodes),'allOldSourceRowsAndArcCostsExact':True,'allNewNativePricedArcsChecked':True,'previousConditionalPackedFieldsByteIdentical':checks,'previousConditionalPaidFixturesExact':82,'previousConditionalFinite':77,'previousConditionalUnavailable':5,'queriesExecutedHere':0,'sourcePbfReads':0,'sourceConstructorExecutions':0,'providerRequests':0,'applicationDbReads':0,'nationalGraphMerged':False,'appActivated':False,'overlayBytes':writer.bytes,'factRoster':writer.roster,'overlayCounts':overlay['counts'],'insertions':insertions,'scope':'Complete captured native-cost/fixed-width streaming merge audit, all old source rows preserved and all new prices/normalized way flags checked. Every previous conditional packed byte/82 paid fixtures identical; previous77 finite/5 unavailable results reused by byte identity, no new search or witness claim. Selected source IDs/places are validation only. No country graph/source acquisition/provider/ETA/app admission.'}
    finally:
        if writer:writer.finish()
        for rows in reversed(opened):rows.close()
