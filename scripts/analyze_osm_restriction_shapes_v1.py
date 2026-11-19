"""One bounded saved-metadata inventory; no source constructor or graph read."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

from coarse_osm_restriction_shapes_v1 import classify


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(recipe, pin):
    began = time.monotonic()
    repo = Path(__file__).resolve().parents[1]
    assert sha(recipe) == pin
    plan = json.loads(recipe.read_bytes())
    assert plan['output'] == 'data/coarse-quality/us-osm-restriction-shapes-v1'
    assert plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+8388608 < 72*1024**3
    for name, expected in plan['bindings'].items():
        assert sha(repo/name) == expected, name
    root = repo/plan['output']
    root.mkdir()
    (root/'execution-plan.json').write_bytes(recipe.read_bytes())
    try:
        results = []
        for source in plan['sources']:
            filename = repo/source['path']
            assert filename.is_file() and not filename.is_symlink() and filename.stat().st_size == source['bytes'] <= 32*1024**2
            digest = hashlib.sha256(); selected = hashlib.sha256()
            counts, kinds = Counter(), Counter()
            rows = 0
            with filename.open('rb') as stream:
                for line in stream:
                    assert len(line) <= 8388608
                    digest.update(line)
                    raw = json.loads(line)
                    element = raw['element'] if 'element' in raw else raw
                    shape, members = classify(element)
                    counts[shape] += 1
                    if members is not None:
                        selected.update(json.dumps([element['id'], shape, members], separators=(',', ':')).encode()+b'\n')
                    if shape == 'static-single-via-way-only':
                        tags = element['tags']
                        kind = next(tags[k] for k in ('restriction:motorcar','restriction:motor_vehicle','restriction:vehicle','restriction') if k in tags)
                        kinds[kind] += 1
                    rows += 1
                    assert rows <= source['rows']
                    if rows % 1024 == 0:
                        assert time.monotonic()-began < 120
                        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform == 'darwin' else 1024)
                        assert rss < 4*1024**3
            assert rows == source['rows'] and digest.hexdigest() == source['sha256']
            results.append({'source':source['path'], 'rows':rows, 'shapes':dict(counts), 'staticSingleViaOnlyKinds':dict(kinds), 'selectedIdentityShapeDigest':selected.hexdigest()})
        report = {'status':'saved_restriction_shapes_inventory_complete', 'recipeSha256':pin,
                  'sources':results, 'hostSecondsIncludingBindingsReadClassifyAndWrite':time.monotonic()-began,
                  'sourcePbfReads':0, 'countryGraphReads':0, 'queries':0, 'policyActivated':False,
                  'scope':'Complete saved national unsupported-relation and captured relation metadata shape counts only. A static single-via-way only shape is a potential prototype,not permission,join resolution,causal detour diagnosis or accuracy improvement. Every current closure remains. No coordinates/source constructor/query/provider/DB/app/parameter fit.'}
        (root/'report.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report))
    except BaseException as error:
        (root/'failure.json').write_text(json.dumps({'error':repr(error),'hostSeconds':time.monotonic()-began})+'\n')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe', type=Path); parser.add_argument('pin')
    args = parser.parse_args(); run(args.recipe, args.pin)
