# Visible local long-range experiment

**Archived report.** This describes an earlier run or proposal. Use [the current handoff](../agent-handoff.md) and [next steps](../next-steps.md) for active instructions.

Updated October 18, 2026. The immediate priority is now **visible longer queries, explicit clipping, then coverage expansion**. General build-memory optimization is no longer the default next task.

**Historical smaller-graph report.** The qualified [two-hour baseline](../two-hour-region.md) is now the local default; the [intermediate expansion](larger-region-experiment.md) is also preserved. This page preserves the original graph's commands, measurements and limitations for comparison.

## Run it

```sh
npm run dev:experiment -- --graph-run hour-v3 --cuts-run hour-v3-cuts
```

Open **http://127.0.0.1:3000/experiment** (use Vite's printed port if 3000 is occupied). The main workspace also links to the experiment. Choose **90m** or **120m**, then **Compute reachable roads**. The page also accepts 1–720 whole minutes. The original hosted page/provider keeps its 60-minute limit.

The launcher starts `routing/experiment.py` on loopback port 8787, waits for verified graph startup, then starts TanStack Start with `LOCAL_ROUTING_EXPERIMENT=1` in that child process. It reuses an already-running local worker and does not stop a reused worker on exit. It does not edit `.env.local`, forward provider keys or call a routing API. On a fresh start, checking/reloading/indexing the graph takes time before Vite starts. Python 3.11+, the existing qualified `data/compact-pilot/hour-v3`, `hour-v3-cuts` and their matching macOS native binary are prerequisites. There is no graph download or build in this launcher.

`/api/experiment` is a separate Zod-validated server route. It calls only the fixed loopback worker, has no hosted retries/fallback, and is disabled unless explicitly enabled. It is always disabled when `VERCEL` is set. Normal app builds remain compatible with Vercel; this local process and its regional data are not a deployed Vercel routing solution.

## What is displayed

- **Teal:** a deterministic sample of reachable directed-road intervals, capped at 30,000 displayed segments. Origin-road intervals are included. Counts and search use the full graph, not the visual sample. Short segments are preserved at regional zoom; zoom in to inspect their shape.
- **Red:** audited potential data-edge nodes reached within the budget. Gray markers show the other audited edges. A potential edge is a coverage warning, not proof of a legal continuation outside the extract.
- **Dashed line:** the graph's bounds. Orange is the snapped origin.

This is a road-network experiment, **not a filled-area isochrone**. It calculates legal entry costs from reached history states and includes the reachable prefix of a road even when its head exceeds the budget. Direct source intervals begin at the snapped fraction, not the road's tail. Tests compare sampled interior fractions with the independent terminal oracle for turn restrictions, history restrictions, delays, blocked nodes and direct source travel. Road-coordinate output rounds to seven decimal places; this visual precision is separate from integer-ms cost checks.

The spatial snap index uses the same nearest-segment projection/tie rule and 100 m cutoff as the reference. Startup requires exact attachments/seeds/snapped coordinates for all four qualified geographic origins. Snapping does not verify driveway access or current real-world eligibility.

Searches are serialized through one native client. Health checks remain responsive during a query; another simultaneous query gets a busy error. Changing inputs discards stale browser results and aborts the app request, but does not interrupt a native/geometry calculation already in progress. Retry after that calculation finishes. Results can be exported as JSON; they do not mix with hosted saved-run history.

## Real verification

The existing graph/binary/source/cut artifacts are checksum-verified before startup, and the reloaded graph identity must match the native qualification. The unchanged C++ engine runs fresh bounded searches. The full existing source/turn/access qualification is reused on that identical graph; the new browser road display is a separate verification scope.

Default San Diego, `32.7157,-117.1611`, snaps **0.514 m** to `[-117.1610999455694,32.715695376286924]`:

| Budget | Reached potential cut nodes | N / E / S / W | Reachable directed roads | Native search loop | App HTTP round trip |
| --- | --- | --- | --- | --- | --- |
| 60 min | 0 | 0 / 0 / 0 / 0 | 2,209,935 | 206.8 ms | 3,433.8 ms |
| 90 min | 79 | 77 / 2 / 0 / 0 | 2,580,052 | 224.5 ms | 3,505.7 ms |
| 120 min | 115 | 88 / 6 / 21 / 0 | 2,684,540 | 238.1 ms | 3,702.0 ms |
| 720 min | 149 | See raw record | See raw record | 232.3 ms | 3,698.9 ms |

