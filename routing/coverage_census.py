"""Disk-backed capacity census, not a routing graph or a coverage certificate."""

from collections import Counter
from contextlib import closing
import sqlite3
import xml.etree.ElementTree as ET

from import_maneuvers import candidate
from import_roads import DEFAULT_SPEEDS, access_allowed, inside, speed_kph, tags


def directions(properties):
    """Mirror way-only eligibility; restriction-member closures are bounded later."""
    highway = properties.get("highway")
    if highway not in DEFAULT_SPEEDS or not access_allowed(properties): return 0
    if properties.get("area") == "yes" or properties.get("ford") or properties.get("service") in {"driveway", "parking_aisle"}: return 0
    if any(key.endswith(":conditional") or key.startswith(("reversible", "restriction")) for key in properties): return 0
    if any(key.endswith(":lanes") or ":lanes:" in key for key in properties if key.startswith(("access", "vehicle", "motor", "oneway"))): return 0
    oneway = properties.get("oneway:motorcar", properties.get("oneway:motor_vehicle", properties.get("oneway")))
    if oneway is None:
        oneway = "yes" if properties.get("junction") in {"roundabout", "circular"} or highway == "motorway" else "no"
    if oneway not in {"yes", "1", "true", "no", "0", "false", "-1"}: return 0
    try:
        for key in ("maxspeed:forward", "maxspeed:backward"):
            speed_kph(properties.get(key, properties.get("maxspeed")), DEFAULT_SPEEDS[highway])
    except ValueError:
        return 0
    return int(oneway != "-1" and access_allowed(properties, "forward")) + int(oneway in {"no", "0", "false", "-1"} and access_allowed(properties, "backward"))


def census(source, bounds, database):
    if database.exists(): raise ValueError("Census database exists; preserve it and use a fresh directory")
    counts, classes = Counter(), Counter()
    with closing(sqlite3.connect(database)) as db:
        db.execute("PRAGMA cache_size=-32768")
        db.execute("PRAGMA temp_store=FILE")
        db.execute("CREATE TABLE nodes (id INTEGER PRIMARY KEY, inside INTEGER NOT NULL)")
        db.execute("CREATE TABLE ways (id INTEGER PRIMARY KEY, segments INTEGER NOT NULL, roads INTEGER NOT NULL)")
        db.execute("CREATE TABLE restriction_members (id INTEGER PRIMARY KEY)")
        parser = ET.iterparse(source, events=("start", "end"))
        _, root = next(parser)
        if root.tag != "osm": raise ValueError("Expected OSM XML")
        depth, phase, batch = 1, 0, []
        for event, element in parser:
            if event == "start":
                depth += 1
                continue
            if depth == 2:
                if element.tag == "node":
                    if phase: raise ValueError("Census requires nodes before ways before relations")
                    within = inside([float(element.get("lon")), float(element.get("lat"))], bounds)
                    batch.append((int(element.get("id")), int(within)))
                    counts["sourceNodes"] += 1
                    counts["insideNodes"] += within
                    if len(batch) == 4096:
                        db.executemany("INSERT INTO nodes VALUES (?, ?)", batch)
                        batch.clear()
                elif element.tag == "way":
                    if phase > 1: raise ValueError("Census requires ways before relations")
                    phase = 1
                    if batch:
                        db.executemany("INSERT INTO nodes VALUES (?, ?)", batch)
                        batch.clear()
                    refs = [int(node.get("ref")) for node in element.findall("nd")]
                    properties = tags(element)
                    counts["sourceWays"] += 1
                    points = {}
                    # Bound SQL parameters even for unusually long source ways.
                    for offset in range(0, len(refs), 900):
                        chunk = refs[offset:offset + 900]
                        points.update(db.execute(f"SELECT id, inside FROM nodes WHERE id IN ({','.join('?' for _ in chunk)})", chunk))
                    if any(ref not in points for ref in refs): raise ValueError(f"Missing node on way {element.get('id')}")
                    supported = properties.get("highway") in DEFAULT_SPEEDS
                    segments = sum(tail != head and points[tail] and points[head] for tail, head in zip(refs, refs[1:]))
                    roads = segments * directions(properties)
                    db.execute("INSERT INTO ways VALUES (?, ?, ?)", (int(element.get("id")), max(0, len(refs) - 1), roads))
                    counts["wayEligibleDirectedSegments"] += roads
                    if supported:
                        counts["supportedWays"] += 1
                        counts["supportedPhysicalSegmentsInside"] += segments
                        counts["supportedBoundarySegments"] += sum(bool(points[a]) != bool(points[b]) for a, b in zip(refs, refs[1:]))
                        classes[properties["highway"]] += roads
                elif element.tag == "relation":
                    if batch:
                        db.executemany("INSERT INTO nodes VALUES (?, ?)", batch)
                        batch.clear()
                    phase = 2
                    counts["sourceRelations"] += 1
                    if tags(element).get("type", "").startswith("restriction"):
                        db.executemany("INSERT OR IGNORE INTO restriction_members VALUES (?)", [(int(member.get("ref")),) for member in element.findall("member") if member.get("type") == "way"])
                        try:
                            rule = candidate(element)
                        except ValueError:
                            rule = None
                        if rule:
                            lengths = [db.execute("SELECT segments FROM ways WHERE id=?", (way,)).fetchone() for way in rule["ways"]]
                            if all(length and length[0] > 0 for length in lengths):
                                counts["candidateViaWayRules"] += 1
                                # One entering road + all via segments + one exit;
                                # each proper prefix can add at most one history state.
                                counts["historyPrefixCeiling"] += 1 + sum(length[0] for length in lengths[1:-1])
                root.remove(element)
            depth -= 1
        if batch: db.executemany("INSERT INTO nodes VALUES (?, ?)", batch)
        affected = db.execute("SELECT COALESCE(SUM(roads), 0) FROM ways JOIN restriction_members USING (id)").fetchone()[0]
        db.commit()
    upper = counts["wayEligibleDirectedSegments"]
    return {**counts, "eligibleSegmentsByHighway": dict(sorted(classes.items())),
            "roadStatesLowerBound": upper - affected, "roadStatesUpperBound": upper,
            "historyStatesUpperBound": upper + counts["historyPrefixCeiling"],
            "scope": "Measured segment counts, not built states. Road interval excludes all restriction member ways at lower end and none at upper end. History ceiling sums all candidate proper prefixes; mode/relevance/failed candidates may overcount. Node barriers affect transitions, not road records.",
            "sqliteBytes": database.stat().st_size}
