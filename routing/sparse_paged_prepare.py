"""Sparse preparation with per-file checksum cache advice; frozen selector reused."""

import argparse
import fcntl
import importlib.metadata
import json
from pathlib import Path
import time

from anchors import atomic_write, digest, load_json
from paged_io import advice_report, file_hash
from sparse_prepare import prepare, fixtures
from buffer_resources import Monitor
from compact_storage import save_json
from coverage_census import census


def artifact(path): return {"bytes": path.stat().st_size, "sha256": file_hash(path)}


def run(args):
    output, recipe, inputs = Path(args.output), Path(__file__).parent, Path("/inputs")
    started = time.perf_counter()
    with (output / ".lock").open("w") as lock, Monitor(output) as monitor:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (output / "identity.json").exists(): raise ValueError("Preserve attempts; use a fresh run name")
        prior_dir = inputs / "coverage-pilot" / ("staged-calibration-v2-r4" if args.case == "calibration" else "staged-candidate-v2")
        prior = load_json(prior_dir / "report.json")
        if prior["imageId"] != args.base_image_id: raise ValueError("Base engine/tools image differs")
        profile = prior["profile"]
        scripts = {name: file_hash(recipe / name) for name in (*prior["scripts"], "sparse_select.py", "sparse_prepare.py", "sparse-prepare.mjs", "offline-sparse.mjs", "sparse.Dockerfile", "sparse-tools.mjs", "sparse_paged_prepare.py", "sparse-paged-prepare.mjs", "paged_io.py")}
        identity = {"case": args.case, "profile": profile, "priorReportSha256": file_hash(prior_dir / "report.json"), "scripts": scripts,
                    "imageId": args.image_id, "baseImageId": args.base_image_id, "readerVersion": importlib.metadata.version("osmium"),
                    "wheelLockSha256": file_hash(recipe / "tools/pyosmium-v1.json"), "sourceArtifact": prior["regionArtifact"],
                    "memoryLimit": "4g", "memorySwapLimit": "4g", "cpus": 2, "network": "none"}
        if args.case == "candidate":
            proof_path = inputs / "sparse-pilot" / args.calibration_run / "report.json"
            proof = load_json(proof_path)
            if not proof["xmlByteIdentical"] or proof["imageId"] != args.image_id: raise ValueError("Complete same-selector/image calibration first")
            for name, expected in proof["scripts"].items():
                if file_hash(recipe / name) != expected: raise ValueError("Frozen selector/proof code changed")
            for name, expected in proof["artifacts"].items():
                if artifact(proof_path.parent / name) != expected: raise ValueError("Sparse calibration artifact changed")
            identity["calibrationReportSha256"] = file_hash(proof_path)
        run_id = digest(identity)
        save_json(output / "identity.json", {"runId": run_id, **identity})
        (output / "recipe").mkdir()
        for name in scripts: atomic_write(output / "recipe" / name, (recipe / name).read_bytes())
        atomic_write(output / "recipe/pyosmium-v1.json", (recipe / "tools/pyosmium-v1.json").read_bytes())
        if artifact(Path("/data/region.osm.pbf")) != prior["regionArtifact"]: raise ValueError("Parent source differs")
        for name, expected in prior["artifacts"].items():
            if artifact(prior_dir / name) != expected: raise ValueError(f"Frozen preparation differs: {name}")
        monitor.checkpoint("validated")
        fixture_rows = fixtures(inputs, output) if args.case == "calibration" else proof["fixtures"]
        monitor.checkpoint("fixtures")
        xml, selection, commands = prepare(Path("/data/region.osm.pbf"), profile["bbox"], output, monitor)
        actual = artifact(xml)
        if actual != prior["artifacts"]["car-roads.osm"]: raise ValueError("Sparse XML differs from frozen preparation")
        counts = census(xml, profile["bbox"], output / "candidate.sqlite")
        if counts != prior["candidate"]: raise ValueError("Sparse census differs")
        monitor.checkpoint("complete")
        artifacts = {str(path.relative_to(output)): artifact(path) for path in output.rglob("*") if path.is_file() and path.name not in {"identity.json", "progress.json", ".lock"} and "recipe" not in path.parts}
        save_json(output / "report.json", {"runId": run_id, **identity, "selection": selection, "fixtures": fixture_rows, "commands": commands,
                  "xmlByteIdentical": True, "candidate": counts, "artifacts": artifacts, "resourceCheckpoints": monitor.checkpoints,
                  "sampling": monitor.summary(), "cacheAdvice": advice_report(), "workerWallMs": (time.perf_counter() - started) * 1000, "publicApiCalls": 0,
                  "fullGraphBuilt": False, "coverageVerified": False, "scope": "Frozen sparse selector and six fixture proofs reused; per-file checksum cache advice only. Exact frozen XML/census; no new graph, routes, eligibility or complete coverage claim."})
        print(json.dumps({"case": args.case, "xmlByteIdentical": True, "selection": selection, "resources": monitor.checkpoints["complete"]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("calibration", "candidate"), required=True)
    parser.add_argument("--calibration-run", default="sparse-calibration-v1")
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--base-image-id", required=True)
    parser.add_argument("--output", default="/output")
    run(parser.parse_args())
