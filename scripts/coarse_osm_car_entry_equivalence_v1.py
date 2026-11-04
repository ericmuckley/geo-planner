"""Compare the typed native pipeline with the sealed captured correction."""
import hashlib
import json
from pathlib import Path
import shutil
import struct
import time

from coarse_osm_car_packed_native_v1 import NativePacked
from coarse_osm_entry_graph_v1 import plan_entries
from coarse_osm_entry_records_v1 import ENTRY
from coarse_osm_restriction_entry_v1 import entry_restriction
from coarse_osm_car_policy_v1 import restriction_policy


def run(native, repo, check):
    began = time.monotonic()
    root = Path('/work')
    closed = json.loads((repo/'docs/evidence/coarse-osm-car-capacity-2026-11-01/graph-capture-closed-run-v5.json').read_bytes())
    source = repo/closed['root']/'cost-facts'
    roster = closed['roster']
    def read(name):
        pin = roster['cost-facts/'+name]
        path = source/name
        assert path.is_file() and not path.is_symlink() and path.stat().st_size == pin['bytes']
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == pin['sha256']
        check()
        return raw
    ways = list(struct.iter_unpack('<QddII', read('ways-0000.bin')))
    raw_arcs = list(struct.iter_unpack('<IIIIIb3xQ', read('arcs-0000.bin')))
    facts = json.loads((repo/closed['root']/'cost-facts-summary.json').read_bytes())
    assert len(ways) == 28995 and len(raw_arcs) == 78811
    raw_relations = (repo/closed['root']/'deferred-relations.jsonl').read_bytes()
    pin = roster['deferred-relations.jsonl']
    assert len(raw_relations) == pin['bytes'] and hashlib.sha256(raw_relations).hexdigest() == pin['sha256']
    elements = [json.loads(line)['element'] for line in raw_relations.splitlines()]
    assert len(elements) == 4900
    reference = plan_entries(elements, [{'tail': a[0], 'head': a[1], 'way': ways[a[2]][0]} for a in raw_arcs])
    rules_path, fallback_path = root/'rules.bin', root/'fallback.u64'
    candidates, fallback = [], set()
    for e in elements:
        r = restriction_policy(e)
        if r['status'] != 'closed-unsupported':
            continue
        c = entry_restriction(e)
        if c:
            candidates.append(c)
        else:
            fallback.update(r['memberWays'])
    rules_path.write_bytes(b''.join(ENTRY.pack(c.identity, c.from_way, c.via_way, c.to_way) for c in candidates))
    fallback_path.write_bytes(b''.join(struct.pack('<Q', n) for n in sorted(fallback)))
    resolved = root/'resolved'
    resolved.mkdir()
    counts = native.resolve(source, rules_path, fallback_path, resolved,
                            [len(ways), facts['anchors'], len(raw_arcs), len(candidates), len(fallback)])
    actual_closed = {r[0] for r in struct.iter_unpack('<Q', (resolved/'closures-0000.bin').read_bytes())}
    actual_pairs = set(struct.iter_unpack('<II', (resolved/'entry-pairs-pre.u32').read_bytes()))
    assert actual_closed == reference['closed'] and actual_pairs == reference['pairs']
    assert counts[0] == 461 and counts[1] == len(reference['converted']) == 295
    # Tiny captured qualification copies6.87MB; national execution will use a
    # separately bound read-only fact view, never copy the1.37GB source facts.
    view = root/'view'
    view.mkdir()
    for name in sorted(roster):
        if not name.startswith('cost-facts/') or name.startswith('cost-facts/closures-'):
            continue
        body = read(Path(name).name)
        (view/Path(name).name).write_bytes(body)
    shutil.copyfile(resolved/'closures-0000.bin', view/'closures-0000.bin')
    base = root/'base-routing'
    base.mkdir()
    packed = NativePacked(native.path, native.sha256)
    packed_result = packed.encode(view, base, [facts['selectedNodes'], facts['anchors'], len(ways), len(raw_arcs), counts[-1], facts['supportedViaNodeRules']])
    augmented = root/'augmented-forbidden.u24'
    augmentation = native.augment(source, resolved/'closures-0000.bin', resolved/'entry-pairs-pre.u32', base, augmented,
                                 [len(ways), facts['anchors'], len(raw_arcs), counts[-1]])
    expected_root = repo/'data/coarse-quality/us-osm-car-restriction-entry-capture-v1'
    expected = json.loads((expected_root/'artifacts.json').read_bytes())
    checked = 0
    for name, pin in expected.items():
        actual = augmented if name.endswith('forbidden-turns.u24') else base/Path(name).name
        raw = actual.read_bytes()
        assert len(raw) == pin['bytes'] and hashlib.sha256(raw).hexdigest() == pin['sha256']
        checked += len(raw)
    assert checked == 1037031 and augmentation[2] == 271 and augmentation[-2] == 2650
    return {'status': 'typed_native_entry_pipeline_matches_captured_source_replayed_candidate',
            'resolvedCounts': counts, 'augmentationCounts': augmentation,
            'filesByteIdentical': len(expected), 'bytesIndependentlyCompared': checked,
            'capturedQueryProofCasesBound': 82, 'queriesExecutedHere': 0,
            'basePackedResult': packed_result, 'hostFunctionalSeconds': time.monotonic()-began,
            'sourcePbfReads': 0, 'sourceConstructorExecutions': 0, 'providerRequests': 0,
            'countryOrEtaOrAppQualified': False}
