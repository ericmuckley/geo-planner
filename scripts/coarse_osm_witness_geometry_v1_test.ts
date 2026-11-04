import assert from "node:assert/strict";
import test from "node:test";
import { prepared } from "./coarse_osm_access_fixture_v2.ts";
import type { AccessStart } from "./coarse_osm_access_road_field_v1.ts";
import { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import { fixture, words } from "./coarse_osm_packed_fixture_v1.ts";
import {
	PAID_GEOMETRY_FILES,
	type PaidGeometryFiles,
	PaidRoadGeometry,
} from "./coarse_osm_paid_geometry_v1.ts";
import type { RoadPosition } from "./coarse_osm_paid_positions_v1.ts";
import {
	type RoadWitness,
	searchRoadWitness,
} from "./coarse_osm_road_witness_v1.ts";
import { sphericalDistance } from "./coarse_osm_spherical_v1.ts";
import {
	roadWitnessGeometry,
	witnessPositionCoordinate,
} from "./coarse_osm_witness_geometry_v1.ts";

const pos = (fraction: number, arc = 0, segment = 0): RoadPosition => ({
	canonicalArc: arc,
	segment,
	segmentFraction: fraction,
});
const start = (position: RoadPosition, initialTicks = 0): AccessStart => ({
	position,
	initialTicks,
});

test("direct partial geometry clips both paid endpoints without expanding the full road", () => {
	const p = prepared(
			[
				[-0.004, 0],
				[0.004, 0],
			],
			[[0, 1]],
		),
		starts = [start(pos(0.25), 20)],
		target = pos(0.75);
	const witness = searchRoadWitness(p.graph, p.geometry, starts, target, {
		maxHeapEntries: 256,
	});
	const shape = roadWitnessGeometry(
		p.graph,
		p.geometry,
		starts,
		target,
		witness,
	);
	assert.ok(shape);
	assert.equal(shape.coordinates.length, 2);
	assert.ok(Math.abs(shape.coordinates[0][0] + 0.002) < 1e-12);
	assert.ok(Math.abs(shape.coordinates[1][0] - 0.002) < 1e-12);
	assert.ok(
		Math.abs(
			shape.retainedRoadMeters -
				sphericalDistance(shape.coordinates[0], shape.coordinates[1]),
		) < 1e-9,
	);
	assert.ok(
		shape.conservativeWholeSpanSourceUpperMeters >= shape.retainedRoadMeters,
	);
});
test("reverse curved portions retain the bend and actual physical direction", () => {
	const raw = fixture(2, [
		[0, 1, 1000, 1],
		[1, 0, 1000, 0],
	]);
	raw["routing/xy.i32"] = words([-40000, 0, 40000, 0], 4, true);
	const graph = new PackedCarGraph(raw);
	const files = Object.fromEntries(
		PAID_GEOMETRY_FILES.map((n) => [n, new Uint8Array()]),
	) as PaidGeometryFiles;
	const word = (n: number) => {
		const result = [];
		do {
			const byte = n & 127;
			n = Math.floor(n / 128);
			result.push(byte + (n ? 128 : 0));
		} while (n);
		return result;
	};
	const packet = Uint8Array.from([
		...word(80000),
		...word(40000),
		0,
		128,
		0,
		128,
	]);
	files["geometry/curve-keys.u24"] = new Uint8Array(3);
	files["geometry/curve-offsets.u32"] = words([0, packet.length], 4);
	files["geometry/curve-packets.u8"] = packet;
	const geometry = new PaidRoadGeometry(graph, files),
		starts = [start(pos(0.5, 0, 1), 20)],
		target = pos(0.5),
		witness = searchRoadWitness(graph, geometry, starts, target, {
			maxHeapEntries: 256,
		});
	assert.equal(witness.steps[0].arc, 1);
	const shape = roadWitnessGeometry(graph, geometry, starts, target, witness);
	assert.ok(shape);
	assert.equal(shape.coordinates.length, 3);
	const last = shape.coordinates.at(-1);
	assert.ok(last);
	assert.ok(shape.coordinates[0][0] > 0 && last[0] < 0);
	assert.deepEqual(shape.coordinates[1], [0, 0.002]);
	assert.deepEqual(
		shape.coordinates[0],
		witnessPositionCoordinate(geometry, starts[0].position),
	);
	assert.deepEqual(
		shape.coordinates.at(-1),
		witnessPositionCoordinate(geometry, target),
	);
});
test("suffix and prefix geometry meet at the real shared vertex", () => {
	const p = prepared(
		[
			[0, 0],
			[0.004, 0],
			[0.004, 0.004],
		],
		[
			[0, 1],
			[1, 2],
		],
	);
	const first = Array.from({ length: p.graph.arcs }, (_, i) => i).find(
		(i) => p.graph.coordinate(p.graph.arcTail(i))[0] === 0,
	);
	assert.ok(first !== undefined);
	const second = 1 - first;
	const starts = [start(pos(0.5, first))],
		target = pos(0.5, second),
		witness = searchRoadWitness(p.graph, p.geometry, starts, target, {
			maxHeapEntries: 256,
		});
	const shape = roadWitnessGeometry(
		p.graph,
		p.geometry,
		starts,
		target,
		witness,
	);
	assert.ok(shape);
	assert.equal(shape.coordinates.length, 3);
	assert.deepEqual(shape.coordinates[1], [0.004, 0]);
	assert.deepEqual(
		shape.steps.map((s) => s.portion),
		["source-suffix", "target-prefix"],
	);
});
test("coincident coordinates cannot create a missing junction; zero-road paths stay explicit", () => {
	const p = prepared(
		[
			[-0.004, 0],
			[0, 0],
			[0, 0],
			[0.004, 0],
		],
		[
			[0, 1],
			[2, 3],
		],
	);
	const first = Array.from({ length: p.graph.arcs }, (_, i) => i).find(
		(i) => p.graph.coordinate(p.graph.arcTail(i))[0] < 0,
	);
	assert.ok(first !== undefined);
	const second = 1 - first;
	const starts = [start(pos(0, first))],
		target = pos(1, second),
		forged: RoadWitness = {
			ticks: 2000,
			startIndex: 0,
			steps: [first, second].map((arc) => ({
				arc,
				portion: "full",
				ticks: 1000,
				signalBeforeTicks: 0,
				reversalBeforeTicks: 0,
			})),
			stats: {
				settles: 0,
				maximumHeapEntries: 0,
				offlineSearchBackingBytes: 0,
			},
		};
	assert.throws(
		() => roadWitnessGeometry(p.graph, p.geometry, starts, target, forged),
		/transition/,
	);
	const same = searchRoadWitness(
			p.graph,
			p.geometry,
			starts,
			starts[0].position,
			{ maxHeapEntries: 256 },
		),
		zero = roadWitnessGeometry(
			p.graph,
			p.geometry,
			starts,
			starts[0].position,
			same,
		);
	assert.ok(zero);
	assert.equal(zero.retainedRoadMeters, 0);
	assert.equal(zero.coordinates.length, 1);
});
