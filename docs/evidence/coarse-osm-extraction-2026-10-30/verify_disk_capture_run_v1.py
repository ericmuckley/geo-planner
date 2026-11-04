"""Verify a closed national attempt; optional reads inspect new derived output only."""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import sqlite3
import sys

folder=Path(__file__).resolve().parent;repo=folder.parents[2];load=lambda p:json.loads(p.read_bytes())
def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--local-assets',action='store_true');args=parser.parse_args()
saved=sys.argv
try:
    sys.argv=[str(folder/'verify_disk_capture_controls_v1.py')]
    with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(sys.argv[0],run_name='__main__')
finally:sys.argv=saved
sys.path.insert(0,str(repo/'scripts'))
from coarse_osm_records import canonical,strict_json
from coarse_osm_disk_resources_v1 import OWNED_LIMIT,RETAINED,TMP,TOTAL,WRITABLE_WORST_CASE
from run_osm_disk_capture_v1 import validate,isolation,check_receipt,output_ledger
plan=load(folder/'disk-capture-plan-run-v1.json');validate(plan)
freeze=load(folder/'disk-capture-freeze-run-v1.json');assert sha(folder/'disk-capture-plan-run-v1.json')==freeze['sha256']
for name,pin in plan['inputs'].items():
    if not name.startswith('data/'):assert sha(repo/name)==pin,name
closed=load(folder/'disk-capture-closed-run-v1.json');raw=folder/'disk-capture-raw/run-v1';root=repo/closed['root']
assert closed['files']==len(closed['roster']) and closed['bytes']==sum(row['bytes'] for row in closed['roster'].values())
assert closed['closerSha256']==sha(repo/'scripts/close_osm_disk_capture_v2.py')
for name,row in closed['roster'].items():
    assert 0<=row['bytes']<=2*1024**3,name
    if row['ignoredLargeAsset'] and not args.local_assets:continue
    path=(root if row['ignoredLargeAsset'] else raw)/name
    assert path.stat().st_size==row['bytes'] and sha(path)==row['sha256'],name
isolation(load(raw/'container-initial.json'))
result=load(raw/'container-result.json');assert result['State']['ExitCode']==result['clientExitCode']
cleanup=load(raw/'cleanup.json');assert cleanup['removed'] and cleanup['independentInspectAbsent']
assert load(folder/'disk-capture-cleanup-run-v1.json')['independentlyAbsent']
assert closed['usage']['conservativeAllocatedBytes']<=OWNED_LIMIT and RETAINED+OWNED_LIMIT+TMP==TOTAL==64*1024**3 and WRITABLE_WORST_CASE<OWNED_LIMIT
binding=load(raw/'host-source-binding.json');assert binding['bytesRead']==plan['source']['bytes'] and binding['sha256']==plan['source']['sha256'] and binding['md5']==plan['source']['md5']
summary=load(raw/'run-summary.json');assert summary['networkRequests']==0 and not summary['modelChanged']
state=load(raw/'extraction-result.json') if (raw/'extraction-result.json').exists() else load(raw/'extract/state.json')
passed=summary['status']=='passed_full_road_capture';assert summary['status'] in ('passed_full_road_capture','stopped')
# Completed bank files remain exact even when a later phase stops. Do not
# promote a stopped attempt because its earlier node/bank pass was complete.
for label in ('all-highway-primary-selection-cells','all-highway-independent-materialization-cells'):
    prefix='extract/'+label+'/'
    actual={name.removeprefix(prefix):{'bytes':row['bytes'],'sha256':row['sha256']} for name,row in closed['roster'].items() if name.startswith(prefix)}
    assert all(name in plan['expectedBank'] and row==plan['expectedBank'][name] for name,row in actual.items())
    if passed:assert actual==plan['expectedBank'] and sum(r['bytes'] for r in actual.values())==938364831
