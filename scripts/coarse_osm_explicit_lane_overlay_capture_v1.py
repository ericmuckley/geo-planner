"""Complete small captured native overlay/merge versus frozen Python graph logic."""
import json
from pathlib import Path

from coarse_osm_car_cost_math_v1 import NativeCosts
from coarse_osm_conditional_fact_io_v1 import Rows,Writer,replace_rows,insert_arcs
from coarse_osm_explicit_lane_overlay_v1 import prepare
from coarse_osm_explicit_lanes_graph_v1 import augment
from coarse_osm_multiway_entry_v1 import plan_multiway
from coarse_osm_packed_capture_v1 import encode
from evaluate_osm_conditional_capture_v1 import arc_dict,packed_arcs,unpack24


def run(plan,root,check):
    source=Path('/facts/capture');original=json.loads(Path('/inputs/capture-closed.json').read_bytes())['roster']
    current=Path('/facts/current');current_report=json.loads(Path('/inputs/current-overlay-report.json').read_bytes())
    current_roster=current_report['factRoster'];opened=[];writer=None
    def field(prefix,shape,where=None,pins=None):
        if where is None:
            where,pins=(current,current_roster) if prefix in ('ways','arcs','flags') else (source,original)
        rows=Rows(where,pins,prefix,shape,check);opened.append(rows);return rows
    try:
        ids,xy,anchors,geometry,flags,ways,arcs=[field(n,f) for n,f in [('ids','<Q'),('xy','<i'),('anchors','<I'),('geometry','<I'),('flags','<B'),('ways','<QddII'),('arcs','<IIIIIb3xQ')]]
        assert len(ids)==143560 and len(ways)==28995 and len(arcs)==79118 and len(geometry)<500000
        assert current_report['changedWayRows']==108 and current_report['changedNodeFlags']==0
        raw_records=json.loads(Path('/inputs/lane-records.json').read_bytes());assert len(raw_records)==32
        records=[{'type':'way','id':r['id'],'tags':r['tags']} for r in raw_records if r['eligibilityGained']]
        assert len(records)==28
        kernel=NativeCosts('/artifacts/car-cost-math.so',plan['artifact']['sha256'])
        overlay=prepare(ids,xy,anchors,geometry,ways,arcs,records,kernel,check)
        assert len(overlay['wayRows'])==28 and len(overlay['arcs'])==30 and not overlay['nodeFlags']
        (root/'cost-facts').mkdir();writer=Writer(root,32*1048576,check)
        writer.start('ways');replace_rows(ways,overlay['wayRows'],writer)
        writer.start('flags');replace_rows(flags,{},writer)
        writer.start('arcs');insertions=insert_arcs(arcs,overlay['arcs'],writer);writer.finish()
        new_ways=field('ways','<QddII',root,writer.roster);new_arcs=field('arcs','<IIIIIb3xQ',root,writer.roster)
        new_flags=field('flags','<B',root,writer.roster)
        assert len(new_ways)==len(ways) and len(new_arcs)==len(arcs)+30
        assert len(new_flags)==len(flags)
        for i in range(len(flags)):assert new_flags[i]==flags[i]
        for i in range(len(ways)):
            if i%2048==0:check()
            assert new_ways[i]==overlay['wayRows'].get(i,ways[i])
        cursor=shift=0
        for i in range(len(arcs)):
            if i%2048==0:check()
            while cursor<len(insertions) and insertions[cursor]['oldArcInsertion']<=i:
                shift+=insertions[cursor]['newArcCount'];cursor+=1
            assert new_arcs[i+shift]==arcs[i],'Every original preclosure arc/price unchanged'
        at=0
        for group in insertions:
            for i in range(group['newArcCount']):assert new_arcs[group['newArcFirst']+i]==overlay['arcs'][at];at+=1
        assert at==30
        # This object expansion is restricted to the complete <=200k-node capture.
        values=lambda rows:[rows[i] for i in range(len(rows))]
        ids,xy,anchors,geometry,flags,old_ways,old_arcs,actual_ways,actual_arcs=map(values,(ids,xy,anchors,geometry,flags,ways,arcs,new_ways,new_arcs))
        expected_ways,expected_arcs,changed=augment(ids,xy,anchors,geometry,old_ways,old_arcs,raw_records,check)
        assert actual_ways==expected_ways and len(changed)==28
        assert sorted(actual_arcs)==sorted(expected_arcs),'Every native new source primitive sum independently Python-priced'
        elements=[json.loads(line)['element'] for line in (source/'deferred-relations.jsonl').read_text().splitlines()]
        assert len(elements)==4900
        turns=values(field('turns','<QQQQB7x'))
        cases=json.loads(Path('/inputs/original-report.json').read_bytes())['queries'];assert len(cases)==82
        frozen=json.loads(Path('/inputs/lane-graph-report.json').read_bytes());assert frozen['candidateFinite']==81 and len(frozen['rows'])==82
        def graph(source_ways,source_arcs):
            proposal=plan_multiway(elements,[arc_dict(a,source_ways) for a in source_arcs],len(source_arcs))
            fields,fixtures,counts=encode(ids,xy,anchors,flags,geometry,source_ways,source_arcs,proposal['closed'],turns,cases)
            active=packed_arcs(source_arcs,source_ways,proposal['closed']);index={tuple(a[:6]):i for i,a in enumerate(active)}
            extra={(index[tuple(source_arcs[a][:6])],index[tuple(source_arcs[b][:6])]) for a,b in proposal['multiPairs']
                   if tuple(source_arcs[a][:6]) in index and tuple(source_arcs[b][:6]) in index}
            numbers=unpack24(fields['forbidden-turns.u24']);pairs=set(zip(numbers[::2],numbers[1::2]))|extra
            fields['forbidden-turns.u24']=b''.join(i.to_bytes(3,'little') for pair in sorted(pairs) for i in pair)
            for fixture,row in zip(fixtures,frozen['rows'],strict=True):
                assert fixture['sourceNodeIds']==row['sourceNodeIds'] and fixture['windowId']==row['windowId']
                fixture['expectedTicks']=row['candidateTicks']
            return fields,fixtures,counts,proposal
        actual_fields,actual_fixtures,counts,actual=graph(actual_ways,actual_arcs)
        expected_fields,expected_fixtures,_,expected=graph(expected_ways,expected_arcs)
        assert actual_fields==expected_fields and actual_fixtures==expected_fixtures
        assert actual['closed']==expected['closed'] and actual['contextRules']==expected['contextRules']
        assert counts['arcs']==frozen['newPhysicalArcs']==77459
        assert len(actual['closed'])==506 and len(actual['contextRules'])==295
        assert len(actual_fields)==11
        for rows in opened:rows.verify_unchanged()
        return {'status':'complete_captured_explicit_lane_native_overlay_merge_audit_passed',
                'originalWaysChecked':len(old_ways),'originalFlagsChecked':len(flags),'originalArcsChecked':len(old_arcs),
                'changedWayRows':28,'addedNativePricedArcs':30,'changedNodeFlags':0,
                'allOldSourceRowsAndArcPricesExact':True,'allNewNativePricedArcsIndependentlyChecked':True,
                'physicalPackedFieldsByteIdentical':len(actual_fields),'paidFixturesExact':82,
                'singleViaContextRulesExact':295,'remainingClosedWaysExact':506,
                'qualifiedFiniteResultsReusedByIdentity':81,'qualifiedUnavailableResultsReusedByIdentity':1,
                'queriesExecutedHere':0,'sourcePbfReads':0,'sourceConstructorExecutions':0,'providerRequests':0,
                'applicationDbReads':0,'nationalGraphMerged':False,'appActivated':False,
                'overlayBytes':writer.bytes,'factRoster':writer.roster,'overlayCounts':overlay['counts'],'insertions':insertions,
                'scope':'Complete bounded captured typed-source merge audit. Current conditional overlay supplies normalized old ways/flags/arcs;all other original columns unchanged. New lane native primitive costs and all new source rows independently match frozen Python lane augmentation;all old source rows/arc costs fixed. All11physical CSR fields/82paid fixtures/source closures/295single-via histories match the frozen lane prototype logic;81finite/1null outcomes reused by identity,not new search/source-witness/ETA measurement. No country/sourcePBF/constructor/provider/DB/app admission,policy broadening,speed fit or place exception.'}
    finally:
        if writer:writer.finish()
        for rows in reversed(opened):rows.close()
