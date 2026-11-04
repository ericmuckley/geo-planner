import assert from "node:assert/strict";
import test from "node:test";
import { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import { fixture, type TestArc } from "./coarse_osm_packed_fixture_v1.ts";
import { searchPackedCar } from "./coarse_osm_packed_search_v1.ts";

const query = (
	graph: PackedCarGraph,
	a: number,
	b: number,
	maxTicks = 345600,
) =>
	searchPackedCar(
		graph,
		{ vertex: a },
		{ vertex: b },
		{ maxTicks, maxHeapEntries: 1000 },
	).ticks;

test("signals charge on departure; blocked nodes allow endpoint travel", () => {
	const arcs: TestArc[] = [
		[0, 1, 10],
		[1, 2, 20],
	];
	assert.equal(
		query(new PackedCarGraph(fixture(3, arcs, [2, 2, 2])), 0, 2),
		70,
	);
	const blocked = new PackedCarGraph(fixture(3, arcs, [1, 1, 0]));
	assert.equal(query(blocked, 0, 1), 10);
	assert.equal(query(blocked, 0, 2), null);
	assert.equal(query(blocked, 1, 2), 20);
	assert.equal(query(blocked, 1, 1), 0);
});

test("one-way travel, forbidden turns and horizon inclusivity", () => {
	const arcs: TestArc[] = [
		[0, 1, 10],
		[1, 2, 20],
	];
	const graph = new PackedCarGraph(fixture(3, arcs));
	assert.equal(query(graph, 0, 2, 30), 30);
	assert.equal(query(graph, 0, 2, 29), null);
	assert.equal(query(graph, 2, 0), null);
	assert.equal(
		query(new PackedCarGraph(fixture(3, arcs, undefined, [0, 1])), 0, 2),
		null,
	);
});

test("incoming arc state preserves alternate legal approaches", () => {
	const arcs: TestArc[] = [
		[0, 1, 1],
		[0, 2, 3],
		[1, 3, 1],
		[2, 3, 3],
		[3, 4, 1],
	];
	assert.equal(
		query(new PackedCarGraph(fixture(5, arcs, undefined, [2, 4])), 0, 4),
		7,
	);
});

test("physical U-turn permission and delay, separate parallel roads", () => {
	const arcs: TestArc[] = [
		[0, 1, 10, 1],
		[1, 0, 20, 0],
	];
	const source = { partials: [{ arc: 0, ticks: 3 }] };
	const target = { partials: [{ arc: 1, ticks: 5 }] };
	const run = (flags: number[]) =>
		searchPackedCar(
			new PackedCarGraph(fixture(2, arcs, flags)),
			source,
			target,
			{ maxHeapEntries: 10 },
		).ticks;
	assert.equal(run([4, 0]), null);
	assert.equal(run([4, 4]), 168);
	assert.equal(run([4, 6]), 208);
	const parallel = new PackedCarGraph(
		fixture(
			2,
			[
				[0, 1, 10],
				[1, 0, 20],
			],
			[0, 0],
		),
	);
	assert.equal(
		searchPackedCar(parallel, source, target, { maxHeapEntries: 10 }).ticks,
		8,
	);
});

test("paid partial targets observe turn/signal rules and source travel is paid", () => {
	const arcs: TestArc[] = [
		[0, 1, 100],
		[1, 2, 100],
	];
	const graph = new PackedCarGraph(fixture(3, arcs, [0, 2, 0]));
	const source = { partials: [{ arc: 0, ticks: 20 }] };
	const target = { partials: [{ arc: 1, ticks: 30 }] };
	assert.equal(
		searchPackedCar(graph, source, target, { maxHeapEntries: 10 }).ticks,
		90,
	);
	assert.equal(
		searchPackedCar(graph, { vertex: 1 }, target, { maxHeapEntries: 10 }).ticks,
		30,
	);
	assert.equal(
		searchPackedCar(graph, source, { vertex: 1 }, { maxHeapEntries: 10 }).ticks,
		20,
	);
	assert.equal(
		searchPackedCar(
			new PackedCarGraph(fixture(3, arcs, undefined, [0, 1])),
			source,
			target,
			{ maxHeapEntries: 10 },
		).ticks,
		null,
	);
});

test("bounded search reports buffers and fails explicitly on limits", () => {
	const graph = new PackedCarGraph(
		fixture(3, [
			[0, 1, 1],
			[0, 2, 2],
		]),
	);
	const a = { vertex: 0 },
		b = { vertex: 2 };
	assert.throws(
		() => searchPackedCar(graph, a, b, { maxHeapEntries: 1 }),
		/heap limit/,
	);
	assert.throws(
		() => searchPackedCar(graph, a, b, { maxSettles: 0 }),
		/settle limit/,
	);
	assert.throws(
		() => searchPackedCar(graph, a, b, { maxTicks: 345601 }),
		/horizon/,
	);
	assert.throws(
		() => searchPackedCar(graph, { partials: [{ arc: 0, ticks: 2 }] }, b),
		/partial cost/,
	);
	assert.throws(
		() =>
			searchPackedCar(graph, a, b, {
				check: () => {
					throw Error("cancel");
				},
			}),
		/cancel/,
	);
	const result = searchPackedCar(graph, a, b, { maxHeapEntries: 10 });
	assert.equal(result.searchBufferBytes, 2 * 4 + 10 * 8);
});

test("seeded directed graphs match an independent simple state-search oracle", () => {
	let state = 3026;
	function random(n: number): number {
		state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
		return state % n;
	}
	for (let run = 0; run < 40; run++) {
		const arcs: TestArc[] = [];
		const flags = Array.from({ length: 8 }, () => random(8));
		for (let a = 0; a < 8; a++)
			for (let b = 0; b < 8; b++)
				if (random(4) === 0) arcs.push([a, b, 1 + random(40)]);
		const pairs: number[] = [];
		for (let a = 0; a < arcs.length; a++)
			for (let b = 0; b < arcs.length; b++)
				if (arcs[a][1] === arcs[b][0] && random(4) === 0) pairs.push(a, b);
		const graph = new PackedCarGraph(fixture(8, arcs, flags, pairs));
		for (let source = 0; source < 8; source++)
			for (let target = 0; target < 8; target++) {
				const labels = arcs.map(([tail, , cost]) =>
					tail === source ? cost : Infinity,
				);
				const done = new Set<number>();
				let best = source === target ? 0 : Infinity;
				while (done.size < arcs.length) {
					let current = -1;
					for (let a = 0; a < arcs.length; a++)
						if (
							!done.has(a) &&
							Number.isFinite(labels[a]) &&
							(current < 0 || labels[a] < labels[current])
						)
							current = a;
					if (current < 0) break;
					done.add(current);
					const head = arcs[current][1];
					if (head === target) best = Math.min(best, labels[current]);
					if (flags[head] & 1) continue;
					for (let next = 0; next < arcs.length; next++) {
						if (arcs[next][0] !== head) continue;
						let banned = false;
						for (let i = 0; i < pairs.length; i += 2)
							if (pairs[i] === current && pairs[i + 1] === next) banned = true;
						if (!banned)
							labels[next] = Math.min(
								labels[next],
								labels[current] + (flags[head] & 2 ? 40 : 0) + arcs[next][2],
							);
					}
				}
				assert.equal(
					query(graph, source, target),
					Number.isFinite(best) ? best : null,
				);
			}
	}
});
