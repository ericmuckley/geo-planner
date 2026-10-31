# Fixed-policy saved-path control — October 25, 2026

**The 10% allowance changes the travel cost; rerouting offsets very little of it.** On all 83 saved cases, holding the earlier graph-state/source-arc sequences raises predicted time by **34.601 min on average**. Actual new path choices recover **0.0268 min (1.61 s)**. The six new missed-reachable cases gain 54.933 min on average. This explains why a uniform allowance improves the overall average yet harms some queries. It does not select another factor or qualify either rejected candidate. Deployed v9 remains unchanged.

Local/uncommitted work at HEAD `648c731`; no new routing search, field, contour, provider call, source producer/download, env/key/DB input, dependency/config change, commit or deployment. The [prior cost experiment](../coarse-road-time-allowance-2026-10-25/README.md) remains rejected under its original six failed gates. All older evidence/producers retain their bindings.

## Method and controls

The [exact recipe](plan.json), SHA `674b94d1b822dbbd670fa804acf438aa377b84f1f4632d031b40e15ddf02a65d`, freezes tools and inputs before the full-data calculation. [Pure helper](../../../src/server/backbone-path-control.ts), [eight synthetic tests](../../../src/server/backbone-path-control.test.ts), [CLI](../../../scripts/inspect-road-time-path-control.ts). The earlier unbuffered path is priced at old costs, repriced at the same 1.10 policy, then compared with the actual captured 1.10 path. Every old/current recorded price, graph state, source arc identity, position, transition eligibility and component sum reproduces.

This holds **graph states and source arc IDs**, not literally all geometry. An endpoint may use a different cheapest eligible attachment to its held state; a held base-state pair may choose its existing road/local minimum. These effects are explicit. No held base-pair kind changes occur in this dataset. The independently saved base source/connector proofs separate pure road allowance from connector and rounding costs. Mixed endpoint costs stay separate from source-class exposure.

For each case:

```text
direct cost shift   = held-state new cost − old cost
path-choice benefit = held-state new cost − actual new cost
actual cost shift   = direct cost shift − path-choice benefit
```

All **83 held graph-state prefixes fit the 900-minute cap**, including the origin attachment and excluding the final destination attachment; maximum 797.786 min. Every actual prediction is at or below its eligible held-state bound. No cap-limited, missing or replaced case. All 35 older Valhalla sensitivities remain linked in the same rows. These are point-cost accounting checks; saved shading/accuracy decisions are inherited from the prior comparison, not newly computed.

## Measurements

Means below are minutes. Signed error is model minus saved ORS time. Cohorts are frozen by the prior comparison's classifications and original 20/5-minute regression limits.

| Cohort | Cases | Direct shift | Path-choice benefit | Actual shift | Old signed error | New signed error |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| All | 83 | 34.601 | 0.0268 | 34.574 | −40.084 | −5.510 |
| Frontier | 48 | 52.992 | 0.0459 | 52.946 | −59.290 | −6.344 |
| Original | 11 | 11.573 | 0.0008 | 11.573 | −16.832 | −5.260 |
| Regional | 24 | 8.373 | 0.0006 | 8.372 | −12.329 | −3.957 |
| New misses vs v9 and unbuffered | 6 | 54.955 | 0.0221 | 54.933 | +8.453 | +63.386 |
| Persistent unbuffered misses | 2 | 65.489 | 0 | 65.489 | +19.302 | +84.791 |
| Original individual-regression limit exceeded | 17 | 44.715 | 0.0170 | 44.698 | −15.614 | +29.084 |

The overall direct shift decomposes into **34.5013 min pure source-road allowance**, −0.0005 base rounding, zero base road/local substitution and +0.1002 endpoint cost. Path choice offsets only **0.0775%** of the direct shift. State/arc sequences change in 51 cases, but only 30 have a benefit above numerical tolerance; the largest benefit is **0.3654 min (21.9 s)**. Counting changed paths alone would overstate their effect.

Four of the six new misses were already slower than ORS; two were faster. Their old signed errors range −22.003 to +23.025 min; after the allowance, all six are +44.925 to +93.336 min. Across all 83, 74 unbuffered predictions were faster than ORS, versus 57 with the allowance. These summaries demonstrate heterogeneous residuals; they do not establish which road class, access rule, provider behavior or missing real-world delay causes them. Names/coordinates identify validation records only.

[Raw report and all rows](report.json), [three-way transition audit](edge-audit.json.gz), [independent analysis](analysis.json), [independent audit recipe](analysis-plan.json). No new gate evaluation, parameter sweep or holdout claim. ORS's observed recommended fallback and the older Valhalla disagreement remain as described in the [provider audit](../coarse-backbone-path-audit-2026-10-25/README.md).

## Verification and continuation

Eight synthetic tests pass, including parallel-arc identity, same-state base alternatives, attachment costs, conditional cap bounds and invalid captures. Biome checks 197 files; app and strict CLI typechecks and ordinary build pass. The independent Python audit reproduces **249 component totals**, sums **87,483 transition prices**, verifies captured identities/equations/cohorts and confirms the complete cap/bound ledger. A TypeScript inference annotation was corrected before the frozen dataset run; [development notes](development-notes.json).

One offline control takes **2.300 s**, observing **877,608,960 bytes RSS** with two decoded models and audit objects. This is neither retained application memory nor peak/cloud memory or packaged query latency. No application performance qualification is claimed.

Ignored `data/coarse-quality/road-time-path-control-v1/` holds the three completed outputs. The report and compressed transition audit are copied here; the plan is byte-identical. Do not rerun the named output. Read-only recovery:

```sh
python3 -B docs/evidence/coarse-road-time-control-2026-10-25/verify.py
python3 -B docs/evidence/coarse-road-time-control-2026-10-25/verify.py --local-assets
```

Next use the **existing saved per-case residual, road-class exposure and corridor evidence** to decide whether a selective generic correction has support, or whether required evidence is missing. The [next diagnostic specification](next-diagnostic-plan.json) excludes another blanket-factor trial, fitted case rules and new routing/provider work. Freeze its exact join/audit tool before measurement. Any later candidate needs a separately frozen implementation and every original accuracy/physical/software/packaging/query/visual gate. [Ordered task](../../next-steps.md).
