import type { OriginConnection } from "./coarse_osm_origin_connections_v2.ts";
import { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import {
	fixture,
	type TestArc,
	words,
} from "./coarse_osm_packed_fixture_v1.ts";
import {
	PAID_GEOMETRY_FILES,
	type PaidGeometryFiles,
	PaidRoadGeometry,
} from "./coarse_osm_paid_geometry_v1.ts";
import {
	type Coordinate,
	sphericalDistance,
} from "./coarse_osm_spherical_v1.ts";
import {
	type ContextRule,
	contextFiles,
} from "./coarse_osm_turn_context_fixture_v1.ts";
import { TurnContexts } from "./coarse_osm_turn_contexts_v1.ts";
import { packUint24 } from "./coarse_osm_u24_v1.ts";

export function contextDisplayFixture(
	points: Coordinate[],
	edges: TestArc[],
	rules: ContextRule[] = [],
) {
	const raw = fixture(points.length, edges);
	raw["routing/xy.i32"] = words(
		points.flatMap((p) => p.map((v) => Math.round(v * 1e7))),
		4,
		true,
	);
	const graph = new PackedCarGraph(raw);
	const files = Object.fromEntries(
		PAID_GEOMETRY_FILES.map((n) => [n, new Uint8Array()]),
	) as PaidGeometryFiles;
	files["geometry/curve-offsets.u32"] = words([0], 4);
	const keys: number[] = [],
		lengths: number[] = [];
	edges.forEach(([a, b], i) => {
		const meters = sphericalDistance(points[a], points[b]);
		if (meters > 1000) {
			keys.push(i);
			lengths.push(Math.ceil(meters / 8) + 1);
		}
	});
	files["geometry/long-keys.u24"] = packUint24(keys);
	files["geometry/long-lengths.u16"] = words(lengths, 2);
	const contexts = new TurnContexts(
		graph.arcs,
		contextFiles(
			edges.map(([tail, head], i) => ({ tail, head, way: 10 * (i + 1) })),
			rules,
		),
	);
	const source: OriginConnection = {
		origin: points[0],
		snap: {
			canonicalArc: 0,
			segment: 0,
			segmentFraction: 0,
			coordinate: points[0],
			distanceMeters: 0,
			forwardProgress: 0,
			backwardProgress: 0,
		},
		connectorTicks: 0,
		connectorMeters: 0,
		kind: "modeled-road",
	};
	return {
		raw,
		files,
		graph,
		geometry: new PaidRoadGeometry(graph, files),
		contexts,
		source,
	};
}
