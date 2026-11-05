"""One bounded read-only captured-source tag census; no routing or constructor."""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

from inventory_osm_car_conditional_scope_v1 import inventory,selected_ordinals

REPO=Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def stat(path):
    s=path.stat();return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe');parser.add_argument('pin');args=parser.parse_args()
    recipe=REPO/args.recipe;assert sha(recipe)==args.pin;raw=recipe.read_bytes();plan=json.loads(raw)
    assert plan['output']=='data/coarse-quality/us-osm-car-conditional-scope-capture-v1'
    assert plan['controlsPassed']==8 and plan['hostSeconds']==120 and plan['maxOwnedBytes']==67108864
    assert plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+plan['maxOwnedBytes']<72*1024**3
    for name,pin in plan['bindings'].items():assert sha(REPO/name)==pin,name
    source=REPO/plan['database'];selected=REPO/plan['selection']
    assert source.is_file() and not source.is_symlink() and source.stat().st_size==plan['databaseBytes']<=536870912
    assert selected.is_file() and not selected.is_symlink() and selected.stat().st_size==574240
    root=REPO/plan['output'];root.mkdir()
    with (root/'execution-plan.json').open('xb') as stream:stream.write(raw)
    began=time.monotonic()
    def check():
        assert time.monotonic()-began<120,'Captured tag census deadline'
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        assert peak<4*1024**3,'Captured tag census RSS'
    def save(name,value):
        encoded=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode();assert len(encoded)<=1048576
        with (root/name).open('xb') as stream:stream.write(encoded)
    try:
        before=stat(source);assert sha(source)==plan['databaseSha256'];check()
        selection=selected_ordinals(selected.read_bytes());assert len(selection)==143560
        output_bytes=0;output_records=0
        with (root/'ignored-conditional-records.jsonl').open('xb') as stream:
            def emit(value):
                nonlocal output_bytes,output_records
                encoded=(json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode()
                output_bytes+=len(encoded);output_records+=1
                assert output_bytes<=16777216 and output_records<=10000,'Captured output quota'
                stream.write(encoded)
            result=inventory(source,selection,plan['expected'],emit,check)
        check();assert stat(source)==before and sha(source)==plan['databaseSha256'];assert stat(source)==before
        report={'status':'captured_source_conditional_scope_census_complete','recipeSha256':args.pin,**result,
                'records':output_records,'recordBytes':output_bytes,'recordsSha256':sha(root/'ignored-conditional-records.jsonl'),
                'sourceStatBefore':before,'sourceStatAfter':stat(source),'sourceSha256':plan['databaseSha256'],
                'hostSecondsIncludingSourceHashes':time.monotonic()-began,
                'capturedSourceSqliteReads':1,'nodeCoordinatesProjected':0,'nationalSourcePbfReads':0,'routingQueries':0,
                'applicationDbReads':0,'providerRequests':0,'graphConstructors':0,'engineOrProductionChanged':False,
                'nativePrototypeParityQualified':False,'nationalImpactMeasured':False,
                'scope':'All143560 selected native-node tag records/all28995 major-way tags in the complete saved21-area source capture. Python receives IDs/tags only, no node coordinates; source SQLite opened immutable/read-only and exact full SHA/stat unchanged. All old positive classifications retained; record every ignored key even when another exclusion remains. Narrow foot/bicycle/hgv key grammar only; car/general/unknown/lane/relation policy remains. No road graph/native constructor/PBF/provider/app DB, cost fit, routing or deployment. Captured eligibility changes are not national connectivity/ETA/permission or native parity acceptance. Host-only deadline/RSS checks do not establish cgroup/CPU/swap admission.'}
        save('report.json',report);print(json.dumps({k:report[k] for k in ['status','counts','records','hostSecondsIncludingSourceHashes']}))
    except BaseException as error:
        save('failure.json',{'error':str(error),'hostSeconds':time.monotonic()-began});raise


if __name__=='__main__':main()
