import assert from "node:assert/strict";
import { mkdtemp, readdir, readFile, stat, writeFile } from "node:fs/promises";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { join, resolve, sep } from "node:path";
import { pathToFileURL } from "node:url";
import { parseArgs } from "node:util";

const { values } = parseArgs({
	options: {
		bindings: { type: "string" },
		config: { type: "string" },
		tiles: { type: "string" },
		output: { type: "string" },
	},
});
for (const key of ["bindings", "config", "tiles", "output"])
	assert.ok(values[key], `Missing --${key}`);
const { Actor, VALHALLA_VERSION } = await import(
	pathToFileURL(resolve(values.bindings)).href
);
const base = JSON.parse(await readFile(values.config, "utf8"));
const tiles = resolve(values.tiles);
const requests = [];
const server = createServer(async (request, response) => {
	const path = resolve(
		tiles,
		`.${new URL(request.url, "http://localhost").pathname}`,
	);
	if (!path.startsWith(`${tiles}${sep}`) || !path.endsWith(".gph")) {
		response.writeHead(404).end();
		return;
	}
	try {
		const data = await readFile(path);
		requests.push({
			path: path.slice(tiles.length),
			status: 200,
			bytes: data.length,
		});
		response
			.writeHead(200, {
				"Content-Type": "application/octet-stream",
				"Content-Length": data.length,
			})
			.end(data);
	} catch {
		requests.push({ path: path.slice(tiles.length), status: 404, bytes: 0 });
		response.writeHead(404).end();
	}
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const port = server.address().port;
const cache = await mkdtemp(join(tmpdir(), "geo-planner-native-tiles-"));
async function directoryBytes(path) {
	let bytes = 0;
	for (const entry of await readdir(path, { withFileTypes: true })) {
		const child = join(path, entry.name);
		bytes += entry.isDirectory()
			? await directoryBytes(child)
			: (await stat(child)).size;
	}
	return bytes;
}
const payload = {
	locations: [{ lat: 32.7157, lon: -117.1611 }],
	costing: "auto",
	costing_options: { auto: { speed_types: ["freeflow", "constrained"] } },
	contours: [{ time: 60 }],
	polygons: true,
	show_locations: true,
	generalize: 100,
	denoise: 0,
};
try {
	const localConfig = structuredClone(base);
	localConfig.mjolnir.tile_extract = "";
	localConfig.mjolnir.tile_dir = tiles;
	const local = new Actor(localConfig);
	const expected = await local.isochrone(payload);
	const remoteConfig = structuredClone(base);
	remoteConfig.mjolnir.tile_extract = "";
	remoteConfig.mjolnir.tile_dir = cache;
	remoteConfig.mjolnir.tile_url = `http://127.0.0.1:${port}/{tilePath}`;
	remoteConfig.mjolnir.tile_url_gz = false;
	remoteConfig.mjolnir.max_cache_size = 128 * 1024 ** 2;
	const actor = new Actor(remoteConfig);
	const started = performance.now();
	const result = await actor.isochrone(payload);
	const elapsedMs = performance.now() - started;
	assert.deepEqual(result, expected);
	assert.ok(
		requests.some((r) => r.status === 200),
		"Remote actor must fetch actual tiles",
	);
	const firstRequestCount = requests.length;
	const warmStarted = performance.now();
	assert.deepEqual(await actor.isochrone(payload), expected);
	const warmElapsedMs = performance.now() - warmStarted;
	const summary = {
		engineVersion: VALHALLA_VERSION,
		graph: values.tiles,
		runtime: process.version,
		platform: `${process.platform}/${process.arch}`,
		query: payload,
		equivalentToLocal: true,
		coldActorCallMs: elapsedMs,
		warmActorCallMs: warmElapsedMs,
		firstRequestCount,
		additionalWarmRequests: requests.length - firstRequestCount,
		downloadedBytes: requests.reduce((sum, r) => sum + r.bytes, 0),
		requests,
		cacheDirectory: cache,
		cacheBytes: await directoryBytes(cache),
		limitations:
			"Local HTTP tile server only; no Vercel deployment, WAN, worldwide graph, missing-required-tile failure handling, or concurrency validation. Native package revision differs from graph builder; this tests loading equivalence only.",
	};
	await writeFile(values.output, JSON.stringify(summary, null, 2));
	console.log(
		JSON.stringify(
			{
				...summary,
				requests: `${requests.length} requests retained in output`,
			},
			null,
			2,
		),
	);
} finally {
	await new Promise((resolve) => server.close(resolve));
}
