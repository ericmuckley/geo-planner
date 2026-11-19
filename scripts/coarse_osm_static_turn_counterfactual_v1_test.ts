import assert from "node:assert/strict";
import test from "node:test";
import { searchContextRoadWitness } from "./coarse_osm_context_witness_v1.ts";
import { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import { fixture, words } from "./coarse_osm_packed_fixture_v1.ts";
import {
	PAID_GEOMETRY_FILES,
	type PaidGeometryFiles,
	PaidRoadGeometry,
} from "./coarse_osm_paid_geometry_v1.ts";
import {
	mappedStaticTurnKeys,
	withStaticTurnSubset,
} from "./coarse_osm_static_turn_counterfactual_v1.ts";
import { contextFiles } from "./coarse_osm_turn_context_fixture_v1.ts";
import { TurnContexts } from "./coarse_osm_turn_contexts_v1.ts";
import { packUint24, Uint24View } from "./coarse_osm_u24_v1.ts";

const graph = () =>
	new PackedCarGraph(
		fixture(
			4,
			[
				[0, 1, 10],
				[1, 2, 10],
				[1, 3, 10],
			],
			undefined,
			[0, 1, 0, 2],
		),
	);

test("source bans remap through the complete permutation and remain in the static union", () => {
	const g = graph();
	const retained = mappedStaticTurnKeys(
		g,
		new Uint24View(packUint24([1, 0])),
		Uint32Array.from([2, 0, 1]),
	);
	assert.deepEqual([...retained], [2]);
	assert.throws(() =>
		mappedStaticTurnKeys(
			g,
			new Uint24View(packUint24([1, 0])),
			Uint32Array.from([2, 0, 0]),
		),
	);
	assert.throws(() =>
		mappedStaticTurnKeys(
			g,
			new Uint24View(packUint24([0, 1])),
			Uint32Array.from([2, 0, 1]),
		),
	);
});

test("only declared static bans are relaxed and source bans and argument checks retain", () => {
	const g = graph(),
		original = g.forbidsTurn;
	withStaticTurnSubset(g, new Set([1]), () => {
		assert.equal(g.forbidsTurn(0, 1), true);
		assert.equal(g.forbidsTurn(0, 2), false);
		assert.equal(g.forbidsTurn(1, 2), false);
		assert.throws(() => g.forbidsTurn(-1, 2));
	});
	assert.equal(g.forbidsTurn, original);
	assert.equal(g.forbidsTurn(0, 2), true);
	assert.throws(() => withStaticTurnSubset(g, new Set([5]), () => 0));
});

test("errors and nested calls restore the exact original method", () => {
	const g = graph(),
		original = g.forbidsTurn;
	assert.throws(() =>
		withStaticTurnSubset(g, new Set(), () => {
			assert.throws(() => withStaticTurnSubset(g, new Set(), () => 0));
			throw new Error("deliberate diagnostic stop");
		}),
	);
	assert.equal(g.forbidsTurn, original);
	assert.equal(Object.hasOwn(g, "forbidsTurn"), false);
	assert.equal(g.forbidsTurn(0, 1), true);
});

test("relaxing a static entry never removes the matching single-via history restriction", () => {
	const edges: [number, number, number][] = [
		[0, 1, 10],
		[1, 2, 10],
		[2, 3, 10],
		[2, 4, 10],
	];
	const g = new PackedCarGraph(fixture(5, edges, undefined, [0, 1]));
	const files = Object.fromEntries(
		PAID_GEOMETRY_FILES.map((name) => [name, new Uint8Array()]),
	) as PaidGeometryFiles;
	files["geometry/curve-offsets.u32"] = words([0], 4);
	const paid = new PaidRoadGeometry(g, files);
	const contexts = new TurnContexts(
		g.arcs,
		contextFiles(
			edges.map(([tail, head], i) => ({
				tail,
				head,
				way: [10, 20, 30, 40][i],
			})),
			[[10, 20, 30]],
		),
	);
	const position = (arc: number, fraction: number) => ({
		canonicalArc: arc,
		segment: 0,
		segmentFraction: fraction,
	});
	const run = (arc: number) =>
		searchContextRoadWitness(
			g,
			paid,
			contexts,
			[{ position: position(0, 0), initialTicks: 0 }],
			position(arc, 1),
			{ maxTicks: 100, maxHeapEntries: 32 },
		);
	assert.equal(run(3).ticks, null);
	withStaticTurnSubset(g, new Set(), () => {
		assert.equal(run(2).ticks, null);
		assert.equal(run(3).ticks, 30);
	});
	assert.equal(run(3).ticks, null);
});
