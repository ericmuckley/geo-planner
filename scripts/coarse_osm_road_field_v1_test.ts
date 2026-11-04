import assert from "node:assert/strict";
import test from "node:test";
import { MinQueue } from "./coarse_osm_min_queue_v1.ts";
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
	searchRoadPositions,
} from "./coarse_osm_paid_positions_v1.ts";
import {
	arrivalAtRoadPosition,
	computeRoadField,
	regularArcEntryTicks,
	UNREACHED_SECONDS,
} from "./coarse_osm_road_field_v1.ts";
import { packUint24 } from "./coarse_osm_u24_v1.ts";

function prepared(
	vertices: number,
	arcs: TestArc[],
	flags?: number[],
	turns?: number[],
	flat = false,
	lane: [number, number] = [0, 0],
) {
	const graph = new PackedCarGraph(fixture(vertices, arcs, flags, turns));
	const files = Object.fromEntries(
		PAID_GEOMETRY_FILES.map((name) => [name, new Uint8Array()]),
	) as PaidGeometryFiles;
	files["geometry/curve-offsets.u32"] = words([0], 4);
	if (flat) {
		files["geometry/curve-keys.u24"] = packUint24([0]);
		files["geometry/curve-offsets.u32"] = words([0, 6], 4);
		files["geometry/curve-packets.u8"] = Uint8Array.from([
			0,
			0,
			lane[0] & 255,
			lane[0] >>> 8,
			lane[1] & 255,
			lane[1] >>> 8,
		]);
	}
	return { graph, geometry: new PaidRoadGeometry(graph, files) };
}
const pos = (fraction: number, arc = 0, segment = 0): RoadPosition => ({
	canonicalArc: arc,
	segment,
	segmentFraction: fraction,
});
const build = (
	p: ReturnType<typeof prepared>,
	from = pos(0),
	initial = 0,
	horizon = 480,
) =>
	computeRoadField(p.graph, p.geometry, from, initial, {
		maxTicks: horizon,
		maxHeapEntries: 256,
	});
const at = (
	p: ReturnType<typeof prepared>,
	field: ReturnType<typeof build>,
	target: RoadPosition,
) => arrivalAtRoadPosition(p.graph, p.geometry, field, target);

test("frontier prefixes remain reachable when a whole head is beyond horizon", () => {
	const p = prepared(2, [[0, 1, 1000]]);
	const field = build(p, pos(0), 0, 500);
	assert.equal(field.vertexArrivalSeconds[1], UNREACHED_SECONDS);
	assert.equal(field.stats.settles, 0);
	assert.equal(regularArcEntryTicks(p.graph, field, 0), 0);
	assert.equal(at(p, field, pos(0.25)), 250);
	assert.equal(at(p, field, pos(0.5)), 500);
	assert.equal(at(p, field, pos(0.51)), null);
	assert.equal(at(p, field, pos(1)), null);
});

test("cheap partial seed and later loop prefix preserve their unpaid gap", () => {
	const p = prepared(3, [
		[0, 1, 1000],
		[1, 2, 10],
		[2, 0, 10],
	]);
	const field = build(p, pos(0.75), 0, 500);
	assert.equal(field.labels[0], 250);
	assert.equal(regularArcEntryTicks(p.graph, field, 0), 270);
	assert.equal(at(p, field, pos(0.1)), 370);
	assert.equal(at(p, field, pos(0.5)), null);
	assert.equal(at(p, field, pos(0.75)), 0);
	assert.equal(at(p, field, pos(0.9)), 150);
});

test("paid connector initial cost is separate from a shorter road portion", () => {
	const p = prepared(3, [
		[0, 1, 50],
		[1, 2, 25],
	]);
	const field = build(p, pos(0.5), 100, 200);
	assert.equal(field.partials[0].remainingTicks, 25);
	assert.equal(field.labels[0], 125);
	assert.equal(field.labels[1], 150);
	assert.equal(at(p, field, pos(0.5)), 100);
	assert.equal(at(p, field, pos(0.75)), 113);
	assert.equal(at(p, field, pos(0.25)), null);
	assert.equal(at(p, build(p, pos(0.5), 201, 200), pos(0.5)), null);
});

