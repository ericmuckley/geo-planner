"""Choose a local candidate from every reached cut and its remaining time."""

import math


EARTH_METERS = 6371008.8  # Same sphere as import_roads.distance_m.
MAX_SPEED_KPH = 160  # import_roads.speed_kph rejects higher explicit values.


def plan(records, current_bounds, parent_bounds, budget_ms=7200000):
    if budget_ms <= 0: raise ValueError("Expected a positive budget")
    boxes, nodes = [], set()
    for record in records:
        lon, lat = record["point"]
        if not -180 <= lon <= 180 or not -90 <= lat <= 90: raise ValueError("Invalid cut coordinate")
        for witness in record["origins"].values():
            cost = witness["costMs"]
            if cost is None: continue
            if cost < 0: raise ValueError("Negative cut cost")
            if cost > budget_ms: continue
            nodes.add(record["node"])
            angle = (budget_ms - cost) * MAX_SPEED_KPH / 3600 / EARTH_METERS
            low, high = max(-90, lat - math.degrees(angle)), min(90, lat + math.degrees(angle))
            if low == -90 or high == 90:
                west, east = -180, 180
            else:
                span = math.degrees(math.asin(min(1, math.sin(angle) / math.cos(math.radians(lat)))))
                west, east = lon - span, lon + span
                if west < -180 or east > 180: west, east = -180, 180
            boxes.append([west, low, east, high])
    envelope = [min([current_bounds[i]] + [box[i] for box in boxes]) for i in (0, 1)] + [max([current_bounds[i]] + [box[i] for box in boxes]) for i in (2, 3)]
    rounded = [math.floor(envelope[i] * 10) / 10 for i in (0, 1)] + [math.ceil(envelope[i] * 10) / 10 for i in (2, 3)]
    candidate = [max(rounded[i], parent_bounds[i]) for i in (0, 1)] + [min(rounded[i], parent_bounds[i]) for i in (2, 3)]
    clipped = [side for i, side in enumerate(("west", "south", "east", "north")) if candidate[i] != rounded[i]]
    return {"budgetMs": budget_ms, "reachedCutNodes": len(nodes), "originCutPairs": len(boxes), "maxSpeedKph": MAX_SPEED_KPH,
            "earthRadiusMeters": EARTH_METERS, "envelopeBounds": envelope, "roundedBounds": rounded,
            "candidateBounds": candidate, "clippedSides": clipped, "envelopeContainedInParent": not clipped,
            "coverageVerified": False,
            "scope": "Remaining-time spherical envelopes for every recorded reachable cut, using the static model's maximum supported speed and nonnegative costs. Retains existing margins, rounds outward to 0.1 degree, then clips to cached parent. Conditional on unchanged interior prefixes/topology; not a coverage certificate. Source gaps and newly restored restrictions/roads require fresh qualification."}
