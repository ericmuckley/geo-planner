"""Read-only failure/diagnostic proof; no Docker, native or national source reads."""
import hashlib
import json
from pathlib import Path
import sys

f=Path(__file__).resolve().parent;r=f.parents[2]
load=lambda p:json.loads(p.read_text())
def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def check_files(raw,roster):
    for name,row in roster.items():
        p=raw/name
        assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],name

sys.path.insert(0,str(r/'scripts'))
from coarse_osm_records import canonical
from run_osm_country_screen_v1 import isolation
closed=load(f/'screen-stop-closed.json');raw=f/'screen-stop-raw'
check_files(raw,{row['path']:row for row in closed['files'] if row['mirrored']})
assert len(closed['files'])==closed['fileCount']==34
assert sum(row['bytes'] for row in closed['files'])==closed['bytes']==132557861
assert sum(not row['mirrored'] for row in closed['files'])==7 and not closed['partialPayloadsTrusted']
freeze=load(f/'screen-freeze.json')
assert sha(f/'screen-plan.json')==freeze['recipeSha256']
assert (raw/'execution-plan.json').read_bytes()==(f/'screen-plan.json').read_bytes()
isolation(load(raw/'container-initial.json'),'controls')
part=load(raw/'screen/partial-result.json');receipt=part['lastNativeReceipt']
assert part['status']=='stopped' and part['error']=='Native screen stopped: member_copy_identity'
assert not part['eof'] and not part['indexesTrusted'] and part['completedPasses']==0
assert receipt['acceptedNodes']==1606229364 and receipt['acceptedWays']==162688797
assert receipt['relations']==56976 and receipt['acceptedRelations']==56975 and receipt['maxRelationId']==1205149
assert receipt['visits']==sum(receipt['counts'].values())==part['objectReceipts']==1768975137
assert not receipt['nativeEof'] and receipt['metadata']=={} and receipt['error']=='member_copy_identity'
binding=load(raw/'host-source-binding.json');source=load(f/'screen-plan.json')['source']
assert binding['bytesRead']==source['bytes'] and binding['sha256']==source['sha256'] and binding['md5']==source['md5']
state=load(raw/'container-result.json');assert state['State']['ExitCode']==state['clientExitCode']==2 and not state['State']['OOMKilled']
assert load(raw/'cleanup.json')['removed'] and load(raw/'cleanup.json')['independentInspectAbsent']
metrics=load(raw/'metrics-end.json')['latest']['cgroup']
assert metrics['memory.peak']=='4294967296' and 'oom 0\n' in metrics['memory.events'] and 'oom_kill 0\n' in metrics['memory.events']
assert load(raw/'run-summary.json')['fullImportAdmitted'] is False
for version,record in load(f/'member-diagnostic-closed.json').items():
    raw=f/'member-diagnostic-raw'/version;check_files(raw,record['roster'])
    suffix='-v2' if version=='v2' else ''
    freeze=load(f/f'member-diagnostic-freeze{suffix}.json');plan=f/f'member-diagnostic-plan{suffix}.json'
    assert sha(plan)==freeze['sha256'] and (raw/'execution-plan.json').read_bytes()==plan.read_bytes()
    for name,pin in load(plan)['inputs'].items():assert sha(r/name)==pin
    summary=load(raw/'run-summary.json');assert not summary['wholeSourceQualified'] and summary['networkRequests']==0
    if version=='v1':
        assert summary['status']=='stopped' and 'Invalid container name' in load(raw/'driver-failure.json')['error']
        assert not (raw/'container-initial.json').exists()
        continue
    isolation(load(raw/'container-initial.json'),'controls')
    state=load(raw/'container-result.json');assert state['State']['ExitCode']==state['clientExitCode']==0 and not state['State']['OOMKilled']
    result=load(raw/'result.json');stats=load(raw/'object-stats.json');census=load(raw/'relation-size-census.json')
    assert summary['status']=='captured' and result['relationId']==1205151 and result['afterRelationId']==1205149
    assert not result['normalWholeSourceEof'] and not result['qualifiedForExtraction']
    assert census['relationCount']==1624265 and census['invalidMemberIdentitiesOrTypes']==0
    assert census['maxOldIncrementalCopyCharge']==3664144 and census['maxCanonicalBytes']==1266503
    fixtures=load(f/'member-diagnostic-regression.json')['objects']
    assert fixtures==[load(raw/'relation.json'),load(raw/'largest-copy-relation.json')]
    for row,expected_size,expected_charge in zip(fixtures,[680871,1266503],[1966841,3664144]):
        charge=256+sum(len(k.encode())+len(v.encode())+64 for k,v in row['tags'].items())+sum(128+len(m['role'].encode()) for m in row['members'])
        assert len(canonical(row))==expected_size and charge==expected_charge
        assert all(m['type'] in ('node','way','relation') and 0<m['ref']<2**63 for m in row['members'])
    assert stats['canonicalBytes']==680871 and stats['oldIncrementalCopyCharge']==1966841 and stats['invalidMemberIdentitiesOrTypes']==0
assert all(row['independentAbsent'] and row['returncode']==1 for row in load(f/'screen-diagnostic-cleanup-audit.json'))
print(json.dumps({'preservedNationalStopVerified':True,'diagnosticAndExactCapturedObjectSizesVerified':True,'sourceWideEofQualified':False,'workersAbsent':True,'nationalSourceReadByProof':False}))
