"""Complete typed source-fact overlay and independent price/byte audit.

Controls use the entire small saved capture. A separately frozen run applies the
same code to the country facts, with no PBF reader or ordinary node dictionary.
"""
from array import array
import hashlib
import json
from pathlib import Path
from coarse_osm_car_cost_math_v1 import NativeCosts
from coarse_osm_car_policy_v2 import restriction_policy
from coarse_osm_conditional_records_v1 import read_records
from coarse_osm_conditional_fact_io_v1 import Rows,Writer,replace_rows,insert_arcs
from coarse_osm_conditional_overlay_v1 import closed_relation_nodes,prepare

FORMATS={'ids':'<Q','xy':'<i','anchors':'<I','flags':'<B','geometry':'<I','ways':'<QddII','arcs':'<IIIIIb3xQ'}


def source_records(operation):
    if operation=='controls':
        return ({'type':r['kind'],'id':r['id'],'tags':r['tags']} for r in json.loads(Path('/inputs/conditional-records.json').read_bytes())['records'] if r['eligibilityGained'])
    return read_records('/inputs/changed-tags.bin')


def relations(operation,check):
    previous=total=count=0
    with Path('/facts/relations.jsonl').open('rb') as stream:
        while raw:=stream.readline(2*1048576+1):
            check();total+=len(raw);count+=1
            assert len(raw)<=2*1048576 and raw.endswith(b'\n') and total<=32*1048576 and count<=100000
            record=json.loads(raw);element=record['element'] if operation=='controls' else record
            assert element['id']>previous;previous=element['id']
            if restriction_policy(element)['status']=='closed-unsupported':yield element


