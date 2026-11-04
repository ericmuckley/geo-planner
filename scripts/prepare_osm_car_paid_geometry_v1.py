"""Freeze one unused paid-geometry stage against closed parent artifacts."""
import argparse
import json
from pathlib import Path

from coarse_osm_build_v1 import sha
from coarse_osm_python_bindings_v1 import dependencies
from coarse_timing_input import require
from run_osm_car_paid_geometry_v1 import CAPS,FLAGS,OUTPUTS,POLICY,TESTS,roots,validate

REPORT=Path('docs/evidence/coarse-osm-car-capacity-2026-11-01')
CPP=['coarse_osm_car_paid_geometry_v1.cpp','coarse_osm_car_geometry_native_v1.cpp','coarse_osm_car_packed_native_v1.cpp','coarse_osm_car_cost_math_v1.hpp']


def prepare(stage):
    repo=Path(__file__).resolve().parents[1]
    load=lambda name:json.loads((repo/REPORT/name).read_bytes())
    base=load('geometry-native-plan-build-v1.json')
    plan={key:base[key] for key in ('rootfs','headers','assetProof','site','runtime','image','network','imagePull')}
    plan.update(date='2026-11-02',phase='car_paid_geometry_v1',stage=stage,caps=CAPS,flags=FLAGS,policy=POLICY,tests=TESTS,output=OUTPUTS[stage])
    require(not (repo/OUTPUTS[stage]).exists(),'Unused paid-geometry stage required')
    mounts={name:dest for name,dest in base['mounts'].items() if name.startswith('data/coarse-quality/us-osm-tools-v3/')}
    for name in dependencies(repo,roots(stage)):
        mounts[name]=('/reference/' if name.startswith('routing/') else '/code/')+Path(name).name
    if stage=='build':
        for name in CPP:mounts['scripts/'+name]='/code/'+name
    bindings={}
    def parent(record_name):
        record=load(record_name);bindings[str(REPORT/record_name)]=sha(repo/REPORT/record_name)
        return record
    def closed_mount(record,name,destination):
        path=Path(record['root'])/name;pin=record['roster'][name]['sha256']
        require((repo/path).stat().st_size==record['roster'][name]['bytes'] and sha(repo/path)==pin,'Closed parent drift: '+str(path))
        mounts[str(path)]=destination
    if stage!='build' and not stage.endswith('audit'):
        record=parent('paid-geometry-closed-build-v1.json');name='car-paid-geometry.so'
        path=str(Path(record['root'])/name)
        require(sha(repo/path)==record['roster'][name]['sha256'],'Closed paid binary drift')
        plan['artifact']={'path':path,'sha256':record['roster'][name]['sha256']}
    if stage in ('captured','country'):
        record=parent('paid-geometry-closed-controls-v1.json')
        plan['admission']=json.loads((repo/record['root']/'controls.json').read_bytes())
        require(sha(repo/record['root']/'controls.json')==record['roster']['controls.json']['sha256'],'Closed controls drift')
    if stage.startswith('country'):
        record=parent('paid-geometry-closed-captured-audit-v1.json')
        plan['capturedAdmission']=json.loads((repo/record['root']/'result.json').read_bytes())
        require(sha(repo/record['root']/'result.json')==record['roster']['result.json']['sha256'],'Closed captured audit drift')
    if stage not in ('build','controls'):
        country=stage.startswith('country')
        plan['expected']=[42993567,5731903,4227238,48163649,9837326,9620680] if country else [143560,46881,28995,177956,78811,75137]
        facts=parent('country-cost-closed-run-v1.json' if country else 'graph-capture-closed-run-v5.json')
        for name in facts['roster']:
            if name.startswith('cost-facts/') and Path(name).name.split('-')[0] in ('xy','geometry','anchors','ways','arcs','closures'):
                closed_mount(facts,name,'/inputs/facts/'+Path(name).name)
        packed=parent('packed-country-closed-run-v1.json' if country else 'packed-capture-closed-run-v1.json')
        closed_mount(packed,'routing/offsets.u24','/inputs/offsets.u24')
        spatial=parent('spatial-country-closed-run-v1.json' if country else 'spatial-native-closed-equivalence-v2.json')
        closed_mount(spatial,'routing/old-arc-to-new.u32','/inputs/arc-map.u32')
        if stage.endswith('audit'):
            produced=parent('paid-geometry-closed-'+stage.removesuffix('-audit')+'-v1.json')
            for name in produced['roster']:
                if name.startswith('geometry/'):closed_mount(produced,name,'/inputs/geometry/'+Path(name).name)
    allocations=dict(base['newClosedAllocations'])
    for path in (repo/REPORT).glob('*closed*.json'):
        record=json.loads(path.read_bytes());root=record.get('root');usage=record.get('usage',{})
        if root and root.startswith('data/coarse-quality/us-osm-car-') and 'conservativeAllocatedBytes' in usage:
            allocations[root]=max(allocations.get(root,0),usage['conservativeAllocatedBytes'])
    producers=['scripts/'+name for name in CPP]+['scripts/'+name for name in (
        'coarse_osm_car_paid_geometry_v1.py','coarse_osm_car_paid_geometry_v1_test.py',
        'coarse_osm_car_paid_geometry_audit_v1.py','coarse_osm_car_paid_geometry_audit_v1_test.py',
        'coarse_osm_paid_projection_v1.py','run_osm_car_paid_geometry_v1.py',
        'prepare_osm_car_paid_geometry_v1.py','close_osm_car_paid_geometry_v1.py')]
    plan.update(newClosedAllocations=allocations,parentRecordBindings=bindings,mounts=mounts,
                producerBindings={name:sha(repo/name) for name in producers},
                inputs={name:sha(repo/name) for name in mounts},
                numericalAuditAllowance={'meters':0.001,'milliseconds':1},
                scope='Fixed 100m geometry/10000ms time-progress error at discarded source vertices; source costs and core graph unchanged. No snap, ETA, app or model admission.')
    validate(plan)
    recipe=repo/REPORT/('paid-geometry-plan-'+stage+'-v1.json')
    with recipe.open('x') as stream:json.dump(plan,stream,indent=2);stream.write('\n')
    print('PYTHONPATH=scripts:routing python3 -B scripts/run_osm_car_paid_geometry_v1.py '+str(recipe.relative_to(repo))+' '+sha(recipe))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=list(OUTPUTS));prepare(parser.parse_args().stage)
