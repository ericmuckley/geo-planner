"""Saved disk-selected qualification proof; optional archive checks never decode PBF."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

folder=Path(__file__).resolve().parent;repo=folder.parents[2]
sys.path.insert(0,str(repo/'scripts'))
from coarse_osm_country_wire_v4 import reference_seal
from coarse_osm_records import canonical
from run_osm_country_screen_v14 import validate as validate14,isolation as isolation14
from run_osm_country_screen_v15 import validate as validate15,isolation as isolation15

def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
load=lambda p:json.loads(p.read_bytes())
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--local-assets',action='store_true');args=parser.parse_args()
for version,validate,isolation in [('v14',validate14,isolation14),('v15',validate15,isolation15)]:
    plan=load(folder/('qualification-plan-'+version+'.json'));validate(plan)
    freeze=load(folder/('qualification-freeze-'+version+'.json'))
    assert sha(folder/('qualification-plan-'+version+'.json'))==freeze['recipeSha256']
    for name,pin in plan['inputs'].items():
        if not name.startswith('data/'):assert sha(repo/name)==pin,name
    for name,pin in freeze['newProducerFiles'].items():assert sha(repo/name)==pin,name
    closed=load(folder/('qualification-closed-'+version+'.json'));raw=folder/('qualification-raw/'+version)
    assert closed['files']==len(closed['roster']) and closed['bytes']==sum(row['bytes'] for row in closed['roster'].values())
    for name,row in closed['roster'].items():
        p=(repo/closed['root'] if row['ignoredLargeAsset'] else raw)/name
        if row['ignoredLargeAsset'] and not args.local_assets:continue
        assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],str(p)
    assert closed['closerSha256']==sha(repo/'scripts/close_osm_selected_qualification_v1.py')
    for phase in plan['phases']:
        isolation(load(raw/phase/'container-initial.json'),phase)
        result=load(raw/phase/'container-result.json');assert not result['State']['OOMKilled'] and result['State']['ExitCode']==result['clientExitCode']
        cleanup=load(raw/phase/'cleanup.json');assert cleanup['removed'] and cleanup['independentInspectAbsent']
        assert load(folder/('cleanup-audit-'+version+'.json'))[phase]['independentAbsent']
        metrics=load(raw/phase/'metrics-end.json');assert metrics['memory.swap.max']=='0' and 'oom_kill 0' in metrics['memory.events']
    controls=load(raw/'controls/controls.json');assert controls=={'tests':71,'successful':True,'errors':0,'failures':0,'skipped':0}
    summary=load(raw/'run-summary.json')
    if version=='v14':
        assert summary['status']=='stopped' and summary['phaseClientExitCodes']=={'build':0,'controls':2}
        assert load(raw/'controls/worker-failure.json')['error']=='Independent tiny reference failed'
        assert load(raw/'controls/four-pass-reference/state.json')['error']=='SQLite index arithmetic'
    else:assert summary['status']=='country_screen_synthetic_qualified' and summary['phaseClientExitCodes']=={'controls':0}
    assert summary['networkRequests']==summary['wholeSourceOrSavedPbfReads']==0
old=(repo/'scripts/coarse_osm_country_screen_v6.cpp').read_text();new=(repo/'scripts/coarse_osm_country_screen_v7.cpp').read_text()
assert new==old.replace('count<=250000','count<=2000000').replace('return 0x50000','return 0x60000')
raw=folder/'qualification-raw/v15/controls';tiny=load(raw/'tiny-proof.json');state=tiny['state']
assert state['status']=='passed_disk_selected_extraction_prototype' and state['independentAuditComplete'] and state['scanObjectVisits']==18
assert (state['retainedElements'],state['windowOccurrences'])==(4,8) and tiny['outputBytes']==1470
assert tiny['inputBeforeSha256']==tiny['inputAfterSha256'] and all(v['wholeFileVerificationPasses']==1 and v['nodeRowsCompared']==4 for v in tiny['sourceIndexViews'])
output=raw/'disk-extract/elements.jsonl';assert output.read_bytes()==(raw/'four-pass-reference/elements.jsonl').read_bytes()
assert sha(output)==tiny['outputSha256']=='dd2315bf022fa0ebe4ac7db1fee38329d40fb5c87f2e236577627d73730d875c'
for label in ('primary','audit'):
    p=raw/('disk-extract/'+label+'-selected.sqlite');report=state['selectedStores'][0 if label=='primary' else 1]
    assert report['databaseSha256']==sha(p) and report['sealed'] and report['integrityOk'] and report['closed']
    db=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)
    try:
        assert db.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
        assert db.execute('SELECT count(*) FROM selected_keys').fetchone()[0]==report['unique']==4
        assert db.execute('SELECT count(*) FROM memberships').fetchone()[0]==report['occurrences']==8
        assert db.execute('SELECT count(*) FROM objects').fetchone()[0]==report['objects']==4
    finally:db.close()
proof=load(raw/'native-boundary-proof.json');r=proof['nativeReceipt']
assert proof['selectedNodes']==r['selectedNodeProjections']==r['witnessRows']==r['nodes']==r['acceptedNodes']==r['visits']==2000000
assert r['nativeEof'] and r['counts']=={'node':2000000} and r['ways']==r['relations']==0
assert proof['firstId']==2**63-2000000 and proof['lastId']==r['maxNodeId']==2**63-1 and proof['allSelectedFieldsCompared']
assert r['sourceIdentity']['sourceSha256']==proof['source']['sha256'] and r['postSourceHashBytes']==proof['source']['bytes']
archive_verified=False
if args.local_assets:
    # Independent formula from the frozen design; no producer helper or native code.
    archive=repo/'data/coarse-quality/us-osm-country-controls-v15/controls/two-million-fields.jsonl.gz'
    assert archive.stat().st_size==proof['archiveBytes'] and sha(archive)==proof['archiveSha256']
    fields_hash=hashlib.sha256();counts=[0,0]
    def rows():
        with gzip.open(archive,'rb') as stream:
            for ordinal in range(2000000):
                line=stream.readline(257);assert 0<len(line)<=256 and line.endswith(b'\n')
                row=json.loads(line);expected={'type':'node','id':2**63-2000000+ordinal,'version':1,'timestamp':'2026-10-25T21:21:21Z','visible':True,'tags':{},'lon':(ordinal%20001-10000)/10000000,'lat':(ordinal%10001-5000)/10000000}
                assert row==expected and line==canonical(expected)+b'\n'
                fields_hash.update(line);counts[0]+=1;counts[1]+=len(line);yield row
            assert not stream.read(1)
    assert reference_seal(rows())==r['semanticSha256'] and counts==[2000000,proof['fullFieldBytes']] and fields_hash.hexdigest()==proof['fullFieldSha256']
    archive_verified=True
print(json.dumps({'linuxTests':71,'skips':0,'diskStoreAndReferenceOutputExact':True,'nativeSelectedNodeBoundary':2000000,'savedFieldsIndependentlyVerified':archive_verified,'workersAbsent':True,'nationalSourceRead':False,'nationalCaptureQualified':False},indent=2))