independent_output=False
if passed:
    assert result['State']['ExitCode']==0 and not result['State']['OOMKilled']
    assert state['status']=='passed_disk_selected_extraction_prototype' and state['independentAuditComplete']
    assert len(state['nativeReceipts'])==2 and state['scanObjectVisits']==3541084852
    for receipt in state['nativeReceipts']:check_receipt(receipt,plan)
    views=load(raw/'fine-revalidation.json');assert len(views)==2 and all(v['nodeRowsCompared']==1606229364 and v['wholeFileVerificationPasses']==1 for v in views)
    assert len(state['selectedStores'])==2 and all(s['closed'] and s['sealed'] and s['integrityOk'] for s in state['selectedStores'])
    assert state['extractBytes']==closed['roster']['extract/elements.jsonl']['bytes'] and state['outputSha256']==closed['roster']['extract/elements.jsonl']['sha256']
    ledger=load(raw/'window-ledger.json');assert ledger['uniqueElements']==state['retainedElements'] and ledger['windowOccurrences']==state['windowOccurrences'] and len(ledger['windows'])==21
    assert all(w['status']=='complete_from_acquired_file_only' for w in ledger['windows'])
    worker=load(raw/'result.json');assert worker['rawAcquiredFileCaptureComplete'] and worker['nationalRawAcquiredFileCaptureComplete'] and worker['sourceObjects']==3541084852 and worker['sourcePasses']==2
    assert not any(worker[name] for name in ('sourceFeasibilityQualified','publisherBoundaryQualified','sourceAdapterImplemented','modelChanged'))
    metrics=load(raw/'metrics-end.json');assert metrics['latest']['cgroup']['memory.swap.max']=='0' and 'oom_kill 0' in metrics['latest']['cgroup']['memory.events']
    for report,label in zip(state['selectedStores'],['primary','audit']):assert report['databaseSha256']==closed['roster']['extract/'+label+'-selected.sqlite']['sha256']
    if args.local_assets:
        # Compare the independent full raw DBs, their selected typed keys and
        # ordered memberships, then reconstruct every output field/geometry seal.
        def connect(label):return sqlite3.connect((root/('extract/'+label+'-selected.sqlite')).as_uri()+'?mode=ro',uri=True)
        primary=connect('primary');audit=connect('audit')
        try:
            for db,report in zip([primary,audit],state['selectedStores']):
                assert db.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
                assert db.execute('SELECT count(*) FROM selected_keys').fetchone()[0]==report['unique']==report['objects']==state['retainedElements']
                assert db.execute('SELECT count(*) FROM memberships').fetchone()[0]==report['occurrences']==state['windowOccurrences']
                assert db.execute('SELECT coalesce(sum(length(raw)),0) FROM objects').fetchone()[0]==report['rawBytes']
            sentinel=object()
            from itertools import zip_longest
            for sql in ['SELECT kind,id FROM selected_keys ORDER BY kind,id','SELECT kind,id,w FROM memberships ORDER BY kind,id,w','SELECT kind,id,raw FROM objects ORDER BY kind,id']:
                for left,right in zip_longest(primary.execute(sql),audit.execute(sql),fillvalue=sentinel):assert left==right
            proposal=strict_json((repo/plan['proposal']).read_bytes());windows=[w['id'] for w in proposal['windows']];snapshot=plan['source']['publisherState']
            with (root/'extract/elements.jsonl').open('rb') as stream:
                rows=byte_count=occurrences=0
                for kind,identity,body in audit.execute('SELECT kind,id,raw FROM objects ORDER BY kind,id'):
                    element=strict_json(body);assert (element['type'],element['id'])==(kind,identity) and canonical(element)==body
                    membership=[windows[w] for w, in audit.execute('SELECT w FROM memberships WHERE kind=? AND id=? ORDER BY w',(kind,identity))]
                    assert membership
                    expected={'publisherStateUtc':snapshot,'element':element,'elementSha256':hashlib.sha256(body).hexdigest(),'windowIds':membership}
                    if kind=='way':
                        dependencies=[]
                        for node in element['nodes']:
                            raw_node=audit.execute("SELECT raw FROM objects WHERE kind='node' AND id=?",(node,)).fetchone();assert raw_node is not None
                            dependencies.append(strict_json(raw_node[0]))
                        expected['geometryDependencySha256']=hashlib.sha256(canonical([snapshot,dependencies])).hexdigest()
                        assert primary.execute('SELECT digest FROM way_hashes WHERE id=?',(identity,)).fetchone()[0]==expected['elementSha256']
                    line=stream.readline(8388609);assert len(line)<=8388608 and line==canonical(expected)+b'\n'
                    rows+=1;byte_count+=len(line);occurrences+=len(membership)
                assert not stream.read(1) and rows==state['retainedElements'] and byte_count==state['extractBytes'] and occurrences==state['windowOccurrences']
            assert output_ledger(root/'extract/elements.jsonl',proposal['windows'])==ledger
            independent_output=True
        finally:primary.close();audit.close()
else:
    assert (raw/'driver-failure.json').exists() or (raw/'worker-failure.json').exists()
    if (raw/'result.json').exists():assert not load(raw/'result.json').get('nationalRawAcquiredFileCaptureComplete',False)
print(json.dumps({'nationalAcquiredFileCaptureQualified':passed,'independentSavedOutputVerified':independent_output,'sourceAndPublisherAdequacyQualified':False,'workerAbsent':True,'closedFiles':closed['files'],'closedBytes':closed['bytes'],'modelChanged':False,'nativeExecuted':False,'nationalSourcePbfRead':False},indent=2))
