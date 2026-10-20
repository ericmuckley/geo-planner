# Historical documentation archive

These reports describe earlier experiments, resource gates, proposals and handoff states. Some still explain code/proof dependencies; archived does not mean safe to delete. Their old “current,” “next” and admission-hold statements do not override [the current handoff](../agent-handoff.md), [status](../implementation-status.md) or [next steps](../next-steps.md).

The current baseline is [the two-hour region](../two-hour-region.md). [Evidence](../evidence/) stays at its existing paths because frozen build recipes and checksums reference it. Only unbound evidence-index navigation links were adjusted; measurement files and checksum-bound indexes are preserved.

Thirty-six reports moved here on October 19, 2026. Four small forwarding pages remain at their former top-level paths for checksum-bound evidence indexes. The old handoff snapshot is preserved byte for byte as a raw `.txt` record; its historical links are text, not current navigation. The relocation/validation record is `reorganization-2026-10-19.json` in this folder.

## Original brief and proposals

- [Init](init.md)
- [Routing on Vercel: two options](worldwide-routing-options.md)
- [Brainstorm: inexpensive 12-hour US driving reachability](long-range-routing-brainstorm.md)
- [Proposal: precomputed anchors for US reachability](anchor-precomputation-proposal.md)

## Early routing references and models

- [Offline anchor pilot](offline-anchor-pilot.md)
- [Static turn-aware routing reference](state-routing-reference.md)
- [Grouped road-state reachability experiment](cell-routing-experiment.md)
- [Compact native routing baseline](native-routing-baseline.md)
- [Maneuver history and interior destinations](maneuver-routing-model.md)
- [Qualified control-point access (v3)](barrier-access-model.md)
- [Regional routing capacity and border findings](regional-routing-capacity.md)
- [Streaming importer and wider-region retry](streaming-import-capacity.md)
- [Wider v3 routing qualification](wide-v3-routing.md)

## Previous coverage and visible experiments

- [Broader San Diego–Tijuana capacity preflight](coverage-buffer-preflight.md)
- [Compact routing import and larger buffer](compact-routing-import.md)
- [Compact OSM input and explicit no-swap recipe](compact-osm-input.md)
- [Cut inventory and next coverage preflight](coverage-increment-preflight.md)
- [Sparse preparation and complete-workload resource gate](sparse-routing-resources.md)
- [San Diego and northern Baja coverage increment](regional-coverage-increment.md)
- [Qualification headroom and the next one-hour buffer](hour-coverage-preflight.md)
- [East/south one-hour coverage qualification](hour-coverage-qualification.md)
- [Two-hour frontier and resource preflight](two-hour-coverage-preflight.md)
- [Visible local long-range experiment](local-routing-experiment.md)
- [Expanded local routing baseline](larger-region-experiment.md)

## Earlier resource and storage work

- [Routing preparation and importer lifetimes](routing-preparation-lifetimes.md)
- [Completed input reads and bounded graph exports](routing-io-lifetimes.md)
- [Restriction-member road lookup — October 18, 2026](routing-member-lookup.md)
- [Targeted source-evidence indexes — October 18, 2026](routing-source-evidence.md)
- [Base-graph road-ID storage — October 18, 2026](routing-base-id-storage.md)
- [Range-advised source XML reads — October 18, 2026](routing-xml-streams.md)
- [Compact outgoing-road storage — October 18, 2026](routing-outgoing-storage.md)

## Previous provider and Valhalla verification

- [Regional routing verification — 2026-10-16](routing-baseline-verification.md)
- [Regional expansion and Vercel verification](routing-expansion-verification.md)
- [Hosted US routing verification](hosted-routing-verification.md)

## Historical handoff material

- [Historical routing recipes](historical-routing-recipes.md)
- [Pre-audit handoff snapshots (raw historical text)](handoff-history-2026-10-19.txt)

Frozen tooling can still name former `docs/<report>.md` paths in error messages. Look up the same basename in this archive; those source files were not edited merely to update diagnostics.
