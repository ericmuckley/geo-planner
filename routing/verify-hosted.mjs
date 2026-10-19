import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import {
	defaultQuery,
	engineConfigSchema,
	resultSchema,
} from "../src/lib/reachability.ts";

const app = process.env.GEO_PLANNER_URL || "http://localhost:3000";
const output = new URL("../data/hosted-routing/verification/", import.meta.url);
const origins = [
	["san-diego", 32.7157, -117.1611, 60],
	["los-angeles", 34.0522, -118.2437, 30],
	["new-york", 40.7128, -74.006, 60],
	["anchorage", 61.2181, -149.9003, 30],
	["honolulu", 21.3099, -157.8581, 30],
];
await mkdir(output, { recursive: true });
const runs = [];
try {
	const healthResponse = await fetch(`${app}/api/reachability`, {
		signal: AbortSignal.timeout(10_000),
	});
	assert.ok(healthResponse.ok, "Could not load app routing configuration");
	const config = engineConfigSchema.parse(await healthResponse.json());
	assert.equal(
		config.provider,
		"openrouteservice",
		"Select ROUTING_PROVIDER=openrouteservice",
	);
	assert.ok(config.configured, "Configure the server-only ORS_API_KEY first");
	for (const [name, lat, lon, budgetMinutes] of origins) {
		const started = performance.now();
		const response = await fetch(`${app}/api/reachability`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({
				...defaultQuery,
				origin: { lat, lon },
				budgetMinutes,
			}),
			signal: AbortSignal.timeout(35_000),
		});
		const body = await response.json();
		assert.ok(
			response.ok,
			`${name}: HTTP ${response.status} ${body.error || "Request failed"}`,
		);
		const result = resultSchema.parse(body);
		assert.equal(result.metadata.engine, "openrouteservice");
		runs.push({ name, appRequestMs: performance.now() - started, result });
		console.log(
			`${name}: ${result.contours.features.length} features; engine HTTP round trip ${result.metadata.timings.engineRoundTripMs.toFixed(1)} ms`,
		);
	}
} finally {
	await writeFile(
		new URL("summary.json", output),
		JSON.stringify(
			{
				checkedAt: new Date().toISOString(),
				expectedRequests: origins.length,
				completedRequests: runs.length,
				protocol:
					"One sequential query per public US origin. No retries or isolated graph-search measurement; not an independent correctness proof.",
				runs,
			},
			null,
			2,
		),
	);
}
