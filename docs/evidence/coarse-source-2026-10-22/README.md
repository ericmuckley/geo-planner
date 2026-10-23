# Compact road-source assessment — October 22, 2026

**Decision:** trial Census primary/secondary roads as a **nationwide augmentation** of the current Natural Earth roads, keeping v4 active until a separately versioned generic candidate is validated. A one-state source pilot is evidence for that method, not a region-specific production feature or nationwide accuracy claim. No application artifact, runtime behavior, deployed version, class-speed assumptions or reference route changed here.

## Sources considered

| Source | Useful properties | Decision/limits |
| --- | --- | --- |
| Census 2026 primary/secondary roads | Annual US state archives; S1100/S1200 linework; small one-state acquisition | Selected for the first generic augmentation experiment. Classification gaps remain; source geometry alone does not supply legal driving topology or speeds. |
| Overture transportation | Global OSM-derived road segments, explicit shared connector IDs, monthly releases and bounding-box extraction | Keep as a later topology/source option. No data downloaded or nationwide size measured. It requires an additional extraction path and ODbL attribution/license treatment. |
| Direct OSM | Cached regional inputs and known routing provenance are available | Available for later comparison; do not restart the parked detailed graph pipeline to use them. Nationwide acquisition/compact conversion remains unmeasured. |

Census released the [2026 files](https://www.census.gov/geographies/mapping-files/2026/geo/tiger-line-file.html) October 14. Its [technical description](https://www2.census.gov/geo/pdfs/maps-data/data/tiger/tgrshp2026/TGRSHP2026_TechDoc_Ch4.pdf) distinguishes state primary/secondary roads from county all-roads and explicitly notes classification gaps. The [citation/reuse page](https://www2.census.gov/geo/pdfs/maps-data/data/tiger/tgrshp2026/TGRSHP2026_TechDoc_Ch1.pdf) permits reproduction of government materials, requests source credit and describes accuracy/trademark limits; include appropriate source/repackaging notices before publishing a derived dataset.

Overture's [current transportation guide](https://docs.overturemaps.org/guides/transportation/) identifies release `2026-10-21.0`. Its [connector model](https://docs.overturemaps.org/guides/transportation/segments-and-connectors/) distinguishes real shared connectivity from overlapping lines. [Area extraction](https://docs.overturemaps.org/getting-data/) and [ODbL attribution](https://docs.overturemaps.org/attribution/#transportation) are documented. This assessment does not claim either source is a complete/current driving network.

## Measured California pilot

[Raw result](pilot.json), [source lock](source.json), [reader lock](tool.json). One official state ZIP was downloaded: **12,720,908 bytes**, SHA-256 `c57ce6c837b1d28d28ac60c8fe7cf8ea1705e2a08f26b6d61cda05b66d70efe8`. A **46,537-byte PyShp 2.3.1 wheel** is read directly after checking its PyPI hash, with no global installation or app dependency change. Raw files remain ignored.

The archive contains 7,350 polyline records: 1,260 S1100 and 6,090 S1200, with 1,245,029 points. The diagnostic respects multipart boundaries, verifies source/tool hashes and record counts, and measures the same 23 distinct saved endpoints. Source coordinates are NAD83 degrees; local projection plus haversine distances are approximate observations, not survey-grade transformations or accessible-road snaps.

| Endpoint | Nearest current source | Nearest Census primary/secondary road |
| --- | ---: | ---: |
| Big Bear | 29.958 km | 0.0247 km |
| Bombay Beach | 22.496 km | 0.9068 km |
| Idyllwild | 3.943 km | 0.0371 km |
| Borrego Springs | 13.162 km | 2.2695 km |
| Palm Springs | 0.0295 km | 1.6223 km |

**Nineteen endpoints have a nearer source road; four have a farther one** (Riverside, Palm Springs, Salton City and Indio). Therefore retain existing roads rather than replacing them wholesale. Nearer geometry is not an ETA, legal connection or proof of faster/more accurate isochrones.

At the existing 0.1° resolution, this source touches **2,240 road cells / 2,626 link slots**, including **1,026 slots absent from Natural Earth**. These are unmasked source candidates, not verified road topology. A naive canonical-owner representation alone contains **348,482 points / 4,497,541 JSON bytes** for this one state—more points than v4's entire US owner geometry. National geometry size cannot be extrapolated reliably from this single state. Keep full road arcs/physical cost semantics and use a compact encoding or justified geometry reduction before shipping; fixed grid arrays already bound search size, but source-attachment geometry still needs measurement.

## Next implementation slice

Build a generic source adapter and separately versioned **offline** augmentation candidate using this cached input. Preserve Natural Earth roads, country/lake handling, explicit road bridges, positive distance/time charges and recorded speed assumptions. Address compact geometry storage without free within-cell transfers or loss of water barriers. Compare both saved route sets against v4, separating timing, reachability and regressions. The pilot remains offline validation; do not ship a California-specific branch. Acquire/process all contiguous-US state partitions before claiming the new source is nationwide or replacing the active artifact. Measure final bytes and Vercel behavior before activation.

```sh
python3 -B scripts/inspect-coarse-road-source.py \
  --source-lock docs/evidence/coarse-source-2026-10-22/source.json \
  --tool-lock docs/evidence/coarse-source-2026-10-22/tool.json
```

This is now offline and writes no inputs. A fresh clone needs the ignored files at the lock paths; URLs/hashes are in the locks. [Acquisition note](acquisition-note.txt) preserves the initial Python certificate-store failure and the normally verified TLS fallback. No detailed graph build, routing-service query or hosted reference quota was used.
