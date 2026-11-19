"""Complete bounded captured cost derivation and independent Python price audit."""
import math
from pathlib import Path

from import_roads import distance_m
from coarse_osm_car_cost_math_v1 import NativeCosts
from coarse_osm_conditional_fact_io_v1 import Rows,Writer,replace_rows
from coarse_osm_tagged_timing_v1 import POLICY,estimated_way,reprice_arcs

FORMATS={'ids':'<Q','xy':'<i','anchors':'<I','flags':'<B','geometry':'<I','ways':'<QddII','arcs':'<IIIIIb3xQ'}


def run(plan,root,check):
    source=Path('/facts/captured');opened=[];writer=None
    def field(name,where=source,roster=None):
        rows=Rows(where,plan['sourceRoster'] if roster is None else roster,name,FORMATS[name],check);opened.append(rows);return rows
    try:
        fields={name:field(name) for name in FORMATS}
        assert {n:len(r) for n,r in fields.items()}==plan['sourceCounts']
        assert len(fields['ids'])<=200000 and len(fields['arcs'])<=200000 and len(fields['ways'])<=100000 and len(fields['geometry'])<=1000000,'Captured prototype only;country requires separate qualification/freeze'
        assert plan['policy']==POLICY
        kernel=NativeCosts('/artifacts/car-cost-math.so',plan['artifact']['sha256'])
        (root/'cost-facts').mkdir();writer=Writer(root,32*1048576,check);changed=0
        writer.start('ways');buffer=bytearray()
        for i in range(len(fields['ways'])):
            old=fields['ways'][i];new=estimated_way(old);changed+=new!=old
            buffer.extend(fields['ways'].row.pack(*new))
            if len(buffer)>=1048576:writer.append(buffer);buffer.clear()
        if buffer:writer.append(buffer)
        writer.start('flags');replace_rows(fields['flags'],{},writer)
        writer.start('arcs');buffer.clear();stats={}
        for row in reprice_arcs(fields['ways'],fields['geometry'],fields['xy'],fields['anchors'],fields['arcs'],kernel,stats,check):
            buffer.extend(fields['arcs'].row.pack(*row))
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
        maximum=overflows=0
        for i in range(len(fields['arcs'])):
            if i%1024==0:check()
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
        return dict(status='complete_captured_tagged_timing_native_and_independent_python_prices_passed',policy=POLICY,
                    sourceCounts={n:len(r) for n,r in fields.items()},changedEstimatedWayRows=changed,pricing=stats,
                    allPhysicalArcDescriptorsAndOrderExact=True,allDirectionsDefaultsRolesAndFlagsExact=True,nodeFlagsChanged=0,
                    everyOldAndNewMacroPricePythonAudited=len(fields['arcs']),maximumProposedMacroMs=maximum,proposedCostOverflowArcs=overflows,
                    derivedFactBytes=writer.bytes,factRoster=writer.roster,originalLegalSpeedSourceFactsModified=False,
                    costFactsMeaning='Derived estimated driving speeds and costs;original legal/default source speeds retained separately in bound read-only inputs.',
                    sourcePbfReads=0,sourceConstructorExecutions=0,routingQueries=0,providerRequests=0,applicationDbReads=0,
                    countryCostFactsBuilt=False,runtimeGraphBuilt=False,accuracyOrAppAccepted=False,
                    scope='Complete captured source only. Fixed9/10 explicit-speed model/defaults unchanged;all source directions/default markers/IDs/geometry/node/closure/turn inputs remain. Native batched old+new primitive arithmetic and every arc independently Python-rebuilt. Original legal speeds stay read-only;output way speeds are derived estimates,never relabeled source tags. No shortest-path/map/ETA/national/runtime/app admission.')
    finally:
        if writer:writer.finish()
        for rows in reversed(opened):rows.close()
