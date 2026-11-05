/** Country-certified raster links can omit repeated country geometry, never lakes. */
import { prepareGeography } from "../src/server/coarse-geography.ts";
import type { OriginGeography } from "./coarse_osm_origin_connections_v1.ts";
import type {
	RoutingGeography,
	WaterPacket,
} from "./coarse_osm_routing_geography_v1.ts";
import { waterRoutingGeographyV4 } from "./coarse_osm_routing_geography_v4.ts";
import { prepareWaterGeographyV3 } from "./coarse_osm_water_geography_v3.ts";

export type CountryRoutingGeography = RoutingGeography & {
	readonly inlandConnection?: (a: number[], b: number[]) => boolean;
};
export function waterRoutingGeographyV6(
	source: OriginGeography,
	packet: WaterPacket,
): CountryRoutingGeography {
	const full = waterRoutingGeographyV4(source, packet);
	const fullPredicate = full.connectionPolicy;
	const [west, south, east, north] = source.bounds;
	const box = [
		Math.max(-180, west - 1),
		Math.max(-90, south - 1),
		Math.min(180, east + 1),
		Math.min(90, north + 1),
	];
	// This envelope is used only after raster cells certify original-country
	// coverage. Original lake/fine-water checks and every price stay unchanged.
	const boundary = [
		[
			[
				[box[0], box[1]],
				[box[2], box[1]],
				[box[2], box[3]],
				[box[0], box[3]],
				[box[0], box[1]],
			],
		],
	];
	const inland = prepareWaterGeographyV3(
		{ boundary, lakes: source.lakes },
		packet,
	);
	const result = Object.freeze({
		...full,
		inlandConnection: (a: number[], b: number[]) => {
			if (
				[a, b].some(
					(p) =>
						p[0] <= box[0] ||
						p[0] >= box[2] ||
						p[1] <= box[1] ||
						p[1] >= box[3],
				)
			)
				return fullPredicate(a, b);
			return inland.landConnection(
				a as [number, number],
				b as [number, number],
			);
		},
	});
	prepareGeography(result);
	return result;
}
