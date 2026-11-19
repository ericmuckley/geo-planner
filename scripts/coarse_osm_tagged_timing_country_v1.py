"""Complete streamed cost-only derivation and independent per-arc Python audit."""
import math
from pathlib import Path

from import_roads import distance_m
from coarse_osm_car_cost_math_v1 import NativeCosts
from coarse_osm_conditional_fact_io_v1 import Rows,Writer,replace_rows
from coarse_osm_tagged_timing_v1 import POLICY,estimated_way,reprice_arcs

FORMATS={'ids':'<Q','xy':'<i','anchors':'<I','flags':'<B','geometry':'<I','ways':'<QddII','arcs':'<IIIIIb3xQ'}


def run(plan,root,check):
    source=Path('/facts/input');opened=[];writer=None
    operation=plan['operation'];assert operation in ('controls','run')
    def field(name,where=source,roster=None):
        rows=Rows(where,plan['sourceRoster'] if roster is None else roster,name,FORMATS[name],check);opened.append(rows);return rows
    try:
        fields={name:field(name) for name in FORMATS}
        assert {n:len(r) for n,r in fields.items()}==plan['sourceCounts']
        if operation=='controls':
            assert len(fields['ids'])==143560 and len(fields['ways'])==28995 and len(fields['arcs'])==79148
            assert len(fields['geometry'])==177956 and len(fields['anchors'])==46881
        else:
            assert len(fields['ids'])==42993567 and len(fields['ways'])==4227238 and len(fields['arcs'])==9882872
            assert len(fields['geometry'])==48163649 and len(fields['anchors'])==5731903
        assert len(fields['xy'])==2*len(fields['ids']) and len(fields['flags'])==len(fields['anchors'])
        assert plan['policy']==POLICY
        kernel=NativeCosts('/artifacts/car-cost-math.so',plan['artifact']['sha256'])
        (root/'cost-facts').mkdir();writer=Writer(root,512*1048576,check);changed=0
        print('phase: estimated-way metadata',flush=True)
        writer.start('ways');buffer=bytearray()
        for i in range(len(fields['ways'])):
            old=fields['ways'][i];new=estimated_way(old);changed+=new!=old
            buffer.extend(fields['ways'].row.pack(*new))
            if len(buffer)>=1048576:writer.append(buffer);buffer.clear()
        if buffer:writer.append(buffer)
        writer.start('flags');replace_rows(fields['flags'],{},writer)
        print('phase: original-price verification and exact derived costs',flush=True)
        writer.start('arcs');buffer.clear();stats={};emitted=0
        for row in reprice_arcs(fields['ways'],fields['geometry'],fields['xy'],fields['anchors'],fields['arcs'],kernel,stats,check):
            buffer.extend(fields['arcs'].row.pack(*row));emitted+=1
            if emitted%1000000==0:print('priced arcs:',emitted,flush=True)
            if len(buffer)>=1048576:writer.append(buffer);buffer.clear()
        if buffer:writer.append(buffer)
        writer.finish()
        outputs={n:field(n,root,writer.roster) for n in ('ways','flags','arcs')}
        for n in outputs:assert len(outputs[n])==len(fields[n])
        for i in range(len(fields['ways'])):
            old,new=fields['ways'][i],outputs['ways'][i]
            assert (old[0],old[3],old[4])==(new[0],new[3],new[4])
            for index in (1,2):assert new[index]==old[index]*(1.0 if old[3]&(1<<(index+1)) else 0.9)
            if i%4096==0:check()
        for i in range(len(fields['flags'])):assert outputs['flags'][i]==fields['flags'][i]
        # The constructor batches native primitive arithmetic. This independent
        # pass rebuilds each arc separately from original integer coordinates,
        # original direction/default flags and the frozen Python distance rule.
        print('phase: independent per-arc original and proposed Python prices',flush=True)
        maximum=overflows=0
        for i in range(len(fields['arcs'])):
            if i%1024==0:check()
            if i and i%1000000==0:print('independently audited arcs:',i,flush=True)
            old,new=fields['arcs'][i],outputs['arcs'][i];assert old[:6]==new[:6]
            way=old[2];w=fields['ways'][way];start=0 if way==0 else fields['ways'][way-1][4];index=1 if old[5]==1 else 2
            speed=w[index];estimate=speed*(1.0 if w[3]&(1<<(index+1)) else 0.9);a=b=0
            for p in range(old[3],old[4]):
                left,right=fields['geometry'][start+p],fields['geometry'][start+p+1]
                if left==right:continue
                distance=distance_m([fields['xy'][2*left]/1e7,fields['xy'][2*left+1]/1e7],[fields['xy'][2*right]/1e7,fields['xy'][2*right+1]/1e7])
                a+=max(1,math.ceil(distance*3600/speed));b+=max(1,math.ceil(distance*3600/estimate))
            assert a==old[6] and b==new[6],'Every original/proposed primitive-ms source sum independently Python-rebuilt'
            assert b>=a;maximum=max(maximum,b);overflows+=(b+124)//125>=65535
        for rows in opened:rows.verify_unchanged()
        assert stats['arcsChecked']==len(fields['arcs']) and writer.bytes==len(fields['ways'])*32+len(fields['flags'])+len(fields['arcs'])*32
        return dict(status='complete_typed_tagged_timing_costs_and_independent_python_prices_passed',operation=operation,policy=POLICY,
                    sourceCounts={n:len(r) for n,r in fields.items()},changedEstimatedWayRows=changed,pricing=stats,
                    allPhysicalArcDescriptorsAndOrderExact=True,allDirectionsDefaultsRolesAndFlagsExact=True,nodeFlagsChanged=0,
                    everyOldAndNewMacroPricePythonAudited=len(fields['arcs']),maximumProposedMacroMs=maximum,proposedCostOverflowArcs=overflows,
                    derivedFactBytes=writer.bytes,factRoster=writer.roster,originalLegalSpeedSourceFactsModified=False,
                    costFactsMeaning='Derived estimated driving speeds and costs;original legal/default source speeds retained separately in bound read-only inputs.',
                    sourcePbfReads=0,sourceConstructorExecutions=0,routingQueries=0,providerRequests=0,applicationDbReads=0,
                    countryCostFactsBuilt=operation=='run',runtimeGraphBuilt=False,accuracyOrAppAccepted=False,
                    scope='Complete bound typed source;captured qualification or country cost-only run. Fixed9/10 explicit-speed model/defaults unchanged;all source directions/default markers/IDs/geometry/node/closure/turn inputs remain. Native batched old+new primitive arithmetic and every arc independently Python-rebuilt. Original legal speeds stay read-only;output way speeds are derived estimates,never relabeled source tags. No shortest-path/map/ETA/national/runtime/app admission.')
    finally:
        if writer:writer.finish()
        for rows in reversed(opened):rows.close()
