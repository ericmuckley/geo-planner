import type { FeatureCollection, Point } from "geojson";
import { z } from "zod";
import { elevationMatches, gridCellIndex } from "./area-layers";
import { areaMembership } from "./contour-membership";
import type { ReachabilityResult } from "./reachability";

export const placeKinds = ["fuel", "trailheads", "campgrounds"] as const;
export type PlaceKind = (typeof placeKinds)[number];

export const placeLayers = {
	fuel: {
		label: "Fuel stops",
		singular: "fuel stop",
		url: "/places/fuel-us-v1.json",
		color: "#a55315",
	},
	trailheads: {
		label: "Trailheads",
		singular: "trailhead",
		url: "/places/trailheads-us-v1.json",
		color: "#28623a",
	},
	campgrounds: {
		label: "Campgrounds",
		singular: "campground",
		url: "/places/campgrounds-us-v1.json",
		color: "#255ca8",
	},
};

export const placeAttribution = "© OpenStreetMap contributors";
export const placeAttributionUrl = "https://www.openstreetmap.org/copyright";

const placeRows = z
	.array(
		z.tuple([
			z.number().finite().min(-180).max(180),
			z.number().finite().min(-90).max(90),
			z.string().max(320),
			z.string().regex(/^[nw][1-9][0-9]*$/),
		]),
	)
	.max(300_000);

const catalogMetadata = z.object({
	version: z.literal(1),
	sourceDate: z.iso.date(),
	sourceSha256: z.string().regex(/^[a-f0-9]{64}$/),
});

const outdoorCatalogSchema = catalogMetadata.extend({ places: placeRows });
const fuelCatalogSchema = catalogMetadata.extend({ stations: placeRows });

export function parsePlaceCatalog(kind: PlaceKind, data: unknown) {
	if (kind === "fuel") {
		const { stations, ...metadata } = fuelCatalogSchema.parse(data);
		return { ...metadata, places: stations };
	}
	return outdoorCatalogSchema.parse(data);
}

export type PlaceCatalog = z.infer<typeof outdoorCatalogSchema>;
export type PlaceLocations = FeatureCollection<Point, { name: string }>;
export type OutdoorPlaceKind = Exclude<PlaceKind, "fuel">;
export type OutdoorPlaceSelection = {
	kind: OutdoorPlaceKind;
	location: PlaceLocations["features"][number];
};

export type MapPlaces = Record<PlaceKind, PlaceLocations | null>;
export type PlaceTerrainFilter = (locations: PlaceLocations) => PlaceLocations;

export function placeTerrainFilter(
	land: Uint16Array | null | undefined,
	elevation?: { grid: Uint16Array | null; minimumFeet: number | null },
): PlaceTerrainFilter | null | undefined {
	const elevationGrid = elevation?.grid;
	const minimumFeet = elevation?.minimumFeet;
	if (land === null || elevationGrid === null || minimumFeet === null) {
		return null;
	}
	if (!land && !elevationGrid) return undefined;

	return (locations) => ({
		...locations,
		features: locations.features.filter(({ geometry }) => {
			const [lon, lat] = geometry.coordinates;
			const index = gridCellIndex(lon, lat);
			return (
				index !== undefined &&
				(!land || land[index] > 0) &&
				(!elevationGrid ||
					minimumFeet === undefined ||
					elevationMatches(elevationGrid[index], minimumFeet))
			);
		}),
	});
}

export function placeLocationsInArea(
	kind: PlaceKind,
	catalog: PlaceCatalog,
	contours: ReachabilityResult["contours"],
): PlaceLocations {
	const contains = areaMembership(contours);
	const features: PlaceLocations["features"] = [];
	for (const [lon, lat, name, id] of catalog.places) {
		if (contains(lon, lat)) {
			features.push({
				type: "Feature",
				id,
				properties: { name: name || `Unnamed ${placeLayers[kind].singular}` },
				geometry: { type: "Point", coordinates: [lon, lat] },
			});
		}
	}
	return { type: "FeatureCollection", features };
}
