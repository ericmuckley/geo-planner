"""Inventory narrow no-turns absent from a complete small pre-closure graph."""
import argparse
from array import array
import hashlib
import json
from pathlib import Path
import resource
import struct
import sys
import time

from coarse_osm_absent_entry_v1 import plan_entries
from coarse_osm_entry_graph_v1 import plan_entries as previous_plan
from coarse_osm_restriction_entry_v1 import entry_restriction
from coarse_osm_packed_capture_v1 import ARC, WAY


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def stat_key(path):
    s = path.stat()
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe', type=Path)
    parser.add_argument('pin')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    began = time.monotonic()
    assert sha(args.recipe) == args.pin
    plan = json.loads(args.recipe.read_bytes())
    assert plan['output'] == 'data/coarse-quality/us-osm-absent-entry-capture-inventory-v1'
    assert plan['controlsPassed'] == 20 and plan['expectedPreArcs'] == 79118
    assert plan['priorReserveBytes'] + plan['newClosedAllocationBytes'] + plan['metadataScratchReserveBytes'] + 8388608 < 72*1024**3
    for name, pin in plan['bindings'].items():
        assert sha(repo/name) == pin, name
    before = {name: stat_key(repo/name) for name in plan['dataFiles']}
    assert sum((repo/name).stat().st_size for name in before) <= 24*1048576
    root = repo/plan['output']
    root.mkdir()
    (root/'execution-plan.json').write_bytes(args.recipe.read_bytes())
    def check():
        assert time.monotonic()-began < 120
        assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform == 'darwin' else 1024) < 4*1024**3
    try:
        def rows(names, shape):
            out = []
            for name in names:
                check()
                path = repo/name
                assert path.is_file() and not path.is_symlink() and path.stat().st_size <= 16777216
                with path.open('rb') as stream:
                    while raw := stream.read(shape.size*16384):
                        assert len(raw) % shape.size == 0
                        out.extend(shape.iter_unpack(raw))
            return out
        ways = rows(plan['ways'], WAY)
        arcs = rows(plan['arcs'], ARC)
        assert len(ways) == 28995 and len(arcs) == plan['expectedPreArcs']
        assert len({w[0] for w in ways}) == len(ways)
        pre = []
        for row in arcs:
            assert row[2] < len(ways)
            pre.append({'tail': row[0], 'head': row[1], 'way': ways[row[2]][0]})
        elements = []
        with (repo/plan['relations']).open() as stream:
            for line in stream:
                assert len(line) <= 4*1048576
                elements.append(json.loads(line)['element'])
        assert len(elements) == 4900
        source_closed = {r[0] for r in rows(plan['closures'], struct.Struct('<Q'))}
        old = previous_plan(elements, pre)
        new = plan_entries(elements, pre, plan['expectedPreArcs'])
        assert old['oldClosed'] == new['oldClosed'] == source_closed
        old_active = sum(a['way'] not in old['closed'] for a in pre)
        new_active = sum(a['way'] not in new['closed'] for a in pre)
        assert old_active == 76722 and new_active >= old_active
        present = {a['way'] for a in pre}
        way_ids = {w[0] for w in ways}
        by_id = {e['id']: e for e in elements}
        audits = []
        for item in new['inactive']:
            check()
            rule = entry_restriction(by_id[item['id']])
            assert rule is not None
            absent = sorted({rule.from_way, rule.via_way, rule.to_way} - present)
            assert absent == item['absentEssentialWays'] and absent
            audits.append({**item, 'outsideSelectedWayRows': [w for w in absent if w not in way_ids],
                           'selectedWaysWithNoPreArcs': [w for w in absent if w in way_ids]})
        assert all(stat_key(repo/name) == state for name, state in before.items())
        report = {'status': 'complete_captured_absent_member_no_turn_inventory', 'recipeSha256': args.pin,
                  'relationsChecked': 4900, 'waysChecked': 28995, 'completePreRelationClosureArcs': len(arcs),
                  'previousConverted': len(old['converted']), 'previousFallback': len(old['fallback']),
                  'inactiveNarrowStaticNoTurns': len(audits), 'inactive': audits,
                  'previousClosedWayIds': len(old['closed']), 'newClosedWayIds': len(new['closed']),
                  'newlyOpenedPresentWayIds': sorted((old['closed']-new['closed']) & present),
                  'previousActiveArcs': old_active, 'newActiveArcs': new_active,
                  'existingEntryPairsExact': new['pairs'] == old['pairs'],
                  'sourcePbfReads': 0, 'routingQueries': 0, 'providerRequests': 0, 'appActivated': False,
                  'hostSeconds': time.monotonic()-began,
                  'scope': 'Complete small captured pre-relation-closure facts only, no graph production/search/ETA or nationwide admission. Absence independently checked before ANY relation closure; every other contribution/conditional/only/unknown case retained. Same narrow static no-turn semantics, no speed/coordinate/region rule. Host RSS/deadline only, no cgroup/CPU/swap/cloud admission.'}
        raw = (json.dumps(report, indent=2)+'\n').encode()
        assert len(raw) <= 1048576
        with (root/'report.json').open('xb') as stream:
            stream.write(raw)
        print(json.dumps({k: v for k, v in report.items() if k not in ('inactive', 'newlyOpenedPresentWayIds', 'scope')}))
    except BaseException as error:
        with (root/'failure.json').open('x') as stream:
            json.dump({'error': repr(error), 'hostSeconds': time.monotonic()-began}, stream)
            stream.write('\n')
        raise


if __name__ == '__main__':
    main()
