import { checkCapturedPackedSearch } from "./coarse_osm_packed_search_check_v1.ts";

await checkCapturedPackedSearch(
	"data/coarse-quality/us-osm-car-spatial-equivalence-v2",
	"docs/evidence/coarse-osm-car-capacity-2026-11-01/spatial-search-runtime-v1.json",
);
