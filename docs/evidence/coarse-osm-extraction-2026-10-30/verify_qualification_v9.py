"""Saved native window-cell proof, no native/Docker/national source execution."""
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
    sys.argv=[str(folder/'verify_full_run_v2.py')]
    with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(sys.argv[0],run_name='__main__')
finally:sys.argv=saved
sys.path.insert(0,str(repo/'scripts'))
from run_osm_country_screen_v9 import validate,isolation
plan=load(folder/'qualification-plan-v9.json');validate(plan);freeze=load(folder/'qualification-freeze-v9.json')
assert sha(folder/'qualification-plan-v9.json')==freeze['recipeSha256']
for name,pin in plan['inputs'].items():
    if not name.startswith('data/'):assert sha(repo/name)==pin,name
for name,pin in freeze['newProducerFiles'].items():assert sha(repo/name)==pin
closed=load(folder/'qualification-closed-v9.json');raw=folder/'qualification-raw/v9'
assert closed['files']==len(closed['roster'])==80 and closed['bytes']==sum(row['bytes'] for row in closed['roster'].values())==3731377
for name,row in closed['roster'].items():
    if not row['ignoredLibrary']:assert (raw/name).stat().st_size==row['bytes'] and sha(raw/name)==row['sha256']
audit=load(folder/'cleanup-audit-v9.json')
for phase,peak in [('build',455823360),('controls',296607744)]:
    isolation(load(raw/phase/'container-initial.json'),phase)
    result=load(raw/phase/'container-result.json');assert result['State']['ExitCode']==result['clientExitCode']==0 and not result['State']['OOMKilled']
    assert load(raw/phase/'cleanup.json')['removed'] and load(raw/phase/'cleanup.json')['independentInspectAbsent'] and audit[phase]['independentAbsent']
    metrics=load(raw/phase/'metrics-end.json');assert int(metrics['memory.peak'])==peak and metrics['memory.swap.max']=='0' and 'oom_kill 0' in metrics['memory.events']
build=load(raw/'build/result.json')
assert build['artifactBytes']==2004024 and build['artifactSha256']=='ddad06ea7f2f44e573c9539987b543c3edf67578643bf76cbec2130ba253fad0'
for local,source in [('country-screen.cpp','coarse_osm_country_screen_v6.cpp'),('delta.cpp','coarse_osm_delta_v1.cpp'),('window-cells.cpp','coarse_osm_window_cells_v1.cpp')]:assert sha(raw/'build'/local)==plan['inputs']['scripts/'+source]
controls=load(raw/'controls/controls.json');assert controls['tests']==276 and controls['successful'] and controls['failures']==controls['errors']==controls['skipped']==0
assert len(plan['testIds'])==len(set(plan['testIds']))==276
assert controls['cellCodecChargedRows']==20533 and controls['cellCodecCalls']==30 and controls['cellCodecDirectTestRowReserve']==16
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
print(json.dumps({'nativeWindowCellCodecQualified':True,'linuxTests':276,'skips':0,'exactIndependentCellBlock':True,
                  'persistentNodeRows':4,'workersAbsent':True,'nationalSourceRead':False,'bankOrExtractionIntegrationQualified':False},indent=2))
