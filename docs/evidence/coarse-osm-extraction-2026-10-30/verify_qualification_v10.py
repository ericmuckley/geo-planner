"""Saved immutable-bank/filter proof, no native/Docker/national source execution."""
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
    sys.argv=[str(folder/'verify_qualification_v9.py')]
    with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(sys.argv[0],run_name='__main__')
finally:sys.argv=saved
sys.path.insert(0,str(repo/'scripts'))
from run_osm_country_screen_v10 import validate,isolation
plan=load(folder/'qualification-plan-v10.json');validate(plan);freeze=load(folder/'qualification-freeze-v10.json')
assert sha(folder/'qualification-plan-v10.json')==freeze['recipeSha256']
for name,pin in plan['inputs'].items():
    if not name.startswith('data/'):assert sha(repo/name)==pin,name
for name,pin in freeze['newProducerFiles'].items():assert sha(repo/name)==pin
closed=load(folder/'qualification-closed-v10.json');raw=folder/'qualification-raw/v10'
assert closed['files']==len(closed['roster'])==95 and closed['bytes']==sum(row['bytes'] for row in closed['roster'].values())==3792620
for name,row in closed['roster'].items():
    if not row['ignoredLibrary']:assert (raw/name).stat().st_size==row['bytes'] and sha(raw/name)==row['sha256']
audit=load(folder/'cleanup-audit-v10.json')
for phase,peak in [('build',456687616),('controls',325099520)]:
    isolation(load(raw/phase/'container-initial.json'),phase)
    result=load(raw/phase/'container-result.json');assert result['State']['ExitCode']==result['clientExitCode']==0 and not result['State']['OOMKilled']
    assert load(raw/phase/'cleanup.json')['removed'] and load(raw/phase/'cleanup.json')['independentInspectAbsent'] and audit[phase]['independentAbsent']
    metrics=load(raw/phase/'metrics-end.json');assert int(metrics['memory.peak'])==peak and metrics['memory.swap.max']=='0' and 'oom_kill 0' in metrics['memory.events']
