import assert from "node:assert/strict";
import test from "node:test";
import {
	type AccessStart,
	arrivalAtAccessPosition,
	computeAccessRoadField,
} from "./coarse_osm_access_road_field_v1.ts";
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
import type { RoadPosition } from "./coarse_osm_paid_positions_v1.ts";
import {
	assertPhaseReleased,
	settledPhaseMemory,
} from "./coarse_osm_phase_lifetime_v1.ts";
import { searchRoadWitness as originalSearch } from "./coarse_osm_road_witness_v1.ts";
import {
	type RoadWitness,
	searchRoadWitness,
	validateRoadWitness,
} from "./coarse_osm_road_witness_v2.ts";

function prepared(
	vertices: number,
	arcs: TestArc[],
	flags?: number[],
	pairs?: number[],
) {
	const graph = new PackedCarGraph(fixture(vertices, arcs, flags, pairs)),
		files = Object.fromEntries(
			PAID_GEOMETRY_FILES.map((n) => [n, new Uint8Array()]),
		) as PaidGeometryFiles;
	files["geometry/curve-offsets.u32"] = words([0], 4);
	return { graph, geometry: new PaidRoadGeometry(graph, files) };
}
const position = (fraction: number, arc = 0): RoadPosition => ({
	canonicalArc: arc,
	segment: 0,
	segmentFraction: fraction,
});
const start = (fraction: number, initialTicks = 0, arc = 0): AccessStart => ({
	position: position(fraction, arc),
	initialTicks,
});
const search = (
	p: ReturnType<typeof prepared>,
	starts: AccessStart[],
	target: RoadPosition,
	horizon = 2000,
) =>
	searchRoadWitness(p.graph, p.geometry, starts, target, {
		maxTicks: horizon,
		maxHeapEntries: 256,
	});

