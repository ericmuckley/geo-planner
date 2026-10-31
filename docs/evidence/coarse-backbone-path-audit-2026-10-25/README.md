# Saved backbone paths and provider settings — October 25, 2026

**The completed offline audit identifies a reference-profile mismatch and reconciles all captured costs.** It does not qualify the rejected backbone candidate or change active v9. This is local/uncommitted work at HEAD `648c731`, with no new route search, provider call, source download, env/key/DB input, schema/dependency/config change or deployment.

The [prior candidate](../coarse-backbone-routing-2026-10-25/README.md) remains rejected: ORS MAE 29.257→43.234 min while older Valhalla sensitivity improves. This audit uses its captured paths and all 83 saved ORS/35 Valhalla records. The [primary recipe](plan.json) freezes 312 input files before measurement; the separately frozen [base-link annex](base-plan.json) checks the remaining coarse-road cost attribution. [Findings](findings.json), [complete per-case report and coverage ledger](report.json), [detailed source-edge audit](edge-audit.json.gz), [base report](base-report.json), [base-edge audit](base-edge-audit.json.gz).

| Measured item | Result |
| --- | --- |
| References retained | 83 ORS /35 Valhalla; none missing |
| ORS requested preference | `fastest`, in all 83 requests and response-query echoes |
| ORS service warning | All 83 say `fastest` was deprecated and `recommended` was used |
| ORS minus Valhalla duration,35 pairs | Median **14.458 min**; ORS slower in all 35, range 2.804–32.285 min |
| ORS /Valhalla reported distance | Median **0.998902**, about 0.11% shorter; individual ratios 0.98356–1.11926 |
| Whole-provider corridor proximity,1 km | Median 100% in each direction; means 85.62% /86.17% |
| Captured detailed Census edges checked | **22,316**; exact incidence/endpoints/time/speed and decoded geometry/cumulative weights |
| Captured coarse base road edges checked | **6,576**; exact v9 proof costs/source kinds/road and connector pricing |
| Complete captured cost accounting | All 83 paths reconcile, including explicit unresolved attachment portions |

The saved ORS engine cohort is9.10.0, build 2026-08-13, graph 2026-09-21, OSM 2026-09-13. It echoes `preference: fastest` while its system message reports the fallback; both facts remain in the inventory. Requests exclude ferries/borders. Saved Valhalla uses auto costing with freeflow/constrained speed types, version 3.9.1-7fd2228e5 and the recorded tile timestamp. Its35 returned summaries report no ferry; the requests do not specify identical avoidance/profile semantics. Regional graph provenance records OSM 2026-10-14; original captures retain engine/tile status but no per-route graph identity. The primary benchmark remains its observed ORS result; no old failed gate is reinterpreted.

Similar distances and high median proximity on the older 35 pairs show that route length alone is insufficient to explain the duration gap. Mean proximity is lower, and some paths differ substantially. Profiles, route choices, source dates and speed/turn assumptions remain confounded. The warning does not establish that `recommended` caused the gap, that Valhalla is ground truth or that a particular speed factor is correct. There are no corresponding Valhalla references for the48 frontier cases.

## Exact coverage and fallback check

Detailed source geometry accounts for **70.114% of aggregate candidate time**. Its per-case median source-length share within 3 km of ORS is **92.580% across 80 cases**; three cases have no complete Census arcs and remain in the denominator/coverage ledger. Reverse proximity compares the full provider route to the captured Census subset, not to a complete candidate route.

The remaining aggregate time is 27.355% coarse base-road transitions,0.768% local,0.978% transfers and0.786% mixed endpoint attachments. Base road representative chords and mixed origin/destination attachment geometry remain unresolved; their cost accounting is exact. Source samples retain original cumulative-km weights rather than shortened chord length. Provider samples use the existing length-weighted midpoint scheme. Disconnected arcs/legs never gain artificial joining segments. Corridor proximity is not road identity, road access or contour-area accuracy.

The retained fallback is **mixed-source**, correcting earlier “NE/local fallback” shorthand: its qualified v9 link proof includes Census links. The annex finds only **one captured coarse Census edge**,1.5967 min in one case, versus 6,575 Natural Earth edges. That is 0.00539% of total candidate time. It is a real semantic limitation, but selected-path usage does not support blaming it for the broad timing regression. No fallback filtering, costs, topology or attachment rules were changed.

## Verification and next action

Ten new geometry/accounting tests plus four base-attribution tests pass;85 total Python fixtures, 190-file Biome and ordinary build pass. Every captured detailed source edge matches the qualified arrays, and every selected base-road time matches the existing v9 proof with source/connector/rounding costs reconciled. Source producer and rejected routing comparator were not rerun. The primary audit takes 10.707 s and observes 282,279,936 bytes maxRSS on this Mac—offline diagnostic scope, not application/cloud performance. An initial annex plan preparation used the wrong prior-checks field name; [preparation events](preparation-events.json) preserve the correction before any annex measurement/output.

Ignored `data/coarse-quality/backbone-path-audit-v1/` and `backbone-base-audit-v1/` preserve completed outputs. [Exact commands and prerequisites](../../local-development.md#saved-backbone-pathprovider-audit). Quick read-only recovery:

```sh
python3 -B docs/evidence/coarse-backbone-path-audit-2026-10-25/verify.py
python3 -B docs/evidence/coarse-backbone-path-audit-2026-10-25/verify.py --local-assets
```

Next specify and freeze **one generic cost-only hypothesis** before a new candidate. Hold source geometry, selected source alternatives, grid/access/fallback eligibility and all original 83/35 gates fixed; separate road travel from artificial connectors/local transfers and rounding. Reproduce the current costs before changing one declared component, and preserve this provider/coverage uncertainty. No fitted factor or speed change is selected by this audit. Any candidate still needs all accuracy, physical/source, software/API, packaging/storage, first-query and visual gates before activation. All 48/6/29 provider budgets remain consumed; the runtime stays v9.
