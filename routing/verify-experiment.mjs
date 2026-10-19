import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { root } from "./settings.mjs";

const options = { graph: "experiment-region-v1", name: "expanded-map-v1" };
const args = process.argv.slice(2);
while (args.length) {
	const option = args.shift();
	const value = args.shift();
	if (!/^[a-zA-Z0-9_-]+$/.test(value ?? ""))
		throw new Error("Invalid run name");
	if (option === "--graph-run") options.graph = value;
	else if (option === "--run-name") options.name = value;
	else
		throw new Error(
			"Usage: node routing/verify-experiment.mjs [--graph-run name] [--run-name fresh-name]",
		);
}
const directory = resolve(root, "data/compact-pilot", options.graph);
const output = resolve(root, "data/experiment-pilot", options.name);
const load = async (name) =>
	JSON.parse(await readFile(resolve(directory, name), "utf8"));
const manifest = await load("manifest.json");
const summary = await load("summary.json");
const cuts = JSON.parse(
	await readFile(
		resolve(
			root,
			"data/compact-pilot",
			`${options.graph}-cuts`,
			"cut-nodes.json",
		),
		"utf8",
	),
);
await mkdir(output);
const samples = [];
const base = "http://127.0.0.1:3000/api/experiment";
const config = await (await fetch(base)).json();
assert.equal(
	config.graphIdentity,
	manifest.graphIdentity,
	"App is running a different graph",
);
let first120;
for (const origin of manifest.profile.origins) {
	const qualified = summary.origins.find((row) => row.origin === origin.id);
	const labels = await readFile(
		resolve(directory, `oracles/${origin.id}.u64le`),
	);
	assert.equal(labels.byteLength, summary.states * 8);
	let previousRoads = 0;
	for (const minutes of origin.id === "san-diego"
		? [60, 90, 120, 360, 720]
		: [60, 90, 120]) {
		const query = {
			origin: { lat: origin.lat, lon: origin.lon },
			budgetMinutes: minutes,
		};
		const started = performance.now();
		const response = await fetch(base, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(query),
			signal: AbortSignal.timeout(90000),
		});
		const raw = await response.text();
		const httpMs = performance.now() - started;
		await writeFile(resolve(output, `${origin.id}-${minutes}.json`), raw, {
			flag: "wx",
		});
		assert.equal(response.status, 200, raw.slice(0, 300));
		const result = JSON.parse(raw);
		const metadata = result.metadata;
		const budget = minutes * 60000;
		const reached = cuts.filter(
			(row) =>
				row.origins[origin.id].costMs !== null &&
				row.origins[origin.id].costMs <= budget,
		);
		const sides = Object.fromEntries(
			["north", "east", "south", "west"].map((side) => [
				side,
				reached.filter((row) => row.outsideSides.includes(side)).length,
			]),
		);
		let settled = 0;
		for (let offset = 0; offset < labels.byteLength; offset += 8)
			if (labels.readBigUInt64LE(offset) <= BigInt(budget)) settled++;
		assert.deepEqual(result.query, query);
		assert.equal(metadata.graphIdentity, manifest.graphIdentity);
		assert.deepEqual(metadata.bounds, manifest.profile.bbox);
		assert.equal(metadata.publicApiCalls, 0);
		assert.equal(metadata.coverageVerified, false);
		assert.equal(
			metadata.settledStates,
			settled,
			"Fresh native labels differ from independent full field",
		);
		assert.equal(metadata.reachedCutNodes, reached.length);
		assert.equal(metadata.auditedCutNodes, cuts.length);
		assert.deepEqual(metadata.cutsBySide, sides);
		assert.equal(
			metadata.firstReachedCutMs,
			reached.length
				? Math.min(...reached.map((row) => row.origins[origin.id].costMs))
				: null,
		);
		assert.equal(metadata.truncated, reached.length > 0);
		assert.deepEqual(metadata.snap.snapped, qualified.snap.snapped);
		assert.equal(metadata.snap.distanceMeters, qualified.snap.distanceMeters);
		assert.ok(metadata.display.reachableDirectedRoads >= previousRoads);
		assert.ok(metadata.display.displayedSegments <= 30000);
		assert.ok(
			result.geometry.features.some(
				(feature) => feature.properties.kind === "coverage",
			),
		);
		assert.ok(metadata.warnings.some((warning) => warning.includes("sampled")));
		if (reached.length)
			assert.ok(
				metadata.warnings.some((warning) => warning.startsWith("INCOMPLETE:")),
			);
		previousRoads = metadata.display.reachableDirectedRoads;
		if (origin.id === "san-diego" && minutes === 120)
			first120 = { query, roads: previousRoads, cuts: reached.length };
		samples.push({
			origin: origin.id,
			minutes,
			httpMs,
			responseBytes: Buffer.byteLength(raw),
			metadata,
		});
		console.log(
			`${origin.id} ${minutes}m: ${settled} states; ${reached.length} edges; ${httpMs.toFixed(1)} ms HTTP`,
		);
	}
}
const repeated = await (
	await fetch(base, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(first120.query),
	})
).json();
assert.equal(repeated.metadata.display.reachableDirectedRoads, first120.roads);
assert.equal(repeated.metadata.reachedCutNodes, first120.cuts);
const errors = [];
for (const query of [
	{ origin: { lat: 32.7157, lon: -117.1611 }, budgetMinutes: 721 },
	{ origin: { lat: 40.7, lon: -74 }, budgetMinutes: 120 },
]) {
	const response = await fetch(base, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(query),
	});
	const body = await response.json();
	errors.push({ query, status: response.status, body });
	assert.equal(response.status, 400);
}
await writeFile(
	resolve(output, "report.json"),
	`${JSON.stringify({ config, samples, errors, repeatCountsIdentical: true, publicApiCalls: 0, coverageVerified: false }, null, 2)}\n`,
	{ flag: "wx" },
);
console.log(
	`Verified ${samples.length} live app queries, repeat counts and controlled errors: ${output}`,
);
