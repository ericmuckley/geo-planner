import assert from "node:assert/strict";
import { readdir, readFile, stat } from "node:fs/promises";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { parse } from "dotenv";

const secrets = new Set([process.env.DATABASE_URL, process.env.ORS_API_KEY]);
for (const path of [".env", ".env.local"]) {
	try {
		const values = parse(await readFile(path));
		secrets.add(values.DATABASE_URL);
		secrets.add(values.ORS_API_KEY);
	} catch (error) {
		if (error.code !== "ENOENT") throw error;
	}
}
const secretValues = [...secrets].filter((value) => value && value.length > 8);

process.env.VERCEL = "1";
process.env.LOCAL_ROUTING_EXPERIMENT = "1";
const root = process.argv[2] ?? ".";
const expectedEngine = process.argv[3] ?? "coarse-road-grid-v6";
const directory = resolve(root, ".vercel/output/functions/__server.func");
let functionBytes = 0;
let functionFiles = 0;
async function inspect(path) {
	for (const entry of await readdir(path, { withFileTypes: true })) {
		const child = join(path, entry.name);
		assert.ok(!entry.name.startsWith(".env"));
		assert.ok(!/\.(pbf|osm|csr|gph|pmtiles|py)$/.test(entry.name));
		if (entry.isDirectory()) await inspect(child);
		else {
			functionFiles++;
			functionBytes += (await stat(child)).size;
			const content = await readFile(child);
			assert.ok(
				!secretValues.some((secret) => content.includes(secret)),
				`Secret embedded in function file: ${entry.name}`,
			);
		}
	}
}
await inspect(directory);
assert.ok(functionBytes < 250_000_000);
const handler = (await import(pathToFileURL(join(directory, "index.mjs")).href))
	.default;
let outboundCalls = 0;
globalThis.fetch = async () => {
	outboundCalls++;
	throw new Error("Unexpected outbound call");
};
const configResponse = await handler.fetch(
	new Request("http://localhost/api/estimate"),
);
assert.equal(configResponse.status, 200);
assert.equal((await configResponse.json()).maxMinutes, 720);
const samples = [];
for (const [name, lat, lon, minutes] of [
	["San Diego", 32.7157, -117.1611, 360],
	["Denver", 39.7392, -104.9903, 600],
	["New York", 40.7128, -74.006, 720],
]) {
	const started = performance.now();
	const response = await handler.fetch(
		new Request("http://localhost/api/estimate", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({
				version: 1,
				origin: { lat, lon },
				mode: "auto",
				direction: "outbound",
				metric: "time",
				budgetMinutes: minutes,
			}),
		}),
	);
	const text = await response.text();
	assert.equal(response.status, 200, text);
	assert.ok(Buffer.byteLength(text) < 1_000_000);
	const body = JSON.parse(text);
	assert.equal(body.metadata.engine, "coarse");
	assert.equal(body.metadata.engineVersion, expectedEngine);
	if (expectedEngine === "coarse-road-grid-v6") {
		assert.equal(
			body.metadata.graphVersion,
			"natural-earth-census-2026-grid-v6",
		);
		assert.match(
			body.metadata.attribution,
			/modified and repackaged Census data/,
		);
		assert.match(body.metadata.approximation.sourceRelease, /2026 TIGER\/Line/);
		assert.equal(body.metadata.coverageVerified, false);
	}
	assert.ok(body.contours.features[0].geometry.coordinates.length);
	samples.push({
		name,
		minutes,
		bytes: Buffer.byteLength(text),
		localHandlerMs: performance.now() - started,
	});
}
const disabled = await handler.fetch(
	new Request("http://localhost/api/experiment"),
);
assert.equal(disabled.status, 503);
const previousDatabaseUrl = process.env.DATABASE_URL;
delete process.env.DATABASE_URL;
const localHistory = await handler.fetch(
	new Request("http://localhost/api/saved-runs"),
);
assert.equal(localHistory.status, 200);
assert.deepEqual(await localHistory.json(), { configured: false, runs: [] });
const unsaved = await handler.fetch(
	new Request("http://localhost/api/saved-runs", {
		method: "POST",
		body: "[]",
	}),
);
assert.equal(unsaved.status, 503);
if (previousDatabaseUrl !== undefined)
	process.env.DATABASE_URL = previousDatabaseUrl;
assert.equal(outboundCalls, 0);
const clientDirectory = resolve(root, ".vercel/output/static/assets");
for (const entry of await readdir(clientDirectory)) {
	if (!entry.endsWith(".js")) continue;
	const content = await readFile(join(clientDirectory, entry), "utf8");
	assert.ok(
		!secretValues.some((secret) => content.includes(secret)),
		`Secret embedded in client file: ${entry}`,
	);
	assert.ok(
		!content.includes("natural-earth-5.1.2-road-grid-"),
		`Server dataset in client asset: ${entry}`,
	);
	assert.ok(!content.includes("natural-earth-census-2026-"));
	assert.ok(!content.includes("cell-visits-le-v1"));
}
console.log(
	JSON.stringify(
		{
			functionFiles,
			functionBytes,
			samples,
			outboundCalls,
			coarseRouteEnabledOnVercel: true,
			detailedExperimentDisabled: true,
			serverDatasetInClientAssets: false,
			secretsEmbeddedInOutput: false,
			localHistoryFallbackWithoutDatabase: true,
			rawSourcesOrEnvironmentFilesBundled: false,
			scope:
				"Generated Vercel handler invoked locally with network calls rejected. This proves packaging and handler behavior, not a cloud deployment, cloud cold start, concurrency or peak memory.",
		},
		null,
		2,
	),
);
