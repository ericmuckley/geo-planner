# Six-hour preflight evidence — October 19, 2026

Read [the current preflight report](../../six-hour-preflight.md) for commands, interpretation and the admit/hold decision. These files preserve the unclipped plan, official source listings/current footprints, failed metadata attempt, capped cached-source merge, partial-source preparation/census and code-check logs. No larger graph was built, no road PBF was downloaded and no routing-provider call was made.

Large PBF/XML/SQLite inputs and outputs remain ignored under `data/`; their hashes and exact recipes are recorded in the reports. `recipe-sha256.json` binds the producer dependencies. The existing qualified graph and its separate evidence bundle remain unchanged. Current source footprints and listing dates are not verified dated PBF extent/completeness proofs. Partial-source forecasts are not measured graph memory or a rigorous full-region lower bound.

The first catalog attempt failed because Python did not find a usable CA bundle; the retry used `/etc/ssl/cert.pem` with TLS verification enabled. The first npm test invocation was blocked at tsx's sandbox IPC pipe before running tests; the permitted retry passed. Both logs are retained.

`validation/collect-evidence.py` records the collection process and refuses overwrite. `evidence-sha256.json` binds every other file in this directory; do not overwrite this evidence to reflect later work.
