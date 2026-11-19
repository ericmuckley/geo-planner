"""Separate all83 road-time changes from adaptive-display-grid timing changes."""
import argparse
import hashlib
import json
from pathlib import Path

from review_osm_water_candidate_v1 import review


def changes(previous, current):
    review(previous, current)
    def indexed(report):
        result = {}
        for phase in report['phases']:
            for identity, timing in phase['diagnostic']['timings'].items():
                assert identity not in result
                result[identity] = (timing, phase['diagnostic']['frame'])
        assert len(result) == 83
        return result
    old, new = indexed(previous), indexed(current)
    assert old.keys() == new.keys()
    rows = []
    for identity in old:
        before, old_frame = old[identity]
        after, new_frame = new[identity]
        def delta(key):
            a, b = before[key], after[key]
            return None if a is None or b is None else b-a
        rows.append({'id': identity, 'pointChangeTicks': delta('ticks'),
                     'roadChangeTicks': delta('roadTicks'), 'localGridChangeTicks': delta('localGridTicks'),
                     'sameFrame': old_frame == new_frame, 'previousWinner': before['kind'], 'currentWinner': after['kind']})
    raised = [r for r in rows if r['pointChangeTicks'] is not None and r['pointChangeTicks'] > 0]
    return {'rows': rows, 'cases': 83, 'changedPointTimes': sum(r['pointChangeTicks'] != 0 for r in rows),
            'pointIncreases': raised,
            'pointIncreasesWithNonworseRoadAndChangedFrame': [r['id'] for r in raised if r['roadChangeTicks'] is not None and r['roadChangeTicks'] <= 0 and not r['sameFrame']],
            'roadRegressions': [r['id'] for r in rows if r['roadChangeTicks'] is not None and r['roadChangeTicks'] > 0],
            'casesWithChangedFrame': sum(not r['sameFrame'] for r in rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('previous', 'current', 'output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    old, new = args.previous.read_bytes(), args.current.read_bytes()
    result = changes(json.loads(old), json.loads(new))
    result.update(status='all83_saved_road_and_raster_time_deltas_complete',
                  inputs={str(args.previous): hashlib.sha256(old).hexdigest(), str(args.current): hashlib.sha256(new).hexdigest()},
                  producerSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  providerRequests=0, modelQueries=0, policyChanged=False,
                  scope='Metadata-only diagnosis of all83 frozen cases. Changed frames and local-grid times are observed together, not a controlled causal counterfactual. No new graph/search/map/source/provider/DB operation, fit or policy change. Local-grid time is an approximate representation; this does not establish actual road speeds or national accuracy.')
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('rows', 'inputs', 'scope')}))


if __name__ == '__main__':
    main()
