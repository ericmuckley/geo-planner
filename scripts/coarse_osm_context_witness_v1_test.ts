import assert from "node:assert/strict";
import test from "node:test";
import {
	type AccessStart,
	arrivalAtAccessPosition,
} from "./coarse_osm_access_road_field_v1.ts";
import { withDiagnosticContextRoadField } from "./coarse_osm_context_road_field_v1.ts";
import {
	searchContextRoadWitness,
	validateContextRoadWitness,
} from "./coarse_osm_context_witness_v1.ts";
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
import { searchRoadWitness } from "./coarse_osm_road_witness_v2.ts";
import {
	type ContextRule,
	contextFiles,
} from "./coarse_osm_turn_context_fixture_v1.ts";
import {
	type TurnContextFiles,
	TurnContexts,
} from "./coarse_osm_turn_contexts_v1.ts";
import { packUint24 } from "./coarse_osm_u24_v1.ts";

function prepared(
	vertices: number,
	edges: TestArc[],
	ways = edges.map((_, i) => i + 1),
	rules: ContextRule[] = [],
	flags?: number[],
	bans?: number[],
) {
	const graph = new PackedCarGraph(fixture(vertices, edges, flags, bans));
	const files = Object.fromEntries(
		PAID_GEOMETRY_FILES.map((name) => [name, new Uint8Array()]),
	) as PaidGeometryFiles;
	files["geometry/curve-offsets.u32"] = words([0], 4);
	const geometry = new PaidRoadGeometry(graph, files);
	const contexts = new TurnContexts(
		graph.arcs,
		contextFiles(
			edges.map(([tail, head], i) => ({ tail, head, way: ways[i] })),
			rules,
		),
	);
	return { graph, geometry, contexts };
}
const pos = (canonicalArc: number, segmentFraction: number): RoadPosition => ({
	canonicalArc,
	segment: 0,
	segmentFraction,
});
const start = (arc: number, fraction = 0, initialTicks = 0): AccessStart => ({
	position: pos(arc, fraction),
	initialTicks,
});
const search = (
	p: ReturnType<typeof prepared>,
	starts: AccessStart[],
	target: RoadPosition,
	maxTicks = 2000,
) =>
	searchContextRoadWitness(p.graph, p.geometry, p.contexts, starts, target, {
		maxTicks,
		maxHeapEntries: 256,
	});
function rawHistory(
	result: ReturnType<typeof search>,
	ways: number[],
	rules: ContextRule[],
) {
	const sequence: number[] = [];
	for (const step of result.steps)
		if (sequence.at(-1) !== ways[step.arc]) sequence.push(ways[step.arc]);
	for (let i = 2; i < sequence.length; i++)
		assert.ok(
			!rules.some((rule) =>
				rule.every((way, j) => way === sequence[i - 2 + j]),
			),
		);
}

