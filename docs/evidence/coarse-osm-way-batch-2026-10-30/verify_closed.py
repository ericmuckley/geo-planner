"""Check sealed batch evidence, then saved receipts or optional local witnesses."""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import sys

parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--local-assets',action='store_true');args=parser.parse_args()
root=Path(__file__).resolve().parent
for name,pin in json.loads((root/'sha256.json').read_text()).items():
    with (root/name).open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==pin,name
previous=sys.argv
try:
    sys.argv=[str(root/'verify_measurement.py')]+(['--local-assets'] if args.local_assets else [])
    with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(sys.argv[0],run_name='__main__')
finally:sys.argv=previous
print(json.dumps({'closedBatchEvidenceVerified':True,'allCoordinatesLocallyVerified':args.local_assets,'nationalPbfRead':False}))
