"""Describe all still-static fallback shapes from closed metadata, without routing."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time

from coarse_osm_restriction_shapes_v1 import classify


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(recipe, pin):
    began = time.monotonic(); repo = Path(__file__).resolve().parents[1]
    assert sha(recipe) == pin
    plan = json.loads(recipe.read_bytes())
    assert plan['output'] == 'data/coarse-quality/us-osm-restriction-fallbacks-v1'
    assert plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+8388608 < 72*1024**3
    for name, expected in plan['bindings'].items():
        assert sha(repo/name) == expected
    root = repo/plan['output']; root.mkdir()
    (root/'execution-plan.json').write_bytes(recipe.read_bytes())
    try:
        results = []
        for source in plan['sources']:
            filename = repo/source['path']
            assert filename.is_file() and not filename.is_symlink() and filename.stat().st_size == source['bytes'] <= 32*1024**2
            digest = hashlib.sha256(); shapes = Counter(); signatures = Counter(); rows = 0
            with filename.open('rb') as stream:
                for line in stream:
                    assert len(line) <= 8388608 and time.monotonic()-began < 120
                    digest.update(line); raw = json.loads(line)
                    element = raw['element'] if 'element' in raw else raw
                    shape, _ = classify(element); shapes[shape] += 1; rows += 1
                    assert rows <= source['rows']
                    if shape != 'other-static-fallback': continue
                    tags = element['tags']
                    kind = next((tags[k] for k in ('restriction:motorcar','restriction:motor_vehicle','restriction:vehicle','restriction') if k in tags), None)
                    members = Counter((m['role'], m['type']) for m in element['members'])
                    signature = json.dumps([kind, sorted((role,typ,count) for (role,typ), count in members.items())], separators=(',', ':'))
                    signatures[signature] += 1
                    assert len(signatures) <= 10000
            assert rows == source['rows'] and digest.hexdigest() == source['sha256']
            assert sum(signatures.values()) == shapes['other-static-fallback']
            results.append({'source':source['path'], 'rows':rows, 'shapes':dict(shapes),
                            'otherStaticFallbackSignatures':[{'kind':json.loads(key)[0], 'memberRoleTypeCounts':json.loads(key)[1], 'relations':count}
                                                             for key, count in signatures.most_common()]})
        report = {'status':'saved_static_fallback_signatures_complete', 'recipeSha256':pin, 'sources':results,
                  'hostSecondsIncludingBindingReadClassifyAndWrite':time.monotonic()-began,
                  'sourcePbfReads':0,'countryGraphReads':0,'queries':0,'policyActivated':False,
                  'scope':'Complete count of remaining static fallback kind/member-role/type arities only;member sequence is not inferred from sorted signature. No permissions,joins,geometry,causal detour diagnosis,graph,query,accuracy or app admission.'}
        (root/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
    except BaseException as error:
        (root/'failure.json').write_text(json.dumps({'error':repr(error),'hostSeconds':time.monotonic()-began})+'\n');raise


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe',type=Path);parser.add_argument('pin')
    args=parser.parse_args();run(args.recipe,args.pin)
