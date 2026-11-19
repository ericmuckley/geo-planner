import assert from "node:assert/strict";
import test from "node:test";
import {
	type AccessStart,
	arrivalAtAccessPosition,
	computeDiagnosticAccessRoadField,
} from "./coarse_osm_access_road_field_v2.ts";
import { withDiagnosticContextRoadField } from "./coarse_osm_context_road_field_v1.ts";
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
	resolveRoadPosition,
} from "./coarse_osm_paid_positions_v1.ts";
import {
	assertPhaseReleased,
	settledPhaseMemory,
} from "./coarse_osm_phase_lifetime_v1.ts";
import {
	type ContextRule,
	contextFiles,
} from "./coarse_osm_turn_context_fixture_v1.ts";
import { TurnContexts } from "./coarse_osm_turn_contexts_v1.ts";
import { packUint24 } from "./coarse_osm_u24_v1.ts";

function prepared(
	vertices: number,
	edges: TestArc[],
	ways: number[],
	rules: ContextRule[],
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
const start = (
	canonicalArc: number,
	segmentFraction = 0,
	initialTicks = 0,
): AccessStart => ({
	position: pos(canonicalArc, segmentFraction),
	initialTicks,
});

test("history labels remain distinct until search ends; stopping and unrelated exits use valid minima", () => {
	const p = prepared(
		5,
		[
			[0, 1, 10],
			[0, 1, 50],
			[1, 2, 10],
			[2, 3, 10],
			[2, 4, 10],
		],
		[10, 40, 20, 30, 50],
		[[10, 20, 30]],
	);
	const result = withDiagnosticContextRoadField(
		p.graph,
		p.geometry,
		p.contexts,
		[start(0)],
		(field) => ({
			blockedExit: arrivalAtAccessPosition(
				p.graph,
				p.geometry,
				field,
				pos(3, 1),
			),
			otherExit: arrivalAtAccessPosition(p.graph, p.geometry, field, pos(4, 1)),
			via: arrivalAtAccessPosition(p.graph, p.geometry, field, pos(2, 1)),
			labels: Array.from(field.labels),
		}),
		{ maxTicks: 100, maxHeapEntries: 64 },
	);
	assert.equal(result.blockedExit, 70);
	assert.equal(result.otherExit, 30);
	assert.equal(result.via, 20);
	assert.equal(result.labels[2], 20);
	assert.equal(result.labels[3], 70);
});

test("regular entry shadows preserve paid prefixes when source suffix wins the same arc", () => {
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
	const values = withDiagnosticContextRoadField(
		p.graph,
		p.geometry,
		p.contexts,
		starts,
		(field) =>
			[0.1, 0.5, 0.7, 0.75, 0.9].map((fraction) =>
				arrivalAtAccessPosition(p.graph, p.geometry, field, pos(0, fraction)),
			),
		{ maxTicks: 500, maxHeapEntries: 64 },
	);
	assert.deepEqual(values, [370, 350, null, 0, 150]);
	const forbidden = withDiagnosticContextRoadField(
		p.graph,
		p.geometry,
		p.contexts,
		[start(2)],
		(field) => arrivalAtAccessPosition(p.graph, p.geometry, field, pos(1, 0.5)),
		{ maxTicks: 2000, maxHeapEntries: 64 },
	);
	assert.equal(forbidden, null);
});

test("no context rules retain sealed labels, vertex summaries, seeds and statistics", () => {
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
			[10, 10, 20, 20],
			[],
			flags,
			[0, 2],
		);
		const starts = [start(0, 0.25, 20), start(0, 0.75, 200), start(2, 0, 300)];
		const expected = computeDiagnosticAccessRoadField(
			p.graph,
			p.geometry,
			starts,
			{ maxTicks: 1500, maxHeapEntries: 64 },
		);
		const actual = withDiagnosticContextRoadField(
			p.graph,
			p.geometry,
			p.contexts,
			starts,
			(field) => ({
				labels: Uint32Array.from(field.labels),
				vertices: Uint16Array.from(field.vertexArrivalSeconds),
				seeds: Uint8Array.from(new Uint8Array(field.seeds.buffer)),
				stats: { ...field.stats },
			}),
			{ maxTicks: 1500, maxHeapEntries: 64 },
		);
		assert.deepEqual(actual, {
			labels: expected.labels,
			vertices: expected.vertexArrivalSeconds,
			seeds: new Uint8Array(expected.seeds.buffer),
			stats: expected.stats,
		});
	}
});

