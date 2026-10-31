"""One frozen lossless storage experiment on saved preflight arrays, not a router."""
import argparse
from array import array
import gzip
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

from coarse_backbone_codec import decode_signed32, encode_signed32
from coarse_census import ROOT

PLAN = ROOT/'docs/evidence/coarse-backbone-preflight-2026-10-25/codec-plan.json'
PLAN_SHA = '4f397a310ccc134d4b9ce22f0ce13fefb1cb9304f6fb521c3baf548ed6b0a0c0'


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(1048576):
            result.update(block)
    return result.hexdigest()


def run(output):
    started = time.perf_counter()
    assert digest(PLAN) == PLAN_SHA
    plan = json.loads(PLAN.read_text())
    for name, expected in plan['inputs'].items():
        assert digest(ROOT/name) == expected, name
    old = json.loads((ROOT/'data/coarse-quality/census-backbone-preflight-v1/report.json').read_text())
    assert old['advanceToRoutingPrototype'] is False and old['gates']['projectedFunction'] is False
    for record in old['packedArrays'].values():
        assert digest(ROOT/record['path']) == record['sha256']
    output = output.resolve()
    assert output.is_relative_to(ROOT/'data/coarse-quality')
    output.mkdir()
    (output/'plan.json').write_bytes(PLAN.read_bytes())
    source = ROOT/old['packedArrays']['pointDeltas']['path']
    target = output/'pointDeltas.signed32-varint.gz'
    source_hash = hashlib.sha256()
    encoded_bytes = count = 0
    with gzip.open(source,'rb') as stream, target.open('wb') as packed_file:
        with gzip.GzipFile(fileobj=packed_file, mode='wb', filename='', mtime=0, compresslevel=6) as compressed:
            while raw := stream.read(1048576):
                assert len(raw)%4 == 0
                source_hash.update(raw)
                values = array('i'); values.frombytes(raw)
                if sys.byteorder != 'little':
                    values.byteswap()
                encoded = encode_signed32(values)
                compressed.write(encoded)
                encoded_bytes += len(encoded)
                count += len(values)
    assert count == plan['expectedValues']
    restored_hash = hashlib.sha256()
    restored = array('i')
    decoded_count = 0
    with gzip.open(target,'rb') as stream:
        blocks = iter(lambda:stream.read(1048576),b'')
        for value in decode_signed32(blocks,plan['expectedValues']):
            restored.append(value)
            decoded_count += 1
            if len(restored) == 262144:
                if sys.byteorder != 'little':
                    restored.byteswap()
                restored_hash.update(restored.tobytes())
                restored = array('i')
    if sys.byteorder != 'little':
        restored.byteswap()
    restored_hash.update(restored.tobytes())
    assert decoded_count == count and restored_hash.digest() == source_hash.digest()
    old_size = old['packedArrays']['pointDeltas']['base64Bytes']
    base64_size = 4*((target.stat().st_size+2)//3)
    # Retain the original4MiB integration reserve plus an extra1KiB format description.
    forecast = old['storageForecast']['projectedFunctionBytes']-old_size+base64_size+1024
    for record in old['packedArrays'].values():
        assert digest(ROOT/record['path']) == record['sha256']
    elapsed = time.perf_counter()-started
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform == 'darwin' else 1024)
    gates = {'integerStreamExact':True,'allOtherArraysUnchanged':True,
             'existingConnectivity':old['gates']['largestComponent'],
             'existingEndpointProximity':old['gates']['endpointProximity'],
             'projectedFunction':forecast <= plan['gates']['maximumProjectedFunctionBytes'],
             'producerTime':elapsed <= plan['gates']['maximumSeconds'],
             'producerRss':rss <= plan['gates']['maximumProducerRssBytes']}
    report = {'planSha256':PLAN_SHA,'sourcePreflightPlanSha256':old['planSha256'],
              'sourceRawInt32Sha256':source_hash.hexdigest(),'restoredRawInt32Sha256':restored_hash.hexdigest(),
              'values':count,'decodedValues':decoded_count,'uncompressedVarintBytes':encoded_bytes,
              'file':{'path':str(target.relative_to(ROOT)),'sha256':digest(target),'bytes':target.stat().st_size,'base64Bytes':base64_size},
              'originalProjectedFunctionBytes':old['storageForecast']['projectedFunctionBytes'],
              'projectedFunctionBytes':forecast,'integrationReserveBytes':plan['gates']['preserveOriginalIntegrationReserveBytes'],
              'gates':gates,'advanceToRuntimeDesign':all(gates.values()),
              'originalStorageFailurePreserved':True,'newSourcePasses':0,'providerRequests':0,'runtimeChanged':False,
              'wallSeconds':elapsed,'producerMaxRssBytes':rss,
              'scope':'Byte-exact integer-stream encoding and storage forecast only. No topology/geometry/cost/index/source/query change, routing comparison, app integration, cloud memory/latency/package qualification or accuracy claim. Future bounded geometry decoder/index remains to implement.'}
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(run(args.output),indent=2))
