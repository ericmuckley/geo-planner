"""Saved capacity-controller proof, tiny data only; no native/Docker/national reads."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import struct
import sys
import xml.etree.ElementTree as ET

folder=Path(__file__).resolve().parent;repo=folder.parents[2];load=lambda p:json.loads(p.read_text())
def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
saved=sys.argv
try:
    sys.argv=[str(folder/'verify_qualification_v12.py')]
    with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(sys.argv[0],run_name='__main__')
finally:sys.argv=saved
sys.path.insert(0,str(repo/'scripts'))
from run_osm_cell_census_v1 import validate,check_receipt,isolation
from coarse_osm_cell_resources_v1 import OWNED,RETAINED,TMP,TOTAL
plan=load(folder/'cell-census-plan-controls-v1.json');validate(plan)
freeze=load(folder/'cell-census-freeze-controls-v1.json');assert sha(folder/'cell-census-plan-controls-v1.json')==freeze['recipeSha256']
for name,pin in plan['inputs'].items():
    if not name.startswith('data/'):assert sha(repo/name)==pin,name
for name,pin in freeze['newProducerFiles'].items():assert sha(repo/name)==pin
raw=folder/'cell-census-raw/controls-v1';closed=load(folder/'cell-census-closed-controls-v1.json')
assert closed['files']==len(closed['roster'])==30 and closed['bytes']==sum(r['bytes'] for r in closed['roster'].values())==106565
assert {str(p.relative_to(raw)) for p in raw.rglob('*') if p.is_file()}==set(closed['roster'])
for name,row in closed['roster'].items():assert (raw/name).stat().st_size==row['bytes'] and sha(raw/name)==row['sha256'],name
isolation(load(raw/'container-initial.json'),'controls')
result=load(raw/'container-result.json');assert result['State']['ExitCode']==result['clientExitCode']==0 and not result['State']['OOMKilled']
assert load(raw/'cleanup.json')['removed'] and load(raw/'cleanup.json')['independentInspectAbsent']
assert load(folder/'cell-census-cleanup-controls-v1.json')['independentAbsent']
assert load(raw/'controls.json')=={'errors':0,'failures':0,'skips':0,'successful':True,'tests':11}
previous=folder/'qualification-raw/v10/controls/window-cells.bin';xml=ET.parse(folder/'qualification-raw/v12/controls/full-fixture.osm').getroot()
nodes={int(n.attrib['id']):(round(float(n.attrib['lon'])*10000000),round(float(n.attrib['lat'])*10000000)) for n in xml.findall('node')}
identity=None
for label in ['pass-a','pass-b']:
    p=raw/label;receipt=load(p/'source-receipt.json');check_receipt(receipt,plan)
    assert receipt['nativeEof'] and receipt['visits']==9 and receipt['witnessRows']==2
    fine=load(p/'fine-revalidation.json');assert fine['nodeRowsCompared']==4 and fine['sourceBlocksCompared']==fine['sourceShardsCompared']==fine['wholeFileVerificationPasses']==1
    assert fine['payloadBytesRead']==681 and fine['readOnly'] and fine['wholeSourceEofStillRequiredFromCaller']
    proof=load(p/'witness-proof.json');assert proof['sourceRows']==[[key,*nodes[key]] for key in plan['queryIDs']]
    assert proof['queries']==[4,1,1,4,1] and proof['cells']==[72,36,36,72,36]
    assert proof['bankBytes']==proof['snapshotBytes']==578 and proof['bankBlocks']==proof['bankParts']==1
    bank=p/'bank';assert (bank/'0000.bin').read_bytes()==previous.read_bytes()
    directory=struct.pack('<qQIIII',4,0,83,4,0,0);assert (bank/'directory.bin').read_bytes()==directory
    m=load(bank/'index.json');assert m['rows']==4 and m['blocks']==1 and m['windows']==plan['windows']
    result=load(p/'result.json');assert result['status']=='passed_cell_bank_capacity_pass' and not result['nationalPass'] and not result['wholeTwoPassBankCapacityQualified']
    assert result['identity']['catalogSha256']==sha(bank/'index.json') and result['identity']['directorySha256']==sha(bank/'directory.bin')
    assert result['identity']['partSha256']==[sha(bank/'0000.bin')]
    assert identity is None or identity==result['identity'];identity=result['identity']
result=load(raw/'result.json');assert result['status']=='passed_cell_bank_capacity_census' and result['sourcePasses']==2 and result['sourceObjects']==18
assert result['identity']==identity and result['fineCodecRows']==8 and result['fineCodecCalls']==2 and result['cellCodecRows']==40 and result['cellCodecCalls']==10
assert result['readOnlyFineInputRevalidatedForThisStage'] and not any(result[k] for k in ['nationalBankCapacityQualified','oldFailedEvidenceChanged','wholeRoadCaptureQualified','sourceSuitabilityQualified','modelChanged'])
metrics=load(raw/'metrics-end.json');assert metrics['retainedReservationBytes']==RETAINED==53324308583 and metrics['ownedLimitBytesExcludingTmp']==OWNED==15126732697
assert RETAINED+TMP+OWNED==TOTAL and metrics['observedWorkPeaks']['conservativeAllocatedBytes']<OWNED
cgroup=metrics['latest']['cgroup'];assert cgroup['memory.max']=='4294967296' and cgroup['memory.swap.max']=='0' and int(cgroup['memory.peak'])==48332800 and 'oom_kill 0' in cgroup['memory.events']
assert load(raw/'run-summary.json')['status']=='passed_cell_bank_capacity_census'
print(json.dumps({'capacityControllerTinyQualified':True,'linuxTests':11,'skips':0,'completeSourcePasses':2,'sourceObjects':18,
                  'exactIndependentSourceCells':True,'identicalRebuiltBanks':True,'readOnlyInputPreserved':True,'workerAbsent':True,
                  'nationalSourceOrStoppedIndexRead':False,'nationalBankCapacityQualified':False},indent=2))
