import assert from "node:assert/strict";
import test from "node:test";
import {
	type ContextArc,
	type ContextRule,
	contextFiles,
} from "./coarse_osm_turn_context_fixture_v1.ts";
import {
	type TurnContextFiles,
	TurnContexts,
} from "./coarse_osm_turn_contexts_v1.ts";
import { packUint24 } from "./coarse_osm_u24_v1.ts";

const arcs: ContextArc[] = [
	{ tail: 0, head: 1, way: 10 },
	{ tail: 1, head: 2, way: 20 },
	{ tail: 2, head: 3, way: 20 },
	{ tail: 3, head: 4, way: 30 },
	{ tail: 2, head: 5, way: 40 },
	{ tail: 6, head: 1, way: 50 },
];
const rules: ContextRule[] = [
	[10, 20, 30],
	[50, 20, 30],
];

test("from history persists on via, permits unrelated exits and keeps arrivals distinct", () => {
	const contexts = new TurnContexts(arcs.length, contextFiles(arcs, rules));
	assert.equal(contexts.groups, 2);
	assert.equal(contexts.states, 4);
	const first = contexts.nextState(0, 1);
	assert.equal(first, 6);
	assert.equal(contexts.physicalArc(first), 1);
	const second = contexts.nextState(first, 2);
	assert.equal(second, 7);
	assert.equal(contexts.nextState(second, 3), null);
	assert.equal(contexts.nextState(first, 4), 4);
	assert.equal(contexts.nextState(1, 2), 2);
	assert.equal(contexts.nextState(2, 3), 3);
	assert.equal(contexts.nextState(5, 1), 8);
});

test("empty prefixes before, between and after states keep correct group identity", () => {
	const files = contextFiles(arcs, rules);
	files["context/state-offsets.u32"] = new Uint8Array(
		Uint32Array.from([0, 0, 2, 2, 4, 4]).buffer,
	);
	files["context/exit-offsets.u32"] = new Uint8Array(
		Uint32Array.from([0, 0, 1, 1, 2, 2]).buffer,
	);
	const contexts = new TurnContexts(arcs.length, files);
	assert.equal(contexts.nextState(6, 2), 7);
	assert.equal(contexts.nextState(7, 3), null);
	assert.equal(contexts.nextState(8, 2), 9);
	assert.equal(contexts.nextState(9, 3), null);
	const empty = new TurnContexts(6, contextFiles(arcs, []));
	assert.equal(empty.states, 0);
	assert.equal(empty.nextState(1, 2), 2);
});

test("reader rejects malformed dimensions, histories, overlap, bits and foreign buffers", () => {
	const mutations: Partial<TurnContextFiles>[] = [
		{ "context/state-offsets.u32": new Uint8Array(0) },
		{ "context/state-arcs.u24": packUint24([1, 1, 1, 2]) },
		{ "context/exit-arcs.u24": packUint24([1, 3]) },
		{ "context/triggers.u24": packUint24([0, 1, 99, 5, 1, 2]) },
		{ "context/triggers.u24": packUint24([0, 0, 0, 5, 1, 2]) },
		{ "context/trigger-incoming.bit": new Uint8Array(1) },
		{ "context/state-offsets.u32": new Uint8Array(16).subarray(4) },
	];
	for (const mutation of mutations)
		assert.throws(
			() => new TurnContexts(6, { ...contextFiles(arcs, rules), ...mutation }),
			RangeError,
		);
	const contexts = new TurnContexts(6, contextFiles(arcs, rules));
	for (const value of [-1, 0.5, NaN, 10])
		assert.throws(() => contexts.physicalArc(value), RangeError);
	assert.throws(() => contexts.nextState(0, 6), RangeError);
	assert.throws(
		() => new TurnContexts(0, contextFiles(arcs, rules)),
		RangeError,
	);
});

test("5000 state-search queries match independent exhaustive way-sequence walks", () => {
	let seed = 20261105;
	const random = (limit: number) => {
		seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
		return seed % limit;
	};
	let compared = 0;
	for (let generated = 0; generated < 200; generated++) {
		const edges: (ContextArc & { ticks: number })[] = [];
		for (let tail = 0; tail < 5; tail++)
			for (let head = tail + 1; head < 5; head++)
				if (random(100) < 65)
					edges.push({ tail, head, way: 1 + random(3), ticks: 1 + random(9) });
		if (!edges.length) edges.push({ tail: 0, head: 1, way: 1, ticks: 1 });
		const restrictions: ContextRule[] = [];
		for (let n = random(5); n > 0; n--) {
			const a = 1 + random(3),
				b = 1 + random(3),
				c = 1 + random(3);
			if (b !== a && b !== c) restrictions.push([a, b, c]);
		}
		const forbidden = new Set<string>();
		edges.forEach((a, i) => {
			edges.forEach((b, j) => {
				if (a.head === b.tail && random(100) < 15) forbidden.add(`${i}/${j}`);
			});
		});
		const contexts = new TurnContexts(
			edges.length,
			contextFiles(edges, restrictions),
		);
		for (let source = 0; source < 5; source++)
			for (let target = 0; target < 5; target++) {
				let expected: number | null = null;
				const walk = (
					vertex: number,
					before: number | null,
					ways: number[],
					cost: number,
				) => {
					if (vertex === target) {
						expected = expected === null ? cost : Math.min(expected, cost);
						return;
					}
					edges.forEach((edge, arc) => {
						if (
							edge.tail !== vertex ||
							(before !== null && forbidden.has(`${before}/${arc}`))
						)
							return;
						const sequence =
							ways.at(-1) === edge.way ? ways : [...ways, edge.way];
						if (
							sequence.length >= 3 &&
							restrictions.some((r) =>
								r.every((w, k) => w === sequence[sequence.length - 3 + k]),
							)
						)
							return;
						walk(edge.head, arc, sequence, cost + edge.ticks);
					});
				};
				walk(source, null, [], 0);
				let actual: number | null = source === target ? 0 : null;
				const pending: [number, number][] = [],
					distances = new Map<number, number>();
				const offer = (state: number, cost: number) => {
					if (cost < (distances.get(state) ?? Infinity)) {
						distances.set(state, cost);
						pending.push([state, cost]);
					}
				};
				edges.forEach((a, i) => {
					if (a.tail === source) offer(i, a.ticks);
				});
				while (pending.length) {
					pending.sort((a, b) => b[1] - a[1]);
					const [state, cost] = pending.pop() as [number, number];
					if (distances.get(state) !== cost) continue;
					const before = contexts.physicalArc(state),
						vertex = edges[before].head;
					if (vertex === target) {
						actual = actual === null ? cost : Math.min(actual, cost);
						continue;
					}
					edges.forEach((edge, arc) => {
						if (edge.tail !== vertex || forbidden.has(`${before}/${arc}`))
							return;
						const next = contexts.nextState(state, arc);
						if (next !== null) offer(next, cost + edge.ticks);
					});
				}
				assert.equal(actual, expected);
				compared++;
			}
	}
	assert.equal(compared, 5000);
});
