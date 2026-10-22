# V3 general shore connectivity — October 22, 2026

The local app now serves `coarse-road-grid-v3`. The same rules apply throughout the contiguous-US dataset; selected place names/coordinates occur only in tests and diagnostics. V2 road weights, existing road anchors, class speeds and original land mask are unchanged. No hosted routing request, graph expansion, new environment variable or migration is required. This session did not commit or deploy the change. [Model and limitations](../../coarse-estimator.md#v3-general-shore-connectivity).

## Implemented behavior

- **1,535 mixed shore representatives** lie on retained generalized country land outside lakes. **4,599 bidirectional local links** follow continuous land in one country polygon component at the existing 25 km/h assumption. Links are partitioned at every polygon intersection, so narrow channels and diagonal island contact cannot disappear between samples.
- **245 road access points** are derived from the exact retained road visit owning each unchanged v2 anchor. An input may reach a land access point by checked local travel and follow that visit’s geometry to the anchor, permitting explicit bridge/tunnel access. Positive access cost includes road arc length, rounding/anchor connectors and local distance, all at 25 km/h.
- Straight input attachment is used when supported. Otherwise all supported fallback attachments in the input cell/eight neighbors seed search; a nearby land patch can be a dead end while another access point reaches the road network. An unsupported accepted origin displays only its isolated cell. A maximum 1 km water prefix applies only at the input end, not at internal water gaps. Shared land/traversal masks stay unchanged by queries.
- Filled contours still cover whole cells. One representative per cell can omit/merge smaller land components, interior overland travel remains approximate, and inherited cartographic road crossings/access are not real-world guarantees. `attachmentKm` is the minimum initial attachment distance, not a decomposition of every reached route.

## Preserved attempts and final comparison

The first [land-only prototype smoke](land-only-attachment-smoke.json) stranded New York at one cell and Key West at two. Its [builder](land-only-builder.py), [kernel](land-only-grid.ts) and [regional comparison](land-only-attachment-comparison.json) remain preserved. A second [greedy-attachment attempt](greedy-attachment.json), with [kernel snapshot](greedy-attachment-grid.ts), restored New York but chose a dead-end Key West land representative. Those apparent regional gains were insufficient. Retained-road access and all supported fallback seeds restore bridge-connected origins while leaving unrelated islands isolated. Intermediate artifact identities and current source snapshots are in [provenance](provenance.json).

[Final offline comparison](comparison.json) uses unchanged saved reference responses:

| Set | Common finite point cases | Mean absolute reference difference, v2 → v3 | Changes |
| --- | ---: | ---: | --- |
| Original San Diego sample | 11 | 31.381m → 31.381m | All unchanged |
| Broader regional set | 23 | 37.730m → 36.893m | Two improve; 21 unchanged; none regress |

The previously unreached **24th** regional destination is now reached/shaded from the opposite shore at 6h/12h, with symmetric modeled point cost **145.985m** versus **61.268m** static reference. It is separate from the common-finite timing mean. No sample destination remains unshaded. Membership improves; this substantial time difference and earlier mountain regressions remain. Both sets now guide refinement and are regression evidence, not fresh holdouts, live ETA truth, national accuracy or six-/twelve-hour frontier validation.

V3 approximate point arrival minimizes arrival through the same checked attachments used for departure; v2 retains its original center/anchor access semantics. Cell arrival and exact-point proxy access remain different. The comparison script asserts unchanged v2 costs against the preserved broader report and unchanged roads/speeds in the new artifact. No service or database is called.

## Verification

- [39 passing server tests](server-tests.log), [six passing Python geometry tests](geometry-tests.log): every 4,599 new shore link, 245 access-point land/physical bounds, all 33,398 unchanged road lower bounds, mixed shores, narrow channels, holes, diagonal contact, same-cell islands, explicit road access, multiple fallback seeds and bridge-connected origins. Prior provider/history/server tests pass.
- [42 national smoke cases](national-smoke.json): fourteen origins at 6/10/12h, monotone counts and bounded payloads, now rejecting degenerate connected-origin outputs. [Before/after observations](national-comparison.json) retain scope: Key West 6h counts change 344 → 338 while 10h/12h increase; source-access paths and display membership changed. Counts are not accuracy scores. New York 6h retains 4,000 cells and Key West 6h retains 338.
- [Check](check.log), [app typecheck](typecheck.log), [diagnostic typecheck](diagnostic-typecheck.log), [ordinary build](build.log) and [Vercel build](vercel-build.log) pass. Two builds produce identical **4,673,811-byte** artifacts, SHA-256 `8cfa5616b52138c16d5a8cb8f84fd1ee4345f7e4026e88c104365cad25c523e0`.
- [Generated Vercel handler](vercel-handler.json): **8,464,942-byte** function, San Diego 6h / Denver 10h / New York 12h contours, outbound fetches rejected, detailed experiment disabled, no grid or configured secrets in client output and database-free saved-history fallback. This is local execution, not a hosted deployment, cold-start, concurrency or peak-memory claim.
- [Browser observations](browser.json), [shore 6h screenshot](browser-shore-6h.png) and [New York 12h screenshot](browser-new-york-12h.png) record visible local v3 results. Ordinary public test queries use the existing automatic saved-history flow; no bulk historical upload was triggered. Database implementation is unchanged and live DB write integration was not repeated.

## Reproduce

```sh
npm run routing:compare:coarse:candidate
npm run test:coarse-data
node --import tsx --test src/server/*.test.ts
npm run routing:verify:coarse
npm run check
npm run typecheck
npm run build
npm run build:vercel
npm run check:coarse:vercel
```

The candidate comparison is offline. Regeneration uses the unchanged bundled v2 data and ignored pinned Natural Earth roads: [exact commands](../../local-development.md#regenerate-the-coarse-grid). No old producer/reference capture needs rerunning. [Provenance](provenance.json), [verification](verification.json) and `sha256.json` identify this run; source hashes are observational snapshots, not freezes on future product work. Original v1/v2, both regression bundles and rejected attempts remain intact. Next assess generic local-access detours and missing generalized roads, keeping the current simple bundled app.
