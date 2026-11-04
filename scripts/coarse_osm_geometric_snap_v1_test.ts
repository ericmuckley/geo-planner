import assert from "node:assert/strict";
import test from "node:test";
import { nearestModeledRoad } from "./coarse_osm_geometric_snap_v1.ts";
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
	cellDistanceLowerMeters,
	type Coordinate,
	EARTH_METERS,
	nearestOnSegment,
} from "./coarse_osm_spherical_v1.ts";
import { packUint24, Uint24View } from "./coarse_osm_u24_v1.ts";

const RAD = Math.PI / 180;
type Vec = [number, number, number];
const dot = (a: Vec, b: Vec) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a: Vec, b: Vec): Vec => [
	a[1] * b[2] - a[2] * b[1],
	a[2] * b[0] - a[0] * b[2],
	a[0] * b[1] - a[1] * b[0],
];
const unit = (a: Vec): Vec => a.map((v) => v / Math.hypot(...a)) as Vec;
const vector = (p: Coordinate): Vec => [
	Math.cos(p[1] * RAD) * Math.cos(p[0] * RAD),
	Math.cos(p[1] * RAD) * Math.sin(p[0] * RAD),
	Math.sin(p[1] * RAD),
];
const angular = (a: Vec, b: Vec) =>
	Math.atan2(Math.hypot(...cross(a, b)), dot(a, b));
const distance = (a: Coordinate, b: Coordinate) =>
	EARTH_METERS * angular(vector(a), vector(b));

/** Independent 3D projection and minor-arc membership check. */
function oracle(p: Coordinate, a: Coordinate, b: Coordinate) {
	const q = vector(p);
	const va = vector(a);
	const vb = vector(b);
	const length = angular(va, vb);
	let result =
		distance(p, a) <= distance(p, b)
			? { distance: distance(p, a), fraction: 0 }
			: { distance: distance(p, b), fraction: 1 };
	if (length < 1e-12 || length > Math.PI - 1e-12) return result;
	const normal = unit(cross(va, vb));
	const projected = q.map(
		(value, i) => value - dot(q, normal) * normal[i],
	) as Vec;
	if (Math.hypot(...projected) < 1e-14) return result;
	for (const sign of [1, -1]) {
		const onPlane = unit(projected).map((v) => sign * v) as Vec;
		const start = angular(va, onPlane);
		const end = angular(onPlane, vb);
		if (Math.abs(start + end - length) < 1e-10) {
			const d = EARTH_METERS * angular(q, onPlane);
			if (d < result.distance)
				result = { distance: d, fraction: start / length };
		}
	}
	return result;
}

function cellKey(p: Coordinate): number {
	const x = Math.floor((Math.round(p[0] * 1e7) + 1800000000) / 1048576);
	const y = Math.floor((Math.round(p[1] * 1e7) + 900000000) / 1048576);
	let key = 0;
	for (let i = 0; i < 12; i++)
		key |= (((x >>> i) & 1) << (2 * i)) | (((y >>> i) & 1) << (2 * i + 1));
	return key;
}

