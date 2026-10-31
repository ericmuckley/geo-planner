"""Saved parent-array relative conservation check; no source pass or route search."""
from array import array
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

repo=Path(__file__).resolve().parents[3]
folder=Path(__file__).resolve().parent
report=json.loads((folder/'report.json').read_text())
old=json.loads((repo/'docs/evidence/coarse-backbone-preflight-2026-10-25/report.json').read_text())
def values(record):
    path=repo/record['path']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==record['sha256']
    with gzip.open(path,'rb') as stream:raw=stream.read()
    result=array(record['typecode']);result.frombytes(raw)
    if sys.byteorder!='little':result.byteswap()
    return result
new_km=values(report['packedArrays']['arcRoadKm'])
new_minutes=values(report['packedArrays']['arcMinutes'])
old_km=values(old['packedArrays']['arcRoadKm'])
old_times=values(old['packedArrays']['arcDeciseconds'])
maximum_relative=maximum_minutes=0.
with gzip.open(repo/'data/coarse-quality/census-backbone-geometry-v1/parents.jsonl.gz','rt') as stream:
    for expected,line in enumerate(stream):
        row=json.loads(line);assert row['parent']==expected
        start,end=row['firstArc'],row['lastArc']
        relative=abs(math.fsum(new_km[start:end])-old_km[expected])/old_km[expected]
        difference=abs(math.fsum(new_minutes[start:end])-old_times[expected]/600)
        maximum_relative=max(maximum_relative,relative);maximum_minutes=max(maximum_minutes,difference)
        assert relative<=1e-10 and difference<=1e-8
assert expected+1==501493
print(json.dumps({'parents':expected+1,'maximumRelativeRoadLengthError':maximum_relative,
    'maximumMinutesError':maximum_minutes,'allPerParentRelativeAndTimeLimitsPass':True,
    'gzipRuntimeArrayBytes':sum(v['gzipBytes'] for v in report['packedArrays'].values()),
    'scope':'Saved arrays and parent ranges only; no source rebuild, simplification, runtime change or query.'},indent=2))
