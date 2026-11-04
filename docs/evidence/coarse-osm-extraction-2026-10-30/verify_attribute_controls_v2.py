"""Saved Linux facts-only controls; no network, native helper or PBF decode."""
from decimal import Decimal
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import sys

folder=Path(__file__).resolve().parent;repo=folder.parents[2];load=lambda p:json.loads(p.read_bytes())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
saved=sys.argv
try:
    sys.argv=[str(folder/'verify_disk_capture_run_v1.py')]
    with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(sys.argv[0],run_name='__main__')
finally:sys.argv=saved
sys.path.insert(0,str(repo/'scripts'))
from run_osm_attribute_controls_v1 import validate,isolation
failure=load(folder/'attribute-verifier-stop-v1.json');assert sha(folder/'verify_attribute_controls_v1.py')==failure['verifierSha256'] and failure['status']=='verifier_assertion_failed'
plan=load(folder/'attribute-controls-plan-v1.json');validate(plan);freeze=load(folder/'attribute-controls-freeze-v1.json')
assert sha(folder/'attribute-controls-plan-v1.json')==freeze['recipeSha256']
for name,pin in plan['inputs'].items():
    if not name.startswith('data/'):assert sha(repo/name)==pin
for name,pin in freeze['newProducerFiles'].items():assert sha(repo/name)==pin
assert sha(folder/'attribute-host-controls-v1.json')==plan['hostControlsReceiptSha256']
host=load(folder/'attribute-host-controls-v1.json');assert host['tests']==15 and host['successful'] and not host['actualLinux']
closed=load(folder/'attribute-controls-closed-v1.json');raw=folder/'attribute-controls-raw/v1'
assert closed['files']==len(closed['roster'])==12 and closed['bytes']==sum(r['bytes'] for r in closed['roster'].values())==13163
for name,row in closed['roster'].items():assert (raw/name).stat().st_size==row['bytes'] and sha(raw/name)==row['sha256']
isolation(load(raw/'container-initial.json'));state=load(raw/'container-result.json');assert state['State']['ExitCode']==state['clientExitCode']==0 and not state['State']['OOMKilled']
assert load(raw/'cleanup.json')['removed'] and load(raw/'cleanup.json')['independentInspectAbsent'] and load(folder/'attribute-controls-cleanup-v1.json')['independentlyAbsent']
controls=load(raw/'controls.json');assert controls=={'tests':11,'successful':True,'failures':0,'errors':0,'skips':0}
metrics=load(raw/'metrics.json');assert metrics['memory.max']=='536870912' and metrics['memory.swap.max']=='0' and metrics['memory.peak']=='48295936' and 'oom_kill 0' in metrics['memory.events']
result=load(raw/'result.json');assert result['status']=='passed_linux_attribute_facts_controls' and not result['sourceBoundaryOrUsableLimitQualified'] and not result['modelChanged']
fixture=repo/next(p for p,target in plan['mounts'].items() if target=='/inputs/tiny.jsonl');assert sha(fixture)==result['tinyInputSha256']=='dd2315bf022fa0ebe4ac7db1fee38329d40fb5c87f2e236577627d73730d875c'
rows=[json.loads(line) for line in fixture.read_bytes().splitlines()];nodes={r['element']['id']:r for r in rows if r['element']['type']=='node'};way=next(r for r in rows if r['element']['type']=='way')
facts=load(raw/'facts.json');assert len(facts)==1 and sha(raw/'facts.json')==result['factsSha256']
f=facts[0];assert f['sourceRecord']==way and f['coordinates']==[[nodes[n]['element']['lon'],nodes[n]['element']['lat']] for n in way['element']['nodes']]
assert f['orderedNodeElementSha256']==[nodes[n]['elementSha256'] for n in way['element']['nodes']]
assert f['speed']['kmh']==float(Decimal('55')*Decimal('1.609344')) and f['speed']['raw']=='55 mph' and f['speed']['sourceUnit']=='mph' and not f['speed']['usableForTiming']
assert f['speedScopeTags']=={'maxspeed:conditional':'35 @ wet'} and f['accessTags']=={'access':'private'} and f['barrierNodeIds']==[1]
assert not f['plainNumericWithoutSpeedScopes'] and not f['usableForTiming'] and f['carPermission']=='unreviewed'
summary=load(raw/'run-summary.json');assert summary['exitCode']==summary['networkRequests']==summary['nationalOrPbfReads']==0
print(json.dumps({'linuxFactsTests':11,'skips':0,'tinyRawGeometryUnitsAndScopesPreserved':True,'permissionsRemainUnreviewed':True,'usableForTiming':False,'workerAbsent':True,'nationalOrPbfRead':False,'modelChanged':False},indent=2))
