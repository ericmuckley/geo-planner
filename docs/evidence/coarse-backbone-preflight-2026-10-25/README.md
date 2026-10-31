# V9 deployment and source-backbone feasibility

October 25, 2026, checkout **`648c731`** (commit message `v8`, containing v9). User reports deployed and verified. **Fifteen agent production API checks pass.** The new work below is offline and uncommitted; the runtime/model/UI are unchanged. No new model or accuracy improvement is claimed.

## Hosted v9 verification

[Production result](hosted-v9.json) confirms `coarse-road-grid-v9` / `natural-earth-census-2026-grid-v9`, min30/max720, the saved6/10/12h cell counts, repeat/overlap smoke, input errors, disabled detailed experiment and fresh no-cookie configured/empty history. Fifteen app requests, **zero routing-provider calls or history writes**. HTTP round trips include network/JSON delivery; recorded server search/contour timings retain their own scope. These are not proven cold/warm invocations, production percentiles, load or peak memory. The public API does not expose Git SHA. Hosted browser verification is user-reported and was not independently repeated this turn.

The restricted attempt failed DNS before receiving config; its [log](hosted-restricted-dns-failure.log) and [empty output](hosted-restricted-empty.json) remain distinct. The approved network attempt then completed all15 checks. No auth/key/quota probe, connected-routing call or persistence write occurred.

## Frozen national source preflight

The [plan](plan.json), SHA `56f9d1ac9fb1d0ff782ccbd09479ae90b3076b9ddf59a559c2ced2f1f98bcf54`, precedes this source run. It measures whether a sparse Census backbone could preserve more source connectivity than one road anchor per display cell within the existing70MB function target. It uses all49 cached national Census partitions, exact direction-independent geometry/class duplicate removal and existing assumed primary105/secondary85 speeds. Multipart pieces stay separate. No city, region, coordinate or query-specific rule.

Only identical original source endpoints become junction candidates. Every source part splits where those endpoint coordinates occur internally. No nearby-coordinate snapping or geometric-crossing inference. Interior/interior-only junctions remain unresolved. Shared2D source incidence does not establish legal turns, grade separation, road access or a routable inventory.

[Full result](report.json):

| Measurement | Result |
| --- | ---: |
| Source multipart sections / exact duplicates / unique | 261,862 /38,470 /223,392 |
| Exact endpoint nodes | 245,842 |
| Split source arcs | 501,493 |
| Total retained source length | 1,468,634.488 km |
| Endpoint-only components | 46,952 |
| Split-at-source-endpoint components | 3,100 |
| Largest component length share, endpoint-only → split | 58.415% →98.544% |
| Saved OD cases / endpoint occurrences / unique coordinates | 83 /166 /79 |
| Source-vertex proximity matches within5km | 166 /166 |

All smaller components are retained. Original source arc lengths and positive rounded time costs are conserved; no weights are derived from shortened geometry. The complete83-case proximity ledger is retained. **Proximity to an original source vertex is not nearest-segment snapping, legal access or OD reachability proof**, and the selected observed routes do not establish arbitrary-origin or national accuracy.

Geometry storage is explicitly quantized to1e-5 degrees, while junction/node identity remains exact original float64. Maximum observed per-axis quantization error is approximately5e-6 degrees; nodes never merge because of this storage format. This is proposed storage, not active geometry.

The source run takes **50.391 seconds**, peak process RSS **548,601,856 bytes** on this Mac, within its frozen600s/1GiB source guards. These are offline producer observations, not runtime/cloud request latency or memory.

## Initial storage gate: failed

Typed arrays total214,973,541 raw bytes. Source geometry alone has48,900,800 int32 values /195,603,200 bytes; gzip geometry is65,661,904 bytes before base64.

The frozen projection replaces v9's existing Census layer and supplemental visits, keeps all other v9 data, adds measured gzip/base64 fields, existing function overhead and a **4MiB integration/index/metadata reserve**. Initial forecast is **117,564,652 bytes**, failing unchanged **70,000,000**. Connectivity, proximity and conservation gates pass; `advanceToRoutingPrototype:false` remains preserved. This is a storage forecast, not an assembled runnable app or package qualification.

## Separate lossless encoding gate: also failed

