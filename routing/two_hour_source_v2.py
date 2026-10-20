"""Merge a pinned Arizona snapshot into the preserved California/Mexico source."""

import argparse
import fcntl
import json
from pathlib import Path
import time

from anchors import load_json
from buffer_resources import Monitor
from compact_storage import save_json
from increment import snapshot
from range_hash import advice_report, artifact, file_hash
from staged_prepare import command


ARIZONA = {"bytes": 303543535, "sha256": "d008fac4857d0b520f0ab461bea57063d664f802473720385a359a952c825552"}
PARENT = {"bytes": 677680499, "sha256": "7f3cdfc99196d51e732fff06dabb004c0d2f1a4d557442daec9789a19b633dbe"}
BASE_IMAGE = "sha256:6652906bfea590161b144a6e4fac146a41e14cbafae581dcb9e38c74ceaa53a7"


def run(args):
    output = Path(args.output)
    with (output / ".lock").open("w") as lock, Monitor(output) as monitor:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        started = time.perf_counter()
        parent, arizona = Path("/data/region.osm.pbf"), Path("/sources/arizona-261014.osm.pbf")
        if args.image_id != BASE_IMAGE or artifact(parent) != PARENT or artifact(arizona) != ARIZONA:
            raise ValueError("Pinned tools or source differs")
        previous = load_json(Path("/data/build-complete.json"))
        scripts = {name: file_hash(Path(__file__).parent / name) for name in
                   ("two_hour_source_v2.py", "two-hour-source-v2.mjs", "offline-no-swap.mjs", "settings.mjs",
                    "staged_prepare.py", "range_hash.py", "lifetime_io.py", "paged_io.py", "buffer_resources.py",
                    "increment.py", "compact_storage.py", "anchors.py")}
        identity = {"sources": {"californiaMexico": PARENT, "arizona": ARIZONA}, "scripts": scripts,
                    "arizonaUrl": "https://download.geofabrik.de/north-america/us/arizona-261014.osm.pbf",
                    "previousMetadataSha256": file_hash(Path("/data/build-complete.json")),
                    "bbox": previous["manifest"]["bbox"], "imageId": args.image_id,
                    "memoryLimit": "4g", "memorySwapLimit": "4g", "cpus": 2, "network": "none",
                    "scope": "Add the complete dated Arizona source without altering prior files. Nominal region bounds retained; includes extra referenced objects. Nevada coverage remains absent."}
        run_id = snapshot(output, identity, "identity.json")
        monitor.checkpoint("validated")
        commands = {}
        for name, source in (("arizonaHeader", arizona), ("parentHeader", parent)):
            commands[name] = command(["osmium", "fileinfo", "-j", str(source)], output, name, monitor)
        arizona_header = load_json(output / "arizonaHeader.log")
        timestamp = arizona_header["header"]["option"]["osmosis_replication_timestamp"]
        if timestamp != previous["manifest"]["osmTimestamp"]:
            raise ValueError("Road snapshot timestamps differ")
        destination = output / "region.osm.pbf"
        commands["merge"] = command(["osmium", "merge", str(parent), str(arizona), "-o", str(destination)], output, "merge", monitor)
        commands["mergedInfo"] = command(["osmium", "fileinfo", "-e", "-j", str(destination)], output, "mergedInfo", monitor)
        info = load_json(output / "mergedInfo.log")
        if not info["data"]["objects_ordered"] or info["data"]["multiple_versions"]:
            raise ValueError("Merged source ordering/version validation failed")
        result = artifact(destination)
        monitor.checkpoint("verified")
        report = {"runId": run_id, **identity, "osmTimestamp": timestamp, "previousProvenance": previous["manifest"],
                  "artifacts": {"region.osm.pbf": result}, "commands": commands,
                  "resourceCheckpoints": monitor.checkpoints, "sampling": monitor.summary(), "cacheAdvice": advice_report(),
                  "workerWallMs": (time.perf_counter() - started) * 1000, "publicApiCalls": 0, "coverageVerified": False}
        save_json(output / "report.json", report)
        print(json.dumps({"artifact": result, "timestamp": timestamp, "workerWallMs": report["workerWallMs"]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="/output")
    parser.add_argument("--image-id", required=True)
    run(parser.parse_args())
