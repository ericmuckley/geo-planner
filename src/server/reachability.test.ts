import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { afterEach, beforeEach, mock, test } from "node:test";
import { defaultQuery, querySchema, resultSchema } from "../lib/reachability";
import { getEngineConfig, runReachability } from "./reachability.server";

const envKeys = [
	"ROUTING_PROVIDER",
	"ORS_API_KEY",
	"VALHALLA_URL",
	"VALHALLA_MAX_MINUTES",
	"VALHALLA_GRAPH_VERSION",
	"VALHALLA_ENGINE_VERSION",
	"VALHALLA_COVERAGE",
	"VALHALLA_COVERAGE_BOUNDS",
] as const;
let previous: (string | undefined)[];

beforeEach(() => {
	previous = envKeys.map((key) => process.env[key]);
	for (const key of envKeys) delete process.env[key];
});
afterEach(() => {
	envKeys.forEach((key, index) => {
		const value = previous[index];
		if (value === undefined) delete process.env[key];
		else process.env[key] = value;
	});
	mock.restoreAll();
});

function request(input: unknown = defaultQuery, signal?: AbortSignal) {
	return new Request("http://localhost/api/reachability", {
		method: "POST",
		body: JSON.stringify(input),
		headers: { "Content-Type": "application/json" },
		signal,
	});
}

const fixture = {
	type: "FeatureCollection",
	features: [
		{
			type: "Feature",
			properties: { contour: 60, metric: "time" },
			geometry: {
				type: "Polygon",
				coordinates: [
					[
						[-117.2, 32.7],
						[-117.1, 32.7],
						[-117.1, 32.8],
						[-117.2, 32.7],
					],
				],
			},
		},
		{
			type: "Feature",
			properties: { type: "snapped" },
			geometry: { type: "MultiPoint", coordinates: [[-117.161, 32.716]] },
		},
	],
	warnings: [
		{ code: 1, description: "Synthetic warning for adapter verification" },
	],
};

test("unconfigured service provides honest status without exposing the URL", async () => {
	assert.deepEqual(await (await getEngineConfig()).json(), {
		configured: false,
		health: "unconfigured",
		maxMinutes: 120,
		graphVersion: "unrecorded",
		engineVersion: "unrecorded",
		coverage: "unrecorded; completeness unknown",
	});
	assert.equal((await runReachability(request())).status, 503);
	process.env.VALHALLA_URL = "http://private-router:8002";
	mock.method(globalThis, "fetch", async () => {
		throw new Error("private-router details");
	});
	assert.equal(
		JSON.stringify(await (await getEngineConfig()).json()).includes(
			"private-router",
		),
		false,
	);
});

test("malformed JSON and invalid semantics never call the routing service", async () => {
	const fetchMock = mock.method(globalThis, "fetch", () => {
		throw new Error("Must not fetch");
	});
	assert.equal(
		(
			await runReachability(
				new Request("http://localhost/api/reachability", {
					method: "POST",
					body: "{",
				}),
			)
		).status,
		400,
	);
	for (const input of [
		{ ...defaultQuery, budgetMinutes: 0 },
		{ ...defaultQuery, budgetMinutes: 721 },
		{ ...defaultQuery, budgetMinutes: 60.5 },
		{ ...defaultQuery, origin: { lat: 91, lon: 0 } },
		{ ...defaultQuery, origin: { lat: 32, lon: 181 } },
		{ ...defaultQuery, metric: "distance" },
		{ ...defaultQuery, direction: "inbound" },
		{ ...defaultQuery, mode: "pedestrian" },
		{ ...defaultQuery, budgetMiles: 150 },
	])
		assert.equal((await runReachability(request(input))).status, 422);
	assert.equal(
		querySchema.safeParse({ ...defaultQuery, budgetMinutes: NaN }).success,
		false,
	);
	assert.equal(fetchMock.mock.callCount(), 0);
});

test("app limits reject long-range queries before forwarding", async () => {
	process.env.VALHALLA_URL = "http://router:8002";
	assert.equal(
		(await runReachability(request({ ...defaultQuery, budgetMinutes: 121 })))
			.status,
		422,
	);
	process.env.VALHALLA_MAX_MINUTES = "broken";
	assert.equal((await getEngineConfig()).status, 503);
	assert.equal((await runReachability(request())).status, 503);
});

