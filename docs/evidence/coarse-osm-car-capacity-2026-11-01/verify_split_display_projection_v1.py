"""Independently recompute saved-frame allocation projections, not memory/accuracy."""
import json
import math

from verify_advisory_timing_screen_v1 import verify as previous
from verify_preparation_v1 import HERE, REPO, load, sha


CAP = 67108864


def frame(bounds, step):
    west = math.floor(bounds[0]*1e6/step)*step
    south = math.floor(bounds[1]*1e6/step)*step
    east = math.ceil(bounds[2]*1e6/step)*step
    north = math.ceil(bounds[3]*1e6/step)*step
    return dict(west=west, south=south, step=step, width=round((east-west)/step), height=round((north-south)/step))


def sizes(field, f):
    n = f['width']*f['height'];w=f['width'];h=f['height']
    raster = 2*n+w+h+1
    return field+raster+12*4096, raster+4*math.ceil(n/8)+2*math.ceil(n/2)+2*w+4*h+8000000


def verify():
    result = previous()
    plan = load(HERE/'split-display-capacity-plan-v1.json')
    for name, pin in plan['bindings'].items():
        assert sha(REPO/name) == pin, name
    report = load(HERE/'split-display-capacity-projection-v1.json')
    assert report['recipeSha256'] == sha(HERE/'split-display-capacity-plan-v1.json')
    candidate = load(HERE/'inactive-conditional-evaluation-v1-raw-v1/report.json')
    originals = [(i, item, minutes) for i, phase in enumerate(candidate['phases'])
                 for item, minutes in [(phase['diagnostic'],900), *[(p,p['minutes']) for p in phase['productions']]]]
    assert len(originals) == len(report['rows']) == 58
    for row, (index, old, minutes) in zip(report['rows'], originals):
        assert row['originIndex'] == index and row['minutes'] == minutes
        f=old['frame'];bounds=[f['west']/1e6,f['south']/1e6,(f['west']+f['width']*f['step'])/1e6,(f['south']+f['height']*f['step'])/1e6]
        selected = frame(bounds,row['projectedStepE6'])
        assert selected == row['projectedFrame']
        assert row['fieldPeakBytes'] == old['fieldStats']['maximumBackingBufferBytes']
        seed, fill = sizes(row['fieldPeakBytes'],selected)
        assert seed == row['projectedSeedPhaseBytes'] <= CAP
        assert fill == row['projectedFillPhaseBytes'] <= CAP
        assert selected['width']*selected['height'] == row['projectedCells']
        assert f['width']*f['height'] == row['oldCells']
        if row['projectedStepE6'] > 5000:
            before=frame(bounds,row['projectedStepE6']-1)
            assert max(sizes(row['fieldPeakBytes'],before)) > CAP
    assert report['finerProjectedFrames'] == sum(r['projectedStepE6'] < r['oldStepE6'] for r in report['rows'])
    assert report['finestExistingStepProjectedFrames'] == sum(r['projectedStepE6'] == 5000 for r in report['rows'])
    assert not report['isMemoryMeasurementOrAccuracyEvaluation'] and not report['prototypeImplemented']
    assert report['graphQueries'] == report['newMaps'] == report['providerRequests'] == 0
    return {**result, 'status': 'all58_split_display_capacity_forecasts_independently_recomputed',
            'projectedFinerFrames': report['finerProjectedFrames'],
            'projectedMaximumCells': report['maximumProjectedCells'],
            'splitRendererImplementedOrMeasured': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
