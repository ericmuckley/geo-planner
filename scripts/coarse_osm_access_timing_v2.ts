/** Fixed diagnostic point finish: paid road foot or paid local-grid path. */

import {
	type AccessRoadField,
	arrivalAtAccessPosition,
} from "./coarse_osm_access_road_field_v1.ts";
import {
	bit,
	cellAt,
	center,
	DIRECTIONS,
	hasLink,
	nibble,
} from "./coarse_osm_display_grid_v2.ts";
import type { DisplayProbe } from "./coarse_osm_filled_display_v1.ts";
import {
	connectorPrice,
	type OriginConnection,
	type OriginGeography,
} from "./coarse_osm_origin_connections_v2.ts";
import type { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import type { PaidRoadGeometry } from "./coarse_osm_paid_geometry_v1.ts";
import { landConnection } from "./coarse_osm_routing_geography_v1.ts";
import type { Coordinate } from "./coarse_osm_spherical_v1.ts";

export type PointTiming = {
	ticks: number | null;
	kind: "same-input" | "road-foot" | "local-grid" | "unreached";
	roadTicks: number | null;
	localGridTicks: number | null;
	localWitness: null | {
		terminalTicks: number;
		edgeSeconds: number;
		seedSeconds: number;
		seedCell: number;
		seedKind: number;
		steps: number;
	};
};
export function accessDisplayPointTiming(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	geography: OriginGeography,
	field: AccessRoadField,
	grid: DisplayProbe,
	origin: Coordinate,
	target: Coordinate,
	connection: OriginConnection | null,
): PointTiming {
	if (origin[0] === target[0] && origin[1] === target[1])
		return {
			ticks: 0,
			kind: "same-input",
			roadTicks: 0,
			localGridTicks: 0,
			localWitness: null,
		};
	const roadArrival =
		connection === null
			? null
			: arrivalAtAccessPosition(graph, geometry, field, connection.snap);
	const roadTicks =
		roadArrival === null
			? null
			: roadArrival + (connection?.connectorTicks ?? 0);
	const i = cellAt(grid.frame, target);
	let localGridTicks: number | null = null,
		localWitness: PointTiming["localWitness"] = null;
	if (i >= 0 && grid.times[i] !== 65535) {
		const from = center(grid.frame, i);
		if (
			(!bit(grid.boundary, i) && bit(grid.land, i)) ||
			landConnection(geography, from, [...target])
		) {
			const terminalTicks = connectorPrice(from, target).ticks;
			localGridTicks = grid.times[i] * 8 + terminalTicks;
			let at = i,
				edgeSeconds = 0,
				steps = 0;
			while (nibble(grid.parents, at) < 8) {
				if (++steps > grid.times.length)
					throw new Error("Local timing parent cycle");
				const d = nibble(grid.parents, at),
					[dx, dy] = DIRECTIONS[d],
					y = Math.floor(at / grid.frame.width),
					next = at + dy * grid.frame.width + dx;
				if (
					next < 0 ||
					next >= grid.times.length ||
					!hasLink(grid.links, at, next, d)
				)
					throw new Error("Local timing missing parent link");
				const cost =
					dy === 0
						? grid.horizontal[y]
						: dx === 0
							? grid.vertical
							: grid.diagonal[Math.min(y, y + dy)];
				if (grid.times[at] !== grid.times[next] + cost || cost <= 0)
					throw new Error("Local timing unpaid parent");
				edgeSeconds += cost;
				at = next;
			}
			const seedKind = nibble(grid.parents, at);
			if (seedKind !== 8 && seedKind !== 9)
				throw new Error("Local timing missing seed");
			if ((edgeSeconds + grid.times[at]) * 8 + terminalTicks !== localGridTicks)
				throw new Error("Local timing sum mismatch");
			localWitness = {
				terminalTicks,
				edgeSeconds,
				seedSeconds: grid.times[at],
				seedCell: at,
				seedKind,
				steps,
			};
		}
	}
	const road =
		roadTicks !== null && roadTicks <= field.horizonTicks ? roadTicks : null;
	const local =
		localGridTicks !== null && localGridTicks <= field.horizonTicks
			? localGridTicks
			: null;
	const useRoad = road !== null && (local === null || road <= local);
	return {
		ticks: useRoad ? road : local,
		kind: useRoad ? "road-foot" : local !== null ? "local-grid" : "unreached",
		roadTicks: road,
		localGridTicks: local,
		localWitness,
	};
}