type Road = { a: number; b: number; inside?: Coordinate[]; both?: boolean };
function prepared(input: Coordinate[], roads: Road[]) {
	const order = input
		.map((_, i) => i)
		.sort((a, b) => cellKey(input[a]) - cellKey(input[b]) || a - b);
	const mapping = order.map((_, i) => order.indexOf(i));
	const coordinates = order.map((i) => input[i]);
	const arcs: {
		tail: number;
		head: number;
		road: number;
		backward: boolean;
	}[] = [];
	roads.forEach((road, i) => {
		arcs.push({
			tail: mapping[road.a],
			head: mapping[road.b],
			road: i,
			backward: false,
		});
		if (road.both)
			arcs.push({
				tail: mapping[road.b],
				head: mapping[road.a],
				road: i,
				backward: true,
			});
	});
	arcs.sort(
		(a, b) =>
			a.tail - b.tail ||
			a.road - b.road ||
			Number(a.backward) - Number(b.backward),
	);
	const core = fixture(
		input.length,
		arcs.map((arc, i): TestArc => {
			const reverse = arcs.findIndex(
				(other, j) => j !== i && other.road === arc.road,
			);
			return [
				arc.tail,
				arc.head,
				arc.backward ? 1500 : 1000,
				reverse < 0 ? undefined : reverse,
			];
		}),
	);
	core["routing/xy.i32"] = words(
		coordinates.flatMap((p) => p.map((v) => Math.round(v * 1e7))),
		4,
		true,
	);
	const graph = new PackedCarGraph(core);
	const files = Object.fromEntries(
		PAID_GEOMETRY_FILES.map((name) => [name, new Uint8Array()]),
	) as PaidGeometryFiles;
	const curveKeys: number[] = [];
	const offsets = [0];
	const packet: number[] = [];
	const longKeys: number[] = [];
	const lengths: number[] = [];
	const overflowKeys: number[] = [];
	const overflowUnits: number[] = [];
	const spans: { arc: number; points: Coordinate[] }[] = [];
	const varint = (value: number) => {
		while (value >= 128) {
			packet.push((value & 127) | 128);
			value >>>= 7;
		}
		packet.push(value);
	};
	for (let arc = 0; arc < arcs.length; arc++) {
		const reverse = graph.reverseArc(arc);
		if (reverse !== null && reverse < arc) continue;
		const row = arcs[arc];
		const road = roads[row.road];
		let points = [input[road.a], ...(road.inside ?? []), input[road.b]];
		if (row.backward) points = points.reverse();
		points = points.map(
			(p) => p.map((v) => Math.round(v * 1e7) / 1e7) as [number, number],
		);
		spans.push({ arc, points });
		let length = 0;
		for (let i = 1; i < points.length; i++)
			length += distance(points[i - 1], points[i]);
		if (length > 1000) {
			longKeys.push(arc);
			const units = Math.ceil(length / 8) + 1;
			lengths.push(Math.min(65535, units));
			if (units >= 65535) {
				overflowKeys.push(arc);
				overflowUnits.push(units);
			}
		}
		if (points.length > 2) {
			curveKeys.push(arc);
			let old = points[0];
			for (let i = 1; i + 1 < points.length; i++) {
				for (let j = 0; j < 2; j++) {
					const delta =
						(Math.round(points[i][j] * 1e7) - Math.round(old[j] * 1e7)) | 0;
					varint(((delta << 1) ^ (delta >> 31)) >>> 0);
				}
				const f = Math.round((i / (points.length - 1)) * 65535);
				const b = reverse === null ? 0 : f;
				packet.push(f & 255, f >>> 8, b & 255, b >>> 8);
				old = points[i];
			}
			offsets.push(packet.length);
		}
	}
	files["geometry/curve-keys.u24"] = packUint24(curveKeys);
	files["geometry/curve-offsets.u32"] = words(offsets, 4);
	files["geometry/curve-packets.u8"] = Uint8Array.from(packet);
	files["geometry/long-keys.u24"] = packUint24(longKeys);
	files["geometry/long-lengths.u16"] = words(lengths, 2);
	files["geometry/long-overflow-keys.u24"] = packUint24(overflowKeys);
	files["geometry/long-overflow-units.u32"] = words(overflowUnits, 4);
	const keys: number[] = [];
	const starts: number[] = [];
	coordinates.forEach((p, i) => {
		const key = cellKey(p);
		if (!i || key !== keys[keys.length - 1]) {
			keys.push(key);
			starts.push(i);
		}
	});
	starts.push(input.length);
	return {
		graph,
		files,
		geometry: new PaidRoadGeometry(graph, files),
		keys: new Uint24View(packUint24(keys)),
		starts: new Uint24View(packUint24(starts)),
		spans,
	};
}