A separately [frozen codec plan](codec-plan.json), SHA `4f397a310ccc134d4b9ce22f0ce13fefb1cb9304f6fb521c3baf548ed6b0a0c0`, predates that result and reads only saved arrays. It performs signed32 zigzag, canonical unsigned LEB128 and gzip. Every integer, including repetitions/part starts, retains its position. No geometry/topology/cost/index change, source pass, simplification, tolerance sweep or new query.

[Codec result](codec-report.json): all **48,900,800 integers round-trip exactly**, with identical restored raw-array SHA `2f135e738ddf30bb545676133d2faa8a45148b10e7c65c6da838abc5e8eb664d`. Varint bytes57,686,266; gzip47,945,014; base64 size63,926,688. All other arrays remain byte-identical. The unchanged-reserve projection falls to **93,943,156 bytes**, still failing70MB. `advanceToRuntimeDesign:false` remains preserved. No budget increase or codec sweep. Codec12.470s/32,096,256-byte process peak is a producer scope, not an implemented runtime decoder or cloud measurement.

## Independent checks

[Independent audit](audit.json), [source](audit.py), uses compact adjacency/BFS rather than the producer's union-find, confirms all3,100 components and98.5437% largest length share, source lengths/weights, every83-case/166-endpoint denominator, and both failed forecasts. A separately implemented byte decoder reproduces the raw integer SHA. It checks saved arrays, not another source/graph producer or route search.

Eight synthetic topology/geometry/proximity fixtures and six codec fixtures pass. Tests include exact endpoint/interior splitting, no near-point merge, no unshared geometric crossing, loops/repeated vertices, component lengths, storage rounding without identity merge, radius/bin boundaries, signed limits, chunk boundaries, deterministic random values, malformed/truncated/overflow/noncanonical input and count bounds. **57 total Python fixtures**, **175-file Biome** and ordinary app build pass. Runtime source/dependencies are unchanged, so no redundant full server/DB/Vercel/memory/graph suite was run. Prior v9 qualification retains its original scope. [Checks and source bindings](checks.json), [record manifest](sha256.json).

## Concrete next proposal, not an implemented model

[Next design](next-design.json), SHA `5eece245f8e6922796d6f0511c1beb23b116c966dc69e7064b7843817ec248dd`, specifies **one fixed25m total geometry deviation bound**, including quantization. It protects exact source junctions/endpoints, multipart boundaries and0.025° grid entry/exit crossings; retains full-source cell visitation and original arc lengths/time costs; and adds degree2 cell-crossing road nodes without merging unrelated source visits. Its25m engineering tolerance is below2% of the smallest1.8km display cell, not fitted to route outcomes or an ETA accuracy claim.

The geometry producer has **not** been implemented or run. Independent span/protected-position/physical/source-identity checks and actual indexes/metadata plus the original4MiB reserve must fit70MB before any routing prototype. Only then freeze an exact routing recipe and evaluate all83 observed ORS routes, all35 Valhalla sensitivities, individual losses, means/horizons/median/tails/classifications, finite/path/shading, source/land consistency, retained memory, first local compute<=5s and actual package<=70MB. No deployment/accuracy claim can come from the present connectivity or size forecast. No finer display grid is promised. V9 stays active; all48/6/29 provider budgets remain consumed.

## Assets and safe recovery

Ignored `data/coarse-quality/census-backbone-preflight-v1/` contains plan/report and10 gzip arrays; `census-backbone-codec-v1/` contains its independent plan/report/encoded geometry. Pinned source ZIPs/manifest/tool remain at the existing Census paths; the app needs none of these preflight assets. Source runners refuse overwrite. Preserve failed outputs and sealed producers; do not rerun them as readiness checks.

Read-only saved checks from repo root:

```sh
python3 -B -m unittest discover -s scripts -p 'coarse_backbone*_test.py'
python3 -B docs/evidence/coarse-backbone-preflight-2026-10-25/audit.py > /tmp/backbone-audit.json
python3 -B docs/evidence/coarse-backbone-preflight-2026-10-25/verify.py > /tmp/backbone-bindings.json
```

The audit requires ignored arrays and uses roughly300MB transient memory; it calls no services or source producer. The binding check reads files/hashes only. [Current setup/commands](../../local-development.md#sparse-census-backbone-preflight), [next steps](../../next-steps.md). No provider/key/env/cloud-DB read, download, dependency/schema/runtime change, commit/push or agent deployment. Existing v9, UI, all eight prior sealed runs and all older failures remain unchanged. Current command examples damaged by an earlier formatting cleanup are corrected; original checksum-bound reports are preserved.
