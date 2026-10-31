"""Saved read-only source/index proof and preserved reporter stop; no native/source runs."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import sys

folder=Path(__file__).resolve().parent;repo=folder.parents[2];load=lambda p:json.loads(p.read_text())
def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
saved=sys.argv
try:
    sys.argv=[str(folder/'verify_qualification_v10.py')]
    with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(sys.argv[0],run_name='__main__')
finally:sys.argv=saved
sys.path.insert(0,str(repo/'scripts'))
from run_osm_country_screen_v11 import validate as validate_v11,isolation
from run_osm_country_screen_v12 import validate as validate_v12
for version,validate,files,size,code in [(11,validate_v11,87,655311,2),(12,validate_v12,86,660478,0)]:
    plan=load(folder/f'qualification-plan-v{version}.json');validate(plan);freeze=load(folder/f'qualification-freeze-v{version}.json')
    assert sha(folder/f'qualification-plan-v{version}.json')==freeze['recipeSha256']
    for name,pin in plan['inputs'].items():
        if not name.startswith('data/'):assert sha(repo/name)==pin,name
    for name,pin in freeze['newProducerFiles'].items():assert sha(repo/name)==pin
    raw=folder/f'qualification-raw/v{version}';closed=load(folder/f'qualification-closed-v{version}.json')
    assert closed['files']==len(closed['roster'])==files and closed['bytes']==sum(r['bytes'] for r in closed['roster'].values())==size
    assert {str(p.relative_to(raw)) for p in raw.rglob('*') if p.is_file()}==set(closed['roster'])
    for name,row in closed['roster'].items():assert (raw/name).stat().st_size==row['bytes'] and sha(raw/name)==row['sha256'],name
    isolation(load(raw/'controls/container-initial.json'),'controls')
    result=load(raw/'controls/container-result.json');assert result['State']['ExitCode']==result['clientExitCode']==code and not result['State']['OOMKilled']
    assert load(raw/'controls/cleanup.json')['removed'] and load(raw/'controls/cleanup.json')['independentInspectAbsent']
    assert load(folder/f'cleanup-audit-v{version}.json')['controls']['independentAbsent']
    controls=load(raw/'controls/controls.json');assert controls['tests']==38 and controls['successful'] and controls['failures']==controls['errors']==controls['skipped']==0
    assert len(plan['testIds'])==len(set(plan['testIds']))==38
    assert controls['cellCodecChargedRows']==29712 and controls['cellCodecCalls']==176
    assert controls['maskReferences']==270212 and controls['maskCalls']==36
    assert controls['sourceIndexFixtureNativeRows']==24612 and controls['sourceIndexFixtureNativeCalls']==24
    proof=load(raw/'controls/readonly-prototype-proof.json');state=proof['state']
    assert state['status']=='passed_cell_filtered_extraction_prototype' and state['independentAuditComplete']
    assert state['scanObjectVisits']==18 and state['retainedElements']==4 and state['windowOccurrences']==8
    assert proof['normalSourceEofQualifiedTiny'] and not proof['nationalStoppedIndexReused']
    assert proof['outputBytes']==1470 and proof['outputSha256']=='dd2315bf022fa0ebe4ac7db1fee38329d40fb5c87f2e236577627d73730d875c'
    output=raw/'controls/readonly-filtered-prototype/elements.jsonl'
    assert output.read_bytes()==(raw/'controls/four-pass-reference/elements.jsonl').read_bytes() and sha(output)==proof['outputSha256']
    assert not (raw/'controls/readonly-filtered-prototype/primary-index').exists() and not (raw/'controls/readonly-filtered-prototype/audit-index').exists()
    assert len(state['nativeReceipts'])==2
    for receipt in state['nativeReceipts']:
        assert receipt['nativeEof'] and receipt['visits']==9 and receipt['counts']=={'node':4,'way':3,'relation':2}
        assert receipt['semanticSha256']=='04630ed15b3eb0925917fb1d4dcabb51991d3cfe65eee84bc5a76b7652b9ed81'
    fine=raw/'controls'/proof['inputRelativeRoot'];observed={p.name:sha(p) for p in fine.iterdir()}
    assert observed==proof['inputBeforeSha256']==proof['inputAfterSha256']
    assert observed=={'00000000.bin':'de4453dfea958f65f96093962dcb514cc20e45ceb7a39634c36d9dd1f324072a',
                      'index.json':'2ad713001316ab85a9ade0a443f68b62d493c463cb87cd5f4ffa3f74b8c15725',
                      'directory.bin':'2187cc80fb12567692531a7588986cb593e9944b7b5cf3e301352b3cd0e473f3'}
    assert proof['sourceIndexViews']==[{'nodeRowsCompared':4,'sourceBlocksCompared':1,'sourceShardsCompared':1,
        'wholeFileVerificationPasses':1,'payloadBytesRead':681,'catalogBytesPerRead':458,'readOnly':True,'wholeSourceEofStillRequiredFromCaller':True}]*2
    summary=load(raw/'run-summary.json');assert summary['phaseClientExitCodes']=={'controls':code} and summary['wholeSourceOrSavedPbfReads']==summary['networkRequests']==0
    if version==11:
        assert summary['status']=='stopped' and load(raw/'controls/worker-failure.json')['errorType']=='TypeError'
        assert load(raw/'controls/worker-failure.json')['error']=="unsupported operand type(s) for +: 'int' and 'list'"
    else:
        assert summary['status']=='country_screen_synthetic_qualified'
        assert type(load(raw/'controls/result.json')['encodingNativeViews']) is int
        metrics=load(raw/'controls/metrics-end.json');assert metrics['memory.max']=='4294967296' and metrics['memory.swap.max']=='0'
        assert int(metrics['memory.peak'])==248520704 and 'oom_kill 0' in metrics['memory.events']
print(json.dumps({'readOnlyFineSourceRevalidationTinyQualified':True,'linuxTests':38,'skips':0,'exactIndependentOutput':True,
                  'inputBytesPreserved':True,'reporterFailurePreserved':True,'workersAbsent':True,
                  'nationalSourceOrStoppedIndexRead':False,'nationalCapacityOrCaptureQualified':False},indent=2))