function compare(p: ReturnType<typeof prepared>, origin: Coordinate) {
	const actual = nearestModeledRoad(
		p.graph,
		p.geometry,
		p.keys,
		p.starts,
		origin,
	).snap;
	let expected: {
		arc: number;
		segment: number;
		distance: number;
		fraction: number;
	} | null = null;
	for (const span of p.spans)
		for (let i = 1; i < span.points.length; i++) {
			const q = oracle(origin, span.points[i - 1], span.points[i]);
			if (
				expected === null ||
				q.distance < expected.distance - 1e-6 ||
				(Math.abs(q.distance - expected.distance) <= 1e-6 &&
					(span.arc < expected.arc ||
						(span.arc === expected.arc && i - 1 < expected.segment)))
			)
				expected = { arc: span.arc, segment: i - 1, ...q };
		}
	assert.equal(actual?.canonicalArc ?? null, expected?.arc ?? null);
	if (expected !== null) {
		assert.ok(actual);
		assert.equal(actual.segment, expected.segment);
		assert.ok(
			Math.abs(actual.distanceMeters - expected.distance) < 0.001,
			JSON.stringify({ origin, actual, expected }),
		);
		assert.ok(
			Math.abs(actual.segmentFraction - expected.fraction) *
				distance(
					p.spans.find((span) => span.arc === expected.arc)!.points[
						expected.segment
					],
					p.spans.find((span) => span.arc === expected.arc)!.points[
						expected.segment + 1
					],
				) <
				0.001,
		);
	}
}

function randomizer() {
	let state = 20261103;
	return () => {
		state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
		return state / 2 ** 32;
	};
}

test("one-way sink is found when its only outgoing tail is over 500 m away", () => {
	const p = prepared(
		[
			[0, 0],
			[0.008, 0],
			[0.008, 0.001],
			[0.008, 0.002],
		],
		[
			{ a: 0, b: 1 },
			{ a: 2, b: 3 },
		],
	);
	compare(p, [0.008, 0]);
	assert.equal(
		nearestModeledRoad(p.graph, p.geometry, p.keys, p.starts, [0.008, 0]).snap
			?.distanceMeters,
		0,
	);
});

test("long bent/closed/backtracking, parallel/reversed and zero-length roads", () => {
	const p = prepared(
		[
			[0, 0],
			[1, 0],
			[0, 0],
			[0, 1],
			[0, 0],
		],
		[
			{
				a: 0,
				b: 1,
				inside: [
					[0, 1],
					[1, 1],
				],
				both: true,
			},
			{
				a: 1,
				b: 0,
				inside: [
					[0.5, 0],
					[1, 0],
					[0.5, 0],
				],
				both: true,
			},
			{ a: 2, b: 4 },
			{
				a: 0,
				b: 4,
				inside: [
					[0.2, 0.2],
					[0.2, 0],
				],
				both: true,
			},
			{ a: 3, b: 4 },
		],
	);
	for (const q of [
		[0.5, 1],
		[0.8, 0.01],
		[0.2, 0.2],
		[0, 0],
		[5, 5],
	] as Coordinate[])
		compare(p, q);
});

test("global wrap, poles and far-side endpoint selection", () => {
	for (const points of [
		[
			[179.99, 0],
			[-179.99, 0],
		],
		[
			[0, 89.999],
			[90, 89.999],
		],
		[
			[0, 0],
			[90, 0],
		],
	] as Coordinate[][]) {
		const p = prepared(points, [{ a: 0, b: 1, both: true }]);
		for (const q of [
			[180, 0.001],
			[-179.99, 0],
			[45, 90],
			[-170, 0],
		] as Coordinate[])
			compare(p, q);
	}
	assert.equal(nearestOnSegment([-170, 0], [0, 0], [90, 0]).fraction, 1);
});

