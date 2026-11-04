import assert from "node:assert/strict";
import test from "node:test";
import { prepareGeography } from "../src/server/coarse-geography.ts";
import {
	connectOrigin,
	connectorPrice,
	type OriginGeography,
} from "./coarse_osm_origin_connections_v1.ts";
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

const rectangle = (w: number, s: number, e: number, n: number) => [
	[w, s],
	[e, s],
	[e, n],
	[w, n],
	[w, s],
];
function geography(lakes: number[][][][] = []): OriginGeography {
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
function prepared(coordinates: Coordinate[], edges: [number, number][]) {
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
const connect = (
	p: ReturnType<typeof prepared>,
	geo: OriginGeography,
	origin: Coordinate = [0, 0],
) => connectOrigin(p.graph, p.geometry, p.keys, p.starts, geo, origin);

test("continuous land connection pays its complete local portion", () => {
	const p = prepared(
		[
			[0, -0.001],
			[0, 0.001],
		],
		[[0, 1]],
	);
	const origin: Coordinate = [0.001, 0.0005];
	const result = connect(p, geography(), origin);
	assert.ok(result.connection);
	assert.equal(result.work.fallbackPasses, 0);
	assert.equal(result.connection.kind, "land-connector");
	assert.ok(result.connection.connectorMeters > 100);
	assert.equal(
		result.connection.connectorTicks,
		Math.ceil((result.connection.connectorMeters * 28.8) / 25),
	);
	assert.deepEqual(connectorPrice(origin, origin), { meters: 0, ticks: 0 });
	assert.throws(() => connectorPrice([NaN, 0], [0, 0]));
	assert.throws(() => connectorPrice([0, 0], [180, 90]));
});

test("narrow water channel rejects nearest road and finds alternate land road", () => {
	const p = prepared(
		[
			[0.0004, -0.0001],
			[0.0004, 0.0001],
			[-0.004, -0.0001],
			[-0.004, 0.0001],
		],
		[
			[0, 1],
			[2, 3],
		],
	);
	const geo = geography([[rectangle(0.0001, -0.01, 0.0003, 0.01)]]);
	const result = connect(p, geo);
	assert.ok(result.connection);
	assert.ok(result.work.fallbackPasses > 0);
	assert.ok(result.connection.snap.coordinate[0] < 0);
	assert.ok(result.connection.connectorMeters > 400);
});

test("one-meter modeled-road allowance is global and remains positively priced", () => {
	const geo = geography();
	geo.boundary = [[rectangle(0.01, -0.01, 0.02, 0.01)]];
	let p = prepared(
		[
			[0.0000001, -0.001],
			[0.0000001, 0.001],
		],
		[[0, 1]],
	);
	let result = connect(p, geo);
	assert.ok(result.connection);
	assert.equal(result.connection.kind, "modeled-road");
	assert.equal(result.connection.connectorTicks, 1);
	p = prepared(
		[
			[0.00002, -0.001],
			[0.00002, 0.001],
		],
		[[0, 1]],
	);
	result = connect(p, geo);
	assert.equal(result.connection, null);
	assert.equal(result.reason, "outside-geography-mask");
});

test("one-way sink endpoint fallback is retained for short and long spans", () => {
	for (const scale of [1, 10]) {
		const p = prepared(
			[
				[0.0004 * scale, -0.0002 * scale],
				[-0.003 * scale, 0.005 * scale],
			],
			[[0, 1]],
		);
		const geo = geography([
			[rectangle(0.0001 * scale, -0.1, 0.0003 * scale, 0.1)],
		]);
		const result = connect(p, geo);
		assert.ok(result.connection);
		assert.equal(result.connection.snap.segmentFraction, 1);
		assert.ok(result.connection.snap.coordinate[0] < 0);
		assert.ok(result.work.fallbackPasses > 0);
		if (scale === 10) assert.ok(result.work.fallbackPasses >= 4);
	}
});

test("separate islands, over-budget sources, absent roads and bounds remain explicit", () => {
	let p = prepared(
		[
			[0.01, -0.001],
			[0.01, 0.001],
		],
		[[0, 1]],
	);
	let geo = geography();
	geo.boundary = [
		[rectangle(-0.001, -0.001, 0.001, 0.001)],
		[rectangle(0.009, -0.002, 0.011, 0.002)],
	];
	assert.equal(
		connect(p, geo).reason,
		"no-shore-checked-candidate-within-budget",
	);
	p = prepared(
		[
			[5, 0],
			[5, 0.01],
		],
		[[0, 1]],
	);
	geo = {
		bounds: [-10, -1, 10, 1],
		boundary: [[rectangle(-10, -1, 10, 1)]],
		lakes: [],
	};
	assert.equal(connect(p, geo).reason, "road-beyond-supported-budget");
	assert.equal(connect(p, geo, [11, 0]).reason, "outside-coverage-bounds");
	p = prepared([[0, 0]], []);
	assert.equal(connect(p, geography()).reason, "no-modeled-road");
	assert.throws(() => connect(p, geography(), [NaN, 0]));
});

test("prepared geography agrees without coordinate mutation", () => {
	const p = prepared(
		[
			[0.0004, -0.0001],
			[0.0004, 0.0001],
			[-0.004, -0.0001],
			[-0.004, 0.0001],
		],
		[
			[0, 1],
			[2, 3],
		],
	);
	const geo = geography([[rectangle(0.0001, -0.01, 0.0003, 0.01)]]);
	const before = JSON.stringify(geo);
	const plain = connect(p, geo);
	prepareGeography(geo);
	assert.deepEqual(connect(p, geo), plain);
	assert.equal(JSON.stringify(geo), before);
});
