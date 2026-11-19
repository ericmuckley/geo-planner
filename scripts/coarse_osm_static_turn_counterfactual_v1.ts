/** Offline obstruction diagnosis only: removing a ban never establishes permission. */
import assert from "node:assert/strict";
import type { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import type { Uint24View } from "./coarse_osm_u24_v1.ts";

export function mappedStaticTurnKeys(
	graph: PackedCarGraph,
	pairs: Uint24View,
	permutation: Uint32Array,
): Set<number> {
	assert.equal(permutation.length, graph.arcs);
	assert.equal(pairs.length % 2, 0);
	assert.ok(pairs.length <= 2_000_000);
	const seen = new Uint8Array(Math.ceil(graph.arcs / 8));
	for (const arc of permutation) {
		assert.ok(arc < graph.arcs && !(seen[arc >>> 3] & (1 << (arc & 7))));
		seen[arc >>> 3] |= 1 << (arc & 7);
	}
	const retained = new Set<number>();
	for (let i = 0; i < pairs.length; i += 2) {
		const a = pairs.at(i),
			b = pairs.at(i + 1);
		assert.ok(a < graph.arcs && b < graph.arcs);
		const incoming = permutation[a],
			outgoing = permutation[b];
		assert.ok(
			graph.forbidsTurn(incoming, outgoing),
			"Source ban missing from current static union",
		);
		retained.add(incoming * graph.arcs + outgoing);
	}
	assert.equal(retained.size, pairs.length / 2);
	return retained;
}

export function withStaticTurnSubset<T>(
	graph: PackedCarGraph,
	retained: ReadonlySet<number>,
	use: () => T,
): T {
	assert.ok(
		!Object.hasOwn(graph, "forbidsTurn"),
		"Nested or preexisting static-turn override",
	);
	assert.ok(
		retained.size <= 1_000_000 && graph.arcs ** 2 <= Number.MAX_SAFE_INTEGER,
	);
	const original = graph.forbidsTurn;
	for (const key of retained) {
		assert.ok(Number.isSafeInteger(key) && key >= 0 && key < graph.arcs ** 2);
		assert.ok(
			original.call(graph, Math.floor(key / graph.arcs), key % graph.arcs),
		);
	}
	Object.defineProperty(graph, "forbidsTurn", {
		configurable: true,
		value: (incoming: number, outgoing: number) =>
			original.call(graph, incoming, outgoing) &&
			retained.has(incoming * graph.arcs + outgoing),
	});
	try {
		return use();
	} finally {
		Reflect.deleteProperty(graph, "forbidsTurn");
		assert.equal(graph.forbidsTurn, original);
	}
}
