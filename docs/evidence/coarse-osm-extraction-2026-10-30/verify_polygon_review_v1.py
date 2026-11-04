"""Saved public metadata and independent planar diagnostic; no network/PBF/native."""
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path

folder=Path(__file__).resolve().parent;repo=folder.parents[2];load=lambda p:json.loads(p.read_bytes())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for version in ('v1','v2'):
    plan=load(folder/('polygon-metadata-plan-'+version+'.json'));assert sha(repo/('scripts/inspect_osm_polygon_metadata_'+version+'.py'))==plan['producerSha256']
    closed=load(folder/('polygon-metadata-closed-'+version+'.json'));raw=folder/('polygon-metadata-raw/'+version)
    assert closed['files']==len(closed['roster']) and closed['bytes']==sum(r['bytes'] for r in closed['roster'].values())
    for name,row in closed['roster'].items():
        if not row['ignoredRawMetadata']:assert (raw/name).stat().st_size==row['bytes'] and sha(raw/name)==row['sha256']
    summary=load(raw/'run-summary.json');assert summary['pbfOrRoutingRequests']==0 and summary['bodyBytes']<=524288
    if version=='v1':assert summary['exitCode']==2 and summary['requestsAttempted']==1 and summary['bodyBytes']==0 and 'CERTIFICATE_VERIFY_FAILED' in load(raw/'failure.json')['error']
    else:
        assert summary['exitCode']==0 and summary['requestsAttempted']==4 and summary['bodyBytes']==27759
        assert not load(raw/'transport.json')['tlsVerificationDisabled'] and load(raw/'transport.json')['userConfigDisabled']
        for i in range(1,5):
            receipt=load(raw/f'{i:03d}-receipt.json');assert receipt['httpStatus']==200 and receipt['curlExitCode']==receipt['tlsVerifyResult']==0 and receipt['status']=='received'
        m=load(raw/'result.json');assert m['historicalCommit']=='9e71ba22cb4a7b7b1c4228031e2afdfc514d6b6e' and m['historicalCommitUtc']=='2025-07-31T12:51:53Z'
        assert m['noRepositoryChangesInCheckedInterval'] and not m['repositoryAndCurrentDeployedBytesEqual'] and not m['sourceSnapshotBoundaryCryptographicallyBound']
plan=load(folder/'polygon-review-plan-v1.json')
for name,pin in plan['inputs'].items():
    if not name.startswith('data/'):assert sha(repo/name)==pin
closed=load(folder/'polygon-review-closed-v1.json');raw=folder/'polygon-review-raw/v1'
for name,row in closed['roster'].items():assert (raw/name).stat().st_size==row['bytes'] and sha(raw/name)==row['sha256']
assert load(raw/'host-controls.json')['tests']==7 and load(raw/'host-controls.json')['successful']
result=load(raw/'result.json');assert result['status']=='host_polygon_diagnostic_complete'
assert not any(result[k] for k in ('sourceSnapshotBoundaryQualified','roadCompletenessQualified','all21WindowsAdequate','modelChanged'))
windows=load(repo/plan['proposal'])['windows'];assert len(windows)==21
# Independent parser/ray-intersection/parametric segment clip. These exact
# saved source polygons contain two outer rings and no hole rings.
def rings(path):
    groups=[];points=[]
    for line in path.read_text().splitlines()[1:]:
        values=line.split()
        if len(values)==2:points.append(tuple(map(F,values)))
        elif values==['END'] and points:groups.append(points);points=[]
        elif values and values[0].startswith('!'):raise AssertionError('Unexpected saved hole')
    assert len(groups)==2 and all(r[0]==r[-1] for r in groups);return groups

def contains(p,ring):
    inside=False
    for a,b in zip(ring,ring[1:]):
        if (a[1]>p[1])!=(b[1]>p[1]):
            x=a[0]+(p[1]-a[1])*(b[0]-a[0])/(b[1]-a[1])
            assert x!=p[0]
            if x>p[0]:inside=not inside
    return inside

def touches(a,b,box):
    left,bottom,right,top=box;dx,dy=b[0]-a[0],b[1]-a[1];low,high=F(0),F(1)
    for p,q in [(-dx,a[0]-left),(dx,right-a[0]),(-dy,a[1]-bottom),(dy,top-a[1])]:
        if p==0:
            if q<0:return False
        elif p<0:low=max(low,q/p)
        else:high=min(high,q/p)
        if low>high:return False
    return True

for label,filename in [('historicalRepository','002.bin'),('currentDeployed','003.bin')]:
    path=folder/'polygon-metadata-raw/v2'/filename;geometry=rings(path);record=result['polygons'][label]
    assert sha(path)==record['sha256'] and record['rings']==2 and record['holes']==0 and record['strictlyContainedWindows']==21
    for window,saved in zip(windows,record['windows']):
        left,bottom,right,top=box=list(map(F,window['bbox']))
        for point in [(left,bottom),(right,bottom),(right,top),(left,top)]:assert any(contains(point,r) for r in geometry)
        assert not any(touches(a,b,box) for r in geometry for a,b in zip(r,r[1:]))
        assert saved['id']==window['id'] and saved['cornerLocations']==['inside']*4 and saved['strictlyInsideReviewedPolygon'] and not saved['boundaryTouchesWindow']
print(json.dumps({'hostGeometryTests':7,'publicMetadataRequests':4,'publicBodyBytes':27759,'preservedTlsFailure':True,'bothReviewedPolygonsStrictlyContainAll21Windows':True,'effectiveDatedSourceBoundaryQualified':False,'roadCompletenessOrModelQualified':False,'networkPbfOrNativeCalls':0},indent=2))
