"""Host-only independent complete byte decode of the paid-geometry storage."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import time

from coarse_osm_packed_codec_audit_v1 import decode

NAMES=['curve-keys.u24','curve-offsets.u32','curve-packets.u8','long-keys.u24',
       'long-lengths.u16','long-overflow-keys.u24','long-overflow-units.u32']


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def run(recipe,pin):
    began=time.monotonic();repo=Path(__file__).resolve().parents[1]
    assert sha(recipe)==pin
    plan=json.loads(recipe.read_bytes())
    assert plan['source']=='data/coarse-quality/us-osm-car-paid-geometry-country-v1'
    assert plan['codec']=='data/coarse-quality/us-osm-car-paid-geometry-codec-v1'
    assert plan['output']=='data/coarse-quality/us-osm-car-paid-geometry-codec-audit-v1'
    for name,expected in plan['bindings'].items():assert sha(repo/name)==expected,name
    output=repo/plan['output'];output.mkdir();(output/'execution-plan.json').write_bytes(recipe.read_bytes())
    try:
        source=repo/plan['source'];codec=repo/plan['codec'];closed=json.loads((repo/plan['closedRecord']).read_bytes())
        manifest_path=codec/'manifest.json';assert sha(manifest_path)==plan['manifestSha256']
        manifest=json.loads(manifest_path.read_bytes());assert manifest['format']=='packed-integer-delta-byteplanes-gzip-v1'
        fields=manifest['fields'];assert set(fields)=={'geometry/'+name for name in NAMES}
        total=compressed_total=0
        for name in NAMES:
            key='geometry/'+name;row=fields[key];original=closed['roster'][key]
            width=3 if name.endswith('.u24') else 4 if name.endswith('.u32') else 2 if name.endswith('.u16') else 1
            assert (row['wordBytes'],row['lanes'])==(width,1) and row['file']=='fields/'+name+'.gz'
            assert row['rawBytes']==original['bytes']<=50331648 and row['rawSha256']==original['sha256']
            path=codec/row['file'];raw_path=source/key
            assert path.is_file() and not path.is_symlink() and path.stat().st_size==row['compressedBytes']<=50331648
            assert raw_path.is_file() and not raw_path.is_symlink() and raw_path.stat().st_size==row['rawBytes']
            assert sha(path)==row['compressedSha256']
            with gzip.open(path,'rb') as stream:encoded=stream.read(row['rawBytes']+1)
            assert len(encoded)==row['rawBytes']
            restored=decode(encoded,width,1)
            assert restored==raw_path.read_bytes() and hashlib.sha256(restored).hexdigest()==original['sha256']
            total+=len(restored);compressed_total+=row['compressedBytes']
            assert total<=50331648 and compressed_total<=50331648 and time.monotonic()-began<60
        result={'status':'independent_complete_paid_geometry_storage_bytes_passed','fields':len(fields),
                'bytesIndependentlyDecodedAndCompared':total,'compressedBytes':compressed_total,
                'secondsHostIndependentDecodeAndComparison':time.monotonic()-began,
                'scope':'Host-only storage proof; no protected Linux/cgroup, source geometry, snapping, ETA or app timing admission.',
                'nativeProducerExecutions':0,'sourcePbfReads':0,'modelChanged':False}
        with (output/'report.json').open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
        print(json.dumps(result))
    except BaseException as error:
        with (output/'failure.json').open('x') as stream:json.dump({'error':str(error),'seconds':time.monotonic()-began},stream);stream.write('\n')
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe',type=Path);parser.add_argument('pin');args=parser.parse_args();run(args.recipe,args.pin)
