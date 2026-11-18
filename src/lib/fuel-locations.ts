import type { FeatureCollection, Point } from "geojson";
import { z } from "zod";
import { areaMembership } from "./contour-membership";
import type { ReachabilityResult } from "./reachability";

export const fuelCatalogUrl = "/places/fuel-us-v1.json";
export const fuelAttribution = "© OpenStreetMap contributors";
export const fuelAttributionUrl = "https://www.openstreetmap.org/copyright";

export const fuelCatalogSchema = z.object({
	version: z.literal(1),
	sourceDate: z.iso.date(),
	sourceSha256: z.string().regex(/^[a-f0-9]{64}$/),
	stations: z
		.array(
			z.tuple([
				z.number().finite().min(-180).max(180),
				z.number().finite().min(-90).max(90),
				z.string().max(320),
				z.string().regex(/^[nw][1-9][0-9]*$/),
			]),
		)
		.max(300_000),
});

export type FuelCatalog = z.infer<typeof fuelCatalogSchema>;
export type FuelLocations = FeatureCollection<Point, { name: string }>;

export function fuelLocationsInArea(
	catalog: FuelCatalog,
	contours: ReachabilityResult["contours"],
): FuelLocations {
	const contains = areaMembership(contours);
	const features: FuelLocations["features"] = [];
	for (const [lon, lat, name, id] of catalog.stations) {
		if (contains(lon, lat)) {
			features.push({
				type: "Feature",
				id,
				properties: { name: name || "Unnamed fuel stop" },
				geometry: { type: "Point", coordinates: [lon, lat] },
			});
		}
	}
	return { type: "FeatureCollection", features };
}
