import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";
import { experimentConfig, runExperiment } from "./experiment.server";

const originalFetch = globalThis.fetch;
const originalFlag = process.env.LOCAL_ROUTING_EXPERIMENT;
const originalVercel = process.env.VERCEL;
const query = { origin: { lat: 32.7157, lon: -117.1611 }, budgetMinutes: 90 };
const config = {
	ready: true,
	graphIdentity: "a".repeat(64),
	bounds: [-117.65, 31.9, -116, 33.6],
	maxMinutes: 720,
	model: "exploratory-static-car-v3",
	sourceDate: "2026-10-14T20:21:12Z",
	publicApiCalls: 0,
};
function result() {
	return {
		id: "local-test",
		query,
		geometry: {
			type: "FeatureCollection",
			features: [
				{
					type: "Feature",
					properties: { kind: "road" },
					geometry: {
						type: "MultiLineString",
						coordinates: [
							[
								[0, 0],
								[0.01, 0],
							],
						],
					},
				},
				{
					type: "Feature",
					properties: { kind: "cut", reached: true },
					geometry: { type: "Point", coordinates: [0.01, 0] },
				},
			],
		},
		metadata: {
			...config,
			coverageVerified: false,
			truncated: true,
			reachedCutNodes: 1,
			auditedCutNodes: 2,
			cutsBySide: { north: 1, south: 0, east: 0, west: 0 },
			firstReachedCutMs: 3904583,
			settledStates: 100,
			snap: {
				input: [-117.1611, 32.7157],
				snapped: [-117.1611, 32.71569],
				distanceMeters: 1,
			},
			display: {
				reachableDirectedRoads: 100,
				displayedSegments: 1,
				sampleStride: 100,
				displayLimit: 30000,
				reachableBounds: [0, 0, 0.01, 0],
			},
			warnings: ["Incomplete"],
			timings: {
				snapMs: 1,
				nativeSearchMs: 2,
				nativeRoundTripMs: 3,
				geometryMs: 4,
				workerTotalMs: 9,
			},
		},
	};
}
const request = (body: unknown) =>
	new Request("http://localhost/api/experiment", {
		method: "POST",
		body: JSON.stringify(body),
	});

beforeEach(() => {
	process.env.LOCAL_ROUTING_EXPERIMENT = "1";
	delete process.env.VERCEL;
});
afterEach(() => {
	globalThis.fetch = originalFetch;
	if (originalFlag === undefined) delete process.env.LOCAL_ROUTING_EXPERIMENT;
	else process.env.LOCAL_ROUTING_EXPERIMENT = originalFlag;
	if (originalVercel === undefined) delete process.env.VERCEL;
	else process.env.VERCEL = originalVercel;
});

test("local experiment is opt-in and disabled on Vercel without contacting any router", async () => {
	globalThis.fetch = async () => {
		throw new Error("Must not fetch");
	};
	delete process.env.LOCAL_ROUTING_EXPERIMENT;
	assert.equal((await experimentConfig()).status, 503);
	assert.equal((await runExperiment(request(query))).status, 503);
	process.env.LOCAL_ROUTING_EXPERIMENT = "1";
	process.env.VERCEL = "1";
	assert.equal((await runExperiment(request(query))).status, 503);
});

test("malformed budgets, coordinates and extra fields fail before reaching the worker", async () => {
	globalThis.fetch = async () => {
		throw new Error("Must not fetch");
	};
	for (const body of [
		{ ...query, budgetMinutes: 721 },
		{ ...query, budgetMinutes: 90.5 },
		{ ...query, provider: "hosted" },
		{ ...query, origin: { lat: 100, lon: 0 } },
	]) {
		assert.equal((await runExperiment(request(body))).status, 400);
	}
});

test("90-minute request uses only fixed loopback worker and preserves truncation and separate timings", async () => {
	globalThis.fetch = async (url, init) => {
		assert.equal(url, "http://127.0.0.1:8787/query");
		assert.deepEqual(JSON.parse(String(init?.body)), query);
		assert.deepEqual(init?.headers, { "Content-Type": "application/json" });
		return Response.json(result());
	};
	const response = await runExperiment(request(query));
	assert.equal(response.status, 200);
	const body = await response.json();
	assert.equal(body.metadata.truncated, true);
	assert.equal(body.metadata.coverageVerified, false);
	assert.equal(body.metadata.timings.nativeSearchMs, 2);
	assert.ok(body.metadata.timings.appProxyMs >= 0);
});

test("worker failures and invalid responses produce errors without fallback or retries", async () => {
	for (const response of [
		new Response("bad", { status: 503 }),
		Response.json({}),
		Response.json({ ...result(), query: { ...query, budgetMinutes: 120 } }),
	]) {
		let calls = 0;
		globalThis.fetch = async () => {
			calls++;
			return response;
		};
		assert.equal((await runExperiment(request(query))).status, 503);
		assert.equal(calls, 1);
	}
});

test("off-network origin failure is reported clearly without hosted fallback", async () => {
	globalThis.fetch = async () => new Response("bad origin", { status: 400 });
	const response = await runExperiment(request(query));
	assert.equal(response.status, 400);
	assert.match((await response.json()).error, /100 m/);
});

test("health validates local graph identity and does not expose worker URLs or credentials", async () => {
	globalThis.fetch = async (url) => {
		assert.equal(url, "http://127.0.0.1:8787/health");
		return Response.json(config);
	};
	const response = await experimentConfig();
	assert.equal(response.status, 200);
	assert.deepEqual(await response.json(), config);
});
