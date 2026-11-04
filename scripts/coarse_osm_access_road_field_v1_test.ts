import assert from "node:assert/strict";
import test from "node:test";
import {
	AccessSeeds,
	type AccessStart,
	accessArcEntryTicks,
	arrivalAtAccessPosition,
	computeAccessRoadField,
	computeDiagnosticAccessRoadField,
	restoreAccessVertices,
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
	arrivalAtRoadPosition,
	computeRoadField,
} from "./coarse_osm_road_field_v1.ts";

function prepared(
	vertices: number,
	arcs: TestArc[],
	flags?: number[],
	pairs?: number[],
) {
	const graph = new PackedCarGraph(fixture(vertices, arcs, flags, pairs)),
		files = Object.fromEntries(
			PAID_GEOMETRY_FILES.map((name) => [name, new Uint8Array()]),
		) as PaidGeometryFiles;
	files["geometry/curve-offsets.u32"] = words([0], 4);
	return { graph, geometry: new PaidRoadGeometry(graph, files) };
}
const pos = (fraction: number, arc = 0): RoadPosition => ({
	canonicalArc: arc,
	segment: 0,
	segmentFraction: fraction,
});
const start = (fraction: number, ticks = 0, arc = 0): AccessStart => ({
	position: pos(fraction, arc),
	initialTicks: ticks,
});
const build = (
	p: ReturnType<typeof prepared>,
	starts: AccessStart[],
	maxTicks = 500,
) =>
	computeAccessRoadField(p.graph, p.geometry, starts, {
		maxTicks,
		maxHeapEntries: 256,
	});
const at = (
	p: ReturnType<typeof prepared>,
	field: ReturnType<typeof build>,
	fraction: number,
	arc = 0,
) => arrivalAtAccessPosition(p.graph, p.geometry, field, pos(fraction, arc));

