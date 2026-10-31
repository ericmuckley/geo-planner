"""Saved all-highway prototype proof; no native, Docker or national PBF reads."""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import sys
import xml.etree.ElementTree as ET

parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--local-assets',action='store_true');args=parser.parse_args()
f=Path(__file__).resolve().parent;r=f.parents[2]
load=lambda p:json.loads(p.read_text())
def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
parent=f.parent/'coarse-osm-lookup-2026-10-30'
assert sha(parent/'sha256.json')=='6b111218f92e5c8ee3851f739a0cd4f9fb41f77347a1d24901186f16a1736c80'
previous=sys.argv
try:
    sys.argv=[str(parent/'verify_closed.py')]
    with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(sys.argv[0],run_name='__main__')
finally:sys.argv=previous
sys.path.insert(0,str(r/'scripts'))
from run_osm_country_screen_v7 import validate,isolation
from coarse_osm_records import canonical,normalize
from coarse_osm_country_wire_v4 import reference_seal
from coarse_osm_bulk_audit import crossing
from coarse_osm_delta_v2 import Reader,ReferenceCodec
plan=load(f/'qualification-plan-v7.json');validate(plan)
assert sha(f/'qualification-plan-v7.json')==load(f/'qualification-freeze-v7.json')['recipeSha256']
for name,pin in plan['inputs'].items():
    if not name.startswith('data/') or args.local_assets:assert sha(r/name)==pin,name
for version,closed in load(f/'qualification-closed.json').items():
    raw=f/'qualification-raw'/version
    for name,row in closed['roster'].items():
        p=r/closed['root']/name if name.endswith('.so') else raw/name
        if not name.endswith('.so') or args.local_assets:assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],name
    for phase in (('build','controls') if version=='v6' else ('controls',)):
        isolation(load(raw/phase/'container-initial.json'),phase)
        state=load(raw/phase/'container-result.json');expected=2 if version=='v6' and phase=='controls' else 0
        assert state['State']['ExitCode']==state['clientExitCode']==expected and not state['State']['OOMKilled']
        assert load(raw/phase/'cleanup.json')['removed'] and load(raw/phase/'cleanup.json')['independentInspectAbsent']
old=f/'qualification-raw/v6';raw=f/'qualification-raw/v7'
failed=load(old/'controls/controls.json');assert failed['tests']==259 and failed['errors']==1 and failed['failures']==failed['skipped']==0
assert "KeyError: 'members'" in (old/'controls/worker.log').read_text()
controls=load(raw/'controls/controls.json');assert controls['tests']==259 and controls['successful'] and controls['errors']==controls['failures']==controls['skipped']==0
assert len(plan['testIds'])==len(set(plan['testIds']))==259
built=load(old/'build/result.json');assert built['artifactBytes']==2003688 and built['artifactSha256']=='1084fc1b6e9b1a627b52180fd91df0b46e01a967fbd399c2bad672a4f675f48a'
assert sha(old/'build/country-screen.cpp')==sha(r/'scripts/coarse_osm_country_screen_v6.cpp')==built['sourceSha256']
assert all(row['independentAbsent'] for row in load(f/'cleanup-audit.json'))
proof=load(raw/'controls/full-prototype-proof.json');new=proof['newState'];reference=proof['referenceState']
assert new['status']=='passed_all_highway_extraction_prototype' and new['independentAuditComplete']
assert new['scanObjectVisits']==18 and reference['scanObjectVisits']==proof['fourPassReferenceViews']==36
assert new['retainedElements']==reference['retainedElements']==4 and new['windowOccurrences']==reference['windowOccurrences']==8
assert not new['wholeExtractionQualified'] and not new['modelChanged']
rows=[]
for item in ET.parse(raw/'controls/full-fixture.osm').getroot():
    row=dict(type=item.tag,id=int(item.attrib['id']),version=int(item.attrib['version']),timestamp=item.attrib['timestamp'],visible=item.attrib['visible']=='true',
             tags={tag.attrib['k']:tag.attrib['v'] for tag in item if tag.tag=='tag'})
    if item.tag=='node':row.update(lon=float(item.attrib['lon']),lat=float(item.attrib['lat']))
    elif item.tag=='way':row['nodes']=[int(child.attrib['ref']) for child in item if child.tag=='nd']
    else:row['members']=[dict(type=child.attrib['type'],ref=int(child.attrib['ref']),role=child.attrib['role']) for child in item if child.tag=='member']
    rows.append(row)
snapshot=proof['proposal']['source']['proposedPublisherReplicationStateUtc'];windows=proof['proposal']['windows'];nodes={row['id']:row for row in rows if row['type']=='node'}
members={window['id']:set() for window in windows}
for row in rows:
    if row['type']!='way' or 'highway' not in row['tags']:continue
    points=[[nodes[identity]['lon'],nodes[identity]['lat']] for identity in row['nodes']]
    for window in windows:
        if crossing(points,window['bbox']):members[window['id']].update([('way',row['id']),*(('node',identity) for identity in row['nodes'])])
for row in rows:
    if row['type']!='relation' or row['tags'].get('type')!='restriction':continue
    linked={(m['type'],m['ref']) for m in row['members'] if m['type'] in ('node','way')}
    for group in members.values():
        if group & linked:group.add(('relation',row['id']))
keys=set().union(*members.values());objects={(row['type'],row['id']):normalize(row,snapshot,1048576) for row in rows if (row['type'],row['id']) in keys}
expected=[]
for key,element in sorted(objects.items()):
    record=dict(publisherStateUtc=snapshot,element=element,elementSha256=hashlib.sha256(canonical(element)).hexdigest(),windowIds=[name for name,group in members.items() if key in group])
    if element['type']=='way':record['geometryDependencySha256']=hashlib.sha256(canonical([snapshot,[objects['node',identity] for identity in element['nodes']]])).hexdigest()
    expected.append(canonical(record)+b'\n')
expected=b''.join(expected);new_root=raw/'controls/full-prototype';reference_root=raw/'controls/four-pass-reference'
assert expected==(new_root/'elements.jsonl').read_bytes()==(reference_root/'elements.jsonl').read_bytes()
assert len(expected)==proof['outputBytes']==1470 and hashlib.sha256(expected).hexdigest()==proof['outputSha256']=='dd2315bf022fa0ebe4ac7db1fee38329d40fb5c87f2e236577627d73730d875c'
assert all(receipt['nativeEof'] and receipt['visits']==9 and receipt['semanticSha256']==reference_seal(rows) for receipt in new['nativeReceipts'])
assert [receipt['selectedNodeProjections'] for receipt in new['nativeReceipts']]==[0,2]
assert all(receipt['batchWays']==receipt['highwayWays']==2 and receipt['restrictionProjections']==2 for receipt in new['nativeReceipts'])
reader=Reader(new_root/'audit-index',ReferenceCodec());actual=[]
for number in range(reader.manifest['blocks']):
    ids,xy=reader.block(number);actual.extend((identity,xy[2*i],xy[2*i+1]) for i,identity in enumerate(ids))
reader.close();assert actual==[(row['id'],round(row['lon']*10000000),round(row['lat']*10000000)) for row in rows if row['type']=='node']
assert not list((new_root/'primary-index').glob('[0-9]*.bin'))
print(json.dumps({'allHighwayPrototypeQualified':True,'actualLinuxTests':259,'skips':0,'independentXmlFieldsWindowGeometryDependenciesAndFourPassOutputVerified':True,
                  'oldFailurePreserved':True,'workersAbsent':True,'nationalSourceRead':False,'nationalAllocationAdmitted':False},indent=2))
