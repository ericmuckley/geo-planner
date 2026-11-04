/** Keep the primary first, with every other independently qualified alternative. */
import type { AccessStart } from "./coarse_osm_access_road_field_v1.ts";
import type { OriginConnection } from "./coarse_osm_origin_connections_v1.ts";

export function accessStarts(
	primary: OriginConnection,
	connections: OriginConnection[],
): AccessStart[] {
	if (!connections.length || connections.length > 4096)
		throw new Error("Access input connection count");
	const index = connections.findIndex(
		(c) =>
			c.connectorTicks === primary.connectorTicks &&
			c.snap.canonicalArc === primary.snap.canonicalArc &&
			c.snap.segment === primary.snap.segment &&
			c.snap.segmentFraction === primary.snap.segmentFraction,
	);
	if (index < 0) throw new Error("Access input missing primary");
	if (
		connections.some(
			(c) =>
				c.origin[0] !== primary.origin[0] || c.origin[1] !== primary.origin[1],
		)
	)
		throw new Error("Access input origin mismatch");
	return [primary, ...connections.filter((_, i) => i !== index)].map((c) => ({
		position: c.snap,
		initialTicks: c.connectorTicks,
	}));
}
