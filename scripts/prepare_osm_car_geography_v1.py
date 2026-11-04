"""Extract unchanged small geography from pinned v9; no road regeneration."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import time


def sha(raw):return hashlib.sha256(raw).hexdigest()


def prepare(recipe,pin):
    began=time.monotonic();repo=Path(__file__).resolve().parents[1]
    raw_recipe=recipe.read_bytes();assert sha(raw_recipe)==pin;plan=json.loads(raw_recipe)
    assert plan['source']=='src/server/data/coarse-grid-v9.json' and plan['sourceSha256']=='28271c809a04cdfab41ad735ad66b29e3875179b617198b7b1d4490533439bf6'
    assert plan['output']=='data/coarse-quality/us-osm-car-geography-v1'
    for name,expected in plan['bindings'].items():assert sha((repo/name).read_bytes())==expected,name
    root=repo/plan['output'];root.mkdir();(root/'execution-plan.json').write_bytes(raw_recipe)
    def save(name,value):
        with (root/name).open('x') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')
    try:
        source=repo/plan['source'];assert source.stat().st_size<70000000
        raw=source.read_bytes();assert sha(raw)==plan['sourceSha256'];grid=json.loads(raw)
        geo={key:grid[key] for key in ('bounds','boundary','lakes')}
        assert geo['bounds']==[-125,24,-66,50] and len(geo['boundary'])==149 and len(geo['lakes'])==110
        polygons=geo['boundary']+geo['lakes'];rings=sum(len(p) for p in polygons);points=sum(len(r) for p in polygons for r in p)
        assert rings==312 and points==27784 and all(len(r)>=4 and r[0]==r[-1] for p in polygons for r in p)
        encoded=json.dumps(geo,separators=(',',':'),allow_nan=False).encode();assert len(encoded)<1048576
        compressed=gzip.compress(encoded,compresslevel=9,mtime=0)
        with (root/'geography.json.gz').open('xb') as stream:stream.write(compressed)
        manifest={'format':'coarse-boundary-lakes-json-gzip-v1','sourceSha256':plan['sourceSha256'],'file':'geography.json.gz',
                  'rawBytes':len(encoded),'rawSha256':sha(encoded),'compressedBytes':len(compressed),'compressedSha256':sha(compressed)}
        save('manifest.json',manifest)
        save('report.json',{'status':'host_unchanged_geography_extracted_independent_audit_pending','bounds':geo['bounds'],
                           'boundaryPolygons':149,'lakePolygons':110,'rings':rings,'points':points,'rawBytes':len(encoded),'compressedBytes':len(compressed),
                           'secondsHostExtraction':time.monotonic()-began,'sourceCoordinatesChanged':False,'modelChanged':False,
                           'scope':'Host JSON subset extraction from existing pinned app asset only. No PBF/road construction, new coastline/source data, connector or app admission.'})
        print(json.dumps({'rawBytes':len(encoded),'compressedBytes':len(compressed),'points':points}))
    except BaseException as error:
        save('failure.json',{'error':str(error),'secondsHost':time.monotonic()-began});raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe',type=Path);parser.add_argument('pin');args=parser.parse_args();prepare(args.recipe,args.pin)
