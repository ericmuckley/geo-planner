"""Compare the native policy port with frozen Python policy on captured metadata."""
from array import array
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sqlite3

from coarse_osm_car_native_policy_v1 import NativePolicy
from coarse_osm_car_policy_v1 import POLICY, node_policy, restriction_policy, way_policy
from coarse_timing_input import require


def compare(native, kind, tags, members=()):
    actual = native.classify(kind, tags, members)
    if kind == 'way':
        expected = asdict(way_policy(tags))
    elif kind == 'node':
        result = node_policy(tags)
        expected = {key: result[key] for key in ('blocked', 'signal', 'tagged')}
    else:
        result = restriction_policy({'id': 1, 'tags': tags, 'members': members})
        expected = {key: result.get(key, 0 if key in ('fromWay', 'via', 'toWay') else None)
                    for key in ('status', 'kind', 'fromWay', 'via', 'toWay', 'reason')}
    require(actual == expected, f'Native policy metadata mismatch: {kind}')


def run(native, repo, check=lambda: None):
    root = repo / 'data/coarse-quality/us-osm-disk-capture-run-v1/extract'
    path = root / 'audit-selected.sqlite'
    receipt = json.loads((repo / 'docs/evidence/coarse-osm-extraction-2026-10-30/disk-capture-closed-run-v1.json').read_bytes())
    pin = receipt['roster']['extract/audit-selected.sqlite']
    require(path.stat().st_size == pin['bytes'], 'Policy equivalence SQLite size')
    with path.open('rb') as stream:
        require(hashlib.file_digest(stream, 'sha256').hexdigest() == pin['sha256'], 'Policy equivalence sealed SQLite')
    db = sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)
    db.execute('PRAGMA query_only=ON')
    db.execute('PRAGMA cache_size=-16384')
    selected = array('I')
    selected.frombytes((repo / 'data/coarse-quality/us-osm-lineage-run-v1/provenance/selected-nodes.u32').read_bytes())
    ids = array('q', (row[0] for row in db.execute("SELECT id FROM objects WHERE kind='node' ORDER BY id")))
    require(len(ids) == 1123919 and len(selected) == 143560, 'Policy equivalence node denominators')
    counts = {'selectedNodes': 0, 'majorWays': 0, 'relations': 0, 'sourceWaysExamined': 0}
    for ordinal in selected:
        if counts['selectedNodes'] % 1024 == 0:
            check()
        element = json.loads(db.execute("SELECT raw FROM objects WHERE kind='node' AND id=?", (ids[ordinal],)).fetchone()[0])
        compare(native, 'node', element['tags'])
        counts['selectedNodes'] += 1
    for _, raw in db.execute("SELECT id,raw FROM objects WHERE kind='way' ORDER BY id"):
        counts['sourceWaysExamined'] += 1
        if counts['sourceWaysExamined'] % 1024 == 0:
            check()
        element = json.loads(raw)
        if element['tags'].get('highway') in POLICY['roles']:
            compare(native, 'way', element['tags'])
            counts['majorWays'] += 1
    for _, raw in db.execute("SELECT id,raw FROM objects WHERE kind='relation' ORDER BY id"):
        element = json.loads(raw)
        compare(native, 'relation', element['tags'], element['members'])
        counts['relations'] += 1
    db.close()
    require(counts == {'selectedNodes': 143560, 'majorWays': 28995, 'relations': 4900, 'sourceWaysExamined': 239253}, 'Policy equivalence complete source denominators')
    return {'status': 'passed_complete_captured_metadata_native_policy_equivalence', **counts,
            'sourcePbfReads': 0, 'networkRequests': 0, 'applicationDbReads': 0,
            'nationalArtifactBuilt': False, 'etaQualified': False, 'vercelQualified': False, 'modelChanged': False}
