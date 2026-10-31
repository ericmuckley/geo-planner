"""Saved complete national capacity proof; no PBF/native/ignored-part reads."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

REPORT=Path(__file__).resolve().parent
REPO=REPORT.parents[2]


def load(path):return json.loads(path.read_bytes())


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    subprocess.run([sys.executable,'-B',str(REPORT/'verify_cell_census_controls_v2.py')],check=True,stdout=subprocess.DEVNULL)
    sys.path.insert(0,str(REPO/'scripts'))
    from run_osm_cell_census_v2 import validate,check_receipt,queries,isolation
    from coarse_osm_window_cells_v1 import Cells
    plan=load(REPORT/'cell-census-plan-run-v2.json');validate(plan)
    freeze=load(REPORT/'cell-census-freeze-run-v2.json');assert sha(REPO/freeze['recipe'])==freeze['sha256']
    for name,pin in plan['inputs'].items():
        if name.startswith(('scripts/','docs/evidence/')):assert sha(REPO/name)==pin,name
    closed=load(REPORT/'cell-census-closed-run-v2.json');raw=REPORT/'cell-census-raw/run-v2'
    assert closed['closerSha256']==sha(REPO/'scripts/close_osm_cell_census_v2.py')
    assert closed['files']==len(closed['roster']) and closed['bytes']==sum(r['bytes'] for r in closed['roster'].values())
    assert {str(p.relative_to(raw)) for p in raw.rglob('*') if p.is_file()}=={name for name,r in closed['roster'].items() if not r['ignoredPart']}
    for name,pin in closed['roster'].items():
        if not pin['ignoredPart']:assert (raw/name).stat().st_size==pin['bytes'] and sha(raw/name)==pin['sha256'],name
    assert (raw/'execution-plan.json').read_bytes()==(REPORT/'cell-census-plan-run-v2.json').read_bytes()
    isolation(load(raw/'container-initial.json'),'controls')
    end=load(raw/'container-result.json');assert end['State']['ExitCode']==end['clientExitCode']==0 and not end['State']['OOMKilled']
    assert load(raw/'cleanup.json')['removed'] and load(raw/'cleanup.json')['independentInspectAbsent']
    absence=load(REPORT/'cell-census-cleanup-run-v2.json');assert absence['independentlyAbsent'] and absence['queryReturnCode']==0 and absence['containerIds']==[]
    catalog=load(REPO/plan['catalog']);assert plan['queryIDs']==queries(catalog) and len(plan['queryIDs'])==1532
    fine_bytes=sum(part['bytes'] for part in catalog['shards'])
    grid=Cells(plan['windows']);identity=None;bank_sizes=[]
    for label in ('pass-a','pass-b'):
        path=raw/label;receipt=load(path/'source-receipt.json');check_receipt(receipt,plan)
        assert receipt['visits']==1770542426 and receipt['nativeEof']
        fine=load(path/'fine-revalidation.json')
        assert (fine['nodeRowsCompared'],fine['sourceBlocksCompared'],fine['sourceShardsCompared'],fine['wholeFileVerificationPasses'])==(1606229364,392146,766,1)
        assert fine['payloadBytesRead']==3*fine_bytes and fine['readOnly']
        proof=load(path/'witness-proof.json');rows=proof['sourceRows'];assert [r[0] for r in rows]==plan['queryIDs']
        expected={node:grid.cell(x,y) for node,x,y in rows}
        ordered=list(reversed(plan['queryIDs']))+plan['queryIDs'][:2]+plan['queryIDs'][:1]
        assert proof['queries']==ordered and proof['cells']==[expected[node] for node in ordered]
        bank=path/'bank';manifest=load(bank/'index.json')
        assert manifest['format']=='immutable-window-cell-bank-v2' and manifest['windows']==plan['windows']
        assert manifest['rows']==1606229364 and manifest['blocks']==392146
        assert manifest['tableSha256']==hashlib.sha256(grid.codes).hexdigest()
        directory=(bank/'directory.bin').read_bytes();assert len(directory)==manifest['directory']['bytes']==392146*32
        assert hashlib.sha256(directory).hexdigest()==manifest['directory']['sha256']
        entries=list(struct.iter_unpack('<qQIIII',directory));position=previous=total_rows=0
        for number,part in enumerate(manifest['parts']):
            record=closed['roster'][f'{label}/bank/{number:04d}.bin']
            assert record['ignoredPart'] and record['bytes']==part['bytes'] and record['sha256']==part['sha256']
            offset=part_rows=0
            for i in range(part['blocks']):
                last,start,size,count,owner,zero=entries[position]
                assert previous<last and start==offset and owner==number and zero==0 and 0<size<=65576
                assert count==min(4096,manifest['rows']-total_rows)
                offset+=size;part_rows+=count;total_rows+=count;previous=last;position+=1
            assert offset==part['bytes']<=64*1024**2 and part_rows==part['rows'] and previous==part['last']
        assert position==392146 and total_rows==1606229364
        total=sum(p['bytes'] for p in manifest['parts'])+len(directory)+(bank/'index.json').stat().st_size
        assert total==proof['bankBytes']==proof['snapshotBytes']<=2*1024**3;bank_sizes.append(total)
        result=load(path/'result.json');assert result['status']=='passed_cell_bank_capacity_pass' and result['nationalPass']
        expected_identity={'catalogSha256':sha(bank/'index.json'),'directorySha256':sha(bank/'directory.bin'),'partSha256':[p['sha256'] for p in manifest['parts']]}
        assert result['identity']==expected_identity and (identity is None or identity==expected_identity);identity=expected_identity
    result=load(raw/'result.json')
    assert result['status']=='passed_cell_bank_capacity_census' and result['sourcePasses']==2 and result['sourceObjects']==3541084852 and result['identity']==identity
    assert result['nationalBankCapacityQualified'] and result['readOnlyFineInputRevalidatedForThisStage']
    assert not any(result[k] for k in ('oldFailedEvidenceChanged','wholeRoadCaptureQualified','sourceSuitabilityQualified','modelChanged'))
    metrics=load(raw/'metrics-end.json');assert metrics['retainedReservationBytes']==55406628967
    assert metrics['ownedLimitBytesExcludingTmp']==13044412313 and metrics['observedWorkPeaks']['conservativeAllocatedBytes']<13044412313
    assert int(metrics['latest']['cgroup']['memory.peak'])<=4294967296 and 'oom_kill 0' in metrics['latest']['cgroup']['memory.events']
    host=load(raw/'run-summary.json');assert host['status']=='passed_cell_bank_capacity_census' and host['hostSecondsIncludingBindingsAndCleanup']<14400
    assert load(raw/'host-source-binding.json')['sha256']==plan['source']['sha256']
    print(json.dumps({'nationalBankCapacityQualified':True,'fullSourcePasses':2,'sourceObjects':3541084852,'nodeRowsPerPass':1606229364,'bankBytes':bank_sizes,'identicalRebuiltBanks':True,'sourceCoordinateWitnessesPerPass':1532,'workerAbsent':True,'wholeRoadCaptureQualified':False,'modelChanged':False}))


if __name__=='__main__':main()
