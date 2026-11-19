import assert from "node:assert/strict";
import test from "node:test";
import { rectangle } from "./coarse_osm_access_fixture_v2.ts";
import type { PointTiming } from "./coarse_osm_access_timing_v2.ts";
import {
	finishAccessPointTiming,
	type PreparedPointTiming,
	prepareAccessPointTiming,
} from "./coarse_osm_access_timing_v3.ts";
import { contextDisplayFixture } from "./coarse_osm_context_display_fixture_v1.ts";
import { settledPhaseMemory } from "./coarse_osm_phase_lifetime_v1.ts";
import { reusedContextDisplay as originalDisplay } from "./coarse_osm_reused_display_v1.ts";
import { reusedContextDisplay as guardedDisplay } from "./coarse_osm_reused_display_v2.ts";
import { legacyRoutingGeography } from "./coarse_osm_routing_geography_v1.ts";

for (const [name, reusedContextDisplay] of [
	["original", originalDisplay],
	["seed-guard", guardedDisplay],
] as const) {
	test(`${name}: finer cells exceed the old cell cap within actual backing limits and release prepared-point storage`, async () => {
		const p = contextDisplayFixture(
			[
				[0, 0],
				[1, 1],
				[2, 2],
			],
			[
				[0, 1, 1000],
				[1, 2, 1000],
			],
		);
		const geo = legacyRoutingGeography({
			bounds: [-6, -6, 6, 6],
			boundary: [[rectangle(-6, -6, 6, 6)]],
			lakes: [],
		});
		const starts = [{ position: p.source.snap, initialTicks: 0 }];
		const foot = p.graph.coordinate(1);
		const destination = {
			...p.source,
			origin: foot,
			snap: { ...p.source.snap, segmentFraction: 1, coordinate: foot },
		};
		const sourceBefore = Object.fromEntries(
			Object.entries(p.raw).map(([k, v]) => [k, v.slice()]),
		);
		const memory = await settledPhaseMemory();
		const buffers: WeakRef<ArrayBufferLike>[] = [];
		let maxObserved = 0;
		function run(maxCells: number) {
			let prepared: PreparedPointTiming | undefined;
			let timing: PointTiming | undefined;
			const result = reusedContextDisplay(
				p.graph,
				p.geometry,
				p.contexts,
				geo,
				p.source,
				starts,
				{
					maxCells,
					maxTicks: 432000,
					beforeSeed: (field) => {
						prepared = prepareAccessPointTiming(
							p.graph,
							p.geometry,
							field,
							p.source.origin,
							foot,
							destination,
						);
					},
					observeBacking: (backing) => {
						maxObserved = Math.max(
							maxObserved,
							process.memoryUsage().arrayBuffers - memory.arrayBuffers,
						);
						buffers.push(...backing.map((b) => new WeakRef(b)));
					},
					probe: (grid) => {
						assert.ok(prepared);
						timing = finishAccessPointTiming(geo, grid, prepared);
					},
				},
				true,
			);
			assert.ok(timing && prepared);
			return { result, timing, prepared };
		}
		const coarse = run(2500000);
		await settledPhaseMemory();
		const fine = run(33554432);
		assert.ok(coarse.result.frame.step > fine.result.frame.step);
		assert.equal(fine.result.frame.step, 5000);
		assert.ok(
			coarse.result.frame.width * coarse.result.frame.height <= 2500000,
		);
		assert.ok(fine.result.frame.width * fine.result.frame.height > 2500000);
		assert.equal(coarse.timing.roadTicks, fine.timing.roadTicks);
		assert.deepEqual(coarse.prepared, fine.prepared);
		assert.ok(maxObserved > 0 && maxObserved <= 67108864);
		process.stdout.write(
			`${JSON.stringify({ oldCells: coarse.result.frame.width * coarse.result.frame.height, finerCells: fine.result.frame.width * fine.result.frame.height, oldStep: coarse.result.frame.step, finerStep: fine.result.frame.step, maxObservedQueryBacking: maxObserved })}\n`,
		);
		assert.ok(fine.result.stats.maximumBackingBufferBytes <= 67108864);
		await settledPhaseMemory();
		const after = await settledPhaseMemory();
		assert.ok(after.arrayBuffers <= memory.arrayBuffers);
		assert.ok(
			buffers.length >= 16 && buffers.every((b) => b.deref() === undefined),
		);
		assert.deepEqual(p.raw, sourceBefore);
	});
}
