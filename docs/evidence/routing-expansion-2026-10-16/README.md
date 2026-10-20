# Routing expansion evidence — October 16, 2026

See [the report](../../archive/routing-expansion-verification.md) for commands, methodology and limitations. JSON files are captured real engine/app outputs, not synthetic fixtures. Build manifests retain source checksums, settings, admin inventory and artifact hashes. Timing summaries retain all repetitions; HTTP round trip is not isolated graph-search time.

The Vercel report invokes the generated handler locally, not on Vercel. Native tile loading used local HTTP and a different engine revision; it proves local loading equivalence only. Browser screenshots/text show real v2 results. Large sources/graphs and full diagnostic logs remain ignored under `data/`.

`hosted-missing-key.png`/`.txt` show the real production UI without a provider key: cap 60, Compute disabled, no external query. They are setup-state evidence, not a hosted contour. `san-diego-60-production.png`/`.txt` show the real local Valhalla v2 contour.