test("witness keeps slower legal history and rejects a physically legal forbidden sequence", () => {
	const edges: TestArc[] = [
			[0, 1, 10],
			[0, 1, 50],
			[1, 2, 10],
			[2, 3, 10],
			[2, 4, 10],
		],
		ways = [10, 40, 20, 30, 50],
		rules: ContextRule[] = [[10, 20, 30]];
	const p = prepared(5, edges, ways, rules),
		starts = [start(0)],
		target = pos(3, 1),
		result = search(p, starts, target);
	assert.equal(result.ticks, 70);
	assert.deepEqual(
		result.steps.map((s) => s.arc),
		[1, 2, 3],
	);
	rawHistory(result, ways, rules);
	const forbidden = searchRoadWitness(p.graph, p.geometry, starts, target, {
		maxTicks: 2000,
		maxHeapEntries: 256,
	});
	assert.equal(forbidden.ticks, 30);
	assert.throws(
		() =>
			validateContextRoadWitness(
				p.graph,
				p.geometry,
				p.contexts,
				starts,
				target,
				forbidden,
			),
		/prohibited via-way/,
	);
	assert.equal(search(p, starts, pos(4, 1)).ticks, 30);
});
test("paid source suffix, regular prefixes, blocked history and direct travel retain their prices", () => {
	const p = prepared(
		3,
		[
			[0, 1, 1000],
			[1, 2, 10],
			[2, 0, 10],
		],
		[10, 20, 30],
		[[30, 10, 20]],
	);
	const starts = [start(0, 0.25, 100), start(0, 0.75)];
	withDiagnosticContextRoadField(
		p.graph,
		p.geometry,
		p.contexts,
		starts,
		(field) => {
			for (const fraction of [0.1, 0.5, 0.7, 0.75, 0.9]) {
				const target = pos(0, fraction),
					expected = arrivalAtAccessPosition(
						p.graph,
						p.geometry,
						field,
						target,
					);
				assert.equal(search(p, starts, target, 500).ticks, expected);
			}
		},
		{ maxTicks: 500, maxHeapEntries: 256 },
	);
	assert.equal(search(p, [start(2)], pos(1, 0.5)).ticks, null);
	assert.equal(search(p, [start(1, 0.5, 17)], pos(1, 0.75)).ticks, 20);
});
test("same-way reversal cannot erase history; overlapping rules activate on legal exits", () => {
	const p = prepared(
		5,
		[
			[0, 1, 10],
			[1, 2, 10, 2],
			[2, 1, 10, 1],
			[2, 3, 10],
			[2, 4, 10],
			[4, 3, 10],
		],
		[10, 20, 20, 30, 40, 30],
		[
			[10, 20, 30],
			[20, 40, 30],
		],
	);
	assert.equal(search(p, [start(0)], pos(3, 1)).ticks, null);
	assert.equal(search(p, [start(0)], pos(4, 1)).ticks, 30);
	assert.equal(search(p, [start(1, 0.5)], pos(3, 1)).ticks, 15);
});
test("junction summaries retain their explicit endpoint rounding outside the witness", () => {
	const p = prepared(3, [
			[0, 2, 43],
			[1, 2, 100],
		]),
		starts = [start(0)],
		target = pos(1, 1);
	const result = search(p, starts, target, 100);
	assert.equal(result.ticks, 43);
	withDiagnosticContextRoadField(
		p.graph,
		p.geometry,
		p.contexts,
		starts,
		(field) => {
			assert.equal(
				arrivalAtAccessPosition(p.graph, p.geometry, field, target),
				48,
			);
		},
		{ maxTicks: 100, maxHeapEntries: 256 },
	);
});
test("thousands of paid witnesses match qualified fields and raw way-sequence restrictions", () => {
	let seed = 7112026,
		checks = 0;
	const random = (n: number) => {
		seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
		return seed % n;
	};
	for (let generated = 0; generated < 300; generated++) {
		const edges: TestArc[] = [],
			ways: number[] = [];
		for (let a = 0; a < 5; a++)
			for (let b = a + 1; b < 5; b++)
				if (random(100) < 70) {
					edges.push([a, b, 1 + random(29)]);
					ways.push(1 + random(4));
				}
		if (!edges.length) {
			edges.push([0, 1, 1]);
			ways.push(1);
		}
		const rules: ContextRule[] = [];
		for (let n = random(5); n > 0; n--) {
			const a = 1 + random(4),
				b = 1 + random(4),
				c = 1 + random(4);
			if (a !== b && b !== c) rules.push([a, b, c]);
		}
		const flags = Array.from({ length: 5 }, () => random(4)),
			bans: number[] = [];
		edges.forEach((a, i) => {
			edges.forEach((b, j) => {
				if (a[1] === b[0] && random(100) < 10) bans.push(i, j);
			});
		});
		const p = prepared(5, edges, ways, rules, flags, bans),
			starts = [
				start(random(edges.length), [0, 0.25, 0.75, 1][random(4)], random(30)),
				start(random(edges.length), [0, 0.5, 1][random(3)], random(30)),
			],
			horizon = 30 + random(160);
		withDiagnosticContextRoadField(
			p.graph,
			p.geometry,
			p.contexts,
			starts,
			(field) => {
				for (let arc = 0; arc < edges.length; arc++)
					for (const fraction of [0, 0.1, 0.5, 0.75, 1]) {
						const target = pos(arc, fraction),
							expected = arrivalAtAccessPosition(
								p.graph,
								p.geometry,
								field,
								target,
							),
							result = search(p, starts, target, horizon);
						if (expected === null) assert.equal(result.ticks, null);
						else {
							assert.ok(
								result.ticks !== null &&
									result.ticks <= expected &&
									expected - result.ticks <= 7,
							);
						}
						rawHistory(result, ways, rules);
						checks++;
					}
			},
			{ maxTicks: horizon, maxHeapEntries: 256 },
		);
	}
	assert.ok(checks > 5000);
});
test("empty histories retain sealed physical witnesses; static bans and forged charges remain checked", () => {
	const p = prepared(
			3,
			[
				[0, 1, 1000],
				[1, 2, 50],
			],
			[10, 20],
			[],
			[4, 6, 4],
		),
		starts = [start(0, 0.25, 17)],
		target = pos(1, 0.75);
	assert.deepEqual(
		search(p, starts, target),
		searchRoadWitness(p.graph, p.geometry, starts, target, {
			maxTicks: 2000,
			maxHeapEntries: 256,
		}),
	);
	const wrong = structuredClone(search(p, starts, target));
	const last = wrong.steps.at(-1);
	assert.ok(last);
	last.ticks++;
	wrong.ticks = (wrong.ticks ?? 0) + 1;
	assert.throws(
		() =>
			validateContextRoadWitness(
				p.graph,
				p.geometry,
				p.contexts,
				starts,
				target,
				wrong,
			),
		/unpaid road/,
	);
	const blocked = prepared(
		3,
		[
			[0, 1, 10],
			[1, 2, 10],
		],
		[10, 20],
		[],
		undefined,
		[0, 1],
	);
	assert.equal(search(blocked, [start(0)], pos(1, 1)).ticks, null);
});
test("history state identity and offline allocation limits refuse before search", () => {
	const p = prepared(2, [[0, 1, 10]]);
	assert.throws(
		() =>
			searchContextRoadWitness(
				{ ...p.graph, arcs: 2 } as PackedCarGraph,
				p.geometry,
				p.contexts,
				[start(0)],
				pos(0, 1),
			),
		/graph identity/,
	);
	assert.throws(
		() =>
			searchContextRoadWitness(
				{ ...p.graph, arcs: 13000000 } as PackedCarGraph,
				p.geometry,
				{ arcs: 13000000, states: 0 } as TurnContexts,
				[start(0)],
				pos(0, 1),
			),
		/offline backing/,
	);
});
test("country-sized history parent buffers release repeatedly after return and exceptions", async () => {
	const edges: TestArc[] = Array.from({ length: 2050 }, (_, i) => [
		i,
		i + 1,
		1,
	]);
	const p = prepared(2051, edges);
	Object.defineProperty(p.graph, "arcs", { value: 9822101 });
	const count = 300000;
	const files: TurnContextFiles = {
		"context/state-offsets.u32": words([0, count], 4),
		"context/state-arcs.u24": packUint24(
			Array.from({ length: count }, (_, i) => i),
		),
		"context/exit-offsets.u32": words([0, 0], 4),
		"context/exit-arcs.u24": new Uint8Array(),
		"context/triggers.u24": new Uint8Array(),
		"context/trigger-incoming.bit": new Uint8Array(Math.ceil(p.graph.arcs / 8)),
	};
	const contexts = new TurnContexts(p.graph.arcs, files),
		before = await settledPhaseMemory();
	for (let run = 0; run < 16; run++) {
		const result = searchContextRoadWitness(
			p.graph,
			p.geometry,
			contexts,
			[start(0, 0.25, 30)],
			pos(0, 0.75),
		);
		assert.equal(result.ticks, 31);
		assert.equal(result.stats.offlineSearchBackingBytes, 88976808);
		await assertPhaseReleased(
			before.arrayBuffers,
			"context witness successful release",
		);
	}
	for (let run = 0; run < 8; run++) {
		assert.throws(
			() =>
				searchContextRoadWitness(
					p.graph,
					p.geometry,
					contexts,
					[start(0)],
					pos(2049, 1),
					{
						check: () => {
							throw new Error("cancel");
						},
					},
				),
			/cancel/,
		);
		await assertPhaseReleased(
			before.arrayBuffers,
			"context witness exceptional release",
		);
	}
});
