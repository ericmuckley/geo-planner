"""Two bounded official Ubuntu index GETs to propose one runtime package, never fetch it."""
import hashlib
import http.client
import json
import lzma
from pathlib import Path
import signal
import ssl
import sys
import time


def inspect(plan, root):
    root = Path(root); root.mkdir(); records = []; began = time.monotonic()
    def deadline(*_): raise TimeoutError('Metadata inspection deadline')
    signal.signal(signal.SIGALRM, deadline); signal.setitimer(signal.ITIMER_REAL, 60)
    try:
        bodies = []
        for i, spec in enumerate(plan['requests'], 1):
            connection = http.client.HTTPSConnection('ports.ubuntu.com', timeout=15, context=ssl.create_default_context())
            record = {'path': spec['path'], 'method': 'GET', 'deliveredBytes': 0, 'status': 'attempted'}; records.append(record)
            (root / 'ledger.json').write_text(json.dumps(records, indent=2)+'\n')
            try:
                connection.request('GET', spec['path'], headers={'Accept-Encoding': 'identity', 'User-Agent': 'geo-planner-runtime-metadata/2'})
                response = connection.getresponse(); record['httpStatus'] = response.status
                record['headers'] = response.getheaders()
                with (root / f'{i:03d}.bin').open('xb') as stream:
                    while True:
                        chunk = response.read1(min(65536, spec['maxBytes'] + 1 - record['deliveredBytes']))
                        if not chunk: break
                        stream.write(chunk); record['deliveredBytes'] += len(chunk)
                        if record['deliveredBytes'] > spec['maxBytes']: raise ValueError('Metadata body cap')
                if response.status != 200: raise ValueError('Metadata HTTP refusal; no redirect or retry')
                raw = (root / f'{i:03d}.bin').read_bytes(); record['sha256'] = hashlib.sha256(raw).hexdigest(); record['status'] = 'complete'; bodies.append(raw)
            finally:
                connection.close(); (root / 'ledger.json').write_text(json.dumps(records, indent=2)+'\n')
        release, compressed = bodies
        expected = [line.split() for line in release.decode().split('SHA256:\n', 1)[1].splitlines() if line.strip().endswith(' main/binary-arm64/Packages.xz')]
        if len(expected) != 1 or expected[0][0] != hashlib.sha256(compressed).hexdigest() or int(expected[0][1]) != len(compressed): raise ValueError('Publisher Release/index size/SHA binding')
        decoder = lzma.LZMADecompressor(memlimit=67108864); raw = decoder.decompress(compressed, max_length=67108865)
        if len(raw)>67108864 or not decoder.eof or decoder.unused_data: raise ValueError('Metadata decompression cap/framing')
        candidates = []
        for stanza in raw.decode().split('\n\n'):
            fields = dict(line.split(': ', 1) for line in stanza.splitlines() if ': ' in line and not line.startswith(' '))
            if fields.get('Package') == 'libexpat1' and fields.get('Architecture') == 'arm64': candidates.append(fields)
        if len(candidates) != 1: raise ValueError('Expected one arm64 runtime candidate')
        (root / 'package-candidate.json').write_text(json.dumps({'package':candidates[0], 'indexBytes':len(compressed),'expandedIndexBytes':len(raw),
            'indexSha256':hashlib.sha256(compressed).hexdigest(),'indexBoundToRelease':True,'repositorySignatureVerified':False,
            'elapsedSecondsBeforeCandidateWrite':time.monotonic()-began,'packageBinaryFetched':False},indent=2)+'\n')
    except Exception as error:
        (root / 'failure.json').write_text(json.dumps({'errorType':type(error).__name__,'error':str(error),'binaryFetched':False},indent=2)+'\n');raise
    finally: signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == '__main__':
    plan_path, expected, root = sys.argv[1:]
    if hashlib.sha256(Path(plan_path).read_bytes()).hexdigest() != expected: raise ValueError('Metadata plan SHA binding')
    plan = json.loads(Path(plan_path).read_text())
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != plan['scriptSha256']: raise ValueError('Metadata inspector SHA binding')
    if plan['requests'] != [{'path':'/ubuntu-ports/dists/jammy-security/Release','maxBytes':1048576},{'path':'/ubuntu-ports/dists/jammy-security/main/binary-arm64/Packages.xz','maxBytes':8388608}]: raise ValueError('Metadata-only endpoint/cap drift')
    inspect(plan,root)
