# Where Geo Planner stands

Updated October 30, 2026. V9 remains deployed and user-verified at `648c731`. The live map is unchanged; the new work is local and uncommitted.

We have cleared the national data-size bottleneck. The full 14.5 GB coordinate index exists, and fresh source comparisons now validate it. A separate bank for filtering roads by window now fits in 938 MB after lossless compression. Two complete source passes rebuilt that bank identically within the original resource limits.

Road extraction stopped at its old limit of 250,000 selected elements, before producing complete data. We are replacing memory retention with a bounded disk spool so a larger selection can fit the same global resource budget. It will use the same source, validation windows and generic rules. This is data preparation, with no measured map-accuracy improvement yet.

Next we must check source coverage, usable speed attributes and road matching. Only then can we test a new timing model against the saved 83 ORS and 35 Valhalla cases and the existing deployment limits. [Current task](next-steps.md), [evidence and recovery](evidence/coarse-osm-extraction-2026-10-30/README.md).
