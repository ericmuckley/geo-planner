/** Index-only wrapper correction; the frozen mask predicate remains unchanged. */
import { prepareGeography } from "../src/server/coarse-geography.ts";
import type { OriginGeography } from "./coarse_osm_origin_connections_v1.ts";
import {
	type WaterPacket,
	waterRoutingGeography,
} from "./coarse_osm_routing_geography_v1.ts";

export function waterRoutingGeographyV2(
	source: OriginGeography,
	packet: WaterPacket,
) {
	const geography = waterRoutingGeography(source, packet);
	// Coarse fallback in the raster uses this wrapper as a WeakMap key.
	prepareGeography(geography);
	return geography;
}
