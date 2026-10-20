"""Bootstrap reusable reference sinks when absent, then run the v2 verification."""

import argparse
import fcntl
from pathlib import Path

from anchors import load_json
from buffer_resources import Monitor
from increment import check_artifacts, check_scripts, snapshot
from lean_qualification import calibrate
from range_hash import file_hash
from scoped_region_verification_v2 import run as verify


def check_sinks(output, inputs):
    identity = load_json(output / "qualification-identity.json")
    check_scripts(output, identity["scripts"])
    if identity["buildManifestSha256"] != file_hash(output / "build-manifest.json"):
        raise ValueError("Reference sinks belong to another build")
    reference = inputs / "compact-pilot/compact-v1-buffer-v3"
    result = identity["oracleCalibration"]
    if result["sourceManifestSha256"] != file_hash(reference / "manifest.json"):
        raise ValueError("Reference sink source differs")
    expected = load_json(reference / "summary.json")["interiorDestinations"]
    if [{key: row[key] for key in expected[0]} for row in result["partialDestinations"]] != expected:
        raise ValueError("Reference sink costs differ")


def ensure_sinks(args):
    output, inputs = Path(args.output), Path("/inputs")
    if (output / "qualification-identity.json").exists():
        check_sinks(output, inputs)
        print("Verified existing reference-sink identity; no recalculation", flush=True)
        return
    with (output / ".lock").open("w") as lock, Monitor(output) as monitor:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = load_json(output / "build-manifest.json")
        if manifest["imageId"] != args.image_id: raise ValueError("Image differs")
        check_scripts(output, manifest["scripts"])
        check_artifacts(output, manifest["artifacts"])
        scripts = {**manifest["scripts"], **{name: file_hash(Path(__file__).parent / name) for name in
                   ("scoped_region_verification_v3.py", "scoped-region-verify-v3.mjs", "lean_qualification.py", "virtual_sink.py")}}
        base = {"scripts": scripts, "buildManifestSha256": file_hash(output / "build-manifest.json"),
                "imageId": args.image_id, "stage": "reference-destination-calibration-only",
                "scope": "Reusable frozen-reference partial destinations; not qualification of the candidate graph."}
        snapshot(output, base, "standalone-sink-identity.json")
        calibration = calibrate(inputs, output, monitor)
        snapshot(output, {**base, "oracleCalibration": calibration}, "qualification-identity.json")
        check_sinks(output, inputs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="/output")
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--sinks-only", action="store_true")
    args = parser.parse_args()
    if not args.sinks_only and (Path(args.output) / "manifest.json").exists(): parser.error("Preserve completed qualification")
    ensure_sinks(args)
    if not args.sinks_only: verify(args)
