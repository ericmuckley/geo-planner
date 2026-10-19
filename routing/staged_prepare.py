"""Stage geographic selection separately from recursive reference completion."""

import subprocess
import time

from import_roads import DEFAULT_SPEEDS


def command(args, output, stage, monitor):
    before = time.perf_counter()
    with (output / f"{stage}.log").open("w") as log:
        subprocess.run(["/usr/bin/time", "-v", "-o", str(output / f"{stage}-resources.txt"), *args], stdout=log, stderr=subprocess.STDOUT, check=True)
    if monitor: monitor.checkpoint(stage)
    return {"command": args, "wallMs": (time.perf_counter() - before) * 1000}


def prepare(source, bounds, output, monitor=None):
    output.mkdir(parents=True, exist_ok=True)
    seed, selected, xml = (output / name for name in ("seed-region.osm.pbf", "seed-roads.osm.pbf", "car-roads.osm"))
    commands = {}
    commands["completeWaysSelect"] = command(["osmium", "extract", "--strategy=complete_ways", "--bbox=" + ",".join(map(str, bounds)), str(source), "-o", str(seed)], output, "completeWaysSelect", monitor)
    commands["seedFilter"] = command(["osmium", "tags-filter", "--omit-referenced", str(seed), "w/highway=" + ",".join(sorted(DEFAULT_SPEEDS)), "r/type=restriction*", "-o", str(selected)], output, "seedFilter", monitor)
    commands["completeReferences"] = command(["osmium", "getid", "--add-referenced", "--id-osm-file", str(selected), str(source), "-f", "osm", "-o", str(xml)], output, "completeReferences", monitor)
    commands["checkReferences"] = command(["osmium", "check-refs", "--check-relations", str(xml)], output, "checkReferences", monitor)
    return xml, commands
