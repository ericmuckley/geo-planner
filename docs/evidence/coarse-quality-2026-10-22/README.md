# First coarse travel-cost diagnostic — October 22, 2026

The user reports the Vercel-hosted app works, with rudimentary/inaccurate output. This bounded local comparison establishes examples for a correction; it changes no served estimates. See [interpretation and next action](../../coarse-estimator.md#first-regional-travel-cost-comparison).

- [Comparison](comparison.json): eleven public Southern California destinations from the default San Diego origin, their raw static Valhalla route requests/responses, observed reference status, grid cell costs, land-mask membership and summary.
- [Path diagnostics](path-diagnostics.json): three backtracked v1 grid paths, distance/speed decomposition and origin attachment.
- [Provenance](provenance.json): evaluated app commit/model artifact, comparison script hash, observed-service limits and user-reported deployment scope.
- [Check](check.log), [typecheck](typecheck.log), [build](build.log): validation for the reusable diagnostic command; app/kernel/data behavior is unchanged.

All eleven reference routes return successfully. Grid costs are 18.9–86.9 minutes longer (42.4m mean absolute difference) in this sample. Calexico has finite road cost but is excluded from the filled mask. Different path/access semantics and approximate cell centers matter: this is not real-world ETA ground truth, a national accuracy score, or proof that a future model will generalize. The reference itself has the limits recorded in the regional reports. No actual hosted URL/resource measurements were collected.

Run with the already-running retained regional service: `npm run --silent routing:compare:coarse > /tmp/coarse-comparison-new.json`, using an unused output name. It calls fixed loopback port 8002 only, with deadlines, and performs no graph build, database query or hosted routing call. Success means the diagnostic completed, not that accuracy passed. Do not rerun it merely to validate documentation.

`sha256.json` preserves these measurements. The script/app hashes identify this baseline; they do not freeze normal product development. Preserve the original records and use separately versioned candidate results when evaluating changes. Current app baseline is committed at `0ffd6c8`; the new diagnostic was added after that commit.
