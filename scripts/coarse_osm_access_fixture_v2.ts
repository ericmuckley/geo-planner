import type { OriginGeography } from "./coarse_osm_origin_connections_v1.ts";
import { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import { fixture, words } from "./coarse_osm_packed_fixture_v1.ts";
import {
	PAID_GEOMETRY_FILES,
	type PaidGeometryFiles,
	PaidRoadGeometry,
} from "./coarse_osm_paid_geometry_v1.ts";
import {
	type Coordinate,
	sphericalDistance,
} from "./coarse_osm_spherical_v1.ts";
import { packUint24, Uint24View } from "./coarse_osm_u24_v1.ts";
export const rectangle = (w: number, s: number, e: number, n: number) => [
	[w, s],
	[e, s],
	[e, n],
	[w, n],
	[w, s],
];
export function geography(lakes: number[][][][] = []): OriginGeography {
	return {
		bounds: [-0.1, -0.1, 0.1, 0.1],
		boundary: [[rectangle(-0.1, -0.1, 0.1, 0.1)]],
		lakes,
	};
}
function key(p: Coordinate) {
	const x = Math.floor((Math.round(p[0] * 1e7) + 1800000000) / 1048576);
	const y = Math.floor((Math.round(p[1] * 1e7) + 900000000) / 1048576);
	let out = 0;
	for (let i = 0; i < 12; i++)
		out |= (((x >>> i) & 1) << (2 * i)) | (((y >>> i) & 1) << (2 * i + 1));
	return out;
}
export function prepared(coordinates: Coordinate[], edges: [number, number][]) {
	const order = coordinates
		.map((_, i) => i)
		.sort((a, b) => key(coordinates[a]) - key(coordinates[b]) || a - b);
	const mapping = coordinates.map((_, i) => order.indexOf(i));
	const points = order.map((i) => coordinates[i]);
	const arcs = edges
		.map(([a, b]) => [mapping[a], mapping[b]])
		.sort((a, b) => a[0] - b[0]);
	const raw = fixture(
		points.length,
		arcs.map(([a, b]) => [a, b, 1000]),
	);
	raw["routing/xy.i32"] = words(
		points.flatMap((p) => p.map((v) => Math.round(v * 1e7))),
		4,
		true,
	);
	const graph = new PackedCarGraph(raw);
	const files = Object.fromEntries(
		PAID_GEOMETRY_FILES.map((name) => [name, new Uint8Array()]),
	) as PaidGeometryFiles;
	files["geometry/curve-offsets.u32"] = words([0], 4);
	const long: number[] = [];
	const lengths: number[] = [];
	const overflow: number[] = [];
	const overflowUnits: number[] = [];
	arcs.forEach(([a, b], arc) => {
		const length = sphericalDistance(points[a], points[b]);
		if (length > 1000) {
			long.push(arc);
			const units = Math.ceil(length / 8) + 1;
			lengths.push(Math.min(65535, units));
			if (units >= 65535) {
				overflow.push(arc);
				overflowUnits.push(units);
			}
		}
	});
	files["geometry/long-keys.u24"] = packUint24(long);
	files["geometry/long-lengths.u16"] = words(lengths, 2);
	files["geometry/long-overflow-keys.u24"] = packUint24(overflow);
	files["geometry/long-overflow-units.u32"] = words(overflowUnits, 4);
	const keys: number[] = [];
	const starts: number[] = [];
	points.forEach((p, i) => {
		const k = key(p);
		if (!i || k !== keys[keys.length - 1]) {
			keys.push(k);
			starts.push(i);
		}
	});
	starts.push(points.length);
	return {
		graph,
		geometry: new PaidRoadGeometry(graph, files),
		keys: new Uint24View(packUint24(keys)),
		starts: new Uint24View(packUint24(starts)),
	};
}
