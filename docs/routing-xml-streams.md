# Range-advised source XML reads — October 18, 2026

This experiment releases completed source-read ranges during evidence generation, continuing [the base-ID memory work](routing-base-id-storage.md). It changes cache handling and file lifetime while preserving the graph, source excerpts and errors. It uses cached data and no provider quota. [The short progress summary](progress.md) describes the remaining 10–12-hour goal; the hosted app stays at 60 minutes.

Follow-up: [compact outgoing-road storage](routing-outgoing-storage.md) now reproduces all four cases and lowers the current complete peak further to **1.062 GiB**. The measurements below preserve this earlier XML-stream version.

## Implementation and safeguards

`xml_stream.py` wraps a binary file opened with `rb`. After bytes have been copied into a Python read buffer, it requests `POSIX_FADV_DONTNEED` on completed ranges of at most **16 MiB** for files at least **8 MiB**. EOF and explicit close release the last completed partial range. It never advises unread bytes, synchronizes/writes the source, seeks or drops caches globally. Small files skip advice.

`read(size)` returns the original file's bytes, including zero-length and unbounded reads; advice ranges do not impose a general read-buffer limit. The real XML parser's observed read sizes are recorded separately. Each pass records bytes, read/range counts, maximum sizes, advice errors, EOF and close status. Advice failures are recorded without masking parsing/read exceptions. A production worker refuses success if a real enabled stream has failed advice, missing bytes, missing EOF or an unclosed handle. Advice remains a kernel hint; actual memory measurements establish its effect.

`xml_evidence.py` versions `targeted_evidence.source_examples` and `crossing_audit.source_uncertainties`, changing only their XML reads to explicit contexts that close on success, parse errors and consumer errors. An AST check restores those contexts to the old calls and compares the processing bodies exactly. Parser events, selection/order, transition audits, uncertainty rules, tags and excerpt serialization stay unchanged. Graph construction, ID validation, encoders and existing import readers remain frozen. In particular, this does not make every XML pass in the preparation pipeline range-advised.

Eleven focused tests cover bytes/ranges, thresholds, zero reads, EOF, early close, context reuse, missing files, UTF-8 across parser-read boundaries, malformed input, advice failure and a large XML file with unchanged events/hash. Linux tests exercise real advice. Seventeen new synthetic source/uncertainty fixtures compare returns, audits, excerpt bytes and error type/message/priority with frozen readers (nine success/eight failure cases). Each worker also reruns 17 importer fixtures with 296 full/888 bounded independent fixture cost checks and the prior 11 control-point fixtures. Regional route/native qualification is reused on identical graph bytes rather than rerun here.

## Reproduce

Prerequisites are cached qualified graphs and canonical `data/base-id-pilot/base-ids-v1-*` records. No environment file, key, download or network is used:

```sh
npm run routing:xml -- --case downtown-v2
npm run routing:xml -- --case corridor-v3
npm run routing:xml -- --case wide-v3
npm run routing:xml -- --case hour-v3
python3 -B docs/evidence/routing-xml-streams-2026-10-18/analyze.py
```

Completed defaults are sealed in ignored `data/xml-pilot/xml-v1-*`. Repeat with the same fresh `--series xml-repeat-01` on all four commands, smaller cases first. Equality references remain canonical `base-ids-v1-*`; the hour case requires three same-code/same-mode smaller proofs. Changed code requires a new version and output identity; preserve all sealed attempts.

`xml_parity.py` and `xml-parity.mjs` retain two CPUs, 4 GiB RAM, no container swap, `--pull never`, no networking, read-only sources/recipes/root filesystem and a 256 MiB temporary filesystem. Tools stay pinned to image `sha256:6652906bfea590161b144a6e4fac146a41e14cbafae581dcb9e38c74ceaa53a7`, Python 3.12.3/Linux arm64, Valhalla tools revision `7fd2228e5863b442bc1ac8d25eece6415dd91bff`. These custom graph imports do not use Valhalla search. No dependencies are added.

Run identities bind source/profile/image/code, predecessor manifest/report and original qualification. Workers verify actual frozen sources/artifacts/recipes and snapshot their code. The current case verifies original independent/native reports, comparison counts and native source/binary bindings before saving success. No larger graph is attempted.

## Measurements

All **24 artifacts** match across the four cases, including all seven current graph/audit/source/CSR/gzip files. Original full/bounded/partial/native evidence remains bound to those identical bytes. All four workers pass the unchanged resource policy with **zero limit/OOM/kill events and zero swap**.

| Frozen case | Complete peak before → after (GiB) | Import before → after (s) | Complete before → after (s) | Real XML passes / advised ranges |
| --- | --- | --- | --- | --- |
| Downtown v2 | 0.04975 → 0.04989 | 1.74 → 1.97 | 2.11 → 2.42 | 0 / 0 |
| Corridor v3 | 0.270 → 0.238 | 40.54 → 40.28 | 47.54 → 47.60 | 2 / 10 |
| Wide v3 | 0.539 → 0.465 | 123.61 → 123.64 | 147.21 → 147.04 | 4 / 40 |
| Current hour v3 | **1.413 → 1.214** | **401.32 → 400.20** | **475.29 → 474.04** | **4 / 108** |

