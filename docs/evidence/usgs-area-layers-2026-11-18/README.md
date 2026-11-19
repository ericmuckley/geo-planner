# Public lands and elevation layers

November 18, 2026. The local app has separate switches for **Public lands** and **Elevation**. Each loads one static file and shades its intersection with the displayed driving area. Elevation highlights cells at or above a user-selected value from 0 to 15,000 feet and starts at 5,000 feet. Both layers use the same v9 contour, including its holes and separate pieces. [Local preview instructions](../../local-development.md#try-public-lands-and-elevation).

## Sources and processing

**Public lands** uses the federal, state and local government ownership codes `FED`, `STAT` and `LOC` in layer 0 of the USGS PAD-US 4.1 Fee service. A transparent map export used `layers=show:0` and `layerDefs={"0":"Own_Type IN ('FED','STAT','LOC')"}`. Pixels with at least half coverage in the rendered alpha channel become marked pixels. Small parks or narrow parcels can be missed. The selected fee ownership classes exclude easements, other ownership categories and overlapping management designations. Public access and boundaries should be verified with the managing agency. [USGS Fee layer](https://edits.nationalmap.gov/arcgis/rest/services/PAD-US/PAD_US_4_1/MapServer/0), [PAD-US 4.1 citation](https://doi.org/10.5066/P96WBCHS).

**Elevation** uses a USGS 3DEP bare-earth image export as float32 TIFF. The request used `renderingRule={"rasterFunction":"None"}`, bilinear interpolation and `noData=-9999`. The app asset stores signed values rounded to the nearest meter in the red and green channels and reserves zero for nodata. The browser compares decoded elevations in meters using 0.3048 meters per foot. [USGS 3DEP](https://www.usgs.gov/3d-elevation-program/about-3dep-products-services), [USGS image service](https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer).

Both exports cover the contiguous US in the same EPSG:3857 grid. The bounds in meters are `-14000000,2700000,-7300000,6500000`, with dimensions 3,350 by 1,900 and a 2,000 projected-meter cell size. The source exports and their metadata are saved at `data/map-layers/usgs-area-v1/` and are ignored by Git. The [preparation script](../../../scripts/build_usgs_area_layers_v1.py) checks the input hashes and projection before writing the two app assets. [Checksums and exact grid](assets-v1.json).

| App asset | Bytes | Samples |
| --- | ---: | ---: |
| [Public lands](../../../public/overlays/public-lands-us-v1.png) | 166,580 | 923,544 marked |
| [Elevation](../../../public/overlays/elevation-us-v1.png) | 5,152,975 | 4,789,948 valid |

The app loads each grid on demand and clips a cropped canvas to the reachability polygons. The fully static assets can be served from Vercel and require no added runtime service. This first version is a regional planning view. Cell colors approximate land parcels and terrain within the 2 km grid.

## Verification

Independent probes confirmed source pixel encodings in Yellowstone, Yosemite, the Rocky Mountains, Miami Beach, Kansas and the Pacific. Yosemite and Rocky Mountain sample cells store 1,271 and 2,516 meters, respectively, and the ocean sample remains nodata. The two new tests check projection round-tripping and the exact 5,000-foot threshold with nodata and below-threshold heights.

Local Chrome tested both overlays together in the two-hour and 12-hour San Diego estimates. The 5,000-foot shading was visible in both maps. Raising the cutoff to 15,000 feet removed the purple shading and preserved the green overlay and the two-hour estimate. Restoring 5,000 feet brought the elevation layer back. Trailheads and Campgrounds remained visible above both layers in the 12-hour estimate.

All 91 app tests, typecheck, Biome and both builds passed. Both new images and all three point catalogs matched the Vercel static output byte for byte. The v9 handler passed at 65,086,129 bytes, with no outbound calls and a first local estimate of 3.59 seconds after configuration.


## Production release

Release `83e6566` is live at [Geo Planner](https://geo-planner-orcin.vercel.app/). The clean committed copy passed all 91 tests, Biome, typecheck and both builds. The generated routing function measured 65,105,557 bytes, and its first local v9 estimate after configuration took 3.65 seconds with outbound calls rejected. The package contained both overlay images and all three places catalogs.

The production homepage referenced the deployed overlay code, both images and all three catalog hashes matched, and the 30-minute and 12-hour estimates retained their expected counts. The 11 production checks used no history writes. Overlay interaction and appearance were checked in the local Chrome preview. [Production verification](hosted-release-v1.json).

Six additional cases used the clean local Vercel handler and an independent Pillow mask. Both San Diego durations, Denver, central Kansas, New York and Miami matched public-land pixels. The 30-minute San Diego and two-hour Miami cases had zero cells at 5,000 feet or higher, while Denver and the 12-hour San Diego case returned positive counts. The six-hour Central Kansas estimate reaches the Front Range and also contains high cells. These are local raster probes on the approximate v9 contours. [Observed grid counts](release-region-probes-v1.json).

## Outdoor place filters

The local app uses the shipped USGS grids to filter the trailheads and campgrounds already inside the displayed driving area. **On mapped public land** requires a marked ownership cell. **At or above minimum elevation** uses the same cutoff as the elevation shading and starts at 5,000 feet. When both are enabled, each point must meet both conditions. The filters sample the grid cell under the mapped point. Missing elevation data and points outside the grid are excluded when the relevant filter is on.

Filtering and shading share the same decoded grids and can be selected independently. The trailhead and campground pins and counts update in the browser without a new estimate. While required data is loading or unavailable, those pins and counts wait for it. Fuel and destination checks use the current driving area as before. Cell membership is an approximation of ownership and elevation at the mapped location. [Local review steps](../../local-development.md#try-outdoor-place-filters).

An independent Python check read the pixels at every candidate coordinate from three local, packaged v9 estimates. The selected IDs exactly matched the app for land only, 5,000 feet only, both filters and the combined 15,000-foot cutoff.

| Origin and time | Trailheads with both filters | Campgrounds with both filters |
| --- | ---: | ---: |
| Flagstaff, 6 hours | 323 of 763 | 911 of 1,831 |
| Denver, 2 hours | 137 of 278 | 485 of 528 |
| Miami, 2 hours | 0 of 27 | 0 of 80 |

All three cases had zero matches at 15,000 feet. The new unit test checks exact threshold inclusion, missing data, out-of-grid points and pending filters. Rendering checks confirmed the count labels, the shared elevation input and the retry control. [Measured counts](outdoor-filter-probes-v1.json).

All 95 app tests, typecheck, Biome and both builds passed. The Vercel package preserved the existing overlays and catalogs byte for byte. The packaged routing handler passed at 65,104,186 bytes with a 3.77-second first local estimate after configuration and zero outbound requests. The preview opened in Chrome. Interactive filter toggling could not be completed because the active tab changed during the check.

### Browser and production verification

The isolated Chrome review completed on the six-hour Flagstaff estimate. Both switches worked individually and together. The counts matched the independent pixel check. A 15,000-foot cutoff removed the trailhead and campground pins while fuel pins stayed visible. Reusing the 5,000-foot field restored the filtered places and elevation shading. The browser made one estimate request and loaded each grid once.

Release `6feea27` is live at [Geo Planner](https://geo-planner-orcin.vercel.app/). The production check found the new controls in the served client bundle, verified both point catalogs and both grid images byte for byte, and reproduced the six-hour Flagstaff counts from the live estimate. The hosted checks made no provider calls or history writes. [Production verification](outdoor-filter-release-v1.json).

## Browsing matching places

The app adds **Browse trailheads** and **Browse campgrounds** beneath each enabled layer with results. The lists use the same points as the map and counts. Opening a list shows its first 20 names alphabetically, and each **Show more** action adds 20. Selecting a row zooms to a highlighted pin and opens its name, category and mapped coordinates. If a filter removes the selected point, the pin and popup close. The selection needs no estimate request. [Local review steps](../../local-development.md#try-browsing-matching-places).

Isolated Chrome verified keyboard opening and selecting, expanding the campground list from 20 to 40 rows, the camera zoom and popup for each category, and clearing the selection by raising the cutoff to 15,000 feet. Restoring 5,000 feet restored the lists. The test made one estimate request and found no fuel browse list. All 95 tests, typecheck, Biome and both builds passed. The Vercel build preserved every static asset byte for byte. The routing function measured 65,109,038 bytes and the first local estimate after configuration took 3.67 seconds with outbound calls rejected.

### Browse list production release

Release `b765050` passed 95 app tests, typecheck, Biome and both builds in a clean release copy. The Vercel function measured 65,128,460 bytes and the first local handler estimate after configuration took 3.64 seconds with outbound calls rejected.

Chrome verified the live six-hour Flagstaff estimate with both outdoor filters enabled at 5,000 feet. The 911 matching campgrounds and 323 matching trailheads appeared in the two lists. The campground list expanded from 20 to 40 entries, each category focused its pin and details, and 15,000 feet cleared the lists and popup. There was one estimate request and zero history writes. All six public catalogs and overlays matched the committed assets byte for byte. The isolated test substituted a minimal basemap and a disabled history response. [Production verification](browse-lists-release-v1.json).

## Directions links

The local app adds **Directions in Google Maps** to campground and trailhead popups opened from a browse list or an individual pin. The link opens a new tab with the displayed estimate’s starting point, the place’s original catalog coordinates, and driving mode. The catalog point may be approximate. A direct pin click uses the catalog coordinates preserved in the feature properties because the map renderer rounds its tile geometry. [Local review](../../local-development.md#try-directions-links), [Google Maps URL format](https://developers.google.com/maps/documentation/urls/get-started#directions).

Isolated Chrome checked the destination against the original catalog for a campground and a trailhead selected from the Flagstaff lists and for a direct click on the San Elijo State Beach campground pin after a San Diego estimate. The list popup stayed in view as the controls collapsed and reopened. Clicking the trailhead link opened a new tab with the expected URL. The test intercepted that navigation and made no Google Maps request. A separate map click verified the fuel popup still displays the station name.

All 95 tests, Biome, typecheck and both builds passed. All six static assets matched the input bytes. The generated Vercel function measured 65,110,340 bytes. The first local handler estimate after configuration took 3.80 seconds with outbound calls rejected.
