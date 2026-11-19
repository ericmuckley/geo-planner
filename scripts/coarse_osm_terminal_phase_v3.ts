/** Scalar terminal summaries inside the field allocator's explicit lifetime. */
import type { AccessStart } from "./coarse_osm_access_road_field_v1.ts";
import type { OriginConnection } from "./coarse_osm_origin_connections_v2.ts";
import type { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import type { PaidRoadGeometry } from "./coarse_osm_paid_geometry_v1.ts";
import { withDiagnosticAccessRoadField } from "./coarse_osm_scoped_access_field_v3.ts";
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
	return withDiagnosticAccessRoadField(
		graph,
		geometry,
		starts,
		(field) => {
			const finishes = [];
			for (const target of targets) {
				check();
				finishes.push({
					primary: paidTerminalArrival(graph, geometry, field, [
						target.primary,
					]),
					best: paidTerminalArrival(
						graph,
						geometry,
						field,
						target.alternatives,
					),
				});
			}
			return { finishes, fieldStats: { ...field.stats } };
		},
		{ maxTicks: 432000, check },
	);
}
