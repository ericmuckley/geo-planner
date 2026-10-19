"""Exact frozen-graph parity with compact outgoing-road storage."""

import argparse
import fcntl
import gzip
import json
from pathlib import Path
import time

from anchors import atomic_write, digest, load_json
from xml_evidence import source_examples, source_uncertainties
from xml_stream import report as xml_report
from xml_fixtures import qualify as qualify_xml_fixtures
from evidence_fixtures import qualify as qualify_evidence_fixtures
from range_hash import advice_report, artifact, file_hash
from buffer_resources import Monitor
from compact_storage import save_json, write_csr
from crossing_audit import barrier_examples
from import_capacity import graph_data
from outgoing_import import import_barriers, import_maneuvers
from outgoing_fixtures import qualify as qualify_fixtures
from cache_lifetime import release_output, release_read, report as lifetime_report, save_json as save_export
from keyed_parity import CASES
from range_manifest import checked_manifest


def run(args):
    started = time.perf_counter()
    inputs, output, recipe = Path("/inputs"), Path(args.output), Path(__file__).parent
    with (output / ".lock").open("w") as lock, Monitor(output) as monitor:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (output / "run-identity.json").exists(): raise ValueError("Preserve existing attempts; use a fresh series")
        previous = inputs / "xml-pilot" / f"xml-v1-{args.case}"
        old = checked_manifest(previous)
        previous_report = load_json(previous / "report.json")
        qualified_directory = inputs / CASES[args.case][0]
        frozen = checked_manifest(qualified_directory)
        if previous_report["reusedQualification"]["manifestSha256"] != file_hash(qualified_directory / "manifest.json"):
            raise ValueError("Prior qualification binding differs")
        if old["graphIdentity"] != frozen["graphIdentity"] or old["profile"] != frozen["profile"] or old["sourceArtifact"] != frozen["sourceArtifact"]:
            raise ValueError("Frozen graph/profile/source differs")
        if old["imageId"] != args.image_id: raise ValueError("Tools image differs")
        source = inputs / CASES[args.case][1]
        if artifact(source) != old["sourceArtifact"]: raise ValueError("Frozen source changed")
        names = (*old["scripts"], "outgoing_index.py", "outgoing_input.py", "outgoing_import.py", "outgoing_fixtures.py", "outgoing_index_test.py", "outgoing_parity.py", "outgoing-parity.mjs")
        scripts = {name: file_hash(recipe / name) for name in names}
        parity = {}
        if args.case == "hour-v3":
            for case in CASES:
                if case == "hour-v3": continue
                directory = inputs / "outgoing-pilot" / f"{args.series}-{case}"
                proof = checked_manifest(directory)
                # Require the same importer code on the smaller frozen cases first.
                if any(proof["scripts"].get(name) != scripts[name] for name in ("outgoing_index.py", "outgoing_input.py", "outgoing_import.py", "outgoing_fixtures.py", "outgoing_index_test.py", "outgoing_parity.py", "outgoing-parity.mjs")) or any(scripts.get(name) != value for name, value in proof["scripts"].items()):
                    raise ValueError("Smaller parity cases used different code")
                report = load_json(directory / "report.json")
                if report["idMode"] != args.id_mode: raise ValueError("Smaller parity ID mode differs")
                if not report["identicalArtifactSha256"]: raise ValueError("Missing parity proof")
                parity[case] = file_hash(directory / "report.json")
        identity = {"case": args.case, "series": args.series, "idMode": args.id_mode, "profile": old["profile"], "sourceArtifact": artifact(source),
                    "previousManifestSha256": file_hash(previous / "manifest.json"), "previousReportSha256": file_hash(previous / "report.json"),
                    "qualificationManifestSha256": file_hash(qualified_directory / "manifest.json"), "imageId": args.image_id, "scripts": scripts,
                    "parityReports": parity, "memoryLimit": "4g", "memorySwapLimit": "4g", "swapPolicy": "disabled",
                    "cpus": 2, "network": "none"}
        run_id = digest(identity)
        save_json(output / "run-identity.json", {"runId": run_id, **identity})
        (output / "recipe").mkdir()
        for name in scripts: atomic_write(output / "recipe" / name, (recipe / name).read_bytes())
        checkpoints = {}

        def observe(stage):
            monitor.checkpoint(stage)
            checkpoints[stage] = monitor.checkpoints[stage]

        observe("preflight")
        fixture_parity = qualify_fixtures(args.id_mode)
        save_json(output / "fixture-parity.json", fixture_parity)
        evidence_fixtures = qualify_evidence_fixtures()
        save_json(output / "evidence-fixtures.json", evidence_fixtures)
        xml_fixtures = qualify_xml_fixtures()
        save_json(output / "xml-fixtures.json", xml_fixtures)
        observe("fixtures")
        measurements = {}
        profile = old["profile"]
        before = time.perf_counter()
        v3 = args.case.endswith("v3")
        if v3: graph, audit = import_barriers(source, output / "barrier-roads.osm", profile["bbox"], profile["model"], measurements, observe, args.id_mode)
        else: graph, audit = import_maneuvers(source, profile["bbox"], profile["model"], measurements, observe, args.id_mode)
        import_ms = (time.perf_counter() - before) * 1000
        evidence_stages = {}
        observe("beforeSourceExamples")
        if v3:
            source_examples(source, output / "barrier-source-samples.osm", graph, audit, evidence_stages, observe)
            observe("afterSourceExamples")
        if args.case in {"wide-v3", "hour-v3"}:
            uncertain = source_uncertainties(source, output / "uncertain-crossings-source.osm")
            observe("sourceUncertainties")
            by_way = {row["id"]: [] for row in uncertain}
            for road in graph.base.roads:
                if road["way"] in by_way: by_way[road["way"]].append(road["id"])
            for row in uncertain: row["retainedDirectedRoadIds"] = by_way[row["id"]]
            audit["sourceCrossingUncertainties"] = uncertain
            observe("sourceRoadIds")
            # The frozen runner also computes these examples; its audit is unchanged.
            barrier_examples(graph, audit, {1228835396, 8181606580, 9357332258})
            observe("sourceBarrierExamples")
        if v3: release_read(source, "source-evidence")
        observe("sourceEvidence")
        reads = xml_report()
        real_reads = [row for row in reads["requests"] if row["path"] == str(source)]
        expected_passes = 4 if args.case in {"wide-v3", "hour-v3"} else (2 if v3 else 0)
        if len(real_reads) != expected_passes: raise ValueError("Unexpected source XML read count")
        for row in real_reads:
            if not row["closed"] or not row["eofObserved"] or row["readBytes"] != old["sourceArtifact"]["bytes"]:
                raise ValueError("Incomplete source XML stream")
            if row["enabled"] and (row["adviceErrors"] or row["successfulAdviceBytes"] != row["readBytes"]):
                raise ValueError("Source XML cache-advice policy failed")
        save_export(output / "graph.json", graph_data(graph, profile["model"]))
        save_export(output / "import-audit.json", audit)
        write_csr(output / "graph.csr", graph.adjacency, graph.identity)
        release_output(output / "graph.csr", "csr-output")
        atomic_write(output / "graph.csr.gz", gzip.compress((output / "graph.csr").read_bytes(), mtime=0))
        release_read(output / "graph.csr", "gzip-input")
        release_output(output / "graph.csr.gz", "gzip-output")
        observe("exported")
        names = ["graph.json", "import-audit.json", "graph.csr", "graph.csr.gz"]
        if v3: names += ["barrier-roads.osm", "barrier-source-samples.osm"]
        if args.case in {"wide-v3", "hour-v3"}: names.append("uncertain-crossings-source.osm")
        artifacts = {name: artifact(output / name) for name in names}
        if graph.identity != old["graphIdentity"]: raise ValueError("Graph identity differs")
        for name, actual in artifacts.items():
            if actual != old["artifacts"][name]: raise ValueError(f"Compact-input parity differs: {name}")
        reused = {"manifestSha256": identity["qualificationManifestSha256"], "graphIdentity": graph.identity,
                  "artifacts": {name: value for name, value in frozen["artifacts"].items() if name == "summary.json" or name.startswith("oracles/")},
                  "scope": "Checksum-verified existing qualification on the identical graph; no new route/search measurements"}
        if args.case == "hour-v3":
            native = load_json(qualified_directory / "native-verification.json")
            if native["sourceManifestSha256"] != file_hash(qualified_directory / "manifest.json"): raise ValueError("Native evidence manifest differs")
            if native["graphIdentity"] != graph.identity or native["compilation"]["sourceSha256"] != file_hash(recipe / "native_search.cpp") or native["compilation"]["binarySha256"] != file_hash(qualified_directory / "native_search"):
                raise ValueError("Native graph/source/binary differs")
            qualified = load_json(qualified_directory / "qualification-report.json")
            if qualified["graphIdentity"] != graph.identity or qualified["costComparisons"] != len(graph.states) * 5 or qualified["boundedCostComparisons"] != len(graph.states) * 40 or qualified["interiorDestinationComparisons"] != 2:
                raise ValueError("Independent qualification differs")
            if native["costComparisons"] != len(graph.states) * 45 or native["membershipComparisons"] != len(graph.states) * 40 or native["interiorDestinationComparisons"] != 2:
                raise ValueError("Native comparison counts differ")
            reused["qualificationReport"] = artifact(qualified_directory / "qualification-report.json")
            reused["nativeVerification"] = artifact(qualified_directory / "native-verification.json")
            if any(reused[name] != previous_report["reusedQualification"][name] for name in ("qualificationReport", "nativeVerification")):
                raise ValueError("Prior independent/native report differs")
        observe("complete")
        report = {"runId": run_id, "case": args.case, "idMode": args.id_mode, "graphIdentity": graph.identity, "roads": len(graph.base.roads), "states": len(graph.states),
                  "transitions": len(graph.adjacency.targets), "viaWayRestrictions": len(graph.patterns), "importMs": import_ms,
                  "importStages": measurements, "sourceEvidenceStages": evidence_stages, "workerWallMs": (time.perf_counter() - started) * 1000, "resourceCheckpoints": checkpoints,
                  "artifacts": artifacts, "identicalArtifactSha256": {name: value["sha256"] for name, value in artifacts.items()},
                  "reusedQualification": reused, "publicApiCalls": 0, "coverageVerified": False,
                  "fixtureParity": artifact(output / "fixture-parity.json"), "evidenceFixtures": artifact(output / "evidence-fixtures.json"),
                  "xmlFixtures": artifact(output / "xml-fixtures.json"), "xmlStreams": xml_report(),
                  "sampling": monitor.summary(), "cacheAdvice": advice_report(), "ioLifetime": lifetime_report(),
                  "scope": "Exact frozen graph/audit/source/packed parity with compact outgoing-road storage. Unchanged routing/validation, source-evidence streams, serialization and access rules. Fresh importer, source and uncertainty fixtures; original regional full/bounded/partial/native qualification reused on identical bytes. No fresh regional searches or coverage."}
        save_json(output / "report.json", report)
        save_json(output / "manifest.json", {"runId": run_id, **identity, "graphIdentity": graph.identity,
                                            "artifacts": {**artifacts, "report.json": artifact(output / "report.json"), "fixture-parity.json": artifact(output / "fixture-parity.json"), "evidence-fixtures.json": artifact(output / "evidence-fixtures.json"), "xml-fixtures.json": artifact(output / "xml-fixtures.json")}})
        print(json.dumps({key: report[key] for key in ("case", "states", "transitions", "importMs", "workerWallMs")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES, required=True)
    parser.add_argument("--series", default="outgoing-v1")
    parser.set_defaults(id_mode="ordered")
    parser.add_argument("--output", default="/output")
    parser.add_argument("--image-id", required=True)
    run(parser.parse_args())
