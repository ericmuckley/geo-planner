/** One required geography predicate for every versioned experimental consumer. */
import assert from "node:assert/strict";
import { landConnection as legacyConnection } from "../src/server/coarse-geography.ts";
import type { OriginGeography as CoarseGeography } from "./coarse_osm_origin_connections_v1.ts";
import { prepareWaterGeography } from "./coarse_osm_water_geography_v1.ts";
import type { loadWaterRasterV2 } from "./coarse_osm_water_raster_loader_v2.ts";

export type WaterPacket = Awaited<ReturnType<typeof loadWaterRasterV2>>;
type Connection = (
	a: number[],
	b: number[],
	maxWaterPrefix?: number,
) => boolean;
export type RoutingGeography = CoarseGeography & {
	readonly connectionPolicy: Connection;
	readonly rasterMask: WaterPacket | null;
};

export function legacyRoutingGeography(
	source: CoarseGeography,
): RoutingGeography {
	return Object.freeze({
		...source,
		rasterMask: null,
		connectionPolicy: (a: number[], b: number[], prefix = 0) =>
			legacyConnection(source, a, b, prefix),
	});
}

export function waterRoutingGeography(
	source: CoarseGeography,
	packet: WaterPacket,
): RoutingGeography {
	const policy = prepareWaterGeography(source, packet);
	return Object.freeze({
		...source,
		rasterMask: packet,
		connectionPolicy: (a: number[], b: number[], prefix = 0) =>
			policy.landConnection(
				a as [number, number],
				b as [number, number],
				prefix,
			),
	});
}

export function landConnection(
	geography: RoutingGeography,
	a: number[],
	b: number[],
	maxWaterPrefix = 0,
) {
	assert.ok(
		typeof geography.connectionPolicy === "function",
		"Routing geography policy required",
	);
	return geography.connectionPolicy(a, b, maxWaterPrefix);
}
