# Where Geo Planner stands

Updated October 18, 2026. The goal is still a US-focused app that can show where you can drive in **10–12 hours**, without depending on a paid routing API.

- **Working today:** the hosted 60-minute map plus a separate local experiment with **90/120-minute queries**, reachable-road samples and clear data-edge warnings. Start it with `npm run dev:experiment` and open `/experiment`.
- **Built and tested separately:** our own offline road router using downloaded OpenStreetMap data. It handles directed roads, turn restrictions and conservative access rules. The current San Diego–northern Baja graph passes extensive route checks, and repeated builds reproduce its files exactly. Experiments use no provider quota.
- **Current work:** expanding coverage after making longer queries visible. A larger cached region is prepared, with **5.2–5.4 million possible road states**. Its verification-memory forecast still needs resolving before building and switching graphs. [Results and next steps](local-routing-experiment.md) explain the limits.
- **Main gap:** geographic coverage. Five tested origins have no graph-edge cuts within 60 minutes, but all tested two-hour searches reach the graph's edges. Longer budgets alone cannot supply missing roads. US-wide coverage and complete 10–12-hour contours remain unfinished.
- **Still ahead:** build and qualify the expanded region, reach complete two-hour coverage for tested origins, then extend toward 6–12 hours. Filled-area contours and Vercel execution remain unfinished; the hosted page stays capped at 60 minutes.

The immediate next work is recorded at the top of [next steps](next-steps.md). Memory measurements, mathematical checks and border-access uncertainties remain separate from claims about real driving times.
