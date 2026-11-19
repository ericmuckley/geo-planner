/** Fixed diagnostic point finish: paid road foot or paid local-grid path. */

import {
	type AccessRoadField,
	arrivalAtAccessPosition,
} from "./coarse_osm_access_road_field_v1.ts";
import type { PointTiming } from "./coarse_osm_access_timing_v2.ts";
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
export type PreparedPointTiming = {
	origin: Coordinate;
	target: Coordinate;
	horizonTicks: number;
	roadTicks: number | null;
};

export function prepareAccessPointTiming(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	field: AccessRoadField,
	origin: Coordinate,
	target: Coordinate,
	connection: OriginConnection | null,
): PreparedPointTiming {
	const same = origin[0] === target[0] && origin[1] === target[1];
	const arrival = same
		? 0
		: connection === null
			? null
			: arrivalAtAccessPosition(graph, geometry, field, connection.snap);
	return {
		origin: [origin[0], origin[1]],
		target: [target[0], target[1]],
		horizonTicks: field.horizonTicks,
		roadTicks: same
			? 0
			: arrival === null
				? null
				: arrival + (connection?.connectorTicks ?? 0),
	};
}

export function finishAccessPointTiming(
	geography: OriginGeography,
	grid: DisplayProbe,
	prepared: PreparedPointTiming,
): PointTiming {
	const { origin, target, roadTicks } = prepared;
	if (origin[0] === target[0] && origin[1] === target[1])
		return {
			ticks: 0,
			kind: "same-input",
			roadTicks: 0,
			localGridTicks: 0,
			localWitness: null,
		};
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
		roadTicks !== null && roadTicks <= prepared.horizonTicks ? roadTicks : null;
	const local =
		localGridTicks !== null && localGridTicks <= prepared.horizonTicks
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