The current complete peak is **1,303,441,408 bytes**, down **14.1%** from 1,517,146,112. With the 25% factor it is **1,629,301,760 bytes / 1.517 GiB**. Worker peak RSS is **1,236,696 KiB / 1.179 GiB**, versus 1,256,536 KiB / 1.198 GiB. Smaller-case peaks do not uniformly fall; downtown has no real source-evidence XML passes and includes the added fixtures.

Each current XML pass reads **451,794,442 bytes** to EOF and closes explicitly, advising **27 ranges** with no advice errors. The four passes read 1,807,177,768 bytes altogether, with a maximum parser read of **16,384 bytes**. This is local source I/O, not downloaded data. Sampled cgroup file memory previously grew from **39,804,928 to 491,601,920 bytes** during source reads. It now stays around **40,214,528–40,222,720 bytes** at the equivalent checkpoints. Anonymous memory is recorded separately: the new source-phase samples are 1,007,714,304 bytes. Source evidence adds no new cumulative peak; the highest peak occurs during base construction (pass five), which remains unchanged in this experiment.

Validation passes: **162 host Python cases (153 pass, nine existing tool/platform skips)**, **71 scoped Linux cases without skips**, **14 adapter tests**, `npm run check`, `npm run typecheck` and `npm run build`. The Linux scope includes the 11 focused stream tests with real kernel advice. Existing database non-null assertion, MapLibre chunk-size and upstream TanStack directive warnings remain. The saved analyzer reproduces exactly, and all **188 pre-existing file fingerprints plus six frozen new recipe files** match. No environment values were read/changed and nothing was staged.

These are single local observations on Apple M4/16 GiB with uncontrolled host/VM/cache conditions. Complete cgroup peaks include fixtures, parsing, all base/history work, evidence, export and verification reads. Checkpoint peaks are cumulative, not isolated stage peaks. RSS and periodic anonymous/file samples are separate scopes; maxima must not be summed. Host/VM paging is unmeasured. The 25% factor checks current-workload headroom, not larger graph/query admission. These are preparation/verification timings, not graph-search, HTTP, contour, browser or Vercel timings.

The current graph remains `b50422b83537cecf12f1ecb4f7a3fa4e80df206726796b562135715f3737d048`: 3,034,771 roads, 3,036,124 states, 6,411,757 arcs and 1,160 via-way prohibitions. Bounds remain `[-117.65,31.9,-116.0,33.6]`; model `exploratory-static-car-v3` retains 5,000 ms signal and 20,000 ms U-turn delays. Source XML remains 451,794,442 bytes, SHA-256 `64462b578bd9b688290fa8777bbb2564ea40ed649c47d88146353c72097ab1a1`, from the cached California/Mexico snapshot dated `2026-10-14T20:21:12Z`. [Preparation/provenance](two-hour-coverage-preflight.md) is unchanged. Original regional full/bounded/partial/native qualification is checksum-bound and reused; the saved native report contains 258,070,540 cost/membership comparisons plus two partial destinations, from its original uncapped macOS run.

## Remaining work

**Next: version compact outgoing-road storage in base construction.** The current builder still retains up to **1,567,609 node entries / 3,039,480 road references**, with **221,840,968 bytes (211.56 MiB)** of dictionary/list containers alone. This excludes integer objects and allocator overhead. Measure construction/overlap peaks as well as retained arrays; a compact final representation alone does not establish a lower peak.

Preserve per-node append order, road-index order, generic/unordered fallback, duplicate/self-loop/cost validation and error priority. Keep routing, restrictions, access policy, source evidence and encoders frozen. Require adversarial fixtures and exact parity on these four graphs, with original independent/native bindings or fresh qualification, under the same cap. Qualification/reload memory still needs a separate complete-workflow assessment before any larger admission.

Coverage remains unchanged. Five sampled origins have no potential cuts within 60 minutes; first cuts are 63m32s–77m34s, and every selected 120-minute case reaches cuts. This does not prove all-origin/source completeness or long-range contours. Northern Baja remains; uncertain Otay ways `114198251`, `185333061` and `577149752` stay reported. Border queues, documents and current crossing eligibility are unmodeled. The larger continuation envelope still exceeds cached eastern/southern geography, including missing Arizona/Nevada roads.

Larger admission remains **on hold** pending source and complete-workflow resources. The old 20.64 GiB estimate is an earlier workflow's scaling forecast, not measured candidate graph/query RAM or a forecast for this path. An admitted graph still needs a fresh identity, exact rebuild, independent full/bounded/partial/native checks and all-direction cut inventory at 120 minutes. US-wide acquisition, the 10k-anchor batch, app range increases, caching and Vercel rollout remain deferred.

Raw records and exact validation commands are in [the evidence directory](evidence/routing-xml-streams-2026-10-18/README.md).
