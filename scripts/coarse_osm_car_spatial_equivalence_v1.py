"""Full captured spatial permutation proof and mapped original paid-point cases."""
from array import array
import hashlib
import json
from pathlib import Path
import time

from coarse_osm_car_spatial_audit_v1 import audit
from coarse_osm_car_spatial_reference_v1 import permute


def run(native,repo,check):
    began=time.monotonic();source=repo/'data/coarse-quality/us-osm-car-packed-capture-v1';output=Path('/work/routing');output.mkdir()
    artifacts=json.loads((source/'artifacts.json').read_bytes())
    fields={Path(name).name:(source/name).read_bytes() for name in artifacts}
    assert sum(map(len,fields.values()))==1027089
    result=native.encode(source/'routing',output);check()
    expected=permute(fields)
    for name,value in expected.items():assert (output/name).read_bytes()==value,name
    independent=audit(source/'routing',output);check()
    with Path('/work/independent-audit.json').open('x') as stream:json.dump(independent,stream,indent=2);stream.write('\n')
    order=array('I');order.frombytes(expected['new-vertex-to-old.u32']);vertex_map={old:new for new,old in enumerate(order)}
    arc_map=array('I');arc_map.frombytes(expected['old-arc-to-new.u32'])
    def point(value):
        if 'vertex' in value:return {'vertex':vertex_map[value['vertex']]}
        return {'partials':[{'arc':arc_map[p['arc']],'ticks':p['ticks']} for p in value['partials']]}
    fixtures=json.loads((source/'query-fixtures.json').read_bytes())
    for fixture in fixtures:fixture['source']=point(fixture['source']);fixture['target']=point(fixture['target'])
    with Path('/work/query-fixtures.json').open('x') as stream:json.dump(fixtures,stream,indent=2);stream.write('\n')
    def roster(names):
        return {'routing/'+name:{'bytes':(output/name).stat().st_size,'sha256':hashlib.sha256((output/name).read_bytes()).hexdigest()} for name in names}
    with Path('/work/artifacts.json').open('x') as stream:json.dump(roster(fields),stream,indent=2);stream.write('\n')
    with Path('/work/spatial-artifacts.json').open('x') as stream:json.dump(roster(['cell-keys.u24','cell-offsets.u24']),stream,indent=2);stream.write('\n')
    result.update(status='captured_spatial_wire_matches_independent_oracle_and_full_audit',filesIndependentlyCompared=len(expected),
                  originalDirectionalFixturesMapped=len(fixtures),secondsIncludingNativeAndIndependentChecks=time.monotonic()-began,
                  sourcePbfReads=0,sourceConstructorExecutions=0,appOrEtaQualified=False,modelChanged=False)
    return result
