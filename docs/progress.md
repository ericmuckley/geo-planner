# Geo Planner progress

**The app is live.** It estimates where you could drive within 30 minutes to 12 hours across the contiguous US. You choose a starting point and use the time slider to redraw the area.

**The road prototype improved the saved long-drive results.** Average error went from 29 to 13 minutes and wrong inside-or-outside calls fell from 13 to six. The prototype still leaves one clearly reachable destination off the map and has several large timing regressions. Seven release checks still fail. [Accuracy review](implementation-status.md#routing-accuracy-for-trip-planning).

**Routing work has a stopping point.** Keep the live app for rough planning and revisit routing when a credible fix would change a real trip decision. A replacement that passes the existing checks and works in the app is ready to ship. Small gains can wait. [Stop rule](next-steps.md#2-decide-when-routing-is-good-enough), [initial product plan](initial-project-plan.md).

The fuel-stop layer is live. Its catalog contains 108,634 mapped locations from the US snapshot. Enable **Fuel stops** after estimating an area and click an individual point for the station name. The map updates the stops when the driving area changes. [Fuel data pilot](evidence/fuel-points-2026-11-18/README.md).

[Open Geo Planner](https://geo-planner-orcin.vercel.app/) · [Hosted release checks](evidence/fuel-points-2026-11-18/hosted-release-v1.json).

**Trailheads and Campgrounds are live.** The October 25 snapshot provides 10,928 trailheads and 34,941 campgrounds. Each switch updates with the driving area. [Hosted verification](evidence/outdoor-places-2026-11-18/hosted-release-v1.json).

**Public lands and Elevation are live.** Shade mapped public land and terrain at or above a chosen height within the driving area. The elevation cutoff starts at 5,000 feet. [Open Geo Planner](https://geo-planner-orcin.vercel.app/) · [Production checks](evidence/usgs-area-layers-2026-11-18/hosted-release-v1.json).

**Place search is live.** Search for a town, natural landmark or street address to set your starting point. [Open Geo Planner](https://geo-planner-orcin.vercel.app/) · [Production verification](evidence/place-search-2026-11-18/hosted-release-v1.json).

**Outdoor filters are live.** Narrow trailheads and campgrounds by mapped public land, minimum elevation, or both. A six-hour Flagstaff estimate returned 911 approximate campground matches with both filters on at 5,000 feet. [Production verification](evidence/usgs-area-layers-2026-11-18/outdoor-filter-release-v1.json) · [Measured results](evidence/usgs-area-layers-2026-11-18/README.md#outdoor-place-filters).

**Browse lists are live.** Open a list of matching trailheads or campgrounds and select one to see its map pin and details. [Open Geo Planner](https://geo-planner-orcin.vercel.app/) · [Production verification](evidence/usgs-area-layers-2026-11-18/browse-lists-release-v1.json).

**The simplified map is ready to preview locally.** The first estimate starts immediately, and the map shows a centered spinner. Failed estimates show an error and Retry. On phones, tap the map to change your start or tap **See where you can drive** to adjust the time, layers and filters. Copy the URL to share the map and its settings. [Try the preview](http://127.0.0.1:4204/), [map URL settings](local-development.md#share-a-map-view).

**Next milestone.** Review the simplified map, then release it and try a short and a six-hour trip on the deployed app. [Release and trip checks](next-steps.md#1-review-and-release-the-simplified-map).
