# Cell-summary experiment evidence

See [commands, proof, measurements and decision](../../cell-routing-experiment.md).

- `summary.json`, `manifest.json`: warm repeat run, all case-level/candidate samples, verified input/code/image identity and limits.
- `initial-summary.json`, `initial-manifest.json`: initial index construction and qualification; the app build ran during its early portion.
- `leaf-64-manifest.json`, `leaf-256-manifest.json`, `leaf-1024-manifest.json`: exact binary file layout metadata, sizes and checksums.
- `comparison.json`: per-budget/candidate aggregate comparison; aggregation is defined in each row.
- `reproducibility.json`: saved index files, classification/access/search-work counts unchanged across runs; all final memberships qualified again.

Full binary indexes and worker snapshots remain in ignored `data/cell-pilot/downtown-cells-v1/`. The source reference was mounted read-only. Both runs used Docker networking disabled and made zero public API calls or bulk downloads.

Correctness applies to the existing simplified downtown state model. Logical local index reads exclude preflight, resident graph data and full output expansion; they are not physical disk or network measurements. No browser/product behavior or driving-range limit changed.
