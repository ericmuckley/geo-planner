"""Merge cached dated roads for partial six-hour resource screening, offline."""

import argparse
import fcntl
from pathlib import Path
import time

from anchors import load_json
from buffer_resources import Monitor
from compact_storage import save_json
from increment import snapshot
from paged_io import advice_report, artifact, file_hash
from staged_prepare import command
from two_hour_source_v2 import ARIZONA, BASE_IMAGE


def run(args):
    output = Path(args.output)
    with (output / ".lock").open("w") as lock, Monitor(output) as monitor:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        started = time.perf_counter()
        manifest = load_json(Path(__file__).with_name("manifest.json"))
        sources = manifest["sources"] + [{"file": "arizona-261014.osm.pbf", **ARIZONA,
            "url": "https://download.geofabrik.de/north-america/us/arizona-261014.osm.pbf",
            "publisherChecksumVerified": False}]
        if args.image_id != BASE_IMAGE:
            raise ValueError("Pinned tools image differs")
        for source in sources:
            if artifact(Path("/sources") / source["file"]) != {key: source[key] for key in ("bytes", "sha256")}:
                raise ValueError(f"Cached source differs: {source['file']}")
        names = ("six_hour_source.py", "six-hour-source.mjs", "two_hour_source_v2.py", "manifest.json",
                 "offline-no-swap.mjs", "settings.mjs", "buffer_resources.py", "import_capacity.py",
                 "staged_prepare.py", "paged_io.py", "range_hash.py", "lifetime_io.py", "increment.py", "anchors.py", "compact_storage.py")
        scripts = {name: file_hash(Path(__file__).parent / name) for name in names}
        identity = {"sources": sources, "scripts": scripts, "imageId": args.image_id,
                    "memoryLimit": "4g", "memorySwapLimit": "4g", "cpus": 2, "network": "none",
                    "sourceComplete": False, "license": manifest["license"],
                    "scope": "Full cached Southern California, Mexico and Arizona extracts only; no admin supplements. Missing Northern California, Nevada, Utah, New Mexico and the Colorado corner of the enclosing six-hour rectangle. Not a complete six-hour source or a new routing graph."}
        run_id = snapshot(output, identity, "identity.json")
        monitor.checkpoint("validated")
        commands, paths = {}, []
        for index, source in enumerate(sources):
            path = Path("/sources") / source["file"]
            stage = f"sourceHeader{index}"
            commands[stage] = command(["osmium", "fileinfo", "-j", str(path)], output, stage, monitor)
            info = load_json(output / f"{stage}.log")
            if info["header"]["option"]["osmosis_replication_timestamp"] != manifest["osmTimestamp"]:
                raise ValueError("Road snapshot timestamps differ")
            paths.append(str(path))
        destination = output / "region.osm.pbf"
        commands["merge"] = command(["osmium", "merge", *paths, "-o", str(destination)], output, "merge", monitor)
        commands["mergedInfo"] = command(["osmium", "fileinfo", "-e", "-j", str(destination)], output, "mergedInfo", monitor)
        info = load_json(output / "mergedInfo.log")
        if not info["data"]["objects_ordered"] or info["data"]["multiple_versions"]:
            raise ValueError("Merged source ordering/version validation failed")
        result = artifact(destination)
        monitor.checkpoint("verified")
        report = {"runId": run_id, **identity, "osmTimestamp": manifest["osmTimestamp"],
                  "artifacts": {"region.osm.pbf": result}, "commands": commands,
                  "resourceCheckpoints": monitor.checkpoints, "sampling": monitor.summary(),
                  "cacheAdvice": advice_report(), "workerWallMs": (time.perf_counter() - started) * 1000,
                  "publicApiCalls": 0, "coverageVerified": False}
        save_json(output / "report.json", report)
        print({"artifact": result, "workerWallMs": report["workerWallMs"]}, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="/output")
    parser.add_argument("--image-id", required=True)
    run(parser.parse_args())