test("declared regional coverage rejects unsupported origins before routing and handles the date line", async () => {
	process.env.VALHALLA_URL = "http://router:8002";
	process.env.VALHALLA_COVERAGE_BOUNDS = "[-119.8,30.8,-114.5,35.5]";
	const fetchMock = mock.method(globalThis, "fetch", async () =>
		Response.json(fixture),
	);
	assert.equal(
		(
			await runReachability(
				request({ ...defaultQuery, origin: { lat: 35.9, lon: 14.5 } }),
			)
		).status,
		422,
	);
	assert.equal(fetchMock.mock.callCount(), 0);
	assert.equal((await runReachability(request())).status, 200);
	process.env.VALHALLA_COVERAGE_BOUNDS = "[170,-30,-170,0]";
	for (const lon of [179, -179])
		assert.equal(
			(
				await runReachability(
					request({ ...defaultQuery, origin: { lat: -17, lon } }),
				)
			).status,
			200,
		);
	assert.equal((await runReachability(request())).status, 422);
	process.env.VALHALLA_COVERAGE_BOUNDS = "invalid";
	assert.equal((await getEngineConfig()).status, 503);
	assert.equal((await runReachability(request())).status, 503);
});

test("routing readiness checks reachable isochrone capability and expected engine identity", async () => {
	process.env.VALHALLA_URL = "https://private-router:8002";
	process.env.VALHALLA_ENGINE_VERSION = "recorded-engine";
	mock.method(globalThis, "fetch", async (url: URL, init: RequestInit) => {
		assert.equal(url.href, "https://private-router:8002/status");
		assert.equal(init.cache, "no-store");
		assert.ok(init.signal instanceof AbortSignal);
		return Response.json({
			version: "recorded-engine",
			available_actions: ["isochrone", "route"],
		});
	});
	const config = await (await getEngineConfig()).json();
	assert.equal(config.health, "ready");
	assert.ok(config.checkedAt);
	assert.equal(JSON.stringify(config).includes("private-router"), false);
	mock.restoreAll();
	mock.method(globalThis, "fetch", async () =>
		Response.json({
			version: "different-engine",
			available_actions: ["isochrone"],
		}),
	);
	assert.equal((await (await getEngineConfig()).json()).health, "mismatch");
});

test("an unreachable, malformed, or incapable routing service is not advertised ready", async () => {
	process.env.VALHALLA_URL = "http://private-router:8002";
	for (const response of [
		new Response("private-router failure", { status: 503 }),
		Response.json({ version: "engine", available_actions: ["route"] }),
		Response.json({ version: "engine" }),
		new Response("invalid json"),
	]) {
		mock.method(globalThis, "fetch", async () => response);
		const config = await (await getEngineConfig()).json();
		assert.equal(config.health, "unavailable");
		assert.equal(config.configured, true);
		assert.equal(JSON.stringify(config).includes("private-router"), false);
		mock.restoreAll();
	}
	mock.method(globalThis, "fetch", async () => {
		throw new DOMException("private-router timeout", "TimeoutError");
	});
	assert.equal((await (await getEngineConfig()).json()).health, "unavailable");
});

test("adapter sends static outbound time contours and preserves provenance, snaps, and warnings", async () => {
	process.env.VALHALLA_URL = "http://router:8002/";
	process.env.VALHALLA_GRAPH_VERSION = "test-graph";
	process.env.VALHALLA_ENGINE_VERSION = "test-build";
	process.env.VALHALLA_COVERAGE = "test region";
	process.env.VALHALLA_MAX_MINUTES = "720";
	mock.method(globalThis, "fetch", async (url: URL, init: RequestInit) => {
		assert.equal(url.href, "http://router:8002/isochrone");
		assert.equal(init.method, "POST");
		assert.deepEqual(JSON.parse(String(init.body)), {
			locations: [{ lat: 32.7157, lon: -117.1611 }],
			costing: "auto",
			costing_options: { auto: { speed_types: ["freeflow", "constrained"] } },
			contours: [{ time: 720 }],
			polygons: true,
			show_locations: true,
			reverse: false,
			generalize: 100,
			denoise: 0,
		});
		assert.ok(init.signal instanceof AbortSignal);
		return Response.json(fixture);
	});
	const response = await runReachability(
		request({ ...defaultQuery, budgetMinutes: 720 }),
	);
	assert.equal(response.status, 200);
	assert.equal(response.headers.get("Cache-Control"), "no-store");
	const result = resultSchema.parse(await response.json());
	assert.deepEqual(result.contours, fixture);
	assert.equal(result.query.budgetMinutes, 720);
	assert.equal(result.metadata.graphVersion, "test-graph");
	assert.equal(result.metadata.coverageVerified, false);
	assert.equal(
		result.metadata.upstreamBytes,
		new TextEncoder().encode(JSON.stringify(fixture)).byteLength,
	);
	assert.ok(
		result.metadata.timings.serverTotalMs >=
			result.metadata.timings.engineRoundTripMs,
	);
});