build=load(raw/'build/result.json')
assert build['artifactBytes']==2004312 and build['artifactSha256']=='a84d4641026dbe250fd13f8e098082ac2ba7987bf54b9e63ff5d1126d94bee38'
for local,source in [('country-screen.cpp','coarse_osm_country_screen_v6.cpp'),('delta.cpp','coarse_osm_delta_v1.cpp'),('window-cells.cpp','coarse_osm_window_cells_v1.cpp'),('window-masks.cpp','coarse_osm_window_masks_v1.cpp')]:assert sha(raw/'build'/local)==plan['inputs']['scripts/'+source]
controls=load(raw/'controls/controls.json');assert controls['tests']==304 and controls['successful'] and controls['failures']==controls['errors']==controls['skipped']==0
assert len(plan['testIds'])==len(set(plan['testIds']))==304
assert controls['cellCodecChargedRows']==50185 and controls['cellCodecCalls']==191 and controls['cellCodecDirectTestRowReserve']==16
assert controls['cellCodecChargedRows']+16<=250000
proof=load(raw/'controls/window-cells-proof.json');block=(raw/'controls/window-cells.bin').read_bytes()
xml=ET.parse(raw/'controls/full-fixture.osm').getroot()
nodes=[(int(n.attrib['id']),round(float(n.attrib['lon'])*10000000),round(float(n.attrib['lat'])*10000000)) for n in xml.findall('node')]
assert proof['sourceNodeRows']==[list(row) for row in nodes]
def bounds(value,upper=False):
    n,d=value.as_integer_ratio();n*=10000000
    return -((-n)//d) if upper else n//d
boxes=[(bounds(w['bbox'][0]),bounds(w['bbox'][1]),bounds(w['bbox'][2],True),bounds(w['bbox'][3],True)) for w in proof['windows']]
xs=sorted({v for box in boxes for v in (box[0],box[2])});ys=sorted({v for box in boxes for v in (box[1],box[3])})
def slot(edges,value):return 2*sum(edge<value for edge in edges)+int(value in edges)
width=2*len(xs)+1;cells={identity:slot(xs,x)+width*slot(ys,y) for identity,x,y in nodes}
ids=bytearray()
for a,b in zip(nodes,nodes[1:]):
    gap=b[0]-a[0]
    while gap>=128:ids.append((gap&127)|128);gap>>=7
    ids.append(gap)
runs=[]
for identity,_,_ in nodes:
    value=cells[identity]
    if runs and runs[-1][0]==value:runs[-1][1]+=1
    else:runs.append([value,1])
body=struct.pack('<IqqII',len(nodes),nodes[0][0],nodes[-1][0],len(ids),len(runs))+ids+b''.join(struct.pack('<HH',*run) for run in runs)
expected=struct.pack('<4sHH32s',b'WC01',1,0,hashlib.sha256(body).digest())+body
assert block==expected and len(block)==proof['blockBytes']==83 and sha(raw/'controls/window-cells.bin')==proof['blockSha256']
assert proof['cells']==[cells[identity] for identity in proof['queries']]==[72,44,36,44,72]
table=bytearray()
edges=[(2*xs.index(a)+1,2*ys.index(b)+1,2*xs.index(c)+1,2*ys.index(d)+1) for a,b,c,d in boxes]
for y in range(2*len(ys)+1):
    for x in range(width):
        table.extend(int(x<a)|2*int(x>c)|4*int(y<b)|8*int(y>d) for a,b,c,d in edges)
assert len(table)==proof['tableBytes']==162 and hashlib.sha256(table).hexdigest()==proof['tableSha256']
assert proof['codecRows']==12 and proof['codecCalls']==3 and not proof['bankImplemented'] and not proof['nationalSourceRead'] and not proof['modelChanged']
assert (raw/'controls/full-prototype/elements.jsonl').read_bytes()==(folder/'qualification-raw/v8/controls/full-prototype/elements.jsonl').read_bytes()
summary=load(raw/'run-summary.json');assert summary['phaseClientExitCodes']=={'build':0,'controls':0} and summary['wholeSourceOrSavedPbfReads']==summary['networkRequests']==0
filtered=load(raw/'controls/filtered-prototype-proof.json');state=filtered['state']
assert state['status']=='passed_cell_filtered_extraction_prototype' and state['independentAuditComplete']
assert state['scanObjectVisits']==18 and state['retainedElements']==4 and state['windowOccurrences']==8
assert filtered['outputBytes']==1470 and filtered['outputSha256']==filtered['referenceOutputSha256']=='dd2315bf022fa0ebe4ac7db1fee38329d40fb5c87f2e236577627d73730d875c'
assert (raw/'controls/cell-filtered-prototype/elements.jsonl').read_bytes()==(raw/'controls/four-pass-reference/elements.jsonl').read_bytes()
assert filtered['cellCodecRows']==40 and filtered['cellCodecCalls']==10 and filtered['maskReferences']==8 and filtered['maskCalls']==2
assert state['cellBankBytesPeak']==578
for receipt in state['nativeReceipts']:
    assert receipt['nativeEof'] and receipt['counts']=={'node':4,'way':3,'relation':2} and receipt['visits']==9
    assert receipt['semanticSha256']=='04630ed15b3eb0925917fb1d4dcabb51991d3cfe65eee84bc5a76b7652b9ed81'
for lookup in state['coarseLookups']:
    assert lookup['examinedReferences']==4 and lookup['fineReferences']==2 and lookup['certifiedOutsideWays']==1
    assert lookup['bankBytes']==578 and lookup['bankBlocks']==1 and lookup['queryBlocks']==1
for label in ['all-highway-primary-selection','all-highway-independent-materialization']:
    bank=raw/'controls/cell-filtered-prototype'/(label+'-cells');manifest=load(bank/'index.json')
    assert manifest['format']=='immutable-window-cell-bank-v1' and manifest['windows']==proof['windows']
    assert manifest['rows']==4 and manifest['blocks']==1 and manifest['tableSha256']==proof['tableSha256']
    assert (bank/'0000.bin').read_bytes()==block
    directory=struct.pack('<qQIIII',4,0,83,4,0,0)
    assert (bank/'directory.bin').read_bytes()==directory
    assert manifest['directory']=={'bytes':32,'sha256':hashlib.sha256(directory).hexdigest()}
    assert manifest['parts']==[{'blocks':1,'bytes':83,'first':1,'last':4,'rows':4,'sha256':hashlib.sha256(block).hexdigest()}]
assert controls['maskReferences']==270200 and controls['maskCalls']==33 and controls['maskDirectReferenceReserve']==16
assert controls['maskReferences']+16<=1000000
print(json.dumps({'nativeWindowCellCodecQualified' :True,'linuxTests':304,'skips':0,'exactIndependentCellBlock':True,
                  'persistentNodeRows':4,'workersAbsent':True,'nationalSourceRead':False,'tinyBankAndFilteredExtractionQualified':True,'nationalBankOrRetainedIndexReuseQualified':False},indent=2))
