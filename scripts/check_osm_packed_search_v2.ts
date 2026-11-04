/** Single-use functional check of the closed captured packed candidate. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { lstat, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import {
	PACKED_CAR_FILES,
	type PackedCarFiles,
	PackedCarGraph,
} from "./coarse_osm_packed_car_v1.ts";
import {
	type PackedPoint,
	searchPackedCar,
} from "./coarse_osm_packed_search_v1.ts";

const sha = (bytes: Uint8Array) =>
	createHash("sha256").update(bytes).digest("hex");
const repo = path.resolve(import.meta.dirname, "..");
const source = "data/coarse-quality/us-osm-car-packed-capture-v1";

async function main(): Promise<void> {
	const began = performance.now();
	const [recipeName, expectedPin] = process.argv.slice(2);
	assert.ok(recipeName && expectedPin, "Supply frozen recipe and SHA256");
	const recipeBytes = await readFile(path.resolve(repo, recipeName));
	assert.equal(sha(recipeBytes), expectedPin);
	const plan = JSON.parse(recipeBytes.toString("utf8"));
	assert.equal(plan.source, source);
	assert.equal(
		plan.output,
		"docs/evidence/coarse-osm-car-capacity-2026-11-01/packed-search-runtime-v2.json",
	);
	for (const [name, pin] of Object.entries(plan.codeBindings)) {
		assert.ok(name.startsWith("scripts/"));
		assert.equal(sha(await readFile(path.join(repo, name))), pin);
	}
	for (const [name, pin] of Object.entries(plan.evidenceBindings)) {
		assert.ok(
			name.startsWith("docs/evidence/coarse-osm-car-capacity-2026-11-01/"),
		);
		assert.equal(sha(await readFile(path.join(repo, name))), pin);
	}
	const closed = JSON.parse(
		(await readFile(path.join(repo, plan.closedRecord))).toString("utf8"),
	);
	assert.equal(closed.root, source);
	let inputBytes = 0;
	async function boundFile(name: string): Promise<Uint8Array> {
		const pin = closed.roster[name];
		assert.ok(pin && !name.includes(".."));
		const filename = path.join(repo, source, name);
		const stat = await lstat(filename);
		assert.ok(
			stat.isFile() && !stat.isSymbolicLink() && stat.size <= 4_194_304,
		);
		inputBytes += stat.size;
		assert.ok(inputBytes <= 8_388_608);
		const bytes = await readFile(filename);
		assert.equal(bytes.length, pin.bytes);
		assert.equal(sha(bytes), pin.sha256);
		// Keep exactly-sized ownership instead of retaining a pooled Buffer slab.
		return Uint8Array.from(bytes);
	}
	const decode = (bytes: Uint8Array) =>
		JSON.parse(new TextDecoder().decode(bytes));
	const artifacts = decode(await boundFile("artifacts.json"));
	assert.deepEqual(Object.keys(artifacts).sort(), [...PACKED_CAR_FILES].sort());
	const files = {} as PackedCarFiles;
	let wireBytes = 0;
	for (const name of PACKED_CAR_FILES) {
		files[name] = await boundFile(name);
		wireBytes += files[name].byteLength;
		assert.equal(files[name].length, artifacts[name].bytes);
		assert.equal(sha(files[name]), artifacts[name].sha256);
	}
	const fixtures: {
		source: PackedPoint;
		target: PackedPoint;
		directTicks: number | null;
		expectedTicks: number | null;
	}[] = decode(await boundFile("query-fixtures.json"));
	assert.equal(fixtures.length, 82);
	const loadBegan = performance.now();
	const graph = new PackedCarGraph(files);
	const readerValidationMs = performance.now() - loadBegan;
	const checks = [];
	let settles = 0;
	let unreachable = 0;
	let partialEndpoints = 0;
	let maxSearchBufferBytes = 0;
	const searchBegan = performance.now();
	for (const [index, fixture] of fixtures.entries()) {
		if ("partials" in fixture.source) partialEndpoints++;
		if ("partials" in fixture.target) partialEndpoints++;
		const result = searchPackedCar(graph, fixture.source, fixture.target, {
			check: () => assert.ok(performance.now() - began < 30_000),
		});
		const ticks =
			fixture.directTicks === null
				? result.ticks
				: Math.min(result.ticks ?? Infinity, fixture.directTicks);
		assert.equal(
			ticks,
			fixture.expectedTicks,
			`Original captured query ${index}`,
		);
		if (ticks === null) unreachable++;
		settles += result.settles;
		maxSearchBufferBytes = Math.max(
			maxSearchBufferBytes,
			result.searchBufferBytes,
		);
		checks.push({ index, ticks, settles: result.settles });
	}
	const allQueryChecksMs = performance.now() - searchBegan;
	assert.equal(unreachable, 14);
	assert.equal(partialEndpoints, 20);
	assert.ok(maxSearchBufferBytes <= 67_108_864);
	const result = {
		status: "all_original_captured_packed_search_queries_exact",
		recipeSha256: expectedPin,
		vertices: graph.vertices,
		arcs: graph.arcs,
		wireBytes,
		retainedBackingBufferBytes: graph.retainedBackingBufferBytes,
		maxSearchBufferBytes,
		originalDirectionalCases: checks.length,
		unreachableCasesPreserved: unreachable,
		paidPartialEndpointsChecked: partialEndpoints,
		settles,
		readerValidationMs,
		allQueryChecksMs,
		hostMsIncludingInputHashesReaderAndQueries: performance.now() - began,
		checks,
		scope:
			"Host functional check of a captured candidate; buffers exclude JS headers, fixtures and loader staging. Not protected Linux national search, packaged first estimate, app fit or ETA accuracy.",
		modelChanged: false,
	};
	await writeFile(
		path.join(repo, plan.output),
		`${JSON.stringify(result, null, 2)}\n`,
		{ flag: "wx" },
	);
	process.stdout.write(`${JSON.stringify({ ...result, checks: undefined })}\n`);
}

await main();