test("same physical road portions are directed, paid once and have exact roots", () => {
	let p = prepared(2, [[0, 1, 1000]]);
	let result = search(p, [start(0.25, 100)], position(0.5));
	assert.equal(result.ticks, 350);
	assert.equal(result.startIndex, 0);
	assert.deepEqual(
		result.steps.map((s) => [s.portion, s.ticks]),
		[["direct", 250]],
	);
	assert.equal(search(p, [start(0.75)], position(0.25)).ticks, null);
	p = prepared(2, [
		[0, 1, 1000, 1],
		[1, 0, 2000, 0],
	]);
	result = search(p, [start(0.75, 30)], position(0.25));
	assert.equal(result.ticks, 1030);
	assert.equal(result.steps[0].arc, 1);
	result = search(p, [start(0.75, 30)], position(0.75));
	assert.equal(result.ticks, 30);
	assert.deepEqual(result.steps, []);
});
test("a legal loop beats a direct alternative without making an upstream prefix free", () => {
	const p = prepared(3, [
			[0, 1, 1000],
			[1, 2, 10],
			[2, 0, 10],
		]),
		result = search(p, [start(0.75, 10), start(0.1, 390)], position(0.1), 500);
	assert.equal(result.ticks, 380);
	assert.equal(result.startIndex, 0);
	assert.deepEqual(
		result.steps.map((s) => [s.arc, s.portion, s.ticks]),
		[
			[0, "source-suffix", 250],
			[1, "full", 10],
			[2, "full", 10],
			[0, "target-prefix", 100],
		],
	);
});
test("target prefixes finish before an unreached whole head, including blocked source departure", () => {
	const p = prepared(
			3,
			[
				[0, 1, 10],
				[0, 2, 1000],
			],
			[1, 4, 4],
		),
		result = search(p, [start(0, 17)], position(0.1, 1), 200);
	assert.equal(result.ticks, 117);
	assert.equal(result.steps[0].portion, "target-prefix");
	assert.equal(result.steps[0].ticks, 100);
});
test("barriers allow arrival and initial departure, while signals and forbidden turns retain their prices", () => {
	let p = prepared(
		3,
		[
			[0, 1, 50],
			[1, 2, 50],
		],
		[4, 1, 4],
	);
	assert.equal(search(p, [start(0)], position(1, 1)).ticks, null);
	assert.equal(
		search(p, [start(0), start(0, 100, 1)], position(1, 1)).ticks,
		150,
	);
	p = prepared(
		3,
		[
			[0, 1, 50],
			[1, 2, 50],
		],
		[4, 6, 4],
	);
	const result = search(p, [start(0, 5)], position(1, 1));
	assert.equal(result.ticks, 145);
	assert.equal(result.steps[1].signalBeforeTicks, 40);
	p = prepared(
		3,
		[
			[0, 1, 50],
			[1, 2, 50],
		],
		[4, 6, 4],
		[0, 1],
	);
	assert.equal(search(p, [start(0)], position(1, 1)).ticks, null);
});
test("physical reversal permissions differ from parallel return roads", () => {
	const p = prepared(
		4,
		[
			[0, 1, 10],
			[1, 2, 100, 3],
			[1, 3, 10],
			[2, 1, 100, 1],
			[2, 1, 200],
		],
		[4, 4, 0, 4],
		[0, 2],
	);
	const result = search(p, [start(0)], position(1, 2));
	assert.equal(result.ticks, 320);
	assert.deepEqual(
		result.steps.map((s) => s.arc),
		[0, 1, 4, 2],
	);
	const invalid = structuredClone(result);
	invalid.steps[2].arc = 3;
	invalid.steps[2].ticks = 100;
	invalid.ticks = 220;
	assert.throws(
		() =>
			validateRoadWitness(
				p.graph,
				p.geometry,
				[start(0)],
				position(1, 2),
				invalid,
			),
		/reversal/,
	);
});
test("a required U-turn is charged and forbidden when its actual endpoint disallows it", () => {
	let p = prepared(
		4,
		[
			[0, 1, 10],
			[1, 2, 10, 3],
			[1, 3, 10],
			[2, 1, 10, 1],
		],
		[4, 4, 4, 4],
		[0, 2],
	);
	let result = search(p, [start(0)], position(1, 2));
	assert.equal(result.ticks, 200);
	assert.deepEqual(
		result.steps.map((s) => s.arc),
		[0, 1, 3, 2],
	);
	assert.equal(result.steps[2].reversalBeforeTicks, 160);
	p = prepared(
		4,
		[
			[0, 1, 10],
			[1, 2, 10, 3],
			[1, 3, 10],
			[2, 1, 10, 1],
		],
		[4, 4, 0, 4],
		[0, 2],
	);
	result = search(p, [start(0)], position(1, 2));
	assert.equal(result.ticks, null);
});
test("actual vertex identity matters even when all geometry coordinates coincide", () => {
	const p = prepared(4, [
		[0, 1, 100],
		[2, 3, 100],
	]);
	assert.equal(search(p, [start(0.5)], position(0.5, 1)).ticks, null);
	const result = search(p, [start(0.5), start(0.25, 200, 1)], position(0.5, 1));
	assert.equal(result.ticks, 225);
	assert.equal(result.startIndex, 1);
});
test("independent parent search matches3000 frozen field arrivals with only explicit endpoint rounding", () => {
	let state = 971231;
	const random = () => {
		state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
		return state / 2 ** 32;
	};
	let checks = 0;
	for (let run = 0; run < 25; run++) {
		const arcs: TestArc[] = [];
		for (let tail = 0; tail < 10; tail++)
			for (let i = 0; i < 2; i++)
				arcs.push([
					tail,
					Math.floor(random() * 10),
					1 + Math.floor(random() * 300),
				]);
		const flags = Array.from({ length: 10 }, () => {
				const n = random();
				return n < 0.1 ? 1 : n < 0.3 ? 6 : 4;
			}),
			pairs: number[] = [];
		arcs.forEach((arc, i) => {
			const next = arcs.findIndex((a) => a[0] === arc[1]);
			if (next >= 0 && random() < 0.2) pairs.push(i, next);
		});
		const p = prepared(10, arcs, flags, pairs),
			starts = Array.from({ length: 4 }, () =>
				start(
					[0, 0.25, 0.5, 0.75, 1][Math.floor(random() * 5)],
					Math.floor(random() * 70),
					Math.floor(random() * arcs.length),
				),
			),
			horizon = 100 + Math.floor(random() * 600);
		const field = computeAccessRoadField(p.graph, p.geometry, starts, {
			maxTicks: horizon,
			maxHeapEntries: 256,
		});
		for (let arc = 0; arc < arcs.length; arc++)
			for (const fraction of [0, 0.1, 0.3, 0.5, 0.75, 1]) {
				const target = position(fraction, arc),
					upper = arrivalAtAccessPosition(p.graph, p.geometry, field, target),
					result = search(p, starts, target, horizon);
				if (upper === null) assert.equal(result.ticks, null);
				else {
					assert.ok(result.ticks !== null);
					assert.ok(result.ticks <= upper && upper <= result.ticks + 7);
				}
				validateRoadWitness(p.graph, p.geometry, starts, target, result);
				checks++;
			}
	}
	assert.equal(checks, 3000);
});
test("replay rejects aggregate-consistent forged prices, turn charges and portion kinds", () => {
	const p = prepared(
			3,
			[
				[0, 1, 50],
				[1, 2, 50],
			],
			[4, 6, 4],
		),
		starts = [start(0, 5)],
		target = position(1, 1),
		result = search(p, starts, target);
	let wrong = structuredClone(result);
	wrong.steps[1].ticks++;
	wrong.ticks = (wrong.ticks ?? 0) + 1;
	assert.throws(
		() => validateRoadWitness(p.graph, p.geometry, starts, target, wrong),
		/unpaid road/,
	);
	wrong = structuredClone(result);
	wrong.steps[1].signalBeforeTicks = 0;
	wrong.ticks = (wrong.ticks ?? 0) - 40;
	assert.throws(
		() => validateRoadWitness(p.graph, p.geometry, starts, target, wrong),
		/unpaid turn/,
	);
	wrong = structuredClone(result);
	wrong.steps[0].portion = "unknown" as RoadWitness["steps"][number]["portion"];
	assert.throws(
		() => validateRoadWitness(p.graph, p.geometry, starts, target, wrong),
		/portion domain/,
	);
});
test("uint32 full costs, source/horizon/resource limits and unreachable records stay explicit", () => {
	const p = prepared(2, [[0, 1, 0xffffffff]]),
		result = search(p, [start(0, 10)], position(1e-8), 500);
	assert.equal(result.ticks, 53);
	assert.throws(() => search(p, [], position(0.5)), /source count/);
	assert.throws(() => search(p, [start(0, -1)], position(0.5)), /initial cost/);
	assert.throws(() => search(p, [start(0)], position(0.5), 432001), /horizon/);
	assert.throws(
		() =>
			searchRoadWitness(
				{ ...p.graph, arcs: 13000000 } as PackedCarGraph,
				p.geometry,
				[start(0)],
				position(0.5),
			),
		/offline backing/,
	);
	assert.equal(search(p, [start(0, 10)], position(0.5), 500).ticks, null);
	assert.equal(search(p, [start(0)], position(0), 0).ticks, 0);
});

// Exercise enough repeated calls to cross normal optimization thresholds.
test("V2 preserves V1 paths and releases country-sized buffers after repeated calls", async () => {
	const p = prepared(2, [
		[0, 1, 1000, 1],
		[1, 0, 1000, 0],
	]);
	const graph = p.graph;
	Object.defineProperty(graph, "arcs", { value: 9620680 });
	const inputs = [start(0.25, 30)],
		target = position(0.75);
	const before = await settledPhaseMemory();
	function one() {
		const result = searchRoadWitness(graph, p.geometry, inputs, target);
		assert.equal(result.ticks, 530);
		return result.stats;
	}
	for (let i = 0; i < 32; i++) {
		assert.equal(one().offlineSearchBackingBytes, 84965440);
		await assertPhaseReleased(
			before.arrayBuffers,
			"V2 repeated country-buffer release",
		);
	}
	Object.defineProperty(graph, "arcs", { value: 2 });
	for (let i = 0; i < 100; i++) {
		const starts = [start(i / 100, 17), start((99 - i) / 100, 43)];
		assert.deepEqual(
			searchRoadWitness(p.graph, p.geometry, starts, target),
			originalSearch(p.graph, p.geometry, starts, target),
		);
	}
});
