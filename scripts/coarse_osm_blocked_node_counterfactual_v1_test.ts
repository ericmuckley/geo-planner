import assert from "node:assert/strict";
import test from "node:test";
import { withUnblockedNodeTraversal } from "./coarse_osm_blocked_node_counterfactual_v1.ts";
import { searchContextRoadWitness } from "./coarse_osm_context_witness_v1.ts";
import { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import { fixture, words } from "./coarse_osm_packed_fixture_v1.ts";
import {
	PAID_GEOMETRY_FILES,
	type PaidGeometryFiles,
	PaidRoadGeometry,
} from "./coarse_osm_paid_geometry_v1.ts";
import { contextFiles } from "./coarse_osm_turn_context_fixture_v1.ts";
import { TurnContexts } from "./coarse_osm_turn_contexts_v1.ts";

test("only blocked traversal clears; signal, reversal and index validation retain", () => {
	const g = new PackedCarGraph(
		fixture(
			3,
			[
				[0, 1, 10],
				[1, 2, 10],
			],
			[1, 3, 7],
		),
	);
	withUnblockedNodeTraversal(g, () => {
		assert.deepEqual(
			[0, 1, 2].map((i) => g.nodeFlags(i)),
			[0, 2, 6],
		);
		assert.throws(() => g.nodeFlags(-1));
		assert.throws(() => g.nodeFlags(3));
	});
	assert.deepEqual(
		[0, 1, 2].map((i) => g.nodeFlags(i)),
		[1, 3, 7],
	);
});

test("normal and exceptional callbacks restore the exact original method", () => {
	const g = new PackedCarGraph(fixture(2, [[0, 1, 10]], [0, 1])),
		original = g.nodeFlags;
	assert.equal(
		withUnblockedNodeTraversal(g, () => 7),
		7,
	);
	assert.equal(g.nodeFlags, original);
	assert.throws(() =>
		withUnblockedNodeTraversal(g, () => {
			throw new Error("deliberate stop");
		}),
	);
	assert.equal(g.nodeFlags, original);
	assert.equal(Object.hasOwn(g, "nodeFlags"), false);
});

test("nested diagnostics refuse and leave the outer scope intact", () => {
	const g = new PackedCarGraph(fixture(2, [[0, 1, 10]], [0, 1]));
	withUnblockedNodeTraversal(g, () => {
		assert.throws(() => withUnblockedNodeTraversal(g, () => 0));
		assert.equal(g.nodeFlags(1), 0);
	});
	assert.equal(g.nodeFlags(1), 1);
});

test("a cleared junction still pays signals and preserves static bans and single-via histories", () => {
	const edges: [number, number, number][] = [
		[0, 1, 10],
		[1, 2, 10],
		[2, 3, 10],
		[2, 4, 10],
		[2, 5, 10],
	];
	const g = new PackedCarGraph(fixture(6, edges, [0, 3, 0, 0, 0, 0], [1, 4]));
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
				way: [10, 20, 30, 40, 50][i],
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
	withUnblockedNodeTraversal(g, () => {
		assert.equal(run(2).ticks, null);
		assert.equal(run(4).ticks, null);
		assert.equal(run(3).ticks, 70);
	});
	assert.equal(run(3).ticks, null);
});