test("upstream rejections and malformed polygons produce actionable errors", async () => {
	process.env.VALHALLA_URL = "http://router:8002";
	for (const response of [
		new Response("internal details", { status: 400 }),
		new Response("not json"),
		Response.json({ type: "FeatureCollection", features: [] }),
		Response.json({ ...fixture, features: [fixture.features[1]] }),
		Response.json({
			...fixture,
			features: [
				{
					type: "Feature",
					properties: { type: "input" },
					geometry: { type: "Point", coordinates: [-117.1611, 32.7157] },
				},
			],
		}),
		Response.json({
			...fixture,
			features: [
				{
					...fixture.features[0],
					geometry: {
						type: "Polygon",
						coordinates: [
							[
								[-117, 32],
								[-116, 33],
								[-115, 34],
								[-114, 35],
							],
						],
					},
				},
			],
		}),
	]) {
		mock.method(globalThis, "fetch", async () => response);
		const result = await runReachability(request());
		assert.equal(result.status, 502);
		assert.equal(
			JSON.stringify(await result.json()).includes("internal details"),
			false,
		);
		mock.restoreAll();
	}
});

test("real Valhalla response retains input Point and snapped MultiPoint alongside polygons", async () => {
	process.env.VALHALLA_URL = "http://router:8002";
	const body = readFileSync(
		new URL("./fixtures/valhalla-san-diego-15.json", import.meta.url),
		"utf8",
	);
	mock.method(globalThis, "fetch", async () => new Response(body));
	const response = await runReachability(
		request({ ...defaultQuery, budgetMinutes: 15 }),
	);
	assert.equal(response.status, 200);
	const result = resultSchema.parse(await response.json());
	assert.deepEqual(result.contours, JSON.parse(body));
	assert.deepEqual(
		result.contours.features.map((feature) => feature.geometry.type),
		["Polygon", "MultiPoint", "Point"],
	);
});

test("timeouts and cancelled clients have distinct statuses", async () => {
	process.env.VALHALLA_URL = "http://router:8002";
	mock.method(globalThis, "fetch", async () => {
		throw new DOMException("Timed out", "TimeoutError");
	});
	assert.equal((await runReachability(request())).status, 504);
	mock.restoreAll();
	const controller = new AbortController();
	controller.abort();
	mock.method(globalThis, "fetch", async () => {
		throw new DOMException("Aborted", "AbortError");
	});
	assert.equal(
		(await runReachability(request(defaultQuery, controller.signal))).status,
		408,
	);
});

test("hosted routing exposes key presence without spending quota or claiming a live health check", async () => {
	process.env.ROUTING_PROVIDER = "openrouteservice";
	const fetchMock = mock.method(globalThis, "fetch", () => {
		throw new Error("Configuration must not spend quota");
	});
	const missing = await (await getEngineConfig()).json();
	assert.equal(missing.configured, false);
	assert.equal(missing.health, "unconfigured");
	assert.equal(missing.maxMinutes, 60);
	assert.equal((await runReachability(request())).status, 503);
	process.env.ORS_API_KEY = "test-secret-key";
	const config = await (await getEngineConfig()).json();
	assert.equal(config.provider, "openrouteservice");
	assert.equal(config.health, "unchecked");
	assert.equal(JSON.stringify(config).includes("test-secret-key"), false);
	assert.equal(fetchMock.mock.callCount(), 0);
	process.env.ROUTING_PROVIDER = "typo";
	assert.equal((await getEngineConfig()).status, 503);
});

