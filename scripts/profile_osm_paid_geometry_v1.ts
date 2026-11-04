/** Fresh-process host load/search probe of the compressed national candidate. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { loadPackedCar } from "./coarse_osm_packed_loader_v1.ts";
import { loadPaidGeometry } from "./coarse_osm_paid_geometry_loader_v1.ts";
import { searchPackedCar } from "./coarse_osm_packed_search_v1.ts";

const repo = path.resolve(import.meta.dirname, "..");
const source = "data/coarse-quality/us-osm-car-wire-codec-v1";
const output = "data/coarse-quality/us-osm-car-paid-geometry-profile-v1";
const sha = (bytes: Uint8Array) =>
	createHash("sha256").update(bytes).digest("hex");

async function main(): Promise<void> {
	const began = performance.now();
	const [recipeName, pin] = process.argv.slice(2);
	assert.ok(
		recipeName && pin && global.gc,
		"Frozen recipe, SHA and --expose-gc required",
	);
	const recipe = await readFile(path.resolve(repo, recipeName));
	assert.equal(sha(recipe), pin);
	const plan = JSON.parse(recipe.toString("utf8"));
	assert.equal(plan.source, source);
	assert.equal(plan.output, output);
	assert.equal(
		plan.geometrySource,
		"data/coarse-quality/us-osm-car-paid-geometry-codec-v1",
	);
	for (const [name, expected] of Object.entries(plan.bindings)) {
		assert.ok(name.startsWith("scripts/") || name.startsWith("docs/evidence/"));
		assert.equal(sha(await readFile(path.join(repo, name))), expected);
	}
	const root = path.join(repo, output);
	await mkdir(root);
	await writeFile(path.join(root, "execution-plan.json"), recipe, {
		flag: "wx",
	});
	const check = () =>
		assert.ok(performance.now() - began < 120_000, "Codec profile deadline");
	try {
		const reference = JSON.parse(
			(await readFile(path.join(repo, plan.queryReference))).toString("utf8"),
		);
		assert.equal(reference.queries.length, 4);
		global.gc();
		const baseline = process.memoryUsage();
		const firstBegan = performance.now();
		const loaded = await loadPackedCar(
			path.join(repo, source),
			plan.manifestSha256,
			check,
		);
		const paid = await loadPaidGeometry(
			path.join(repo, plan.geometrySource),
			plan.geometryManifestSha256,
			loaded.graph,
			check,
		);
		global.gc();
		const retained = process.memoryUsage();
		const queries = [];
		let firstLoadAndQueryMs = 0;
		for (const value of reference.queries) {
			const start = performance.now();
			const result = searchPackedCar(
				loaded.graph,
				{ vertex: value.sourceVertex },
				{ vertex: value.targetVertex },
				{ check },
			);
			assert.equal(
				result.ticks,
				value.ticks,
				`Original national physical query ${value.index}`,
			);
			global.gc();
			if (!queries.length) firstLoadAndQueryMs = performance.now() - firstBegan;
			queries.push({
				index: value.index,
				sourceVertex: value.sourceVertex,
				targetVertex: value.targetVertex,
				...result,
				hostQueryMsIncludingPostQueryGc: performance.now() - start,
			});
		}
		global.gc();
		const report = {
			status: "host_compressed_core_paid_geometry_and_original_queries_passed",
			recipeSha256: pin,
			vertices: loaded.graph.vertices,
			arcs: loaded.graph.arcs,
			spatialCells: loaded.keys.length,
			compressedBytes: loaded.compressedBytes + paid.compressedBytes,
			geometryCompressedBytes: paid.compressedBytes,
			geometryDecodedBytes: paid.decodedBytes,
			curvedSpans: paid.geometry.curvedSpans,
			longSpans: paid.geometry.longSpans,
			decodedWireBytes: loaded.decodedBytes + paid.decodedBytes,
			retainedDataBackingBufferBytes:
				loaded.retainedDataBackingBufferBytes +
				paid.retainedDataBackingBufferBytes,
			loadMsIncludingReadsHashesInflateDecodeAndValidation:
				loaded.loadMsIncludingReadsHashesInflateDecodeAndValidation +
				paid.loadMsIncludingReadsHashesInflateDecodeAndValidation,
			hostFirstLoadAndQueryMsIncludingGc: firstLoadAndQueryMs,
			baseline,
			retained,
			afterQueries: process.memoryUsage(),
			queries,
			hostTotalMs: performance.now() - began,
			scope:
				"Host-only cold process after module/config loading, core routing + anchor index + paid geometry only. Reads/hashes/inflate/decode/validation and first vertex-pair query include GC. No arbitrary-coordinate snap, display/geography, full app/packaged estimate, protected Linux or Vercel admission.",
			modelChanged: false,
		};
		await writeFile(
			path.join(root, "report.json"),
			`${JSON.stringify(report, null, 2)}\n`,
			{ flag: "wx" },
		);
		process.stdout.write(`${JSON.stringify(report)}\n`);
	} catch (error) {
		await writeFile(
			path.join(root, "failure.json"),
			`${JSON.stringify({ error: String(error), hostMs: performance.now() - began })}\n`,
			{ flag: "wx" },
		);
		throw error;
	}
}

await main();
