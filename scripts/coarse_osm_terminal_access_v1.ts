/** Cheapest independently paid terminal connection; never an inter-road transfer. */
import {
	type AccessRoadField,
	arrivalAtAccessPosition,
} from "./coarse_osm_access_road_field_v1.ts";
import {
	connectorPrice,
	type OriginConnection,
} from "./coarse_osm_origin_connections_v2.ts";
import type { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import type { PaidRoadGeometry } from "./coarse_osm_paid_geometry_v1.ts";

export function paidTerminalArrival(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	field: AccessRoadField,
	connections: readonly OriginConnection[],
): { ticks: number; index: number } | null {
	if (!connections.length || connections.length > 4096)
		throw new Error("Terminal connection count domain");
	const target = connections[0].origin;
	let best: { ticks: number; index: number } | null = null;
	for (const [index, connection] of connections.entries()) {
		if (
			connection.origin[0] !== target[0] ||
			connection.origin[1] !== target[1]
		)
			throw new Error("Terminal target mismatch");
		const price = connectorPrice(target, connection.snap.coordinate);
		if (
			price.ticks !== connection.connectorTicks ||
			price.meters !== connection.connectorMeters
		)
			throw new Error("Unpaid terminal connection");
		if (price.meters > 300000 || price.ticks > 345600)
			throw new Error("Terminal connection price cap");
		const arrival = arrivalAtAccessPosition(
			graph,
			geometry,
			field,
			connection.snap,
		);
		if (arrival === null) continue;
		const ticks = arrival + connection.connectorTicks;
		if (ticks <= field.horizonTicks && (best === null || ticks < best.ticks))
			best = { ticks, index };
	}
	return best;
}
