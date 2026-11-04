import assert from "node:assert/strict";
import test from "node:test";
import {
	PACKED_CAR_FILES,
	type PackedCarFiles,
	PackedCarGraph,
} from "./coarse_osm_packed_car_v1.ts";
import {
	fixture,
	type TestArc,
	words,
} from "./coarse_osm_packed_fixture_v1.ts";
import { packUint24 } from "./coarse_osm_u24_v1.ts";

test("unaligned shared backing buffers retain views and correct accounting", () => {
	const files = fixture(
		2,
		[
			[0, 1, 100, 1],
			[1, 0, 200, 0],
		],
		[6, 4],
		[0, 1],
	);
	const allocation = new Uint8Array(500);
	let cursor = 1;
	for (const name of PACKED_CAR_FILES) {
		const original = files[name];
		allocation.set(original, cursor);
		files[name] = allocation.subarray(cursor, cursor + original.length);
		cursor += original.length;
	}
	const graph = new PackedCarGraph(files);
	assert.equal(graph.retainedBackingBufferBytes, 501);
	assert.deepEqual(graph.coordinate(0), [0, 0]);
	assert.equal(graph.nodeFlags(0), 6);
	assert.equal(graph.arcCostTicks(1), 200);
	assert.equal(graph.reverseArc(0), 1);
	assert.equal(graph.forbidsTurn(0, 1), true);
	assert.equal(graph.forbidsTurn(1, 0), false);
});

test("uint16 cost and uint8 reverse sentinels preserve large exact values", () => {
	const arcs: TestArc[] = Array.from({ length: 256 }, () => [0, 0, 1]);
	arcs[0] = [0, 0, 0xffffffff, 255];
	arcs[255][3] = 0;
	const graph = new PackedCarGraph(fixture(1, arcs));
	assert.equal(graph.arcCostTicks(0), 0xffffffff);
	assert.equal(graph.reverseArc(0), 255);
	assert.equal(graph.reverseArc(255), 0);
	assert.equal(graph.reverseArc(254), null);
});

test("empty CSR rows and parallel physical identities remain distinct", () => {
	const graph = new PackedCarGraph(
		fixture(4, [
			[1, 3, 10, 2],
			[1, 3, 20, 3],
			[3, 1, 30, 0],
			[3, 1, 40, 1],
		]),
	);
	assert.equal(graph.outgoingStart(0), graph.outgoingEnd(0));
	assert.deepEqual(
		[0, 1, 2, 3].map((arc) => graph.arcTail(arc)),
		[1, 1, 3, 3],
	);
	assert.equal(graph.reverseArc(0), 2);
	assert.equal(graph.reverseArc(1), 3);
});

test("reject missing, surplus, unsorted and incorrect overflow entries", () => {
	const original = () =>
		fixture(1, [
			[0, 0, 70000],
			[0, 0, 80000],
		]);
	let files = original();
	files["routing/cost-overflow-arcs.u24"] = packUint24([1, 0]);
	assert.throws(() => new PackedCarGraph(files), /sorted overflow/);
	files = original();
	files["routing/cost-overflow-arcs.u24"] = new Uint8Array();
	files["routing/cost-overflow-ticks.u32"] = new Uint8Array();
	assert.throws(() => new PackedCarGraph(files), /Missing packed overflow/);
	files = fixture(1, [[0, 0, 1]]);
	files["routing/cost-overflow-arcs.u24"] = packUint24([0]);
	files["routing/cost-overflow-ticks.u32"] = words([70000], 4);
	assert.throws(() => new PackedCarGraph(files), /overflow sentinel/);
	files = fixture(1, [[0, 0, 1]]);
	files["routing/reverse.u8"][0] = 254;
	assert.throws(() => new PackedCarGraph(files), /Missing packed overflow/);
});

test("reject asymmetric, out-of-row and wrong-endpoint reverse identities", () => {
	for (const arcs of [
		[
			[0, 1, 1, 1],
			[1, 0, 1],
		],
		[
			[0, 1, 1, 2],
			[1, 0, 1, 0],
		],
		[
			[0, 1, 1, 1],
			[1, 1, 1, 0],
		],
	] as TestArc[][]) {
		assert.throws(() => new PackedCarGraph(fixture(2, arcs)), /reverse/);
	}
});

test("reject malformed roster, CSR, coordinates, flags, costs and turns", () => {
	const original = () =>
		fixture(2, [
			[0, 1, 1],
			[1, 0, 1],
		]);
	const corruptions: [keyof PackedCarFiles, Uint8Array][] = [
		["routing/offsets.u24", packUint24([0, 2, 1])],
		["routing/targets.u24", packUint24([2, 0])],
		["routing/xy.i32", words([0, 900000001, 0, 0], 4, true)],
		["routing/node-flags.u8", Uint8Array.of(8, 0)],
		["routing/costs.u16", words([0, 1], 2)],
		["routing/forbidden-turns.u24", packUint24([0, 0])],
		["routing/forbidden-turns.u24", packUint24([0, 1, 0, 1])],
		["routing/forbidden-turns.u24", packUint24([1, 0, 0, 1])],
	];
	for (const [name, bytes] of corruptions) {
		assert.throws(() => new PackedCarGraph({ ...original(), [name]: bytes }));
	}
	const missing = original();
	Reflect.deleteProperty(missing, "routing/xy.i32");
	assert.throws(() => new PackedCarGraph(missing), /roster/);
	assert.throws(
		() =>
			new PackedCarGraph({
				...original(),
				extra: new Uint8Array(),
			} as PackedCarFiles),
		/roster/,
	);
});

test("public methods reject fractional, negative and outside indices", () => {
	const graph = new PackedCarGraph(fixture(2, [[0, 1, 1]]));
	for (const value of [-1, 0.5, Number.NaN, Infinity, 2]) {
		assert.throws(() => graph.coordinate(value));
		assert.throws(() => graph.outgoingStart(value));
		assert.throws(() => graph.arcTarget(value));
		assert.throws(() => graph.forbidsTurn(0, value));
	}
});