def run(plan,root,check):
    operation=plan['operation'];assert operation in ('controls','run')
    source=Path('/facts/input');closed=json.loads(Path('/inputs/fact-closed.json').read_bytes());roster=closed['roster'];opened=[];writer=None
    def field(prefix,where=source,pins=roster):
        rows=Rows(where,pins,prefix,FORMATS[prefix],check);opened.append(rows);return rows
    try:
        fields={name:field(name) for name in FORMATS}
        for name,count in plan['sourceCounts'].items():assert len(fields[name])==count
        if operation=='controls':assert len(fields['ids'])<=200000 and len(fields['arcs'])<=200000
        else:
            assert len(fields['ids'])==42993567 and len(fields['ways'])==4227238 and len(fields['arcs'])==9837326
            assert len(fields['geometry'])==48163649 and len(fields['anchors'])==5731903
        closed_nodes,relation_count=closed_relation_nodes(relations(operation,check),check)
        assert relation_count==(819 if operation=='controls' else 70376)
        kernel=NativeCosts('/artifacts/car-cost-math.so',plan['artifact']['sha256'])
        overlay=prepare(*(fields[n] for n in FORMATS),source_records(operation),closed_nodes,kernel,check)
        expected=108 if operation=='controls' else 16286
        assert overlay['counts'].get('changedGraphWays',0)==len(overlay['wayRows'])==expected
        assert overlay['counts'].get('changedSourceNodes',0)==(0 if operation=='controls' else 2)
        predicted=len(fields['ways'])*32+len(fields['flags'])+(len(fields['arcs'])+len(overlay['arcs']))*32
        assert predicted<=512*1048576
        (root/'cost-facts').mkdir();writer=Writer(root,512*1048576,check)
        writer.start('ways');replace_rows(fields['ways'],overlay['wayRows'],writer)
        writer.start('flags');replace_rows(fields['flags'],overlay['nodeFlags'],writer)
        writer.start('arcs');insertions=insert_arcs(fields['arcs'],overlay['arcs'],writer);writer.finish()
        assert writer.bytes==predicted
        outputs={name:field(name,root,writer.roster) for name in ('ways','flags','arcs')}
        for i in range(len(fields['ways'])):
            if i%2048==0:check()
            assert outputs['ways'][i]==overlay['wayRows'].get(i,fields['ways'][i]),'Every old or source-policy-changed way row exact'
        for i in range(len(fields['flags'])):
            if i%8192==0:check()
            assert outputs['flags'][i]==overlay['nodeFlags'].get(i,fields['flags'][i]),'Every source/retained relation flag exact'
        cursor=shift=0
        for i in range(len(fields['arcs'])):
            if i%2048==0:check()
            while cursor<len(insertions) and insertions[cursor]['oldArcInsertion']<=i:shift+=insertions[cursor]['newArcCount'];cursor+=1
            assert outputs['arcs'][i+shift]==fields['arcs'][i],'Every old preclosure arc direction/geometry/cost exact'
        assert len(outputs['arcs'])==len(fields['arcs'])+len(overlay['arcs'])
        checked=0;maximum_primitive=maximum_macro=0;overflow=0
        for group in insertions:
            for ordinal in range(group['newArcCount']):
                if checked%256==0:check()
                arc=outputs['arcs'][group['newArcFirst']+ordinal];assert arc==overlay['arcs'][checked]
                tail,head,way,first,last,direction,ms=arc;row=outputs['ways'][way]
                assert direction in (1,-1) and row[3]&(1 if direction==1 else 2)
                start=0 if way==0 else fields['ways'][way-1][4]
                assert 0<=first<last<row[4]-start
                a=fields['geometry'][start+first];b=fields['geometry'][start+last]
                assert fields['anchors'][tail]==(a if direction==1 else b) and fields['anchors'][head]==(b if direction==1 else a)
                coordinates=array('i');same=bytearray()
                for position in range(first,last):
                    left=fields['geometry'][start+position];right=fields['geometry'][start+position+1]
                    coordinates.extend((fields['xy'][2*left],fields['xy'][2*left+1],fields['xy'][2*right],fields['xy'][2*right+1]));same.append(int(left==right))
                speed=row[1 if direction==1 else 2];assert 0<speed<=160
                primitive=kernel.costs(coordinates,array('d',[speed])*len(same),same)
                total,ticks=kernel.sum(primitive);assert total==ms and ticks==(ms+124)//125,'Independent per-arc source primitive rebuild'
                maximum_primitive=max(maximum_primitive,max(primitive,default=0));maximum_macro=max(maximum_macro,ms);overflow+=ticks>=65535;checked+=1
        assert checked==len(overlay['arcs'])
        for rows in opened:rows.verify_unchanged()
        raw=array('I',(v for entry in insertions for v in (entry['way'],entry['oldArcInsertion'],entry['newArcFirst'],entry['newArcCount']))).tobytes()
        with (root/'arc-insertions.u32').open('xb') as stream:stream.write(raw)
        return {'status':'complete_conditional_source_fact_overlay_passed','operation':operation,
                'sourceCounts':{n:len(rows) for n,rows in fields.items()},'resultWays':len(outputs['ways']),'resultFlags':len(outputs['flags']),'resultPreClosureArcs':len(outputs['arcs']),
                'overlayCounts':overlay['counts'],'relationClosedNodesRetained':len(closed_nodes),'unsupportedRelationsRead':relation_count,
                'allOldSourceRowsAndArcCostsExact':True,'newNativePricedArcsIndependentlyRebuilt':checked,'maximumNewPrimitiveMs':maximum_primitive,'maximumNewMacroMs':maximum_macro,'newPreClosureCostOverflows':overflow,
                'selectedNodeFlagChanges':[{'anchor':i,'flags':v} for i,v in sorted(overlay['nodeFlags'].items())],
                'insertions':{'file':'arc-insertions.u32','groups':len(insertions),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'format':'U32LE quadruples:way index,old insertion,new first,new count'},
                'overlayBytes':writer.bytes,'factRoster':writer.roster,'sourcePbfReads':0,'sourceConstructorExecutions':0,'routingQueries':0,'providerRequests':0,'applicationDbReads':0,
                'nationalFactOverlayBuilt':operation=='run','runtimeGraphBuilt':False,'etaOrAppAccepted':False,
                'scope':'Complete streaming ways/flags/arcs overlay plus independent all-old-row and all-new-per-arc primitive/native-price audit. Source IDs/coordinates/anchors/full geometry remain unchanged authenticated typed inputs. Relation-derived node closures retained even if own tags unblock. Other old facts/turns/closures remain base inputs, not copied or implicitly discarded. Preclosure facts only, no resolved/CSR/spatial/paid-geometry/storage/runtime graph or route/ETA/physical/app/package acceptance. No PBF/constructor/provider/application DB/model/deployment operation.'}
    finally:
        if writer:writer.finish()
        for rows in reversed(opened):rows.close()