test("multiple suffix seeds retain regular prefixes and their unpaid gaps", () => {
	const p = prepared(3, [
			[0, 1, 1000],
			[1, 2, 10],
			[2, 0, 10],
		]),
		field = build(p, [start(0.25, 100), start(0.75)]);
	assert.equal(field.labels[0], 250);
	assert.equal(accessArcEntryTicks(p.graph, field, 0), 270);
	assert.equal(at(p, field, 0.1), 370);
	assert.equal(at(p, field, 0.5), 350);
	assert.equal(at(p, field, 0.7), null);
	assert.equal(at(p, field, 0.75), 0);
	assert.equal(at(p, field, 0.9), 150);
	assert.equal(field.seeds.shadowIndex.size, 1);
	assert.equal(field.seeds.buffer.byteLength, 128);
});
test("initial alternatives bridge disconnected inputs only via their separately paid starts", () => {
	const p = prepared(4, [
			[0, 1, 80],
			[2, 3, 100],
		]),
		field = build(p, [start(0), start(0.5, 200, 1)]);
	assert.equal(at(p, field, 1), 80);
	assert.equal(at(p, field, 0.25, 1), null);
	assert.equal(at(p, field, 0.5, 1), 200);
	assert.equal(at(p, field, 1, 1), 250);
	assert.equal(at(p, build(p, [start(0), start(0.5, 501, 1)]), 0.6, 1), null);
});
test("two-way, barrier, turn and source-vertex rules equal the minimum original fields", () => {
	for (const flags of [
		[4, 0, 6],
		[4, 1, 4],
		[4, 4, 4],
	]) {
		const p = prepared(
			3,
			[
				[0, 1, 1000, 1],
				[1, 0, 1500, 0],
				[1, 2, 100],
				[2, 1, 100],
			],
			flags,
			[0, 2],
		);
		const starts = [start(0.25, 20), start(0.75, 200), start(0, 300, 2)],
			field = build(p, starts, 1500);
		const references = starts.map((s) =>
			computeRoadField(p.graph, p.geometry, s.position, s.initialTicks, {
				maxTicks: 1500,
				maxHeapEntries: 256,
			}),
		);
		for (const arc of [0, 2, 3])
			for (const fraction of [0, 0.1, 0.5, 0.9, 1]) {
				const values = references
					.map((f) =>
						arrivalAtRoadPosition(p.graph, p.geometry, f, pos(fraction, arc)),
					)
					.filter((v) => v !== null);
				assert.equal(
					at(p, field, fraction, arc),
					values.length ? Math.min(...values) : null,
				);
			}
	}
});
test("generated fields equal4800 minima of original source-qualified fields", () => {
	let state = 20261102;
	const random = () => {
		state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
		return state / 2 ** 32;
	};
	let comparisons = 0;
	for (let run = 0; run < 50; run++) {
		const arcs: TestArc[] = [];
		for (let tail = 0; tail < 8; tail++)
			for (let i = 0; i < 2; i++)
				arcs.push([
					tail,
					Math.floor(random() * 8),
					1 + Math.floor(random() * 500),
				]);
		const flags = Array.from({ length: 8 }, () => {
				const n = random();
				return n < 0.1 ? 1 : n < 0.3 ? 6 : 4;
			}),
			pairs: number[] = [];
		arcs.forEach((arc, i) => {
			const next = arcs.findIndex((a) => a[0] === arc[1]);
			if (next >= 0 && random() < 0.2) pairs.push(i, next);
		});
		const p = prepared(8, arcs, flags, pairs),
			horizon = 100 + Math.floor(random() * 800);
		const starts = Array.from({ length: 5 }, () =>
			start(
				[0, 0.25, 0.5, 0.75, 1][Math.floor(random() * 5)],
				Math.floor(random() * 100),
				Math.floor(random() * arcs.length),
			),
		);
		const field = build(p, starts, horizon),
			references = starts.map((s) =>
				computeRoadField(p.graph, p.geometry, s.position, s.initialTicks, {
					maxTicks: horizon,
					maxHeapEntries: 256,
				}),
			);
		for (let arc = 0; arc < arcs.length; arc++)
			for (const fraction of [0, 0.1, 0.3, 0.5, 0.75, 1]) {
				const finite = references
					.map((f) =>
						arrivalAtRoadPosition(p.graph, p.geometry, f, pos(fraction, arc)),
					)
					.filter((v) => v !== null);
				assert.equal(
					at(p, field, fraction, arc),
					finite.length ? Math.min(...finite) : null,
					`run${run}/arc${arc}/${fraction}`,
				);
				comparisons++;
			}
	}
	assert.equal(comparisons, 4800);
});
test("packed sources allocate exactly64 bytes each and restoration preserves all vertex minima", () => {
	const p = prepared(3, [
			[0, 1, 100],
			[1, 2, 100],
		]),
		starts = [start(0, 15), start(0, 30, 1), start(0.7, 2)];
	const seeds = new AccessSeeds(p.graph, p.geometry, starts);
	assert.equal(seeds.buffer.byteLength, 64 * 3);
	const field = build(p, starts),
		before = field.vertexArrivalSeconds.slice();
	field.vertexArrivalSeconds.fill(2000);
	restoreAccessVertices(p.graph, field);
	assert.deepEqual(field.vertexArrivalSeconds, before);
	const many = build(
		p,
		Array.from({ length: 4096 }, () => start(0.5, 1)),
	);
	assert.equal(many.stats.seedBackingBufferBytes, 262144);
	assert.equal(many.stats.starts, 4096);
});
test("source/cost/horizon/scratch caps fail before oversized field allocation", () => {
	const p = prepared(2, [[0, 1, 400000]]);
	assert.throws(() => build(p, []), /source count/);
	assert.throws(() => build(p, Array(4097).fill(start(0))), /source count/);
	assert.throws(() => build(p, [start(0, -1)]), /initial cost/);
	assert.throws(() => build(p, [start(0, 345601)]), /initial cost/);
	assert.throws(() => build(p, [start(0)], 432000), /horizon/);
	assert.equal(
		computeDiagnosticAccessRoadField(p.graph, p.geometry, [start(0)], {
			maxTicks: 432000,
			maxHeapEntries: 256,
		}).labels[0],
		400000,
	);
	assert.throws(
		() =>
			computeAccessRoadField(
				{ ...p.graph, arcs: 16000000 } as PackedCarGraph,
				p.geometry,
				[start(0)],
			),
		/scratch/,
	);
});
test("flat prefixes cannot create upstream access and uint32 full costs never wrap", () => {
	const p = prepared(2, [[0, 1, 1000]]),
		files = Object.fromEntries(
			PAID_GEOMETRY_FILES.map((n) => [n, new Uint8Array()]),
		) as PaidGeometryFiles;
	files["geometry/curve-keys.u24"] = new Uint8Array(3);
	files["geometry/curve-offsets.u32"] = words([0, 6], 4);
	files["geometry/curve-packets.u8"] = new Uint8Array(6);
	const geometry = new PaidRoadGeometry(p.graph, files),
		field = computeAccessRoadField(
			p.graph,
			geometry,
			[start(1, 100), start(0.5)],
			{ maxTicks: 300, maxHeapEntries: 256 },
		);
	assert.equal(
		arrivalAtAccessPosition(p.graph, geometry, field, pos(0.25)),
		null,
	);
	assert.equal(arrivalAtAccessPosition(p.graph, geometry, field, pos(0.75)), 1);
	assert.equal(field.seeds.vertexInitial.size, 0);
	const wide = prepared(2, [[0, 1, 0xffffffff]]),
		overflow = build(wide, [start(0, 10), start(0.75, 500)], 300);
	assert.equal(accessArcEntryTicks(wide.graph, overflow, 0), 10);
	assert.equal(at(wide, overflow, 1e-8), 53);
	assert.equal(at(wide, overflow, 0.5), null);
});
