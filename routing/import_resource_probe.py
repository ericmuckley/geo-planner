"""Observe the unchanged frozen-buffer reimport through final artifact checking."""

import argparse
import fcntl
from pathlib import Path
import subprocess
import sys
import time

from anchors import atomic_write, digest, file_hash, load_json
from buffer_resources import Monitor
from compact_storage import save_json


def run(args):
    output, recipe = Path(args.output), Path(__file__).parent
    with (output / ".lock").open("w") as lock, Monitor(output) as monitor:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (output / "identity.json").exists(): raise ValueError("Preserve attempts; use a fresh run name")
        source = Path("/inputs/input-pilot/input-v1-buffer-v3")
        prior = load_json(source / "manifest.json")
        if prior["imageId"] != args.image_id: raise ValueError("Image differs")
        scripts = {name: file_hash(recipe / name) for name in (*prior["scripts"], "import_resource_probe.py", "import-resource-probe.mjs", "buffer_resources.py")}
        identity = {"priorManifestSha256": file_hash(source / "manifest.json"), "scripts": scripts, "imageId": args.image_id,
                    "memoryLimit": "4g", "memorySwapLimit": "4g", "cpus": 2, "network": "none", "series": "input-v1"}
        run_id = digest(identity)
        save_json(output / "identity.json", {"runId": run_id, **identity})
        (output / "recipe").mkdir()
        for name in scripts: atomic_write(output / "recipe" / name, (recipe / name).read_bytes())
        child_output = output / "import"
        child_output.mkdir()
        command = [sys.executable, "-u", str(recipe / "input_capacity.py"), "--case", "buffer-v3", "--series", "input-v1", "--output", str(child_output), "--image-id", args.image_id]
        monitor.checkpoint("start")
        child = subprocess.Popen(command)
        seen = set()
        try:
            while child.poll() is None:
                progress = child_output / "progress.json"
                if progress.exists():
                    checkpoints = load_json(progress)
                    for stage, value in sorted(checkpoints.items(), key=lambda item: item[1]["elapsedMs"]):
                        if stage not in seen:
                            monitor.checkpoint(stage)
                            seen.add(stage)
                time.sleep(.2)
        finally:
            if child.poll() is None: child.terminate(); child.wait()
        if child.returncode: raise RuntimeError(f"Frozen importer exited {child.returncode}")
        report = load_json(child_output / "report.json")
        if report["graphIdentity"] != prior["graphIdentity"]: raise ValueError("Graph identity differs")
        monitor.checkpoint("finished")
        save_json(output / "report.json", {"runId": run_id, **identity, "childCommand": command, "childReportSha256": file_hash(child_output / "report.json"),
                  "childManifestSha256": file_hash(child_output / "manifest.json"), "graphIdentity": report["graphIdentity"], "resourceCheckpoints": monitor.checkpoints,
                  "sampling": monitor.summary(), "publicApiCalls": 0, "coverageVerified": False,
                  "scope": "Unchanged frozen importer/outputs, plus an outer 200 ms cgroup composition monitor. Child stage checkpoints can be observed after the stage; child report retains its own RSS/times. No new route search or cache policy."})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--output", default="/output")
    run(parser.parse_args())