test("hosted driving uses seconds and longitude/latitude, retaining returned provenance without Valhalla settings", async () => {
	process.env.ROUTING_PROVIDER = "openrouteservice";
	process.env.ORS_API_KEY = "test-secret-key";
	process.env.VALHALLA_URL = "http://unused-local-engine";
	const responseFixture = {
		type: "FeatureCollection",
		features: [fixture.features[0]],
		metadata: {
			engine: {
				version: "test-ors-build",
				graph_date: "2026-10-14T00:00:00Z",
				osm_date: "2026-10-12T00:00:00Z",
				build_date: "2026-10-10T00:00:00Z",
			},
			query: { api_key: "must-not-be-echoed" },
		},
	};
	mock.method(globalThis, "fetch", async (url: URL, init: RequestInit) => {
		assert.equal(
			url.href,
			"https://api.heigit.org/openrouteservice/v2/isochrones/driving-car",
		);
		assert.equal(init.method, "POST");
		assert.equal(
			new Headers(init.headers).get("Authorization"),
			"test-secret-key",
		);
		assert.deepEqual(JSON.parse(String(init.body)), {
			locations: [[-117.1611, 32.7157]],
			location_type: "start",
			range_type: "time",
			range: [3600],
			smoothing: 0,
		});
		assert.ok(init.signal instanceof AbortSignal);
		return Response.json(responseFixture);
	});
	const response = await runReachability(request());
	assert.equal(response.status, 200);
	const result = resultSchema.parse(await response.json());
	assert.equal(result.metadata.engine, "openrouteservice");
	assert.equal(result.metadata.engineVersion, "test-ors-build");
	assert.equal(result.metadata.graphVersion, "2026-10-14T00:00:00Z");
	assert.equal(result.metadata.osmDate, "2026-10-12T00:00:00Z");
	assert.equal(result.metadata.coverageVerified, false);
	assert.equal(result.metadata.generalizeMeters, undefined);
	assert.equal(result.metadata.speedTypes, undefined);
	assert.equal(result.metadata.denoise, undefined);
	assert.match(result.metadata.attribution || "", /HeiGIT/);
	assert.equal(result.contours.features.length, 1);
	assert.equal(JSON.stringify(result).includes("must-not-be-echoed"), false);
	assert.ok(
		result.metadata.timings.serverTotalMs >=
			result.metadata.timings.engineRoundTripMs,
	);
});

test("hosted driving cap cannot be raised with local-engine settings", async () => {
	process.env.ROUTING_PROVIDER = "openrouteservice";
	process.env.ORS_API_KEY = "test-secret-key";
	process.env.VALHALLA_MAX_MINUTES = "720";
	const fetchMock = mock.method(globalThis, "fetch", () => {
		throw new Error("Must reject before spending quota");
	});
	assert.equal((await (await getEngineConfig()).json()).maxMinutes, 60);
	assert.equal(
		(await runReachability(request({ ...defaultQuery, budgetMinutes: 61 })))
			.status,
		422,
	);
	assert.equal(fetchMock.mock.callCount(), 0);
});

test("hosted quota, access and malformed responses fail safely without retries or fallback", async () => {
	process.env.ROUTING_PROVIDER = "openrouteservice";
	process.env.ORS_API_KEY = "test-secret-key";
	for (const [upstream, expected] of [
		[new Response("test-secret-key", { status: 429 }), 429],
		[new Response("test-secret-key", { status: 403 }), 502],
		[new Response("test-secret-key", { status: 401 }), 502],
		[new Response("invalid json"), 502],
		[Response.json({ type: "FeatureCollection", features: [] }), 502],
	] as const) {
		const fetchMock = mock.method(globalThis, "fetch", async () => upstream);
		const response = await runReachability(request());
		assert.equal(response.status, expected);
		assert.equal(
			JSON.stringify(await response.json()).includes("test-secret-key"),
			false,
		);
		assert.equal(fetchMock.mock.callCount(), 1);
		mock.restoreAll();
	}
});
