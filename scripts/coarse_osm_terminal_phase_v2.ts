/** Own a diagnostic field until all paid terminal summaries are complete. */
import {
	type AccessRoadField,
	type AccessStart,
	computeDiagnosticAccessRoadField,
} from "./coarse_osm_access_road_field_v2.ts";
import type { OriginConnection } from "./coarse_osm_origin_connections_v2.ts";
import type { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import type { PaidRoadGeometry } from "./coarse_osm_paid_geometry_v1.ts";
import { paidTerminalArrival } from "./coarse_osm_terminal_access_v1.ts";

export function terminalRoadPhase(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	starts: AccessStart[],
	targets: readonly {
		primary: OriginConnection;
		alternatives: readonly OriginConnection[];
	}[],
	check: () => void = () => {},
) {
	let field: AccessRoadField | null = computeDiagnosticAccessRoadField(
		graph,
		geometry,
		starts,
		{ maxTicks: 432000, check },
	);
	try {
		const finishes = [];
		for (const target of targets) {
			check();
			finishes.push({
				primary: paidTerminalArrival(graph, geometry, field, [target.primary]),
				best: paidTerminalArrival(graph, geometry, field, target.alternatives),
			});
		}
		return { finishes, fieldStats: { ...field.stats } };
	} finally {
		// Optimized callback contexts must not keep the country work arrays alive.
		field = null;
	}
}