test("flat quantized prefixes never give a partial seed free upstream access", () => {
	const p = prepared(2, [[0, 1, 1000]], undefined, undefined, true);
	const field = build(p, pos(1), 0, 500);
	assert.equal(regularArcEntryTicks(p.graph, field, 0), null);
	assert.equal(at(p, field, pos(0.5)), null);
	assert.equal(at(p, field, pos(1)), 0);
	assert.equal(at(p, field, pos(0.25, 0, 1)), 250);
	assert.equal(at(p, build(p, pos(0), 0, 500), pos(1)), 1);
});

test("signals, blocked arrival/source departure and forbidden turns remain active", () => {
	const arcs: TestArc[] = [
		[0, 1, 10],
		[1, 2, 100],
	];
	let p = prepared(3, arcs, [4, 6, 4]);
	let field = build(p, pos(0), 0, 60);
	assert.equal(regularArcEntryTicks(p.graph, field, 1), 50);
	assert.equal(at(p, field, pos(0.05, 1)), 55);
	assert.equal(at(p, field, pos(0.2, 1)), null);
	p = prepared(3, arcs, [4, 1, 4]);
	field = build(p);
	assert.notEqual(field.vertexArrivalSeconds[1], UNREACHED_SECONDS);
	assert.equal(at(p, field, pos(0.05, 1)), null);
	assert.equal(at(p, build(p, pos(0, 1)), pos(0.05, 1)), 5);
	p = prepared(3, arcs, undefined, [0, 1]);
	field = build(p);
	assert.equal(at(p, field, pos(0.05, 1)), null);
});

test("exact physical reversal permissions and delay stay distinct from parallel roads", () => {
	let p = prepared(
		2,
		[
			[0, 1, 10, 1],
			[1, 0, 20, 0],
		],
		[4, 0],
	);
	let field = build(p);
	assert.equal(regularArcEntryTicks(p.graph, field, 1), null);
	p = prepared(
		2,
		[
			[0, 1, 10, 1],
			[1, 0, 20, 0],
		],
		[4, 4],
	);
	field = build(p);
	assert.equal(regularArcEntryTicks(p.graph, field, 1), 170);
	assert.equal(field.labels[1], 190);
	p = prepared(
		2,
		[
			[0, 1, 10, 1],
			[1, 0, 20, 0],
		],
		[4, 4],
		[0, 1],
	);
	assert.equal(regularArcEntryTicks(p.graph, build(p), 1), null);
	p = prepared(
		2,
		[
			[0, 1, 10],
			[1, 0, 20],
		],
		[4, 0],
	);
	assert.equal(regularArcEntryTicks(p.graph, build(p), 1), 10);
});

test("both source directions keep independent costs/prefixes even without head reach", () => {
	let p = prepared(
		2,
		[
			[0, 1, 1000, 1],
			[1, 0, 2000, 0],
		],
		[4, 0],
	);
	let field = build(p, pos(0.75), 20, 1000);
	assert.equal(field.partials.length, 2);
	assert.equal(field.vertexArrivalSeconds[0], UNREACHED_SECONDS);
	assert.equal(at(p, field, pos(0.5)), 520);
	assert.equal(at(p, field, pos(0.9)), 170);
	assert.equal(at(p, field, pos(0.1)), null);
	p = prepared(
		2,
		[
			[0, 1, 1000, 1],
			[1, 0, 2000, 0],
		],
		undefined,
		undefined,
		true,
		[32768, 16384],
	);
	field = build(p, pos(1), 20, 1000);
	assert.equal(field.labels[0], 520);
	assert.equal(field.labels[1], 521);
	assert.equal(at(p, field, pos(0.5)), 271);
	assert.equal(at(p, field, pos(0.5, 0, 1)), 270);
});

