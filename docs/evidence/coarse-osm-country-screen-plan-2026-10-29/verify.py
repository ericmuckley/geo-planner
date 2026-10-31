"""Read-only proposal proof. Never opens the national source or runs native tools."""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--local-headers", action="store_true")
parser.add_argument("--draft", action="store_true", help="Only before this new report is sealed")
options = parser.parse_args()
folder = Path(__file__).resolve().parent
root = folder.parents[2]


def load(path):
    return json.loads(path.read_text())


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


seal = folder / "sha256.json"
if seal.exists():
    assert not options.draft, "A sealed report cannot use draft verification"
    manifest = load(seal)
    assert set(manifest) == {str(p.relative_to(folder)) for p in folder.rglob("*")
                             if p.is_file() and p != seal}
    for name, pin in manifest.items():
        assert sha(folder / name) == pin, name
else:
    assert options.draft, "Missing report seal"
    manifest = {}

parent = load(folder / "parent-proof.json")
assert parent["priorProducerFiles"] == 259 and parent["priorSealedRuns"] == 52
assert sha(root / parent["path"] / "sha256.json") == parent["manifestSha256"]
# Parent proof is pure Python/read-only. Do not forward our flags to its local-asset mode.
previous_arguments = sys.argv
try:
    sys.argv = [str(root / parent["path"] / "verify.py")]
    with contextlib.redirect_stdout(io.StringIO()):
        runpy.run_path(sys.argv[0], run_name="__main__")
finally:
    sys.argv = previous_arguments

bindings = load(folder / "bindings.json")
for name, pin in bindings["repository"].items():
    assert sha(root / name) == pin, name
if options.local_headers:
    for name, pin in bindings["localHeaders"].items():
        assert sha(root / name) == pin, name
    config = (root / next(n for n in bindings["localHeaders"] if n.endswith("util/config.hpp"))).read_text()
    reader = (root / next(n for n in bindings["localHeaders"] if n.endswith("io/reader.hpp"))).read_text()
    pool = (root / next(n for n in bindings["localHeaders"] if n.endswith("thread/pool.hpp"))).read_text()
    assert 'std::string name{"OSMIUM_MAX_"}' in config and 'name += "_QUEUE_SIZE"' in config
    assert 'get_max_queue_size("INPUT", 20)' in reader and 'get_max_queue_size("OSMDATA", 20)' in reader
    assert 'explicit Pool(int num_threads' in pool and 'max_queue_size > 0' in pool

