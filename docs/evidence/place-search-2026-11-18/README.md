# Place search

November 18, 2026. The app has a submit-and-pick search in **Starting point** and **Check a destination**. Selecting a starting point fills the origin coordinates and pans the map. **Estimate area** uses that point and the current time. Selecting a destination checks the current contour and fills the destination coordinates. [Local review steps](../../local-development.md#try-place-search).

## Data and scope

| Source | Search coverage |
| --- | --- |
| [2026 Census Gazetteer](https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html) | 31,553 incorporated and Census-designated communities |
| [USGS Geographic Names Information System](https://www.usgs.gov/us-board-on-geographic-names/download-gnis-data) | 173,809 named summits, falls, springs, arches, cliffs, craters and valleys |
| [Census Geocoder](https://geocoding.geo.census.gov/geocoder/Geocoding_Services_API.html) | Single submitted street-number and street-name address queries using `Public_AR_Current` |

The catalog covers the contiguous states and DC. Community and natural landmark queries run in the browser with a lazily loaded static asset. The search accepts a state name or abbreviation, folds accents and prefers exact name matches. The first catalog's alphabetical tie order put Portland, Oregon beyond the first six results for **Portland**. The final version keeps the same records and puts larger communities first for tied name matches, using Census land area. Portland, Oregon and New York, New York both lead their unqualified searches. [First catalog and source hashes](assets-v1.json), [ranked catalog hash](assets-v2.json).

The [static asset](../../../public/places/search-us-v2.json) is 9,097,912 bytes. A local gzip measurement is 2,747,722 bytes. A local Node check decoded and indexed the catalog in about 287 milliseconds. Those measurements exclude download, browser rendering and routing.

Street-address queries go through `POST /api/place-search`, which sends the submitted text to the Census Geocoder. The endpoint enforces a small request-body limit, validates the response, keeps up to six matches in the supported states and returns `Cache-Control: no-store`. There are no API keys, setup changes or database calls for search. The Census Geocoder estimates locations along address ranges. Natural landmarks use the source's representative point. For a specific entrance, search its address or choose its location on the map.

The two pinned source archives and the initial catalog are ignored under `data/map-layers/place-search-v1/`. The [catalog builder](../../../scripts/build_place_search_v1.py) and [ranking stage](../../../scripts/rank_place_search_v2.py) verify exact input hashes. The final versioned catalog is sufficient to search names in a fresh app checkout that includes the change.

## Verification

Chrome selected the Flagstaff, Arizona community as the starting point and generated its two-hour estimate. The Grand Canyon, Arizona natural landmark matched and gave an outside result at its mapped point. The public Census office at 4600 Silver Hill Road in Suitland, Maryland returned one address match. Selecting it updated the outside result and destination coordinates without rerouting. Moving the slider to 30 minutes and 12 hours retained both selected points and redrew the estimate.

All 94 app tests, typecheck, Biome and both builds passed. The Vercel package retains the exact ranked name catalog as a static asset. The local Vercel routing handler passed at 65,098,465 bytes and took 3.89 seconds for its first estimate after configuration with outbound requests rejected. The packaged address endpoint passed separately with a stubbed Census response. The address submitted in Chrome used the live Census service.


## Release attempt

The approved twelve-file change is on GitHub main at `06fb19a9d809ad87903f33eb8bb5e9179788c31e`. A clean copy of that exact commit passed all 94 tests, Biome, typecheck, both builds and the Vercel address route with a stubbed Census response. The routing function measured 65,117,887 bytes. Its first local estimate after configuration took 3.73 seconds.

On November 18, GitHub showed no Vercel status for the place-search commit after the push. The production catalog returned HTTP 404 while the previous overlay release remained live. The Vercel dashboard stopped at sign-in. The manual recovery and verification are recorded below. [Vercel Git deployment instructions](https://vercel.com/docs/git).


## Production release

The initial Git push registered no deployment. Once dashboard access was restored, the approved commit was deployed to Production from its exact Git reference. Release `06fb19a` is live at [Geo Planner](https://geo-planner-orcin.vercel.app/).

Production returned the byte-exact ranked catalog and a search bundle that references the catalog and the address endpoint. The hosted catalog matched Flagstaff and Grand Canyon. One real Census lookup returned the expected public office address. Flagstaff estimates from the shipped name match returned 278 reached cells at 30 minutes and 257,034 at 12 hours. The seven production requests made one Census call and no history writes. [Hosted verification](hosted-release-v1.json).