test("uint32 maximum full cost records entry only, without arithmetic wrap", () => {
	const p = prepared(2, [[0, 1, 0xffffffff]]);
	const field = build(p, pos(0), 10, 500);
	assert.equal(regularArcEntryTicks(p.graph, field, 0), 10);
	assert.equal(field.vertexArrivalSeconds[1], UNREACHED_SECONDS);
	assert.equal(at(p, field, pos(1e-8)), 53);
	assert.equal(at(p, field, pos(0.5)), null);
});

test("generated fields agree with qualified pair search on every sampled position", () => {
	let state = 20261105;
	const random = () => {
		state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
		return state / 2 ** 32;
	};
	let comparisons = 0;
	for (let run = 0; run < 50; run++) {
		const arcs: TestArc[] = [];
		for (let tail = 0; tail < 10; tail++)
			for (let n = 0; n < 2; n++)
				arcs.push([
					tail,
					Math.floor(random() * 10),
					1 + Math.floor(random() * 300),
				]);
		const flags = Array.from({ length: 10 }, () => {
			const x = random();
			return x < 0.1 ? 1 : x < 0.3 ? 6 : 4;
		});
		const pairs: [number, number][] = [];
		arcs.forEach((arc, a) => {
			const b = arcs.findIndex((other) => other[0] === arc[1]);
			if (b >= 0 && random() < 0.15) pairs.push([a, b]);
		});
		const p = prepared(10, arcs, flags, pairs.flat());
		const from = pos(
			run % 3 === 0 ? 0 : 0.3,
			Math.floor(random() * arcs.length),
		);
		const initial = Math.floor(random() * 50);
		const horizon = 80 + Math.floor(random() * 500);
		const field = build(p, from, initial, horizon);
		for (let arc = 0; arc < arcs.length; arc++)
			for (const fraction of [0, 0.5, 1]) {
				const target = pos(fraction, arc);
				const expected = searchRoadPositions(
					p.graph,
					p.geometry,
					from,
					target,
					{ maxTicks: horizon - initial, maxHeapEntries: 256 },
				).ticks;
				const actual = at(p, field, target);
				comparisons++;
				if (expected === null) assert.equal(actual, null);
				else {
					assert.ok(actual !== null);
					assert.ok(
						actual >= initial + expected &&
							actual <= initial + expected + (fraction === 0.5 ? 0 : 7),
						JSON.stringify({ run, arc, fraction, actual, expected, initial }),
					);
				}
			}
	}
	assert.equal(comparisons, 3000);
});

test("heap/settle/source/horizon and scratch budget refuse invalid work", () => {
	const p = prepared(2, [[0, 1, 10]]);
	assert.throws(
		() =>
			computeRoadField(p.graph, p.geometry, pos(0), 0, { maxHeapEntries: 0 }),
		/heap limit/,
	);
	assert.throws(
		() => computeRoadField(p.graph, p.geometry, pos(0), 0, { maxSettles: 0 }),
		/settle limit/,
	);
	for (const value of [-1, NaN, 345601])
		assert.throws(() => build(p, pos(0), value));
	assert.throws(() => build(p, pos(0), 0, -1));
	const oversized = {
		arcs: 12000000,
		vertices: 9000000,
	} as unknown as PackedCarGraph;
	assert.throws(
		() => computeRoadField(oversized, p.geometry, pos(0), 0),
		/scratch backing/,
	);
	const field = build(p);
	assert.equal(field.stats.maximumBackingBufferBytes, 4 + 4 + 2048);
});

test("bounded queue returns ordered costs and refuses overflow/empty pops", () => {
	const q = new MinQueue(4);
	for (const cost of [50, 1, 99, 0]) q.push(cost, cost);
	assert.throws(() => q.push(5, 5));
	assert.deepEqual(
		Array.from({ length: 4 }, () => q.pop()[1]),
		[0, 1, 50, 99],
	);
	assert.throws(() => q.pop());
	assert.throws(() => new MinQueue(-1));
});
