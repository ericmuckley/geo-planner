import assert from "node:assert/strict";
import test from "node:test";
import { geography } from "./coarse_osm_access_fixture_v2.ts";
import { contextDisplayFixture } from "./coarse_osm_context_display_fixture_v1.ts";
import { settledPhaseMemory } from "./coarse_osm_phase_lifetime_v1.ts";
import { reusedContextDisplay as original } from "./coarse_osm_reused_display_v1.ts";
import { reusedContextDisplay as guarded } from "./coarse_osm_reused_display_v2.ts";
import { legacyRoutingGeography } from "./coarse_osm_routing_geography_v1.ts";

for (const [name, display] of [
	["original", original],
	["guarded", guarded],
] as const) {
	test(`${name}: queue receiver retention while the actual capacity exception stays alive`, async () => {
		const p = contextDisplayFixture(
			Array.from({ length: 5001 }, (_, i) => [-0.05 + (i * 0.1) / 5000, 0]),
			Array.from({ length: 5000 }, (_, i) => [i, i + 1, 1]),
		);
		const geo = legacyRoutingGeography(geography());
		const buffers: WeakRef<ArrayBufferLike>[] = [];
		let heldError: unknown;
		try {
			display(
				p.graph,
				p.geometry,
				p.contexts,
				geo,
				p.source,
				[{ position: p.source.snap, initialTicks: 0 }],
				{
					maxTicks: 48000,
					maxCells: 10000,
					heapEntries: 16,
					observeBacking: (bs) =>
						buffers.push(...bs.map((b) => new WeakRef(b))),
				},
				true,
			);
		} catch (error) {
			heldError = error;
		}
		assert.ok(heldError instanceof Error);
		assert.equal(heldError.message, "local heap capacity");
		assert.equal(buffers.length, 8);
		await settledPhaseMemory();
		await settledPhaseMemory();
		const remaining = buffers
			.map((b, i) => ({ i, bytes: b.deref()?.byteLength ?? 0 }))
			.filter((x) => x.bytes > 0);
		process.stdout.write(
			`${JSON.stringify({ name, remaining, message: heldError.message })}\n`,
		);
		if (name === "original")
			assert.deepEqual(remaining, [
				{ i: 1, bytes: 10002 },
				{ i: 7, bytes: 10002 },
			]);
		else assert.deepEqual(remaining, []);
	});
}
