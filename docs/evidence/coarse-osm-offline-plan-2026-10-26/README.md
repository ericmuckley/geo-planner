# Proposed offline US-input revision — October 26, 2026

**A concrete versioned offline preparation proposal is ready; no larger budget, snapshot or acquisition is activated.** Local capacity supports the proposed caps at observation time. Completion time, source suitability and actual peak memory remain unmeasured. This completes the [resource/snapshot proposal scope](../coarse-osm-bulk-review-2026-10-26/next-scope-plan.json). [Exact proposal](proposal.json), [capacity observations](capacity.json), [sources](sources.json).

## Source identity and explicit snapshot revision

Propose `https://download.geofabrik.de/north-america/us-261025.osm.pbf`, listed **12,229,320,016 bytes**, with captured publisher MD5 **`c5abaec55e724255277f22fb97941e5a`**. The [checksum response](linux-metadata/dated-md5.bin) identifies that dated filename; it is an integrity checksum, not strong authenticity proof. No PBF was fetched or source SHA256/header observed. Future capture must check exact size/MD5 and retain a new SHA256. No latest/date/mirror fallback. [Publisher listing](https://download.geofabrik.de/north-america/us.html).

The proposed new header state is **`2026-10-25T21:21:21Z`**, explicitly different from the old exact-time query `2026-10-21T00:00:00Z`. It remains a required future header check, not an observation in the dated PBF. PBF replication state does not guarantee inclusion of every object with an earlier timestamp; v2 must describe publisher-state identity accurately. Old snapshot/evidence stays intact. All 21 validation boxes/order/denominators remain unchanged. [Format semantics](https://wiki.openstreetmap.org/wiki/PBF_Format).

## Proposed offline caps and capacity

| Limit | Original pilot | Proposed v2 preparation |
| --- | ---: | ---: |
| Delivered HTTP bodies, tools/metadata/errors included | 512 MiB | **12 GiB** |
| Worker memory / swap | 1 GiB / 0 | **4 GiB / 0** |
| Working files, including tmp reserve | 2 GiB | **64 GiB** |
| Global elapsed limit | 1 hour | **4 hours** |
| Tmpfs | 64 MiB | **256 MiB** |
| Retained normalized elements / window occurrences | 250,000 / 500,000 | unchanged |
| Normalized extract | 128 MiB | unchanged |

The network plan permits at most **17 GETs**, including at most six locked wheels and **one PBF GET**, with zero retry/range/resume/redirect/paid/provider fallback. Planned maximum components total **12,382,412,112 bytes**, below the 12 GiB ceiling by **502,489,776 bytes**. These are assigned caps, not measured transfer. Tool archives remain within 128 MiB; metadata within 16 MiB. Verified direct TLS, journal-before-I/O, absolute/idle/global deadlines and bounded partial/error preservation must be implemented and tested before capture.

Disk assignment totals **65,270,488,400 bytes**, leaving **3,448,988,336 bytes** inside the 64 GiB limit. It includes the exact raw source, two independent **24 GiB** coordinate indexes, installed/archive tools, normalized output, metadata, logs/state and tmp reserve. Require **80 GiB free** at start, preserving 16 GiB host headroom. Observed free space is **166,461,988,864 bytes**; host RAM **16 GiB**, Docker RAM **8,218,034,176 bytes**, ten CPUs. Proposed worker is two CPUs/4 GiB; recheck capacity at execution. This is capacity evidence, not a reservation or processing benchmark.

National upstream scanning is a separate explicit increase: per decode pass at most 1 billion nodes, 100 million ways and 10 million relations, four passes/4.44 billion object visits overall. Selected-element/window/extract caps remain unchanged. No source count is inferred from compressed size. Index, memory, byte or time guards may stop much earlier. Four passes describe object decoding; extra hash/framing I/O also falls within the global elapsed bound.

## Generic extraction and independent audit

Use streaming **Pyosmium 4.3.2**, copying retained native fields before object views expire, without national in-memory location caching. The cached Linux image has Python 3.13.5/SQLite 3.40.0, but no Pyosmium; the host also has no inspected Osmium tools. [Streaming contract](https://docs.osmcode.org/pyosmium/latest/user_manual/01-First-Steps/), [processor reference](https://docs.osmcode.org/pyosmium/latest/reference/File-Processing/).

Pass one builds a capped SQLite ID/coordinate index and checks **every highway-way segment** against the original boxes. Select crossing and touching ways even with both endpoints outside; missing geometry stops the run. Pass two recovers every selected node's full native metadata and relevant raw restriction relations. Keep ordered full-node dependencies and typed identities, outside-box nodes, raw tags/conditions/access/roles and unresolved external references. No speed/access interpretation or matcher.

Passes three/four rebuild a separate coordinate index and independently reconstruct selection/native records/inventories before comparison. Shared Pyosmium decoder/SQLite/low-level primitives are explicit; this is not independent physical-road or source-coverage verification. [Seven synthetic geometry cases and further requirements](synthetic-cases.json) are design fixtures/arithmetic checks, **not a tested PBF reader**.

Each 24 GiB index has 4,096-byte pages and `max_page_count=6291456`; cache/mmap/temp/journal settings are specified and must be read back/tested. `journal_mode=OFF` is limited to new derived indexes: SQLite documents possible corruption after errors/crashes, so failed indexes are retained as untrusted evidence and never resumed. Raw input and failure ledgers remain intact. Cache settings are hints; cgroup memory is the hard guard. No app PostgreSQL access is involved. [SQLite contracts](https://www.sqlite.org/pragma.html).

Complete extraction from the acquired publisher file is distinct from complete global OSM or physical roads. Publisher clipping adequacy/outside-file competitors need a separate source-boundary decision for every window; polygon containment alone does not prove inclusion of every possible long crossing segment. Original all-21-source-complete, 50% unique plausible usable-limit Census-km, independent match review and every model/physical/package/startup/API/visual gate remain unqualified.

## Tool identity, actual inspection and next implementation

Captured [package metadata](linux-metadata/pyosmium-json.bin) pins a **1,729,855-byte** CPython 3.13 Linux aarch64 wheel, SHA256 **`456234255186a6f9aae83e70cce3e878f51673c37595f116d54f2cd861151b61`**. Runtime `requests` dependencies still require exact version/URL/size/SHA256 closure; maximum six wheels, no extras/source build/apt/image pull. No binary was downloaded, installed or imported. Before a PBF request, the later tool-only setup must verify ABI/native tiny-PBF/decoder/framing tests with networking disabled. [Publisher metadata](https://pypi.org/pypi/osmium/4.3.2/json).

Actual direct inspection used **five metadata GET attempts / 51,238 delivered body bytes**, separate from unmetered official-document browsing. The first three host attempts failed certificate verification with zero body bytes; failures remain in [the host ledger](metadata-ledger.json). Two deliberately repeated inspections through the cached Linux trust store succeeded, with verification enabled and no trust/config bypass; [Linux ledger](linux-metadata-ledger.json). There were **two manual metadata repeats**, zero automatic retries, PBF/tool payloads, provider calls or app DB operations. These small inspection reads had socket/elapsed checks; they do not prove the future absolute-deadline acquisition meter.

Next implement the controls/extractor/separate audit and test using captured metadata plus synthetic native/frame/SQLite cases. No live metadata, tools or national data in that implementation task. Actual Pyosmium decoder proof remains pending a later frozen tool-only setup. Then freeze the exact executable data recipe before one future acquisition at new ignored `data/coarse-quality/us-osm-input-v2/`. [Next implementation scope](next-implementation-plan.json), [prospective interfaces and check order](commands.json). Future script names/templates are not executable commands yet.

No existing producer, runtime, UI, env/DB/npm, Vercel configuration or source/model gate changed. Old failed runs, consumed provider budgets and deployed v9 remain; work is local/uncommitted. Larger preparation stays offline and does not enlarge Vercel's compact static-cost package. Previous implementation test/build/resource proofs remain bound; this proposal did not rerun them or claim new reader/resource qualification.

Read-only proposal verification, without network/Docker/producer replay:

```sh
python3 -B docs/evidence/coarse-osm-offline-plan-2026-10-26/verify.py
python3 -B docs/evidence/coarse-osm-offline-plan-2026-10-26/verify.py --local-assets
```

[Handoff](../../agent-handoff.md), [ordered next task](../../next-steps.md), [local recovery](../../local-development.md#proposed-offline-us-input-revision).
