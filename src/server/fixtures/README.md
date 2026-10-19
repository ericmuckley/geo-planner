# Real Valhalla regression response

`valhalla-san-diego-15.json` is a real `/isochrone` response captured locally on 2026-10-16 from Valhalla `3.9.1-7fd2228e5`, graph `san-diego-tijuana-20261014-v1`, OSM timestamp `2026-10-14T20:21:12Z`. Only whitespace was formatted for the repository. It contains OSM-derived data (© OpenStreetMap contributors, ODbL 1.0).

Request: origin `{lat:32.7157,lon:-117.1611}`, `costing:auto`, auto speed types `freeflow,constrained`, one 15-minute contour, `polygons:true`, `show_locations:true`, `reverse:false`, `generalize:100`, `denoise:0`.

This real response exposed the missing `Point` geometry variant in synthetic fixtures. The regression test checks adapter compatibility; replaying a stored fixture does not validate a live graph or measure routing performance. See `docs/regional-routing.md` and `docs/routing-baseline-verification.md` for provenance, resources, and correctness limitations.