test("reversed canonical shape preserves distinct directional paid progress", () => {
	const p = prepared(
		[
			[1, 0],
			[0, 0],
		],
		[{ a: 0, b: 1, both: true, inside: [[0.5, 0.1]] }],
	);
	const raw = p.files["geometry/curve-packets.u8"];
	raw[raw.length - 2] = 0;
	raw[raw.length - 1] = 64;
	const geometry = new PaidRoadGeometry(p.graph, p.files);
	const snap = nearestModeledRoad(
		p.graph,
		geometry,
		p.keys,
		p.starts,
		[0.5, 0.1],
	).snap;
	assert.ok(snap);
	assert.equal(snap.canonicalArc, 0);
	assert.ok(Math.abs(snap.forwardProgress - 32768 / 65535) < 1e-10);
	assert.ok(Math.abs(snap.backwardProgress - 16384 / 65535) < 1e-10);
});

test("empty and isolated graphs return null and invalid origins refuse", () => {
	const p = prepared(
		[
			[0, 0],
			[10, 10],
		],
		[],
	);
	compare(p, [1, 1]);
	assert.throws(() =>
		nearestModeledRoad(p.graph, p.geometry, p.keys, p.starts, [NaN, 0]),
	);
	assert.throws(() =>
		nearestModeledRoad(p.graph, p.geometry, p.keys, p.starts, [181, 0]),
	);
});

test("500 global and clustered generated queries match exhaustive independent physical-span oracle", () => {
	const random = randomizer();
	for (let run = 0; run < 100; run++) {
		const lon = random() * 340 - 170;
		const lat = random() * 150 - 75;
		const scale = run % 2 ? 0.001 : 2;
		const points: Coordinate[] = Array.from({ length: 12 }, () => [
			lon + (random() - 0.5) * scale,
			lat + (random() - 0.5) * scale,
		]);
		const roads = Array.from(
			{ length: 15 },
			(_, i): Road => ({
				a: i % points.length,
				b: (i + 1 + Math.floor(random() * 10)) % points.length,
				both: i % 3 === 0,
				inside:
					i % 4 === 0
						? [[lon + (random() - 0.5) * scale, lat + (random() - 0.5) * scale]]
						: [],
			}),
		);
		const p = prepared(points, roads);
		for (let i = 0; i < 5; i++)
			compare(p, [
				lon + (random() - 0.5) * scale,
				lat + (random() - 0.5) * scale,
			]);
	}
});

test("2000 independent global projection/cell-bound controls", () => {
	const random = randomizer();
	for (let i = 0; i < 2000; i++) {
		const p: Coordinate = [random() * 360 - 180, random() * 180 - 90];
		const a: Coordinate = [random() * 360 - 180, random() * 180 - 90];
		const b: Coordinate = [random() * 360 - 180, random() * 180 - 90];
		const actual = nearestOnSegment(p, a, b);
		const expected = oracle(p, a, b);
		assert.ok(Math.abs(actual.distance - expected.distance) < 0.001);
		assert.ok(
			Math.abs(actual.fraction - expected.fraction) * distance(a, b) < 0.001,
		);
		assert.ok(cellDistanceLowerMeters(p, cellKey(a)) <= distance(p, a) + 0.001);
	}
});

test("E7-sized, wrapped, polar, coincident and antipodal segments", () => {
	const cases: [Coordinate, Coordinate, Coordinate][] = [
		[
			[0.0000001, 0.0000001],
			[0, 0],
			[0.0000002, 0],
		],
		[
			[180, 0.0000001],
			[179.9999999, 0],
			[-179.9999999, 0],
		],
		[
			[45, 89.9999999],
			[0, 89.9999998],
			[90, 89.9999998],
		],
		[
			[20, 5],
			[10, 0],
			[10, 0],
		],
		[
			[30, 10],
			[0, 0],
			[180, 0],
		],
	];
	for (const [p, a, b] of cases) {
		const actual = nearestOnSegment(p, a, b);
		const expected = oracle(p, a, b);
		assert.ok(Math.abs(actual.distance - expected.distance) < 0.001);
		assert.ok(
			Math.abs(actual.fraction - expected.fraction) * distance(a, b) < 0.001,
		);
	}
});
