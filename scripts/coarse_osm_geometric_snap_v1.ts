/** Geometric nearest modeled road only; no origin connection or access policy. */
import type { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import type {
	PaidRoadGeometry,
	PaidShapePoint,
} from "./coarse_osm_paid_geometry_v1.ts";
import {
	cellDistanceLowerMeters,
	type Coordinate,
	EARTH_METERS,
	nearestOnSegment,
	sphericalDistance,
} from "./coarse_osm_spherical_v1.ts";
import type { Uint24View } from "./coarse_osm_u24_v1.ts";

export type GeometricSnap = {
	canonicalArc: number;
	segment: number;
	segmentFraction: number;
	coordinate: Coordinate;
	distanceMeters: number;
	forwardProgress: number;
	backwardProgress: number;
};

export function nearestModeledRoad(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	keys: Uint24View,
	starts: Uint24View,
	origin: Coordinate,
	check: () => void = () => {},
) {
	if (
		!Number.isFinite(origin[0]) ||
		!Number.isFinite(origin[1]) ||
		Math.abs(origin[0]) > 180 ||
		Math.abs(origin[1]) > 90
	)
		throw new Error("Snap origin coordinate domain");
	if (
		starts.length !== keys.length + 1 ||
		starts.at(0) !== 0 ||
		starts.at(keys.length) !== graph.vertices
	)
		throw new Error("Qualified cell index shape required");
	const stats = {
		cellBounds: 0,
		tailVerticesMeasured: 0,
		shortSpansProjected: 0,
		longSpansExamined: 0,
		longEndpointPairsMeasured: 0,
		segmentsProjected: 0,
	};
	if (graph.arcs === 0) return { snap: null, stats };
	let bestDistance = sphericalDistance(
		origin,
		graph.coordinate(graph.arcTail(0)),
	);
	let best: GeometricSnap | null = null;
	let nearestCell = 0;
	let nearestBound = Infinity;
	for (let row = 0; row < keys.length; row++) {
		if (row % 4096 === 0) check();
		const bound = cellDistanceLowerMeters(origin, keys.at(row));
		stats.cellBounds++;
		if (bound < nearestBound) {
			nearestBound = bound;
			nearestCell = row;
		}
	}
	const inspectTails = (row: number) => {
		for (let vertex = starts.at(row); vertex < starts.at(row + 1); vertex++) {
			if (graph.outgoingStart(vertex) === graph.outgoingEnd(vertex)) continue;
			stats.tailVerticesMeasured++;
			if (stats.tailVerticesMeasured % 16384 === 0) check();
			bestDistance = Math.min(
				bestDistance,
				sphericalDistance(origin, graph.coordinate(vertex)),
			);
		}
	};
	inspectTails(nearestCell);
	for (let row = 0; row < keys.length; row++) {
		if (row === nearestCell) continue;
		if (row % 4096 === 0) check();
		stats.cellBounds++;
		if (cellDistanceLowerMeters(origin, keys.at(row)) <= bestDistance + 1)
			inspectTails(row);
	}
	const inspectSpan = (arc: number) => {
		let previous: PaidShapePoint | null = null;
		let segment = -1;
		geometry.visitPoints(arc, (point) => {
			if (previous !== null) {
				segment++;
				stats.segmentsProjected++;
				const candidate = nearestOnSegment(
					origin,
					[previous.xE7 / 1e7, previous.yE7 / 1e7],
					[point.xE7 / 1e7, point.yE7 / 1e7],
				);
				const wins =
					candidate.distance < bestDistance - 1e-6 ||
					(Math.abs(candidate.distance - bestDistance) <= 1e-6 &&
						(best === null ||
							arc < best.canonicalArc ||
							(arc === best.canonicalArc && segment < best.segment)));
				if (wins) {
					bestDistance = candidate.distance;
					best = {
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
				}
			}
			previous = point;
		});
	};
	for (let row = 0; row < keys.length; row++) {
		stats.cellBounds++;
		if (cellDistanceLowerMeters(origin, keys.at(row)) > bestDistance + 1001)
			continue;
		if (row % 4096 === 0) check();
		for (let vertex = starts.at(row); vertex < starts.at(row + 1); vertex++) {
			if (
				sphericalDistance(origin, graph.coordinate(vertex)) >
				bestDistance + 1001
			)
				continue;
			for (
				let arc = graph.outgoingStart(vertex);
				arc < graph.outgoingEnd(vertex);
				arc++
			) {
				if (
					geometry.canonicalArc(arc) !== arc ||
					geometry.lengthUpperMeters(arc) > 1000
				)
					continue;
				stats.shortSpansProjected++;
				inspectSpan(arc);
			}
		}
	}
	for (let row = 0; row < geometry.longSpans; row++) {
		stats.longSpansExamined++;
		if (row % 16384 === 0) check();
		const arc = geometry.longArc(row);
		const radius = bestDistance + geometry.lengthUpperMeters(arc) / 2 + 1;
		const a = graph.coordinate(graph.arcTail(arc));
		const b = graph.coordinate(graph.arcTarget(arc));
		const latitudeLower =
			((EARTH_METERS * Math.PI) / 180) *
			Math.min(Math.abs(origin[1] - a[1]), Math.abs(origin[1] - b[1]));
		if (latitudeLower > radius) continue;
		stats.longEndpointPairsMeasured++;
		if (
			Math.min(sphericalDistance(origin, a), sphericalDistance(origin, b)) <=
			radius
		)
			inspectSpan(arc);
	}
	check();
	return { snap: best as GeometricSnap | null, stats };
}
