/** Exact paid display suffix and its original road seed, before raster reuse. */
import { landConnection } from "../src/server/coarse-geography.ts";
import {
	type AccessRoadField,
	arrivalAtAccessPosition,
} from "./coarse_osm_access_road_field_v1.ts";
import { accessDisplayPointTiming } from "./coarse_osm_access_timing_v1.ts";
import {
	cellAt,
	center,
	DIRECTIONS,
	hasLink,
	nibble,
} from "./coarse_osm_display_grid_v1.ts";
import type { DisplayProbe } from "./coarse_osm_filled_display_v1.ts";
import {
	connectorPrice,
	type OriginConnection,
	type OriginGeography,
} from "./coarse_osm_origin_connections_v1.ts";
import type { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import type { PaidRoadGeometry } from "./coarse_osm_paid_geometry_v1.ts";
import type { RoadPosition } from "./coarse_osm_paid_positions_v1.ts";
import {
	type Coordinate,
	sphericalDistance,
} from "./coarse_osm_spherical_v1.ts";
import type { SeedTrace } from "./coarse_osm_trace_display_v1.ts";
import { witnessPositionCoordinate } from "./coarse_osm_witness_geometry_v1.ts";

export function displayPointWitness(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	geography: OriginGeography,
	field: AccessRoadField,
	grid: DisplayProbe,
	trace: SeedTrace,
	origin: Coordinate,
	target: Coordinate,
	targetConnection: OriginConnection | null,
) {
	const measured = accessDisplayPointTiming(
		graph,
		geometry,
		geography,
		field,
		grid,
		origin,
		target,
		targetConnection,
	);
	const components = {
		inputLocalTicks: 0,
		roadSeedLinkTicks: 0,
		seedRoadRoundingTicks: 0,
		seedLinkRoundingTicks: 0,
		gridTravelTicks: 0,
		gridRoundingTicks: 0,
		terminalTicks: 0,
	};
	let roadTarget: RoadPosition | null = null,
		fieldRoadTicks: number | null = null;
	const coordinates: Coordinate[] = [];
	if (measured.kind === "unreached")
		return { measured, roadTarget, fieldRoadTicks, components, coordinates };
	if (measured.kind === "same-input")
		return {
			measured,
			roadTarget,
			fieldRoadTicks,
			components,
			coordinates: [origin],
		};
	if (measured.kind === "road-foot") {
		if (targetConnection === null)
			throw new Error("Road suffix missing target connection");
		if (
			targetConnection.origin[0] !== target[0] ||
			targetConnection.origin[1] !== target[1]
		)
			throw new Error("Road suffix target input mismatch");
		roadTarget = {
			canonicalArc: targetConnection.snap.canonicalArc,
			segment: targetConnection.snap.segment,
			segmentFraction: targetConnection.snap.segmentFraction,
		};
		fieldRoadTicks = arrivalAtAccessPosition(
			graph,
			geometry,
			field,
			roadTarget,
		);
		if (fieldRoadTicks === null) throw new Error("Road suffix missing arrival");
		if (
			connectorPrice(target, targetConnection.snap.coordinate).ticks !==
			targetConnection.connectorTicks
		)
			throw new Error("Road suffix unpaid terminal connector");
		if (
			targetConnection.snap.distanceMeters > 1 &&
			!landConnection(
				geography,
				[...target],
				[...targetConnection.snap.coordinate],
			)
		)
			throw new Error("Road suffix terminal crosses water");
		if (
			sphericalDistance(
				witnessPositionCoordinate(geometry, roadTarget),
				targetConnection.snap.coordinate,
			) > 0.001
		)
			throw new Error("Road suffix snap reconstruction mismatch");
		components.terminalTicks = targetConnection.connectorTicks;
		coordinates.push(targetConnection.snap.coordinate, target);
	} else {
		const witness = measured.localWitness;
		if (witness === null)
			throw new Error("Local suffix missing parent witness");
		let i = cellAt(grid.frame, target);
		if (i < 0) throw new Error("Local suffix target outside grid");
		const reversed: number[] = [i];
		while (nibble(grid.parents, i) < 8) {
			if (reversed.length > grid.times.length)
				throw new Error("Local suffix parent cycle");
			const d = nibble(grid.parents, i),
				[dx, dy] = DIRECTIONS[d],
				x = i % grid.frame.width,
				y = Math.floor(i / grid.frame.width),
				nx = x + dx,
				ny = y + dy;
			if (nx < 0 || nx >= grid.frame.width || ny < 0 || ny >= grid.frame.height)
				throw new Error("Local suffix wrapped parent");
			const next = ny * grid.frame.width + nx;
			if (!hasLink(grid.links, i, next, d))
				throw new Error("Local suffix forbidden parent");
			const from = center(grid.frame, next),
				to = center(grid.frame, i);
			if (!landConnection(geography, from, to))
				throw new Error("Local suffix crosses water");
			const price = connectorPrice(from, to).ticks,
				paid = (grid.times[i] - grid.times[next]) * 8;
			if (paid <= 0 || paid !== Math.ceil(price / 8) * 8)
				throw new Error("Local suffix unpaid or mispriced grid step");
			components.gridTravelTicks += price;
			components.gridRoundingTicks += paid - price;
			i = next;
			reversed.push(i);
		}
		if (i !== witness.seedCell || nibble(grid.parents, i) !== witness.seedKind)
			throw new Error("Local suffix seed mismatch");
		const seedCenter = center(grid.frame, i);
		if (witness.seedKind === 8) {
			if (trace.arcs[i] === 0xffffffff)
				throw new Error("Local suffix missing road sample");
			roadTarget = {
				canonicalArc: trace.arcs[i],
				segment: trace.segments[i],
				segmentFraction: trace.fractions[i],
			};
			fieldRoadTicks = arrivalAtAccessPosition(
				graph,
				geometry,
				field,
				roadTarget,
			);
			if (fieldRoadTicks === null)
				throw new Error("Local suffix missing seed arrival");
			const point = witnessPositionCoordinate(geometry, roadTarget);
			if (!landConnection(geography, [...point], seedCenter))
				throw new Error("Local suffix seed crosses water");
			components.roadSeedLinkTicks = connectorPrice(point, seedCenter).ticks;
			components.seedRoadRoundingTicks =
				Math.ceil(fieldRoadTicks / 8) * 8 - fieldRoadTicks;
			components.seedLinkRoundingTicks =
				Math.ceil(components.roadSeedLinkTicks / 8) * 8 -
				components.roadSeedLinkTicks;
			coordinates.push(point);
		} else if (witness.seedKind === 9) {
			if (!landConnection(geography, [...origin], seedCenter))
				throw new Error("Local suffix input crosses water");
			components.inputLocalTicks = connectorPrice(origin, seedCenter).ticks;
			components.seedLinkRoundingTicks =
				Math.ceil(components.inputLocalTicks / 8) * 8 -
				components.inputLocalTicks;
			coordinates.push(origin);
		} else throw new Error("Local suffix invalid seed kind");
		const seedTicks =
			(fieldRoadTicks ?? 0) +
			components.inputLocalTicks +
			components.roadSeedLinkTicks +
			components.seedRoadRoundingTicks +
			components.seedLinkRoundingTicks;
		if (seedTicks !== grid.times[i] * 8)
			throw new Error("Local suffix initial sum mismatch");
		coordinates.push(
			...reversed.reverse().map((cell) => center(grid.frame, cell)),
			target,
		);
		const endCenter = coordinates[coordinates.length - 2];
		if (!landConnection(geography, [...endCenter], [...target]))
			throw new Error("Local suffix terminal crosses water");
		components.terminalTicks = connectorPrice(endCenter, target).ticks;
	}
	const total =
		(fieldRoadTicks ?? 0) +
		Object.values(components).reduce((sum, ticks) => sum + ticks, 0);
	if (total !== measured.ticks)
		throw new Error("Display point witness sum mismatch");
	return { measured, roadTarget, fieldRoadTicks, components, coordinates };
}