test("more than5000 paid interior arrivals match exhaustive raw-way-sequence paths", () => {
	let seed = 15112026,
		compared = 0;
	const random = (limit: number) => {
		seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
		return seed % limit;
	};
	for (let generated = 0; generated < 300; generated++) {
		const edges: TestArc[] = [],
			ways: number[] = [];
		for (let a = 0; a < 5; a++)
			for (let b = a + 1; b < 5; b++)
				if (random(100) < 65) {
					edges.push([a, b, 1 + random(9)]);
					ways.push(1 + random(3));
				}
		if (!edges.length) {
			edges.push([0, 1, 1]);
			ways.push(1);
		}
		const rules: ContextRule[] = [];
		for (let i = random(5); i > 0; i--) {
			const a = 1 + random(3),
				b = 1 + random(3),
				c = 1 + random(3);
			if (b !== a && b !== c) rules.push([a, b, c]);
		}
		const flags = Array.from({ length: 5 }, () => random(4)),
			bans: number[] = [];
		edges.forEach((a, i) => {
			edges.forEach((b, j) => {
				if (a[1] === b[0] && random(100) < 15) bans.push(i, j);
			});
		});
		const p = prepared(5, edges, ways, rules, flags, bans);
		const starts = [
			start(random(edges.length), [0, 0.25, 0.75, 1][random(4)], random(20)),
			start(random(edges.length), [0, 0.25, 0.75, 1][random(4)], random(20)),
		];
		const horizon = 40 + random(100);
		withDiagnosticContextRoadField(
			p.graph,
			p.geometry,
			p.contexts,
			starts,
			(field) => {
				for (let targetArc = 0; targetArc < edges.length; targetArc++)
					for (const fraction of [0.25, 0.5, 0.75]) {
						const target = resolveRoadPosition(
							p.graph,
							p.geometry,
							pos(targetArc, fraction),
						);
						assert.ok("partials" in target.target);
						const prefix = target.target.partials[0].ticks;
						let expected: number | null = null;
						const end = (cost: number) => {
							if (cost <= horizon)
								expected = expected === null ? cost : Math.min(expected, cost);
						};
						for (const s of starts) {
							const from = resolveRoadPosition(p.graph, p.geometry, s.position);
							if (
								from.canonicalArc === target.canonicalArc &&
								from.rank <= target.rank
							) {
								const ticks =
									from.rank === target.rank
										? 0
										: Math.max(
												1,
												Math.min(
													edges[targetArc][2],
													Math.ceil(
														(edges[targetArc][2] *
															(target.forwardUnits - from.forwardUnits)) /
															65535,
													),
												),
											);
								end(s.initialTicks + ticks);
							}
							const walk = (
								vertex: number,
								previous: number | null,
								sequence: number[],
								cost: number,
							) => {
								if (cost > horizon || (previous !== null && flags[vertex] & 1))
									return;
								edges.forEach((edge, arc) => {
									if (
										edge[0] !== vertex ||
										(previous !== null && p.graph.forbidsTurn(previous, arc))
									)
										return;
									const next =
										sequence.at(-1) === ways[arc]
											? sequence
											: [...sequence, ways[arc]];
									if (
										next.length >= 3 &&
										rules.some((r) =>
											r.every((w, k) => w === next[next.length - 3 + k]),
										)
									)
										return;
									const arrival =
										cost + (previous !== null && flags[vertex] & 2 ? 40 : 0);
									if (arc === targetArc) end(arrival + prefix);
									walk(edge[1], arc, next, arrival + edge[2]);
								});
							};
							if ("vertex" in from.source)
								walk(from.source.vertex, null, [], s.initialTicks);
							else
								for (const part of from.source.partials)
									walk(
										edges[part.arc][1],
										part.arc,
										[ways[part.arc]],
										s.initialTicks + part.ticks,
									);
						}
						assert.equal(
							arrivalAtAccessPosition(
								p.graph,
								p.geometry,
								field,
								pos(targetArc, fraction),
							),
							expected,
						);
						compared++;
					}
			},
			{ maxTicks: horizon, maxHeapEntries: 64 },
		);
	}
	assert.ok(compared > 5000);
});

function countryAllocation(chain = false) {
	const edges: TestArc[] = chain
		? Array.from({ length: 1100 }, (_, i) => [i, i + 1, 1])
		: [[0, 1, 1000]];
	const p = prepared(
		chain ? 1101 : 2,
		edges,
		edges.map(() => 10),
		[],
	);
	const arcs = 9807359,
		vertices = 5731903,
		states = 300000;
	Object.defineProperty(p.graph, "arcs", { value: arcs });
	Object.defineProperty(p.graph, "vertices", { value: vertices });
	Object.defineProperty(p.graph, "arcTail", {
		value: (arc: number) => {
			assert.ok(arc < edges.length);
			return arc;
		},
	});
	const fields = contextFiles([{ tail: 0, head: 1, way: 10 }], []);
	fields["context/state-offsets.u32"] = words([0, states], 4);
	fields["context/state-arcs.u24"] = packUint24(
		Array.from({ length: states }, (_, i) => i),
	);
	fields["context/exit-offsets.u32"] = words([0, 0], 4);
	fields["context/trigger-incoming.bit"] = new Uint8Array(Math.ceil(arcs / 8));
	return { ...p, contexts: new TurnContexts(arcs, fields) };
}

test("repeated country-sized fields release ordinary, borrowed heap and extra context labels", async () => {
	const p = countryAllocation(),
		baseline = await settledPhaseMemory();
	for (let i = 0; i < 16; i++) {
		const ticks = withDiagnosticContextRoadField(
			p.graph,
			p.geometry,
			p.contexts,
			[start(0, 0.25, 23)],
			(field) =>
				arrivalAtAccessPosition(p.graph, p.geometry, field, pos(0, 0.75)),
		);
		assert.equal(ticks, 523);
		await assertPhaseReleased(
			baseline.arrayBuffers,
			"context field success release",
		);
	}
});

test("country-sized context buffers release on both search and consumer exceptions", async () => {
	const p = countryAllocation(true),
		baseline = await settledPhaseMemory();
	for (let i = 0; i < 8; i++) {
		let checks = 0;
		assert.throws(
			() =>
				withDiagnosticContextRoadField(
					p.graph,
					p.geometry,
					p.contexts,
					[start(0)],
					() => 0,
					{
						maxTicks: 2000,
						check: () => {
							if (++checks === 2) throw new Error("search stop");
						},
					},
				),
			/search stop/,
		);
		await assertPhaseReleased(
			baseline.arrayBuffers,
			"context field interrupted search release",
		);
		assert.throws(
			() =>
				withDiagnosticContextRoadField(
					p.graph,
					p.geometry,
					p.contexts,
					[start(0)],
					() => {
						throw new Error("consumer stop");
					},
					{ maxTicks: 2000 },
				),
			/consumer stop/,
		);
		await assertPhaseReleased(
			baseline.arrayBuffers,
			"context field failed consumer release",
		);
	}
});
