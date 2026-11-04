import assert from "node:assert/strict";
import test from "node:test";
import { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import { fixture, words } from "./coarse_osm_packed_fixture_v1.ts";
import {
	PAID_GEOMETRY_FILES,
	type PaidGeometryFiles,
	PaidRoadGeometry,
	type PaidShapePoint,
} from "./coarse_osm_paid_geometry_v1.ts";
import { packUint24 } from "./coarse_osm_u24_v1.ts";

function graph(reverse = true) {
	const files = fixture(
		2,
		reverse
			? [
					[0, 1, 100, 1],
					[1, 0, 150, 0],
				]
			: [[0, 1, 100]],
	);
	files["routing/xy.i32"] = words([0, 0, 10000000, 0], 4, true);
	return new PackedCarGraph(files);
}

function geometry(backward = 32768): PaidGeometryFiles {
	// Independently hand-encoded zigzag E7 deltas: (+5000000,+100000).
	const packet = Uint8Array.from([
		0x80,
		0xad,
		0xe2,
		0x04,
		0xc0,
		0x9a,
		0x0c,
		0,
		0x80,
		backward & 255,
		backward >>> 8,
	]);
	return {
		"geometry/curve-keys.u24": packUint24([0]),
		"geometry/curve-offsets.u32": words([0, packet.length], 4),
		"geometry/curve-packets.u8": packet,
		"geometry/long-keys.u24": packUint24([0]),
		"geometry/long-lengths.u16": words([14000], 2),
		"geometry/long-overflow-keys.u24": new Uint8Array(),
		"geometry/long-overflow-units.u32": new Uint8Array(),
	};
}

test("canonical shape preserves exact E7 coordinates and both paid directions", () => {
	const files = geometry();
	const reader = new PaidRoadGeometry(graph(), files);
	const points: PaidShapePoint[] = [];
	reader.visitPoints(1, (point) => points.push(point));
	assert.deepEqual(points, [
		{ xE7: 0, yE7: 0, forward: 0, backward: 0 },
		{ xE7: 5000000, yE7: 100000, forward: 32768, backward: 32768 },
		{ xE7: 10000000, yE7: 0, forward: 65535, backward: 65535 },
	]);
	assert.equal(reader.lengthUpperMeters(1), 112000);
	assert.equal(reader.longArc(0), 0);
	assert.equal(
		reader.retainedBackingBufferBytes,
		Object.values(files).reduce((sum, bytes) => sum + bytes.byteLength, 0),
	);
});

test("one-way road never acquires a reverse time prefix", () => {
	assert.doesNotThrow(() => new PaidRoadGeometry(graph(false), geometry(0)));
	assert.throws(() => new PaidRoadGeometry(graph(false), geometry()));
});

test("implicit straight shape and conservative short/overflow lengths", () => {
	const files = Object.fromEntries(
		PAID_GEOMETRY_FILES.map((name) => [name, new Uint8Array()]),
	) as PaidGeometryFiles;
	files["geometry/curve-offsets.u32"] = words([0], 4);
	let reader = new PaidRoadGeometry(graph(), files);
	const points: PaidShapePoint[] = [];
	reader.visitPoints(0, (point) => points.push(point));
	assert.equal(points.length, 2);
	assert.equal(reader.lengthUpperMeters(0), 1000);
	files["geometry/long-keys.u24"] = packUint24([0]);
	files["geometry/long-lengths.u16"] = words([65535], 2);
	files["geometry/long-overflow-keys.u24"] = packUint24([0]);
	files["geometry/long-overflow-units.u32"] = words([100000], 4);
	reader = new PaidRoadGeometry(graph(), files);
	assert.equal(reader.lengthUpperMeters(0), 800000);
});

test("malformed varints, coordinates, offsets, keys and length overflows refuse", () => {
	const mutations: ((files: PaidGeometryFiles) => void)[] = [
		(files) => {
			files["geometry/curve-keys.u24"] = packUint24([1]);
		},
		(files) => {
			files["geometry/curve-offsets.u32"] = words([0, 0], 4);
		},
		(files) => {
			files["geometry/curve-packets.u8"][0] = 0xff;
			files["geometry/curve-packets.u8"].fill(0xff, 1, 5);
		},
		(files) => {
			files["geometry/curve-packets.u8"] = Uint8Array.from([0x80, 0]);
			files["geometry/curve-offsets.u32"] = words([0, 2], 4);
		},
		(files) => {
			files["geometry/long-lengths.u16"] = words([65535], 2);
		},
		(files) => {
			files["geometry/long-overflow-keys.u24"] = packUint24([0]);
			files["geometry/long-overflow-units.u32"] = words([70000], 4);
		},
	];
	for (const mutate of mutations) {
		const files = geometry();
		mutate(files);
		assert.throws(() => new PaidRoadGeometry(graph(), files));
	}
});

test("packet u32 modular deltas preserve dateline coordinates", () => {
	const files = geometry(0);
	const core = fixture(2, [[0, 1, 100]]);
	core["routing/xy.i32"] = words([1799999999, 0, -1799999999, 0], 4, true);
	// Modular signed delta +1 crosses to the retained longitude +180 degrees.
	files["geometry/curve-packets.u8"] = Uint8Array.from([2, 0, 0, 128, 0, 0]);
	files["geometry/curve-offsets.u32"] = words([0, 6], 4);
	const reader = new PaidRoadGeometry(new PackedCarGraph(core), files);
	const points: PaidShapePoint[] = [];
	reader.visitPoints(0, (point) => points.push(point));
	assert.equal(points[1].xE7, 1800000000);
	assert.equal(points[2].xE7, -1799999999);
});
