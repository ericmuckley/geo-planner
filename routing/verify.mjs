import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { defaultQuery, resultSchema } from "../src/lib/reachability.ts";
import { dataDir, manifest } from "./settings.mjs";

const engine = process.env.VALHALLA_URL || "http://127.0.0.1:8002";
const app = process.env.GEO_PLANNER_URL || "http://localhost:3000";
const output = `${dataDir}/verification/`;
const queryTemplate = {
	...defaultQuery,
	origin: manifest.verificationOrigin || defaultQuery.origin,
};
const budgets = manifest.verificationBudgets || [15, 30, 60, 120];
await mkdir(output, { recursive: true });
async function save(name, data) {
	await writeFile(`${output}${name}.json`, JSON.stringify(data, null, 2));
}
async function request(base, path, body) {
	const start = performance.now();
	const response = await fetch(
		`${base}${path}`,
		body
			? {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify(body),
					signal: AbortSignal.timeout(30_000),
				}
			: { signal: AbortSignal.timeout(30_000) },
	);
	const text = await response.text();
	const httpBodyMs = performance.now() - start;
	const data = JSON.parse(text);
	assert.ok(response.ok, `${path}: ${response.status} ${text}`);
	return { data, httpBodyMs, bytes: Buffer.byteLength(text) };
}
function inRing([x, y], ring) {
	let inside = false;
	for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
		const [xi, yi] = ring[i];
		const [xj, yj] = ring[j];
		if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi)
			inside = !inside;
	}
	return inside;
}
function contains(contour, point) {
	return contour.features.some(({ geometry: g }) => {
		if (g.type === "Point" || g.type === "MultiPoint") return false;
		const polygons = g.type === "Polygon" ? [g.coordinates] : g.coordinates;
		return polygons.some(
			([outer, ...holes]) =>
				inRing(point, outer) && !holes.some((r) => inRing(point, r)),
		);
	});
}
function decodeShape(encoded) {
	const points = [];
	let index = 0;
	let lat = 0;
	let lon = 0;
	function delta() {
		let value = 0;
		let shift = 0;
		let byte;
		do {
			byte = encoded.charCodeAt(index++) - 63;
			value |= (byte & 31) << shift;
			shift += 5;
		} while (byte >= 32);
		return value & 1 ? ~(value >> 1) : value >> 1;
	}
	while (index < encoded.length) {
		lat += delta();
		lon += delta();
		points.push([lon / 1e6, lat / 1e6]);
	}
	return points;
}
const status = (await request(engine, "/status")).data;
assert.equal(status.version, manifest.engineVersion);
await save("status", status);
const config = (await request(app, "/api/reachability")).data;
assert.equal(config.graphVersion, manifest.id);
assert.equal(config.engineVersion, manifest.engineVersion);
const contours = new Map();
const timings = [];
for (const minutes of budgets) {
	for (let repetition = 0; repetition < 6; repetition++) {
		const response = await request(app, "/api/reachability", {
			...queryTemplate,
			budgetMinutes: minutes,
		});
		const result = resultSchema.parse(response.data);
		assert.equal(result.metadata.graphVersion, manifest.id);
		assert.equal(result.metadata.engineVersion, manifest.engineVersion);
		timings.push({
			minutes,
			repetition,
			...result.metadata.timings,
			httpBodyMs: response.httpBodyMs,
			upstreamBytes: result.metadata.upstreamBytes,
		});
		if (repetition === 0) {
			contours.set(minutes, result.contours);
			await save(`contour-${minutes}`, result);
		}
	}
}
const samples = manifest.verificationSamples || [
	["balboa-park", 32.7311, -117.1467],
	["la-jolla", 32.8328, -117.2713],
	["escondido", 33.1192, -117.0864],
	["carlsbad", 33.1581, -117.3506],
	["julian", 33.0787, -116.602],
	["temecula", 33.4936, -117.1484],
	["tijuana", 32.5149, -117.0382],
	["rosarito", 32.3661, -117.0618],
	["ensenada", 31.8667, -116.5964],
	["el-centro", 32.792, -115.5631],
];
const routes = [];
async function route(name, from, to) {
	const payload = {
		locations: [from, to],
		costing: "auto",
		costing_options: { auto: { speed_types: ["freeflow", "constrained"] } },
		units: "kilometers",
	};
	const response = await request(engine, "/route", payload);
	await save(`route-${name}`, { request: payload, ...response });
	const trip = response.data.trip;
	assert.equal(trip.status, 0);
	const shape = decodeShape(trip.legs.at(-1).shape);
	const endpoint = shape.at(-1);
	const memberships = Object.fromEntries(
		[...contours].map(([minutes, c]) => [
			minutes,
			{
				modeledRouteWithinBudget: trip.summary.time <= minutes * 60,
				snappedEndpointInContour: contains(c, endpoint),
			},
		]),
	);
	return {
		name,
		from,
		to,
		snappedStart: decodeShape(trip.legs[0].shape)[0],
		snappedEnd: endpoint,
		minutes: trip.summary.time / 60,
		kilometers: trip.summary.length,
		httpBodyMs: response.httpBodyMs,
		warnings: response.data.warnings || [],
		memberships,
	};
}
for (const [name, lat, lon] of samples)
	routes.push(await route(name, queryTemplate.origin, { lat, lon }));
