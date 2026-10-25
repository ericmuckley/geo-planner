# Where Geo Planner stands

Updated October 25, 2026. **V9 is active locally and ready for review/commit/deployment. It has not been deployed.** V8 and the slider remain the last user-reported production model. The working tree starts at `37ff14b`; v9, later reference/calibration evidence and the separately built floating-map UI are uncommitted.

- **A generic timing improvement:** artificial connections to Natural Earth roads now pay for their length at 55 km/h. Secondary roads use 85; major roads remain 105. Census connections and local travel stay 25. No city/region/query exceptions.
- **Measured development result:** average absolute difference against 83 saved ORS routes falls 34.6→29.3 minutes. On 48 boundary probes, correct classifications rise 23→32, false reachable falls 17→11 and missed reachable 5→2. All prospective gates pass. [Complete results](evidence/coarse-path-features-2026-10-24/README.md).
- **Uneven gains:** 59 routes improve and 24 worsen. Frontier median error worsens 37.3→40.6 minutes; older Valhalla sensitivity means also worsen. This does not establish national accuracy or fresh-query performance. Both earlier failed candidates remain rejected.
- **Same precision:** 0.025° cells, about 1.8–2.8 km. This change improves timing assumptions; grid blockiness and merged crossings remain.
- **Vercel remains simple:** 61.23 MB bundled model,65.05 MB function, first local packaged estimate 3.44 seconds after configuration. No routing service or DB is needed for estimation. Decoded retained storage is 158.05 MB, with bounded query retention. These are local observations, not cloud cold-start/peak/load guarantees.
- **Verified:** 56 server tests,43 Python fixtures,9 gate tests,42 API cases, full source/link/shore/transfer checks, independent source repeat, check/typechecks, both builds, generated handler,15 local HTTP checks and browser gain/regression/slider/contour review. No live history writes needed.
- **UI:** full-viewport map with a floating collapsible control panel; automatic 30-minute–12-hour slider defaults to 2 hours. The separate UI edits are preserved byte for byte.
- **Remaining limits:** generalized road geometry, assumed overland access, merged crossings and no traffic, turns, terrain, ferries or verified border access. All 83 references are observed development data; more reference requests require separate authorization.

Next: review/commit/deploy the local changes, then verify v9's hosted API and automatic slider. No new env variable, dependency or migration is required. All 48/6/29 provider budgets are consumed. Detailed regional research remains parked. [Resume guide](agent-handoff.md), [next steps](next-steps.md).