At 90/120 minutes, first reached cut cost remains **3,904,583 ms / 65m05s**, matching the original full-field inventory. At 120 minutes the 115 reached cuts and all directional counts match the frozen qualification. Native search, native pipe round trip, snapping, road-display preparation, worker total, app/browser round trip and map update-to-idle are reported separately. Display preparation is about 3–3.3 s in these samples and dominates the ~0.2 s search. Worker timing stops before HTTP JSON serialization; app HTTP spans the proxy, serialization, transfer, decode and validation. These are single local observations on Apple M4/16 GiB, with other checks/preparation running, not controlled performance distributions or Vercel timings.

The Chrome flow verifies both 90- and 120-minute results and their incomplete-coverage messages. The 12-hour API query proves the range is accepted, not that twelve hours of geography are present. Zero cuts at 60 minutes is a sampled clipping result; `coverageVerified` remains false for every budget.

Graph: `b50422b83537cecf12f1ecb4f7a3fa4e80df206726796b562135715f3737d048`, **3,034,771 roads / 3,036,124 states / 6,411,757 arcs**, bounds `[-117.65,31.9,-116.0,33.6]`. Static model `exploratory-static-car-v3` retains signal/U-turn delays of 5,000/20,000 ms. Source XML SHA-256 is `64462b578bd9b688290fa8777bbb2564ea40ed649c47d88146353c72097ab1a1`; cached California/Mexico data is dated `2026-10-14T20:21:12Z`. The same uncertain Otay ways `114198251`, `185333061`, `577149752` remain. Border queues, documents, current eligibility and live traffic are unmodeled. Source completeness and AZ/NV/eastern/southern gaps remain separate concerns. No provider quota is used.

## Coverage expansion started

```sh
npm run routing:experiment:coverage
```

The new bounded increment **[-118.0,31.6,-115.5,34.0]** expands every side and retains northern Baja. It is an intermediate step toward two-hour coverage, not the full conservative continuation envelope or a completeness certificate. Its selector/reference recipe is unchanged from the checksum-bound six-fixture/current-source calibration. Preparation runs in the pinned cached reader image with **two CPUs / 4 GiB / no swap / no network / read-only source and recipe**.

Completed output `data/coverage-pilot/experiment-increment-v1` is sealed. Repeat with `-- --run-name fresh-name`. The 677,680,499-byte cached parent PBF remains SHA-256 `7f3cdfc99196d51e732fff06dabb004c0d2f1a4d557442daec9789a19b633dbe`. Fresh reference-complete XML is **823,266,297 bytes**, SHA-256 `fba7c77ac4b46c7ac714c843c03311731556f5bfad3797dee5fc4b11539a608f`.

Preparation measures **4,038,439 nodes / 848,787 ways / 25,086 relations**, with **5,241,105–5,417,904 road-state bounds / 5,428,062 history-state ceiling**. It takes **284.54 s**, peaks at **2,498,408,448 bytes / 2.327 GiB**, and records zero limit/OOM/kill/swap events. These are counts, not built/qualified states.

The current conservative gate scales build and qualification separately using the largest corresponding count ratio, **2.615**. Estimated build peak is **2,982,196,981 bytes**; qualification is **4,532,920,985 bytes**. Including 25% margin, the maximum is **5,666,151,232 bytes / 5.277 GiB**, above the unchanged 4 GiB budget. This is a forecast, not measured candidate graph/query RAM. **No larger graph has been built or switched into the app.**

The subsequent [expanded baseline](larger-region-experiment.md) resolves this resource gate, builds/rebuilds/qualifies the candidate and connects it to the local app. The forecasts above describe the original preparation decision; use the newer report's measured results and the current next-steps document for ongoing work.

Raw measurements, test logs and screenshots are in [the evidence directory](../evidence/local-experiment-2026-10-18/README.md).
