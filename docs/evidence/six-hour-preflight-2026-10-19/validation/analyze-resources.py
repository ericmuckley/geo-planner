import json, math, shutil, subprocess
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[3]
prepared = root / "data/coverage-pilot/six-hour-cached-v1"
report = json.loads((prepared / "report.json").read_text())
source = json.loads((root / "data/source-pilot/six-hour-cached-v1/report.json").read_text())
relative = ["compact-pilot/two-hour-region-v2", "compact-pilot/two-hour-region-v2-rebuild",
            "compact-pilot/two-hour-region-v2-cuts", "coverage-pilot/two-hour-region-v2",
            "source-pilot/two-hour-parent-v2", "source-pilot/six-hour-cached-v1", "coverage-pilot/six-hour-cached-v1"]
allocated = {name: int(subprocess.check_output(["du", "-sk", str(root / "data" / name)], text=True).split()[0]) * 1024 for name in relative}
scale = report["admission"]["scalingRatio"]
projected = {name: math.ceil(allocated[name] * scale) for name in relative[:3]}
known = allocated[relative[-1]] + allocated[relative[-2]]
estimate = math.ceil((known + sum(projected.values())) * 1.25)
source_peak = max(int(row["memory.peak"]) for row in source["resourceCheckpoints"].values())
result = {"observedAt": datetime.now(timezone.utc).isoformat(), "hostPhysicalMemoryBytes": 17179869184,
          "dockerVmMemoryBytes": 8218034176, "dockerVisibleCpuCount": 10, "phaseCpuLimit": 2,
          "hostFreeDiskBytes": shutil.disk_usage(root).free, "allocatedDiskBytes": allocated,
          "sourceMergeMeasuredPeakBytes": source_peak, "sourceMergeWith25PercentMarginBytes": int(source_peak * 1.25),
          "partialSourceArtifactDiskForecast": {"sourceAndPreparationMeasuredBytes": known,
              "scaledBuildQualificationNativeRebuildCutOutputsBytes": projected,
              "with25PercentMarginBytes": estimate,
              "fitsCurrentlyFreeDisk": estimate < shutil.disk_usage(root).free,
              "scope": "Sequential retained outputs are summed for disk, unlike maximum-phase RAM. Uses the same census growth ratio on complete baseline graph/qualification/native, rebuild and cut directories plus measured new merge/preparation. Existing raw caches/tool images and all historical data remain in place and are excluded from incremental additions. This is a partial-source heuristic, not a reservation/bound for missing-source full six-hour coverage or arbitrary failed retries."},
          "scope": "Physical host memory and Docker VM capacity are distinct from the per-container 4 GiB/no-swap cap. Host/VM paging and full missing-region demand remain unmeasured; source-merge whole-phase memory is included separately and is below the forecast maximum."}
Path(__file__).with_name("resource-analysis.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(json.dumps(result, indent=2))
