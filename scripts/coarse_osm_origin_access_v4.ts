/** Several independently paid initial road choices; never an inter-road transfer. */

import {
	type GeometricSnap,
	nearestModeledRoad,
} from "./coarse_osm_geometric_snap_v1.ts";
import {
	connectOrigin,
	connectorPrice,
	type OriginConnection,
	type OriginGeography,
} from "./coarse_osm_origin_connections_v2.ts";
import type { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import type { PaidRoadGeometry } from "./coarse_osm_paid_geometry_v1.ts";
import { resolveRoadPosition } from "./coarse_osm_paid_positions_v1.ts";
import { landConnection } from "./coarse_osm_routing_geography_v1.ts";
import {
	type Coordinate,
	cellDistanceLowerMeters,
	EARTH_METERS,
	nearestOnSegment,
	sphericalDistance,
} from "./coarse_osm_spherical_v1.ts";
import type { Uint24View } from "./coarse_osm_u24_v1.ts";

export function connectOriginAccessV4(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	keys: Uint24View,
	starts: Uint24View,
	geography: OriginGeography,
	origin: Coordinate,
	check: () => void = () => {},
	maximumConnections = 4096,
) {
	if (
		!Number.isInteger(maximumConnections) ||
		maximumConnections < 1 ||
		maximumConnections > 4096
	)
		throw new Error("Origin access connection cap domain");
	const original = connectOrigin(
		graph,
		geometry,
		keys,
		starts,
		geography,
		origin,
		check,
	);
	const onMask = landConnection(geography, [...origin], [...origin]);
	const work = {
		spansDecoded: 0,
		segmentsChecked: 0,
		landChecks: 0,
		candidatesChecked: 0,
	};
	const eligible = (snap: GeometricSnap): OriginConnection | null => {
		work.candidatesChecked++;
		if (snap.distanceMeters > 300000) return null;
		if (snap.distanceMeters > 1) {
			if (!onMask) {
				if (snap.distanceMeters > 100) return null;
			} else {
				work.landChecks++;
				if (!landConnection(geography, [...origin], [...snap.coordinate]))
					return null;
			}
		}
		const price = connectorPrice(origin, snap.coordinate);
		if (price.meters > 300000 || price.ticks > 345600) return null;
		return {
			origin,
			snap,
			connectorMeters: price.meters,
			connectorTicks: price.ticks,
			kind:
				!onMask || snap.distanceMeters <= 1 ? "modeled-road" : "land-connector",
		};
	};
	let primary = original.connection,
		maskOmissionAllowance = false;
	if (primary === null && original.reason === "outside-geography-mask") {
		const nearest = nearestModeledRoad(
			graph,
			geometry,
			keys,
			starts,
			origin,
			check,
		);
		primary = nearest.snap === null ? null : eligible(nearest.snap);
		maskOmissionAllowance = primary !== null;
	}
	if (primary === null)
		return {
			primary: null,
			connections: [] as OriginConnection[],
			reason: original.reason,
			maskOmissionAllowance: false,
			radiusMeters: null,
			work,
		};
	const radius = Math.min(300000, primary.connectorMeters + 1000);
	const selected = new Map<string, OriginConnection>();
	const located = resolveRoadPosition(graph, geometry, primary.snap);
	const primaryKey =
		"vertex" in located.source
			? `v${located.source.vertex}`
			: `a${located.canonicalArc}/${located.rank}`;
	selected.set(primaryKey, primary);
	const xy = new Int32Array(8192),
		prefix = new Uint16Array(8192);
	const inspect = (arc: number) => {
		work.spansDecoded++;
		let count = 0;
		geometry.visitPoints(arc, (p) => {
			if (count === 4096) throw new Error("Origin access curve point cap");
			xy[2 * count] = p.xE7;
			xy[2 * count + 1] = p.yE7;
			prefix[2 * count] = p.forward;
			prefix[2 * count + 1] = p.backward;
			count++;
		});
		for (let segment = 0; segment < count - 1; segment++) {
			work.segmentsChecked++;
			const a: Coordinate = [xy[2 * segment] / 1e7, xy[2 * segment + 1] / 1e7],
				b: Coordinate = [xy[2 * segment + 2] / 1e7, xy[2 * segment + 3] / 1e7];
			const foot = nearestOnSegment(origin, a, b);
			for (const point of [
				foot,
				{ coordinate: a, fraction: 0, distance: sphericalDistance(origin, a) },
				{ coordinate: b, fraction: 1, distance: sphericalDistance(origin, b) },
			]) {
				if (point.distance > radius + 1e-6) continue;
				const rank = segment + point.fraction;
				const identity =
					rank === 0
						? `v${graph.arcTail(arc)}`
						: rank === count - 1
							? `v${graph.arcTarget(arc)}`
							: `a${arc}/${rank}`;
				const existing = selected.get(identity);
				if (
					existing &&
					existing.connectorTicks <=
						connectorPrice(origin, point.coordinate).ticks
				)
					continue;
				const connection = eligible({
					canonicalArc: arc,
					segment,
					segmentFraction: point.fraction,
					coordinate: point.coordinate,
					distanceMeters: point.distance,
					forwardProgress:
						(prefix[2 * segment] +
							point.fraction *
								(prefix[2 * segment + 2] - prefix[2 * segment])) /
						65535,
					backwardProgress:
						(prefix[2 * segment + 1] +
							point.fraction *
								(prefix[2 * segment + 3] - prefix[2 * segment + 1])) /
						65535,
				});
				if (connection === null || connection.connectorMeters > radius + 1e-6)
					continue;
				if (!selected.has(identity) && selected.size === maximumConnections)
					throw new Error("Origin access connection cap exceeded");
				selected.set(identity, connection);
			}
		}
	};
	for (let row = 0; row < keys.length; row++) {
		if ((row & 4095) === 0) check();
		if (cellDistanceLowerMeters(origin, keys.at(row)) > radius + 1001) continue;
		for (let vertex = starts.at(row); vertex < starts.at(row + 1); vertex++) {
			if (sphericalDistance(origin, graph.coordinate(vertex)) > radius + 1001)
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
		if ((row & 16383) === 0) check();
		const arc = geometry.longArc(row),
			a = graph.coordinate(graph.arcTail(arc)),
			b = graph.coordinate(graph.arcTarget(arc));
		const bound = radius + geometry.lengthUpperMeters(arc) / 2 + 1;
		if (
			((EARTH_METERS * Math.PI) / 180) *
				Math.min(Math.abs(origin[1] - a[1]), Math.abs(origin[1] - b[1])) >
			bound
		)
			continue;
		if (
			Math.min(sphericalDistance(origin, a), sphericalDistance(origin, b)) <=
			bound
		)
			inspect(arc);
	}
	const connections = [...selected.values()].sort(
		(a, b) =>
			a.connectorTicks - b.connectorTicks ||
			a.snap.canonicalArc - b.snap.canonicalArc ||
			a.snap.segment +
				a.snap.segmentFraction -
				b.snap.segment -
				b.snap.segmentFraction,
	);
	check();
	return {
		primary,
		connections,
		reason: null,
		maskOmissionAllowance,
		radiusMeters: radius,
		work,
	};
}