math_module = runpy.run_path(str(folder / "resource_arithmetic.py"))
arithmetic = math_module["result"]()
assert arithmetic == load(folder / "resource-arithmetic.json")
plan = load(folder / "screen-plan.json")
assert plan["format"] == "geo-planner-country-screen-proposal-v1"
assert plan["status"] == "planning_complete_implementation_and_execution_not_admitted"
assert not any(plan["thisStage"].values())
inventory = load(root / "docs/evidence/coarse-osm-inventory-2026-10-27/v3/result.json")
assert inventory["inventory"]["counts"] == plan["source"]["countsPerPass"] == arithmetic["countsPerPass"]
assert inventory["inventory"]["wholeSourceNativeEof"]
assert not inventory["inventory"]["sourceMetadataValidatedGlobally"]
assert plan["source"]["bytes"] == 12229320016
assert plan["source"]["sha256"] == "1b127070917e2f4e5d9e778e2412bb44d24116519cf084ab72fe13e679eb11ff"
assert plan["source"]["acceptedObjectsTwoPasses"] == arithmetic["acceptedObjectsAcrossTwoPasses"]
assert plan["source"]["formatLimits"] == {"blobHeaderBytesExclusiveMax": 65536, "decodedBlobBytesExclusiveMax": 33554432}
assert plan["implementation"]["oldLimitsUnchanged"] == {"profileInputBytes": 16777216, "projectorAggregateObjects": 2000000}
assert len(plan["implementation"]["newFiles"]) == 4
assert len(plan["qualificationBeforeFreeze"]) == 8
resources = plan["resources"]
assert resources["memoryBytes"] == 4 * 1024**3 and resources["swapBytes"] == 0
assert resources["cpus"] == 2 and resources["pids"] == 64
assert resources["network"] == "none" and resources["capabilities"] == []
assert resources["readOnlyRootAndInputs"]
assert resources["ownedWritableIncludingTmpBytes"] == arithmetic["writableLimitBytes"] == 1024**3
assert resources["tmpBytes"] == 256 * 1024**2 and resources["fileBytes"] == 64 * 1024**2
assert resources["seconds"] == arithmetic["phaseSeconds"]
assert resources["memoryReservationBytes"] == arithmetic["memoryReservationBytes"]
probe = plan["probe"]
assert probe["sourceShardOrdinals"] == arithmetic["selectedSourceShardOrdinals"]
assert probe["blocks"] == arithmetic["selectedBlocks"] == 4050
assert probe["rows"] == arithmetic["selectedRows"] == 16588148
assert probe["maximumShardBytes"] == arithmetic["maximumShardBytes"]
assert arithmetic["maximumMiniIndexBytesIncluding4MiBCatalog"] < probe["aggregateMiniIndexLimitBytes"]
assert probe["perFileLimitBytes"] == resources["fileBytes"]
assert probe["persistentShardsMax"] + 1 == probe["peakWithReplacementShards"] == 9
assert plan["wayTrace"]["minimumEligibleWays"] == 64
assert plan["wayTrace"]["maximumSelectedWays"] == 128
assert plan["wayTrace"]["maxOccurrences"] == arithmetic["roadReferenceOccurrencesMax"]
assert plan["lookup"]["authenticatedShardReadUpperBound"] == arithmetic["lookupAuthenticatedShardBytesUpperBound"]
assert arithmetic["lookupAuthenticatedShardBytesUpperBound"] < plan["lookup"]["authenticatedShardReadBytesLimit"]
assert plan["lookup"]["decodeRowsLimit"] == arithmetic["lookupDecodedRowsLimit"]
assert plan["lookup"]["cohorts"][1]["occurrences"] == arithmetic["spreadQueryOccurrences"]
assert plan["lookup"]["decodedCacheBlocks"] == 64
assert [p["id"] for p in plan["phases"]] == ["preflight", "pass-a", "pass-b", "lookup", "audit-close"]
for phase in plan["phases"][1:3]:
    assert phase["secondsMax"] == 3000 and phase["objectsMax"] == arithmetic["objectsPerPass"]
assert plan["futureOutputContract"]["newUnusedRoot"] == "data/coarse-quality/us-osm-country-screen-v1/"
assert len(plan["futureOutputContract"]["neverAdmits"]) >= 5
assert plan["commandContract"]["availableNow"] == [
    "python3 -B docs/evidence/coarse-osm-country-screen-plan-2026-10-29/resource_arithmetic.py",
    "python3 -B docs/evidence/coarse-osm-country-screen-plan-2026-10-29/verify.py",
]
guards = load(folder / "guard-map.json")
original = load(root / guards["originalPath"])
assert len(guards["entries"]) == len(original) == 10
for old, new in zip(original, guards["entries"]):
    assert old["guard"] == new["guard"] and old["nativeDesign"] == new["preserve"]
    assert not new["newImplementationQualified"]
# Independent selector/counter boundary facts, using only a tiny synthetic corpus.
assert arithmetic["selectedBlocksPerShard"][-1] == 466
assert sum(arithmetic["selectedRowsPerShard"]) == 7 * 2097152 + 1908084
assert (3 * arithmetic["objectsPerPass"] + 1) < 2**64
assert arithmetic["checkpointsPerPassIncludingFinal"] == 27017
assert arithmetic["nationalMaximumId"] is None and arithmetic["nationalLogicalIndexBytes"] is None
assert not arithmetic["fullImportAdmitted"] and not arithmetic["nationalExecutionThisStage"]
verification = load(folder / "verification.json")
assert verification["planningProofDefaultDraft"] == "passed"
assert verification["planningProofDraftWithThreeLocalHeaders"] == "passed"
assert verification["documentationLinks"]["errors"] == []
assert verification["priorSampleDefaultProof"]["recordFiles"] == 48
assert sha(root / "src/server/data/coarse-grid-v9.json") == verification["activeV9Sha256"]
print(json.dumps({"planningProofPassed": True, "draft": options.draft, "recordFiles": len(manifest),
                  "priorProducerFiles": 259, "priorSealedRuns": 52,
                  "localHeadersChecked": options.local_headers,
                  "arithmeticAndGuardBindingsValid": True, "selectedShards": 8,
                  "proposedWritableReservationBytes": arithmetic["writableReservationBytes"],
                  "nationalSourceRead": False, "newNativeImplementationQualified": False,
                  "nationalExecutionAdmitted": False, "modelChanged": False}, indent=2))
