/** Coarse input-to-road proxy; never a transfer between different roads. */

import {
	type GeometricSnap,
	nearestModeledRoad,
} from "./coarse_osm_geometric_snap_v1.ts";
import type { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import type {
	PaidRoadGeometry,
	PaidShapePoint,
} from "./coarse_osm_paid_geometry_v1.ts";
import type { RoutingGeography } from "./coarse_osm_routing_geography_v1.ts";
import { landConnection } from "./coarse_osm_routing_geography_v1.ts";
import {
	type Coordinate,
	cellDistanceLowerMeters,
	EARTH_METERS,
	nearestOnSegment,
	sphericalDistance,
} from "./coarse_osm_spherical_v1.ts";
import type { Uint24View } from "./coarse_osm_u24_v1.ts";
export type OriginGeography = RoutingGeography;
export type OriginConnection = {
	origin: Coordinate;
	snap: GeometricSnap;
	connectorMeters: number;
	connectorTicks: number;
	kind: "modeled-road" | "land-connector";
};
const MAX_METERS = 300000;
const MAX_TICKS = 345600;

import { connectorPrice } from "./coarse_osm_origin_connections_v1.ts";

export { connectorPrice } from "./coarse_osm_origin_connections_v1.ts";

export function connectOrigin(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	keys: Uint24View,
	starts: Uint24View,
	geography: OriginGeography,
	origin: Coordinate,
	check: () => void = () => {},
) {
	if (!Number.isFinite(origin[0]) || !Number.isFinite(origin[1]))
		throw new Error("Origin coordinate domain");
	const work = {
		fallbackPasses: 0,
		spansDecoded: 0,
		segmentsChecked: 0,
		landChecks: 0,
	};
	const [west, south, east, north] = geography.bounds;
	if (
		origin[0] < west ||
		origin[0] > east ||
		origin[1] < south ||
		origin[1] > north
	)
		return { connection: null, reason: "outside-coverage-bounds", work };
	const geometric = nearestModeledRoad(
		graph,
		geometry,
		keys,
		starts,
		origin,
		check,
	);
	if (geometric.snap === null)
		return { connection: null, reason: "no-modeled-road", work };
	const input = [origin[0], origin[1]];
	const onMask = landConnection(geography, input, input);
	const eligible = (snap: GeometricSnap): OriginConnection | null => {
		if (snap.distanceMeters > MAX_METERS) return null;
		if (snap.distanceMeters > 1) {
			if (!onMask) return null;
			work.landChecks++;
			if (!landConnection(geography, input, [...snap.coordinate])) return null;
		}
		const price = connectorPrice(origin, snap.coordinate);
		if (price.ticks > MAX_TICKS) return null;
		return {
			origin,
			snap,
			connectorMeters: price.meters,
			connectorTicks: price.ticks,
			kind: snap.distanceMeters <= 1 ? "modeled-road" : "land-connector",
		};
	};
	const direct = eligible(geometric.snap);
	if (direct !== null) return { connection: direct, reason: null, work };
	if (!onMask)
		return { connection: null, reason: "outside-geography-mask", work };
	if (geometric.snap.distanceMeters > MAX_METERS)
		return { connection: null, reason: "road-beyond-supported-budget", work };
	let best: OriginConnection | null = null;
	for (let radius = 1000; ; radius = Math.min(MAX_METERS, radius * 2)) {
		work.fallbackPasses++;
		let bound = radius;
		const inspect = (arc: number) => {
			work.spansDecoded++;
			let previous: PaidShapePoint | null = null;
			let segment = -1;
			geometry.visitPoints(arc, (point) => {
				if (previous !== null) {
					segment++;
					work.segmentsChecked++;
					const a: Coordinate = [previous.xE7 / 1e7, previous.yE7 / 1e7];
					const b: Coordinate = [point.xE7 / 1e7, point.yE7 / 1e7];
					const foot = nearestOnSegment(origin, a, b);
					for (const candidate of [
						foot,
						{
							coordinate: a,
							fraction: 0,
							distance: sphericalDistance(origin, a),
						},
						{
							coordinate: b,
							fraction: 1,
							distance: sphericalDistance(origin, b),
						},
					]) {
						if (candidate.distance > bound + 1e-6) continue;
						const wins =
							best === null ||
							candidate.distance < best.snap.distanceMeters - 1e-6 ||
							(Math.abs(candidate.distance - best.snap.distanceMeters) <=
								1e-6 &&
								(arc < best.snap.canonicalArc ||
									(arc === best.snap.canonicalArc &&
										(segment < best.snap.segment ||
											(segment === best.snap.segment &&
												candidate.fraction < best.snap.segmentFraction)))));
						if (!wins) continue;
						const snap: GeometricSnap = {
							canonicalArc: arc,
							segment,
							segmentFraction: candidate.fraction,
							coordinate: candidate.coordinate,
							distanceMeters: candidate.distance,
							forwardProgress:
								(previous.forward +
									candidate.fraction * (point.forward - previous.forward)) /
								65535,
							backwardProgress:
								(previous.backward +
									candidate.fraction * (point.backward - previous.backward)) /
								65535,
						};
						const accepted = eligible(snap);
						if (accepted !== null) {
							best = accepted;
							bound = candidate.distance;
						}
					}
				}
				previous = point;
			});
		};
		for (let row = 0; row < keys.length; row++) {
			if (row % 4096 === 0) check();
			if (cellDistanceLowerMeters(origin, keys.at(row)) > bound + 1001)
				continue;
			for (let vertex = starts.at(row); vertex < starts.at(row + 1); vertex++) {
				if (sphericalDistance(origin, graph.coordinate(vertex)) > bound + 1001)
					continue;
				for (
					let arc = graph.outgoingStart(vertex);
					arc < graph.outgoingEnd(vertex);
					arc++
				)
					if (
						geometry.canonicalArc(arc) === arc &&
						geometry.lengthUpperMeters(arc) <= 1000
					)
						inspect(arc);
			}
		}
		for (let row = 0; row < geometry.longSpans; row++) {
			if (row % 16384 === 0) check();
			const arc = geometry.longArc(row);
			const a = graph.coordinate(graph.arcTail(arc));
			const b = graph.coordinate(graph.arcTarget(arc));
			const limit = bound + geometry.lengthUpperMeters(arc) / 2 + 1;
			if (
				((EARTH_METERS * Math.PI) / 180) *
					Math.min(Math.abs(origin[1] - a[1]), Math.abs(origin[1] - b[1])) >
				limit
			)
				continue;
			if (
				Math.min(sphericalDistance(origin, a), sphericalDistance(origin, b)) <=
				limit
			)
				inspect(arc);
		}
		check();
		if (best !== null || radius === MAX_METERS) break;
	}
	return {
		connection: best as OriginConnection | null,
		reason: best === null ? "no-shore-checked-candidate-within-budget" : null,
		work,
	};
}
