# Streaming-import evidence — October 16, 2026

See [implementation, exact commands, resource scope and limits](../../streaming-import-capacity.md).

- `downtown-v2.json`, `corridor-v2.json`, `corridor-v3.json`: graph/audit/packed equality, recipe/input fingerprints, stage counters, worker RSS and fresh-container memory checkpoints.
- `wide-v2.json`: preserved wider-profile retry, new artifact hashes, independent costs/snaps and cut flags.
- `native-verification.json`: unchanged native kernel checked against the wider graph's saved Bellman–Ford vectors; setup/search/encoding/pipe observations are separate.
- `comparison.json`: reproduced measurements, artifact/input preservation, old rebuild comparisons and cut witnesses.
- `wide-border-route-diagnostic.json`: recovered Tijuana → San Diego state-path witness and unreachable reverse result, with explicit partial endpoint and recomputed costs. This is model legality, not real car eligibility.
- `otay-uncertain-crossing-source.osm`: original incident-way/node excerpt for the inspection-facility path, including way 114198251's explicit missing-barrier/uncertain-access note. No real crossing permission is inferred.
- `analyze.py`: rechecks all saved artifacts/recipe fingerprints, graph/binary identity, zero OOM counters and the unchanged failed attempt, then writes derived comparisons.

```bash
python3 -B docs/evidence/streaming-import-2026-10-16/analyze.py
```

Large artifacts/oracle vectors remain in ignored `data/import-pilot/stream-v1-wide-v2/`. Other new runs retain reports and recipe snapshots under `data/import-pilot/`; all frozen inputs and failed attempts remain unchanged. Source data/provenance comes from the previous locally cached October 14 California/Mexico snapshot. No new geographical downloads, provider credentials or public routing calls were involved. Single import observations and model-cost consistency do not establish national capacity, real driving times, complete reachability or cloud feasibility.
