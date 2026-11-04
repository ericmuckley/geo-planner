import assert from "node:assert/strict";
import test from "node:test";
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
	type RoadPosition,
	resolveRoadPosition,
	searchRoadPositions,
} from "./coarse_osm_paid_positions_v1.ts";

type Interior = { x: number; y: number; f: number; b: number };

function prepared(
	vertices: number,
	arcs: TestArc[],
	curves: { arc: number; points: Interior[] }[] = [],
	flags?: number[],
	turns?: number[],
	coordinates?: number[],
) {
	const raw = fixture(vertices, arcs, flags, turns);
	raw["routing/xy.i32"] = words(
		coordinates ??
			Array.from({ length: vertices }, (_, i) => [i * 1000, 0]).flat(),
		4,
		true,
	);
	const graph = new PackedCarGraph(raw);
	const files = Object.fromEntries(
		PAID_GEOMETRY_FILES.map((name) => [name, new Uint8Array()]),
	) as PaidGeometryFiles;
	const packets: number[] = [];
	const offsets = [0];
	const keys: number[] = [];
	const varint = (value: number) => {
		while (value >= 128) {
			packets.push((value & 127) | 128);
			value >>>= 7;
		}
		packets.push(value);
	};
	for (const curve of curves) {
		keys.push(curve.arc);
		let [x, y] = graph
			.coordinate(graph.arcTail(curve.arc))
			.map((v) => Math.round(v * 1e7));
		for (const point of curve.points) {
			for (const delta of [point.x - x, point.y - y])
				varint(((delta << 1) ^ (delta >> 31)) >>> 0);
			packets.push(point.f & 255, point.f >>> 8, point.b & 255, point.b >>> 8);
			x = point.x;
			y = point.y;
		}
		offsets.push(packets.length);
	}
	files["geometry/curve-keys.u24"] = packUint24(keys);
	files["geometry/curve-offsets.u32"] = words(offsets, 4);
	files["geometry/curve-packets.u8"] = Uint8Array.from(packets);
	return { graph, geometry: new PaidRoadGeometry(graph, files) };
}

import { packUint24 } from "./coarse_osm_u24_v1.ts";

const position = (fraction: number, arc = 0, segment = 0): RoadPosition => ({
	canonicalArc: arc,
	segment,
	segmentFraction: fraction,
});
const query = (
	p: ReturnType<typeof prepared>,
	a: RoadPosition,
	b: RoadPosition,
	maxTicks = 345600,
) =>
	searchRoadPositions(p.graph, p.geometry, a, b, {
		maxTicks,
		maxHeapEntries: 64,
	});
const ceiling = (cost: number, units: number) =>
	Number((BigInt(cost) * BigInt(units) + 65534n) / 65535n);

test("one-way partials pay road portions, same-span direction and horizon", () => {
	const p = prepared(2, [[0, 1, 1000]]);
	assert.equal(query(p, position(0.25), position(0.75)).ticks, 500);
	assert.equal(query(p, position(0.75), position(0.25)).ticks, null);
	assert.equal(query(p, position(0.25), position(0.75), 500).ticks, 500);
	assert.equal(query(p, position(0.25), position(0.75), 499).ticks, null);
	assert.equal(query(p, position(0.5), position(0.5), 0).ticks, 0);
	assert.equal(query(p, position(0), position(1)).ticks, 1000);
});

test("asymmetric reverse time uses its own prefix lane and full core cost", () => {
	const p = prepared(
		2,
		[
			[0, 1, 1000, 1],
			[1, 0, 2000, 0],
		],
		[{ arc: 0, points: [{ x: 500, y: 100, f: 32768, b: 16384 }] }],
	);
	const located = resolveRoadPosition(p.graph, p.geometry, position(1));
	assert.deepEqual(located.source, {
		partials: [
			{ arc: 0, ticks: ceiling(1000, 32767) },
			{ arc: 1, ticks: ceiling(2000, 16384) },
		],
	});
	assert.deepEqual(located.target, {
		partials: [
			{ arc: 0, ticks: ceiling(1000, 32768) },
			{ arc: 1, ticks: ceiling(2000, 49151) },
		],
	});
	assert.equal(query(p, position(0), position(1)).ticks, 501);
	assert.equal(query(p, position(1), position(0)).ticks, 501);
	assert.equal(query(p, position(0), position(1, 0, 1)).ticks, 1000);
	assert.equal(query(p, position(1, 0, 1), position(0)).ticks, 2000);
});

