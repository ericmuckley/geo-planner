# Where Geo Planner stands

Updated October 19, 2026. The goal remains a US-focused app showing where you can drive in **10–12 hours**, using our own data without routing-provider quotas.

- **Working locally:** our router accepts 1–720 minutes in `/experiment`, starting at **120 minutes**. The region includes Southern California, northern Baja and the Arizona border area. Start with `npm run dev:experiment`.
- **Progress:** the graph grows from 5.4 to **8.14 million states**. Exact rebuild and independent/native checks pass. All five reference locations now stay within detected data edges for two hours. San Diego’s first edge moves from **94½ to 128 minutes**. Twenty-two live API cases and browser flows pass.
- **Main gap:** geography. Six-to-twelve-hour queries still reach missing roads, and places near the region’s perimeter can clip much earlier. Zero detected edges does not prove every source road or real-world access is correct. Border queues and current crossing eligibility remain unmodeled.
- **Six-hour preflight finished:** cached roads alone contain about **22.9 million eligible directed segments**. Preparation passes, but the larger-build forecast is **9.40 GiB with margin** against our 4 GiB cap. That is an estimate, not measured graph RAM. No larger graph has been released.
- **Memory progress / next:** the first optimized build produces exactly the same eight payloads while reducing complete peak memory by about **9.5%**, from 2.668 to **2.415 GiB**. Its exact repeat and updated resource forecast are pending; no job is running at this checkpoint. Five missing regional downloads total about **1.47 GB**, deferred until the memory path is credible. This work uses **zero routing-provider requests**. [Details and evidence](six-hour-preflight.md#memory-follow-up).
- **Still separate:** the hosted main page stays at 60 minutes. Filled contours and long-range routing on Vercel remain unfinished. Teal roads are display samples; calculations use the full local graph with zero routing-provider requests.

[Exact commands, measurements and limitations](two-hour-region.md) and [next steps](next-steps.md) provide the handoff.

For another coding agent or a disconnected session, start with [the resume guide](agent-handoff.md). Current code changes are uncommitted and large datasets are local-only; keep this workspace to resume smoothly.
