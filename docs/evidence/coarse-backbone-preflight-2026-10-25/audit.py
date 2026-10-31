"""Independent saved-array arithmetic/connectivity/codec audit; no source pass/search/network."""
from array import array
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

folder = Path(__file__).resolve().parent
repo = folder.parents[2]
load = lambda path:json.loads(path.read_text())
r, c = load(folder/'report.json'), load(folder/'codec-report.json')
assert r['planSha256'] == hashlib.sha256((folder/'plan.json').read_bytes()).hexdigest()
assert c['planSha256'] == hashlib.sha256((folder/'codec-plan.json').read_bytes()).hexdigest()
arrays = {}
for name, info in r['packedArrays'].items():
    raw = (repo/info['path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == info['sha256']
    values = array(info['typecode']); values.frombytes(gzip.decompress(raw))
    if sys.byteorder != 'little':values.byteswap()
    assert len(values) == info['elements'] and len(values)*values.itemsize == info['rawBytes']
    assert info['base64Bytes'] == 4*((len(raw)+2)//3)
    arrays[name] = values
n, m = r['nodes'], r['arcs']
a, b, km, cost, speed = [arrays[name] for name in ['arcFrom','arcTo','arcRoadKm','arcDeciseconds','arcSpeedKph']]
assert len(a) == len(b) == len(km) == len(cost) == len(speed) == m
assert r['counts']['parts']-r['counts']['duplicates'] == r['counts']['uniqueParts'] == 223392
assert len(arrays['partPointOffsets']) == 223393
assert arrays['partPointOffsets'][0] == 0
assert arrays['partPointOffsets'][-1]*2 == len(arrays['pointDeltas'])
assert all(0<=x<n and 0<=y<n and length>0 and s in [85,105] and t>=1 and abs(t-max(1,math.ceil(length/s*36000)))<1 for x,y,length,t,s in zip(a,b,km,cost,speed))
assert abs(sum(km)-r['sourceRoadKm']) < .0001
assert all(0<=x<=y<arrays['partPointOffsets'][-1] for x,y in zip(arrays['arcFirstPoint'],arrays['arcLastPoint']))
# Independent compact adjacency/BFS, rather than the producer's union-find.
degree = array('I',[0])*n
for x,y in zip(a,b):degree[x]+=1;degree[y]+=1
starts = array('I',[0])
for count in degree:starts.append(starts[-1]+count)
neighbor = array('I',[0])*(2*m)
cursor = starts[:-1]
for x,y in zip(a,b):
    neighbor[cursor[x]]=y;cursor[x]+=1
    neighbor[cursor[y]]=x;cursor[y]+=1
component = array('i',[-1])*n
count = 0
for node in range(n):
    if component[node]>=0:continue
    stack=[node];component[node]=count
    while stack:
        x=stack.pop()
        for j in range(starts[x],starts[x+1]):
            y=neighbor[j]
            if component[y]<0:component[y]=count;stack.append(y)
    count+=1
lengths=[0.]*count
for x,y,length in zip(a,b,km):
    assert component[x]==component[y]
    lengths[component[x]]+=length
fraction=max(lengths)/sum(lengths)
assert count==r['splitAtSourceEndpoints']['components']
assert abs(fraction-r['splitAtSourceEndpoints']['largestRoadLengthFraction'])<1e-10
# Independent integer-stream decoder; exact little-endian array checksum.
source_values=arrays.pop('pointDeltas')
if sys.byteorder != 'little':source_values.byteswap()
source_hash=hashlib.sha256(memoryview(source_values).cast('B')).hexdigest()
encoded=repo/c['file']['path']
assert hashlib.sha256(encoded.read_bytes()).hexdigest()==c['file']['sha256']
restored_hash=hashlib.sha256(); block_values=array('i');value=shift=decoded=0
with gzip.open(encoded,'rb') as stream:
    while block:=stream.read(1048576):
        for byte in block:
            assert shift<35
            value |= (byte&127)<<shift
            if byte>=128:shift+=7;continue
            assert value<=0xffffffff
            block_values.append((value>>1)^-(value&1));decoded+=1;value=shift=0
            if len(block_values)==262144:
                if sys.byteorder != 'little':block_values.byteswap()
                restored_hash.update(block_values.tobytes());block_values=array('i')
assert shift==0
if sys.byteorder != 'little':block_values.byteswap()
restored_hash.update(block_values.tobytes())
assert decoded==c['values']==48900800
assert source_hash==restored_hash.hexdigest()==c['sourceRawInt32Sha256']==c['restoredRawInt32Sha256']
matched=sum(row[key]['nearestSourceVertexWithin5Km'] is not None for row in r['all83Ledger'] for key in ['origin','destination'])
benchmark=load(repo/'docs/evidence/coarse-path-features-2026-10-24/comparison.json')
assert len(r['all83Ledger'])==len(benchmark['rows'])==83
for row,saved in zip(r['all83Ledger'],benchmark['rows']):
    assert row['id']==f"{saved['set']}/{saved['id']}"
    for key in ['origin','destination']:
        assert row[key]['query']==saved[key]
        if row[key]['nearestSourceVertexWithin5Km'] is not None:assert row[key]['nearestSourceVertexWithin5Km']['distanceKm']<=5
assert matched==r['matchedProbeEndpoints']==166
forecast=r['storageForecast']
assert forecast['projectedFunctionBytes']==sum(forecast[k] for k in ['keptV9JsonBytes','newPackedJsonBytesIncludingMetadata','functionOverheadBytes','integrationReserveBytes'])
assert c['projectedFunctionBytes']==forecast['projectedFunctionBytes']-r['packedArrays']['pointDeltas']['base64Bytes']+c['file']['base64Bytes']+1024
assert not r['advanceToRoutingPrototype'] and not c['advanceToRuntimeDesign']
assert not r['gates']['projectedFunction'] and not c['gates']['projectedFunction']
print(json.dumps({'nodes':n,'arcs':m,'independentBfsComponents':count,'largestRoadLengthFraction':fraction,
    'allSourceLengthAndWeights':True,'all83CasesAnd166Endpoints':True,'byteExactCodecValues':decoded,
    'naiveProjectedBytes':forecast['projectedFunctionBytes'],'codecProjectedBytes':c['projectedFunctionBytes'],
    'bothStorageFailuresConfirmed':True,'providerRequests':0,
    'scope':'Independent saved-array arithmetic/BFS/byte-stream audit, not a source rebuild, routing/ETA result, access check, app deployment or cloud runtime measurement.'},indent=2))
