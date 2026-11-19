"""Weighted geometry proximity, never a road identity or access decision."""
import math


def exposure(samples, winner, excluded, radii=(0.1, 0.25, 1)):
    assert radii and all(math.isfinite(r) and r > 0 for r in radii)
    assert list(radii) == sorted(set(radii)) and len(excluded) == 2
    all_weights, outside_weights = [], []
    near = {name: {str(r): [] for r in radii} for name in excluded}
    outside_near = {name: {str(r): [] for r in radii} for name in excluded}
    any_weights, both_weights = ({str(r): [] for r in radii} for _ in range(2))
    for point, weight in samples:
        assert len(point) == 2 and all(math.isfinite(v) for v in point)
        assert math.isfinite(weight) and weight > 0
        all_weights.append(weight)
        outside = not winner.within(point, 1)
        if outside:
            outside_weights.append(weight)
        hits = {str(r): 0 for r in radii}
        for name, index in excluded.items():
            # Nested radii let one successful observation certify larger ones.
            first = next((i for i, r in enumerate(radii) if index.within(point, r)), len(radii))
            for r in radii[first:]:
                key = str(r)
                near[name][key].append(weight)
                hits[key] += 1
                if outside:
                    outside_near[name][key].append(weight)
        if outside:
            for key, count in hits.items():
                if count:
                    any_weights[key].append(weight)
                if count == 2:
                    both_weights[key].append(weight)
    return {'referenceSampleKm': math.fsum(all_weights),
            'referenceOutsideWinner1Km': math.fsum(outside_weights),
            'referenceNearExcludedKm': {name: {r: math.fsum(values) for r, values in radii.items()} for name, radii in near.items()},
            'outsideWinner1KmNearExcludedKm': {name: {r: math.fsum(values) for r, values in radii.items()} for name, radii in outside_near.items()},
            'outsideWinner1KmNearAnyExcludedKm': {r: math.fsum(values) for r, values in any_weights.items()},
            'outsideWinner1KmNearBothExcludedClassesKm': {r: math.fsum(values) for r, values in both_weights.items()}}
