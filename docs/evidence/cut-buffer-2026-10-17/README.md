# Cut inventory and next-buffer evidence

See [findings, commands and limitations](../../coverage-increment-preflight.md).

`cuts`, `calibration` and `candidate` reports/identities copy the three completed ignored runs. `cut-nodes.json` and `.geojson` contain all 337 endpoints, source boundary links and frozen oracle costs. `parent-fileinfo.json` records the planning inventory of the cached PBF. Stage logs include measured RAM composition; complete reports retain 200 ms sampled maxima, concurrent highest-current sample and cumulative cgroup peaks/events.

`failed-header.log` and `rejected-simple.log` preserve failed attempts. `rejected-simple-*.osm` and `rejected-simple-comparison.json` show the boundary fixture's actual source/old/new products and graph disagreement. Ignored data also retains the superseded successful r3 calibration with its original snapshots; r4 adds explicit provenance bindings.

```bash
python3 -B docs/evidence/cut-buffer-2026-10-17/analyze.py
python3 -B docs/evidence/compact-input-2026-10-17/analyze.py
```

The analyzer checks current/snapshotted code, artifact/source hashes, every reported witness cost against its frozen oracle, all threshold aggregates, first-cut agreement, XML calibration equality, candidate count/resource scope and preserved attempts. `comparison.json` is generated; `validation.json` records actual checks. Large PBF/XML/SQLite and oracle files stay in ignored `data/`; the analyzers require them locally. There is no larger graph, fresh route search, new contour, complete coverage or cloud performance result.
