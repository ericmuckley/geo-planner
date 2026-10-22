import assert from "node:assert/strict";
import { performance } from "node:perf_hooks";
import { defaultQuery, resultSchema } from "../src/lib/reachability";

const started = performance.now();
const { runEstimate } = await import("../src/server/coarse-estimate.server");
const moduleLoadMs = performance.now() - started;
const samples = [];
for (const [name, lat, lon] of [
	["San Diego", 32.7157, -117.1611],
	["Seattle", 47.6062, -122.3321],
	["Denver", 39.7392, -104.9903],
	["Miami", 25.7617, -80.1918],
	["New York", 40.7128, -74.006],
	["Chicago", 41.8781, -87.6298],
	["Rural Utah", 38.5, -110.7],
	["Detroit", 42.3314, -83.0458],
	["Key West", 24.5551, -81.78],
	["Nantucket", 41.2835, -70.0995],
	["Portland Maine", 43.6591, -70.2568],
	["San Francisco", 37.7749, -122.4194],
	["El Paso", 31.7619, -106.485],
	["Brownsville", 25.9017, -97.4975],
] as const) {
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
