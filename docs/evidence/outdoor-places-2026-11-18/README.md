# Trailhead and campground layers

November 18, 2026. The app shows separate optional layers from the cached October 25 OpenStreetMap snapshot. Each catalog loads when its layer is enabled. The map uses the displayed driving area, including disconnected pieces and holes, to choose points. Clusters of nearby points expand on click, and individual points show their names. [Local preview instructions](../../local-development.md#try-the-places-layers).

## Source and coverage

The scan used `highway=trailhead` and `tourism=camp_site`. Mapped points keep their coordinates. Simple closed outlines become interior points. The scan excludes explicitly restricted places, unsupported geometry and duplicates. This includes 3 trailhead and 824 campground relations omitted for unsupported geometry. Campground markers represent mapped sites. Opening dates, reservations and driving access are outside the catalog. [Trailhead tagging](https://wiki.openstreetmap.org/wiki/Tag:highway=trailhead), [campground tagging](https://wiki.openstreetmap.org/wiki/Tag:tourism=camp_site), [OpenStreetMap attribution and license](https://www.openstreetmap.org/copyright).

| Layer | Locations | Static bytes | SHA-256 |
| --- | ---: | ---: | --- |
| [Trailheads](../../../public/places/trailheads-us-v1.json) | 10,928 | 639,870 | `7568ebb8a09ff764681034100af9246a7cf5cf63c61692db30e186c88821e480` |
| [Campgrounds](../../../public/places/campgrounds-us-v1.json) | 34,941 | 1,877,905 | `5e1e82247cbfa8585307dec64a60ac0bcd04db1b626c7618259153034ecd727b` |

The US scan took 173.79 seconds including the complete checksum and both reader passes. All 225,820 requested outline vertices resolved. A check before staging verified metadata, exact bytes, valid coordinates and unique IDs. The catalogs contain points across 47 and 50 five-degree bins, respectively, inside a rectangle spanning the contiguous US. This measures source spread. [Inventory report](../coarse-osm-car-capacity-2026-11-01/outdoor-places-us-v1-raw-v1/report.json) and [closed output](../coarse-osm-car-capacity-2026-11-01/outdoor-places-us-v1-closed-v1.json).

The bounded, network-disabled [reader command](../../../scripts/run_osm_outdoor_places_v1.py) used the cached US source and existing Docker image. Use the finished files in `data/coarse-quality/us-osm-outdoor-places-us-v1/` to verify or recover the packaged catalogs. The layer needs only the static files at runtime.

## App verification

The local Chrome preview uses v9 with cloud history disabled. San Diego counts at both slider limits matched the map:

| Driving time | Fuel stops | Trailheads | Campgrounds |
| --- | ---: | ---: | ---: |
| 30 minutes | 382 | 37 | 6 |
| 12 hours | 12,184 | 1,832 | 5,243 |

Chrome verified independent switches, automatic slider updates, cluster zoom, switching directly between two marker popups and picking a destination while the layers are active. The origin stayed fixed. An unnamed trailhead showed the category fallback and the campground showed its mapped name. [Preview setup](../../local-development.md#try-the-places-layers).

All 89 app tests, typecheck, Biome checks and both builds passed. Biome reported the existing three warnings and three informational items. The Vercel build keeps all three catalogs byte-for-byte in static output. The local v9 handler passed at 65,075,337 bytes with a first estimate at 3.66 seconds after configuration and zero outbound requests. These layers are in the working tree and available in the local preview.

## Production release

Release `8a8424f` is live on [Geo Planner](https://geo-planner-orcin.vercel.app/). The production homepage, v9 configuration, three byte-exact catalogs and both San Diego estimates passed. The 30-minute and 12-hour matches agree with the browser review above. The seven production checks made no history writes. [Hosted verification](hosted-release-v1.json).
