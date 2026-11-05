/** Indexed exact coarse crossings; unchanged frozen mask/cost/allowance semantics. */
import { prepareGeography } from "../src/server/coarse-geography.ts";
import type { OriginGeography } from "./coarse_osm_origin_connections_v1.ts";
import type {
	RoutingGeography,
	WaterPacket,
} from "./coarse_osm_routing_geography_v1.ts";
import { prepareWaterGeographyV4 } from "./coarse_osm_water_geography_v4.ts";

export function waterRoutingGeographyV5(
	source: OriginGeography,
	packet: WaterPacket,
): RoutingGeography {
	const policy = prepareWaterGeographyV4(source, packet);
	const geography = Object.freeze({
		...source,
		rasterMask: packet,
		connectionPolicy: (a: number[], b: number[], prefix = 0) =>
			policy.landConnection(
				a as [number, number],
				b as [number, number],
				prefix,
			),
	});
	prepareGeography(geography);
	return geography;
}
