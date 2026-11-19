/** Synchronous offline use of a complete, source-audited opening set. */
import assert from "node:assert/strict";
import type { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";

export function withSourceNodeOpenings<T>(
	graph: PackedCarGraph,
	openings: ReadonlySet<number>,
	use: () => T,
): T {
	assert.ok(
		!Object.hasOwn(graph, "nodeFlags"),
		"Nested or preexisting node override",
	);
	const original = graph.nodeFlags;
	for (const vertex of openings)
		assert.ok(
			original.call(graph, vertex) & 1,
			"Only existing blockers can open",
		);
	Object.defineProperty(graph, "nodeFlags", {
		configurable: true,
		value: (vertex: number) => {
			const flags = original.call(graph, vertex);
			return openings.has(vertex) ? flags & ~1 : flags;
		},
	});
	try {
		return use();
	} finally {
		Reflect.deleteProperty(graph, "nodeFlags");
		assert.equal(graph.nodeFlags, original);
	}
}
