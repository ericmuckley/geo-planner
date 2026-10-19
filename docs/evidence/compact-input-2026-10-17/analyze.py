"""Check five reimports, frozen qualification reuse and no-swap resource evidence."""

import hashlib
import json
from pathlib import Path
import struct


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).parent
CASES = ("downtown-v2", "corridor-v2", "corridor-v3", "wide-v3", "buffer-v3")
SOURCES = {"downtown-v2": "reference-pilot/downtown-static-v1/roads.osm",
           "corridor-v2": "regional-pilot/san-diego-tijuana-corridor-v2/car-roads.osm",
           "corridor-v3": "regional-pilot/san-diego-tijuana-corridor-v2/car-roads.osm",
           "wide-v3": "regional-pilot/san-diego-tijuana-v2/car-roads.osm",
           "buffer-v3": "coverage-pilot/san-diego-tijuana-buffer-preflight-r2/car-roads.osm"}


def read(path): return json.loads(path.read_text())


def sha(path):
    with path.open("rb") as stream: return hashlib.file_digest(stream, "sha256").hexdigest()


def check(path, expected):
    assert path.stat().st_size == expected["bytes"], path
    assert sha(path) == expected["sha256"], path


def run():
    rows, recipes = [], []
    for case in CASES:
        directory = ROOT / "data/input-pilot" / f"input-v1-{case}"
        previous = ROOT / "data/compact-pilot" / f"compact-v1-{case}"
        manifest, report, identity = (read(directory / name) for name in ("manifest.json", "report.json", "run-identity.json"))
        old_manifest, old = (read(previous / name) for name in ("manifest.json", "report.json"))
        assert report == read(HERE / f"{case}-report.json")
        assert manifest == read(HERE / f"{case}-manifest.json")
        encoded = json.dumps({key: value for key, value in identity.items() if key != "runId"}, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        assert hashlib.sha256(encoded).hexdigest() == identity["runId"] == report["runId"] == manifest["runId"]
        assert manifest["previousManifestSha256"] == sha(previous / "manifest.json")
        assert manifest["sourceArtifact"] == old_manifest["sourceArtifact"]
        check(ROOT / "data" / SOURCES[case], manifest["sourceArtifact"])
        assert manifest["imageId"] == old_manifest["imageId"]
        assert manifest["profile"] == old_manifest["profile"]
        for name, expected in manifest["artifacts"].items(): check(directory / name, expected)
        for name, expected in old_manifest["artifacts"].items(): check(previous / name, expected)
        for name, expected in manifest["scripts"].items():
            assert sha(ROOT / "routing" / name) == sha(directory / "recipe" / name) == expected
        recipes.append(manifest["scripts"])
        assert report["graphIdentity"] == old["graphIdentity"]
        for name, expected in report["artifacts"].items():
            assert expected == old_manifest["artifacts"][name]
            assert report["identicalArtifactSha256"][name] == expected["sha256"]
        with (directory / "graph.csr").open("rb") as stream:
            magic, count, arcs, graph_id = struct.unpack("<8sII32s", stream.read(48))
        assert magic == b"GPCSR001" and count == report["states"] and arcs == report["transitions"]
        assert graph_id.hex() == report["graphIdentity"]
        assert report["artifacts"]["graph.csr"]["bytes"] == 48 + 4 * (count + 1 + 2 * arcs)
        assert manifest["memoryLimit"] == manifest["memorySwapLimit"] == "4g" and manifest["swapPolicy"] == "disabled"
        assert manifest["network"] == "none" and manifest["cpus"] == 2 and report["publicApiCalls"] == 0
        assert report["coverageVerified"] is False
        for resource in report["resourceCheckpoints"].values():
            assert int(resource["memory.max"]) == 4 * 1024 ** 3
            assert resource["memory.swap.max"] == resource["memory.swap.current"] == resource["memory.swap.peak"] == "0"
            for name in ("oom", "oom_kill", "oom_group_kill"): assert int(resource["memory.events"][name]) == 0
        storage = report["importStages"]["inputStorage"]
        for kind in ("nodes", "ways"):
            assert storage[kind]["orderedUniqueIds"] and storage[kind]["fallbackIndexEntries"] == 0
        assert report["reusedQualification"]["manifestSha256"] == sha(previous / "manifest.json")
        for name, expected in report["reusedQualification"]["artifacts"].items(): check(previous / name, expected)
        if case == "buffer-v3":
            check(previous / "native-verification.json", report["reusedQualification"]["nativeVerification"])
            native = read(previous / "native-verification.json")
            assert native["sourceManifestSha256"] == sha(previous / "manifest.json")
            assert native["costComparisons"] + native["membershipComparisons"] == 181826135
            assert native["interiorDestinationComparisons"] == 2
            assert len(manifest["parityReports"]) == 4
            for small, expected in manifest["parityReports"].items():
                assert sha(ROOT / "data/input-pilot" / f"input-v1-{small}" / "report.json") == expected
        final = report["resourceCheckpoints"]["complete"]
        parsed, prior_parsed = (item["resourceCheckpoints"]["parsed"]["workerMaxRssKiB"] for item in (report, old))
        imported, prior_imported = (item["resourceCheckpoints"]["historyBuilt"]["workerMaxRssKiB"] for item in (report, old))
        rows.append({"case": case, "runId": report["runId"], "graphIdentity": report["graphIdentity"], "states": count, "arcs": arcs,
                     "parsedWorkerRssKiB": parsed, "priorParsedWorkerRssKiB": prior_parsed,
                     "parsedWorkerRssReductionPercent": 100 * (1 - parsed / prior_parsed),
                     "importWorkerRssKiB": imported, "priorImportWorkerRssKiB": prior_imported,
                     "importWorkerRssReductionPercent": 100 * (1 - imported / prior_imported),
                     "completeWorkerRssKiB": final["workerMaxRssKiB"], "cgroupPeakBytes": int(final["memory.peak"]),
                     "limitEvents": int(final["memory.events"]["max"]), "swapMaxBytes": 0, "swapPeakBytes": 0,
                     "importMs": report["importMs"], "priorImportMs": old["importMs"], "workerWallMs": report["workerWallMs"],
                     "inputStorage": storage, "identicalArtifacts": list(report["identicalArtifactSha256"])})
    assert all(recipe == recipes[0] for recipe in recipes)
    comparison = {"cases": rows, "fiveGraphsAndAuditsByteIdentical": True, "swapDisabledAllRuns": True,
                  "zeroOomAllRuns": True, "publicRoutingApiCalls": 0, "coverageVerified": False,
                  "scope": "Fresh single-run offline preprocessing observations; buffer oracle/native evidence reused by exact artifact identity. No new search, contour, cloud or complete-coverage claim."}
    (HERE / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
    print(json.dumps(comparison, indent=2))


if __name__ == "__main__": run()