// Inspect asymmetric local routes and international crossing costs in both directions.
const west = { lat: 32.7157, lon: -117.1623 };
const diagnostics = manifest.verificationOrigin
	? []
	: [
			await route("downtown-west", defaultQuery.origin, west),
			await route("downtown-east", west, defaultQuery.origin),
			await route(
				"tijuana-return",
				{ lat: 32.5149, lon: -117.0382 },
				defaultQuery.origin,
			),
		];
const monotonicity = [];
const bounds = manifest.bbox || manifest.sourceBounds;
for (const [lower, upper] of budgets
	.slice(1)
	.map((upper, i) => [budgets[i], upper])) {
	let lowerMembers = 0;
	let missingFromUpper = 0;
	const missingExamples = [];
	for (let lat = bounds[1]; lat <= bounds[3]; lat += 0.025)
		for (let lon = bounds[0]; lon <= bounds[2]; lon += 0.025) {
			if (contains(contours.get(lower), [lon, lat])) {
				lowerMembers++;
				if (!contains(contours.get(upper), [lon, lat])) {
					missingFromUpper++;
					if (missingExamples.length < 20) missingExamples.push([lon, lat]);
				}
			}
		}
	monotonicity.push({
		lower,
		upper,
		stepDegrees: 0.025,
		lowerMembers,
		missingFromUpper,
		missingExamples,
	});
}
const snaps = Object.fromEntries(
	[...contours].map(([m, c]) => [
		m,
		c.features.filter((f) => f.geometry.type === "MultiPoint"),
	]),
);
const warnings = Object.fromEntries(
	[...contours].map(([m, c]) => [m, c.warnings || []]),
);
const additionalOrigins = [];
for (const origin of manifest.verificationOrigins || []) {
	const response = await request(app, "/api/reachability", {
		...defaultQuery,
		origin: { lat: origin.lat, lon: origin.lon },
		budgetMinutes: origin.minutes,
	});
	const result = resultSchema.parse(response.data);
	await save(`origin-${origin.name}`, result);
	additionalOrigins.push({
		origin,
		metadata: result.metadata,
		featureCount: result.contours.features.length,
	});
}
const summary = {
	createdAt: new Date().toISOString(),
	manifestId: manifest.id,
	origin: queryTemplate.origin,
	protocol:
		"Sequential localhost requests; first sample per budget retained separately, five subsequent samples; no page-cache flush, no isolated graph-search measurement. Route membership is a smoke check against the same engine, not an independent optimality proof.",
	status,
	config,
	timings,
	routes,
	diagnostics,
	monotonicity,
	snaps,
	warnings,
	additionalOrigins,
};
await save("summary", summary);
console.log(JSON.stringify(summary, null, 2));
