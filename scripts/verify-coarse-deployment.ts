import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import {
	defaultQuery,
	engineConfigSchema,
	resultSchema,
} from "../src/lib/reachability";

assert.ok(process.argv[2], "Pass the deployed app URL");
const base = new URL(process.argv[2]);
assert.ok(["http:", "https:"].includes(base.protocol));
assert.ok(!base.username && !base.password && base.pathname === "/");
const startedAt = new Date().toISOString();
const expected = JSON.parse(
	await readFile(
		"docs/evidence/coarse-v5-2026-10-22/national-smoke.json",
		"utf8",
	),
).samples as Array<{ name: string; minutes: number; cells: number }>;
let requests = 0;
async function request(path: string, body?: string) {
	requests++;
	const started = performance.now();
	const response = await fetch(new URL(path, base), {
		method: body === undefined ? "GET" : "POST",
		headers: body === undefined ? {} : { "Content-Type": "application/json" },
		body,
		redirect: "error",
		signal: AbortSignal.timeout(20_000),
	});
	const text = await response.text();
	assert.ok(Buffer.byteLength(text) < 1_000_000);
	assert.match(response.headers.get("Cache-Control") ?? "", /no-store/);
	return {
		status: response.status,
		bytes: Buffer.byteLength(text),
		httpRoundTripMs: performance.now() - started,
		body: JSON.parse(text) as unknown,
	};
}
const configResponse = await request("/api/estimate");
assert.equal(configResponse.status, 200);
const config = engineConfigSchema.parse(configResponse.body);
assert.equal(config.engineVersion, "coarse-road-grid-v5");
assert.equal(config.graphVersion, "natural-earth-census-2026-grid-v5");
assert.equal(config.health, "ready");
assert.equal(config.minMinutes, 60);
assert.equal(config.maxMinutes, 720);

const cases = [
	{ name: "San Diego", lat: 32.7157, lon: -117.1611, minutes: 360 },
	{ name: "Denver", lat: 39.7392, lon: -104.9903, minutes: 600 },
	{ name: "New York", lat: 40.7128, lon: -74.006, minutes: 720 },
	{ name: "Rural Utah", lat: 38.5, lon: -110.7, minutes: 360 },
	{ name: "Key West", lat: 24.5551, lon: -81.78, minutes: 720 },
];
async function estimate(sample: (typeof cases)[number]) {
	const query = {
		...defaultQuery,
		origin: { lat: sample.lat, lon: sample.lon },
		budgetMinutes: sample.minutes,
	};
	const response = await request("/api/estimate", JSON.stringify(query));
	assert.equal(response.status, 200);
	const result = resultSchema.parse(response.body);
	assert.deepEqual(result.query, query);
	assert.equal(result.metadata.engineVersion, config.engineVersion);
	assert.equal(result.metadata.graphVersion, config.graphVersion);
	assert.equal(result.metadata.upstreamBytes, 0);
	assert.equal(result.metadata.coverageVerified, false);
	assert.match(
		result.metadata.attribution ?? "",
		/modified and repackaged Census data/,
	);
	assert.ok(result.contours.warnings?.length);
	const recorded = expected.find(
		(s) => s.name === sample.name && s.minutes === sample.minutes,
	);
	assert.ok(recorded);
	assert.equal(result.metadata.approximation?.reachedCells, recorded.cells);
	return {
		...sample,
		status: response.status,
		bytes: response.bytes,
		httpRoundTripMs: response.httpRoundTripMs,
		reachedCells: recorded.cells,
		serverTimings: result.metadata.timings,
	};
}
const samples = [];
for (const sample of cases) samples.push(await estimate(sample));
const repeat = await estimate(cases[0]);
const concurrent = await Promise.all([estimate(cases[1]), estimate(cases[2])]);
const invalid = [];
for (const [name, body, status] of [
	["malformed JSON", "{", 400],
	[
		"below minimum",
		JSON.stringify({ ...defaultQuery, budgetMinutes: 59 }),
		422,
	],
	[
		"above maximum",
		JSON.stringify({ ...defaultQuery, budgetMinutes: 721 }),
		422,
	],
	[
		"unsupported geography",
		JSON.stringify({ ...defaultQuery, origin: { lat: 21.3, lon: -157.8 } }),
		422,
	],
] as const) {
	const response = await request("/api/estimate", body);
	assert.equal(response.status, status);
	invalid.push({ name, status: response.status });
}
const research = await request("/api/experiment");
assert.equal(research.status, 503);
const anonymousHistory = await request("/api/saved-runs");
assert.equal(anonymousHistory.status, 200);
assert.deepEqual(anonymousHistory.body, { configured: true, runs: [] });
console.log(
	JSON.stringify(
		{
			baseUrl: base.origin,
			startedAt,
			finishedAt: new Date().toISOString(),
			requests,
			config,
			samples,
			repeat,
			concurrent,
			invalid,
			researchDisabled: true,
			freshHistoryConfiguredAndEmpty: true,
			routingProviderRequestsByVerifier: 0,
			historyWritesByVerifier: 0,
			scope:
				"Live HTTP observations from this development machine, including network/JSON delivery. First and repeat calls are not proven cold/warm invocations. Two overlapping requests are a smoke check, not load qualification. Saved national cell counts/version metadata match; this is not real-world driving accuracy or a cloud peak-memory measurement. No cookies or existing history are read or printed, and no routing-provider endpoint is called.",
		},
		null,
		2,
	),
);