test("only actual endpoints become graph vertices, even with zero/full interior prefixes", () => {
	for (const units of [0, 65535]) {
		const p = prepared(
			2,
			[
				[0, 1, 1000, 1],
				[1, 0, 2000, 0],
			],
			[{ arc: 0, points: [{ x: 0, y: 0, f: units, b: units }] }],
		);
		assert.deepEqual(
			resolveRoadPosition(p.graph, p.geometry, position(0)).source,
			{ vertex: 0 },
		);
		assert.deepEqual(
			resolveRoadPosition(p.graph, p.geometry, position(1, 0, 1)).target,
			{ vertex: 1 },
		);
		const internal = resolveRoadPosition(p.graph, p.geometry, position(1));
		assert.ok("partials" in internal.source && "partials" in internal.target);
		assert.ok(internal.source.partials.every((p) => p.ticks > 0));
		assert.ok(internal.target.partials.every((p) => p.ticks > 0));
		assert.equal(query(p, position(1), position(0, 0, 1)).ticks, 0);
		assert.equal(
			query(p, position(1), position(0.5, 0, 1)).ticks,
			units === 65535 ? 1 : 500,
		);
	}
});

test("backtracking/coincident geometry never erases distinct paid source positions", () => {
	const p = prepared(
		2,
		[[0, 1, 3000]],
		[
			{
				arc: 0,
				points: [
					{ x: 1000, y: 0, f: 21845, b: 0 },
					{ x: 0, y: 0, f: 43690, b: 0 },
				],
			},
		],
	);
	assert.equal(query(p, position(1), position(1, 0, 2)).ticks, 2000);
	assert.equal(query(p, position(0), position(1, 0, 1)).ticks, 2000);
	assert.equal(query(p, position(1, 0, 1), position(0)).ticks, null);
});

test("a cheaper legal detour can beat the same-span direct candidate", () => {
	const arcs: TestArc[] = [
		[0, 1, 1000, 2],
		[0, 2, 10],
		[1, 0, 10, 0],
		[2, 1, 10],
	];
	let p = prepared(3, arcs);
	let result = query(p, position(0.1), position(0.9));
	assert.equal(result.directCandidateTicks, 800);
	assert.equal(result.ticks, 22);
	p = prepared(3, arcs, [], undefined, [2, 1]);
	result = query(p, position(0.1), position(0.9));
	assert.equal(result.ticks, 800);
});

test("barriers, source departure, target arrival, signals and forbidden turns stay active", () => {
	const arcs: TestArc[] = [
		[0, 1, 1000],
		[1, 2, 10],
		[2, 0, 10],
	];
	let p = prepared(3, arcs, [], [4, 6, 4]);
	assert.equal(query(p, position(0.75), position(0.25)).ticks, 560);
	p = prepared(3, arcs, [], [4, 1, 4]);
	assert.equal(query(p, position(0.75), position(0.25)).ticks, null);
	assert.equal(query(p, position(0.75), position(1)).ticks, 250);
	assert.equal(query(p, position(1), position(0.25)).ticks, 270);
	p = prepared(3, arcs, [], undefined, [0, 1]);
	assert.equal(query(p, position(0.75), position(0.25)).ticks, null);
	assert.equal(query(p, position(1), position(0.25)).ticks, 270);
});

test("parallel/coincident disconnected identities do not become transfers", () => {
	const p = prepared(
		4,
		[
			[0, 1, 100],
			[2, 3, 100],
		],
		[],
		undefined,
		undefined,
		[0, 0, 1000, 0, 0, 0, 1000, 0],
	);
	assert.equal(query(p, position(0.5, 0), position(0.5, 1)).ticks, null);
	assert.equal(query(p, position(0, 0), position(0, 1)).ticks, null);
});

test("canonical arc, segment, fraction and horizon domains refuse invalid input", () => {
	const p = prepared(2, [
		[0, 1, 100, 1],
		[1, 0, 100, 0],
	]);
	for (const invalid of [
		position(NaN),
		position(-0.01),
		position(1.01),
		position(0.5, 1),
		position(0.5, 5),
		position(0.5, 0, 2),
		position(0.5, 0, -1),
	])
		assert.throws(() => resolveRoadPosition(p.graph, p.geometry, invalid));
	assert.throws(() => query(p, position(0.2), position(0.8), -1));
	assert.throws(() => query(p, position(0.2), position(0.8), 345601));
});
