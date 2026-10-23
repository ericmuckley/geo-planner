import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { performance } from "node:perf_hooks";
import { defaultQuery, resultSchema } from "../src/lib/reachability";
import { coarseSmokeOrigins } from "./coarse-smoke-cases";

const started = performance.now();
const { runEstimate } = await import("../src/server/coarse-estimate.server");
const moduleLoadMs = performance.now() - started;
const expected = JSON.parse(
	await readFile(
		"docs/evidence/coarse-national-2026-10-22/national-smoke.json",
		"utf8",
	),
).samples as Array<{ name: string; minutes: number; cells: number }>;
const samples = [];
for (const [name, lat, lon] of coarseSmokeOrigins) {
	let previousCount = 0;
	for (const minutes of [360, 600, 720]) {
		const before = performance.now();
		const response = await runEstimate(
			new Request("http://localhost/api/estimate", {
				method: "POST",
				body: JSON.stringify({
					...defaultQuery,
					origin: { lat, lon },
					budgetMinutes: minutes,
				}),
			}),
		);
		const text = await response.text();
		assert.equal(response.status, 200, text);
		const result = resultSchema.parse(JSON.parse(text));
		const cells = result.metadata.approximation?.reachedCells ?? 0;
		assert.equal(result.metadata.engineVersion, "coarse-road-grid-v5");
		assert.equal(
			cells,
			expected.find((s) => s.name === name && s.minutes === minutes)?.cells,
		);
		assert.ok(cells >= previousCount);
		// The ferry-only island may stay isolated. Road-connected sample origins
		// must not silently collapse to a few cells after attachment changes.
		if (name !== "Nantucket")
			assert.ok(cells >= 10, `Degenerate connected-origin estimate: ${name}`);
		assert.ok(Buffer.byteLength(text) < 1_000_000);
		previousCount = cells;
		samples.push({
			name,
			minutes,
			cells,
			bytes: Buffer.byteLength(text),
			inProcessRequestMs: performance.now() - before,
			searchMs: result.metadata.timings.searchMs,
			contourMs: result.metadata.timings.contourMs,
		});
	}
}
console.log(
	JSON.stringify(
		{
			moduleLoadMs,
			samples,
			memoryUsage: process.memoryUsage(),
			publicRoutingApiCalls: 0,
			scope:
				"Sequential in-process observations, not HTTP/browser/cloud latency, production percentiles, or a peak-memory measurement. Reachable-cell counts and payload bounds are smoke checks, not accuracy validation.",
		},
		null,
		2,
	),
);
