# Native search evidence — October 16, 2026

Read [the findings and limitations](../../native-routing-baseline.md) first. Two runs of `npm run routing:native` used the same frozen reference, host compiler, network-denying macOS policy and ten repetitions per case/output mode. First-run reports were copied before rerunning; repeat reports were copied afterward. No API key, environment file or private coordinates are included.

- `first-summary.json`, `repeat-summary.json`: every raw timing sample, cost/membership comparison count, traversal counters, payload hashes, boundary flags, compilation, resource and launch observations.
- `first-manifest.json`, `repeat-manifest.json`: graph/model/source/worker/compiler identities and artifact checksums, including summary hashes.
- `first-run-identity.json`: immutable run inputs shared by both runs.
- `comparison.json`: deterministic cross-run checks and timing aggregates derived by `analyze.py`.

From the repository root, with the original local data present:

```bash
python3 docs/evidence/native-routing-2026-10-16/analyze.py
```

This rechecks retained summary hashes, all five original reference artifacts, worker source hashes and the current local CSR/executable. It verifies that the 72 cases have identical seeds, result hashes, memberships/counts and boundary flags across runs, then regenerates `comparison.json`. No routing is performed and no network is used. If the local data/compiler/source has intentionally changed, preserve these historical reports and use a new run name for new measurements.

The comparison aggregates medians of nine per-origin p50s. Setup+search is calculated from paired sample sums. It does not pool separate modes or subtract medians to estimate transfer overhead. Ten-sample p95 values in the raw reports are maxima, not stable tail-latency estimates. Timings differ between runs; graph/results/traversal counts and the two compiled binaries match.

Validation commands: `npm run test:routing` (41 tests), `npm test` (14 tests), `npm run check`, `npm run typecheck`, `npm run build`. All passed; existing `src/db/index.ts` assertion and MapLibre/TanStack bundler warnings remain. No browser or hosted query was needed for this local kernel step.
