/** Synchronous offline obstruction probe; cleared barriers never grant permission. */
import assert from "node:assert/strict";
import type { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";

export function withUnblockedNodeTraversal<T>(
	graph: PackedCarGraph,
	use: () => T,
): T {
	assert.ok(
		!Object.hasOwn(graph, "nodeFlags"),
		"Nested or preexisting node override",
	);
	const original = graph.nodeFlags;
	Object.defineProperty(graph, "nodeFlags", {
		configurable: true,
		value: (vertex: number) => original.call(graph, vertex) & ~1,
	});
	try {
		return use();
	} finally {
		Reflect.deleteProperty(graph, "nodeFlags");
		assert.equal(graph.nodeFlags, original);
	}
}
