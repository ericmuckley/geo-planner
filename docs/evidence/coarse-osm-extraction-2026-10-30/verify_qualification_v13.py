"""Saved exact ID-run codec/bank/filter proof; no native or national inputs read."""
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
    sys.argv=[str(folder/'verify_cell_census_stop_v1.py')]
    with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(sys.argv[0],run_name='__main__')
finally:sys.argv=saved
sys.path.insert(0,str(repo/'scripts'))
from run_osm_country_screen_v13 import validate,isolation
plan=load(folder/'qualification-plan-v13.json');validate(plan);freeze=load(folder/'qualification-freeze-v13.json')
assert sha(folder/'qualification-plan-v13.json')==freeze['recipeSha256']
for name,pin in plan['inputs'].items():
    if not name.startswith('data/'):assert sha(repo/name)==pin,name
for name,pin in freeze['newProducerFiles'].items():assert sha(repo/name)==pin
raw=folder/'qualification-raw/v13';closed=load(folder/'qualification-closed-v13.json')
assert closed['files']==len(closed['roster'])==108 and closed['bytes']==sum(r['bytes'] for r in closed['roster'].values())==3796019
for name,row in closed['roster'].items():
    if not row['ignoredLibrary']:assert (raw/name).stat().st_size==row['bytes'] and sha(raw/name)==row['sha256'],name
audit=load(folder/'cleanup-audit-v13.json')
for phase,peak in [('build',456495104),('controls',252387328)]:
    isolation(load(raw/phase/'container-initial.json'),phase)
    result=load(raw/phase/'container-result.json');assert result['State']['ExitCode']==result['clientExitCode']==0 and not result['State']['OOMKilled']
    assert load(raw/phase/'cleanup.json')['removed'] and load(raw/phase/'cleanup.json')['independentInspectAbsent'] and audit[phase]['independentAbsent']
    metrics=load(raw/phase/'metrics-end.json');assert int(metrics['memory.peak'])==peak and metrics['memory.swap.max']=='0' and 'oom_kill 0' in metrics['memory.events']
build=load(raw/'build/result.json');assert build['artifactBytes']==2004888 and build['artifactSha256']=='e82ccc44579ded7e7a6fcae5cdd3a6267250f3f3e00968195e45e567f1c0138e'
for local,source in [('country-screen.cpp','coarse_osm_country_screen_v6.cpp'),('delta.cpp','coarse_osm_delta_v1.cpp'),('window-cells.cpp','coarse_osm_window_cells_v1.cpp'),('window-masks.cpp','coarse_osm_window_masks_v1.cpp'),('window-cells-v2.cpp','coarse_osm_window_cells_v2.cpp')]:assert sha(raw/'build'/local)==plan['inputs']['scripts/'+source]
c=load(raw/'controls/controls.json');assert c['tests']==65 and c['successful'] and c['failures']==c['errors']==c['skipped']==0
assert len(plan['testIds'])==len(set(plan['testIds']))==65 and c['cellCodecChargedRows']==83121 and c['cellCodecCalls']==252
assert c['maskReferences']==270212 and c['maskCalls']==36 and c['sourceIndexFixtureNativeRows']==24612
proof=load(raw/'controls/window-cells-v2-proof.json');xml=ET.parse(raw/'controls/full-fixture.osm').getroot()
nodes=[(int(n.attrib['id']),round(float(n.attrib['lon'])*10000000),round(float(n.attrib['lat'])*10000000)) for n in xml.findall('node')]
assert proof['sourceNodeRows']==[list(row) for row in nodes]
# Independent explicit representation of this tiny case: three unit ID gaps,
# then the36/44/72 cell runs. The full random/sparse/tie controls are in the roster.
payload=struct.pack('<IqqIII',4,1,4,2,1,3)+b'\x01\x03'+struct.pack('<HHHHHH',36,1,44,1,72,2)
expected=struct.pack('<4sHH32s',b'WC02',2,0,hashlib.sha256(payload).digest())+payload
block=raw/'controls/window-cells-v2.bin';assert block.read_bytes()==expected and block.stat().st_size==proof['blockBytes']==86
assert sha(block)==proof['blockSha256']=='324f4f26161b2647d85dc5bc5af94365b32337c6c434d89de874fc443611634d'
assert proof['legacyBlockBytes']==83 and proof['legacyConversionExact'] and proof['cells']==[72,44,36,44,72]
assert proof['cellCodecRows']==20 and proof['cellCodecCalls']==5 and not proof['nationalSourceRead'] and not proof['modelChanged']
for name,directory in [('filtered-prototype-proof.json','cell-filtered-prototype'),('readonly-prototype-proof.json','readonly-filtered-prototype')]:
    p=load(raw/'controls'/name);state=p['state'];assert state['status']=='passed_cell_filtered_extraction_prototype' and state['independentAuditComplete']
    assert state['scanObjectVisits']==18 and state['retainedElements']==4 and state['windowOccurrences']==8 and state['cellBankBytesPeak']==581
    assert p['outputBytes']==1470 and p['outputSha256']=='dd2315bf022fa0ebe4ac7db1fee38329d40fb5c87f2e236577627d73730d875c'
    output=raw/'controls'/directory/'elements.jsonl';assert sha(output)==p['outputSha256'] and output.read_bytes()==(raw/'controls/four-pass-reference/elements.jsonl').read_bytes()
    for receipt in state['nativeReceipts']:assert receipt['nativeEof'] and receipt['counts']=={'node':4,'way':3,'relation':2} and receipt['visits']==9
    for lookup in state['coarseLookups']:assert lookup['fineReferences']==2 and lookup['examinedReferences']==4 and lookup['certifiedOutsideWays']==1
    for label in ['all-highway-primary-selection','all-highway-independent-materialization']:
        bank=raw/'controls'/directory/(label+'-cells');m=load(bank/'index.json')
        assert m['format']=='immutable-window-cell-bank-v2' and m['rows']==4 and m['blocks']==1 and (bank/'0000.bin').read_bytes()==expected
        assert (bank/'directory.bin').read_bytes()==struct.pack('<qQIIII',4,0,86,4,0,0)
    if name.startswith('readonly'):
        assert p['inputBeforeSha256']==p['inputAfterSha256'] and p['normalSourceEofQualifiedTiny'] and not p['nationalStoppedIndexReused']
        assert all(view['nodeRowsCompared']==4 and view['payloadBytesRead']==681 and view['wholeFileVerificationPasses']==1 for view in p['sourceIndexViews'])
        assert not (raw/'controls'/directory/'primary-index').exists() and not (raw/'controls'/directory/'audit-index').exists()
summary=load(raw/'run-summary.json');assert summary['phaseClientExitCodes']=={'build':0,'controls':0} and summary['wholeSourceOrSavedPbfReads']==summary['networkRequests']==0
print(json.dumps({'losslessIdGapRunsTinyQualified':True,'linuxTests':65,'skips':0,'legacyConversionExact':True,
                  'filteredAndReadOnlyOutputExact':True,'workersAbsent':True,'nationalSourceFineOrPrefixRead':False,
                  'nationalCapacityQualified':False},indent=2))
