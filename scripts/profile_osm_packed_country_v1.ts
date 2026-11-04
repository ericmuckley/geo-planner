/** Host footprint/compression/search probe; no app or source construction. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { lstat, mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { gzipSync } from "node:zlib";
import {
	PACKED_CAR_FILES,
	type PackedCarFiles,
	PackedCarGraph,
} from "./coarse_osm_packed_car_v1.ts";
import { searchPackedCar } from "./coarse_osm_packed_search_v1.ts";

const repo = path.resolve(import.meta.dirname, "..");
const source = "data/coarse-quality/us-osm-car-packed-country-run-v1";
const output = "data/coarse-quality/us-osm-car-packed-country-profile-v1";
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
	for (const [name, expected] of Object.entries(plan.bindings)) {
		assert.ok(name.startsWith("scripts/") || name.startsWith("docs/evidence/"));
		assert.equal(sha(await readFile(path.join(repo, name))), expected);
	}
	const closed = JSON.parse(
		(await readFile(path.join(repo, plan.closedRecord))).toString("utf8"),
	);
	assert.equal(closed.root, source);
	const root = path.join(repo, output);
	await mkdir(root);
	await writeFile(path.join(root, "execution-plan.json"), recipe, {
		flag: "wx",
	});
	const check = () =>
		assert.ok(performance.now() - began < 120_000, "Host profile deadline");
	const artifacts: Record<string, { bytes: number; sha256: string }> = {};
	try {
		global.gc();
		const baseline = process.memoryUsage();
		const loadBegan = performance.now();
		const files = {} as PackedCarFiles;
		let wireBytes = 0;
		let compressedBytes = 0;
		let compressionMs = 0;
		for (const name of PACKED_CAR_FILES) {
			const expected = closed.roster[name];
			const filename = path.join(repo, source, name);
			const stat = await lstat(filename);
			assert.ok(
				stat.isFile() && !stat.isSymbolicLink() && stat.size <= 67_108_864,
			);
			const raw = await readFile(filename);
			assert.equal(raw.length, expected.bytes);
			assert.equal(sha(raw), expected.sha256);
			files[name] = Uint8Array.from(raw);
			wireBytes += raw.length;
			assert.ok(wireBytes <= 201_326_592);
			const start = performance.now();
			const compressed = gzipSync(raw, { level: 9 });
			compressionMs += performance.now() - start;
			compressedBytes += compressed.length;
			assert.ok(compressedBytes <= 201_326_592);
			const destination = `${path.basename(name)}.gz`;
			await writeFile(path.join(root, destination), compressed, { flag: "wx" });
			artifacts[destination] = {
				bytes: compressed.length,
				sha256: sha(compressed),
			};
			check();
		}
		const readHashCopyAndCompressionMs = performance.now() - loadBegan;
		const validateBegan = performance.now();
		const graph = new PackedCarGraph(files);
		const readerValidationMs = performance.now() - validateBegan;
		global.gc();
		const retained = process.memoryUsage();
		const queries = [];
		let seed = 20261102;
		const random = () => {
			seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
			return seed % graph.vertices;
		};
		for (let index = 0; index < 4; index++) {
			const sourceVertex = random();
			const targetVertex = random();
			const start = performance.now();
			const result = searchPackedCar(
				graph,
				{ vertex: sourceVertex },
				{ vertex: targetVertex },
				{ check },
			);
			global.gc();
			queries.push({
				index,
				sourceVertex,
				targetVertex,
				...result,
				hostQueryMsIncludingPostQueryGc: performance.now() - start,
			});
			check();
		}
		global.gc();
		const afterQueries = process.memoryUsage();
		const report = {
			status: "host_national_packed_candidate_profile_complete",
			recipeSha256: pin,
			vertices: graph.vertices,
			arcs: graph.arcs,
			wireBytes,
			compressedBytes,
			retainedBackingBufferBytes: graph.retainedBackingBufferBytes,
			baseline,
			retained,
			afterQueries,
			compressionMs,
			readHashCopyAndCompressionMs,
			readerValidationMs,
			queries,
			hostTotalMs: performance.now() - began,
			scope:
				"Host isolated reader/search/compression only, no arbitrary-coordinate snapping, display/geography, app loader or function bundle. Hash/copy/compression and reader validation are separate from query timing, which includes post-query GC. Seeded vertices have no reachability/accuracy expectations; empty/unreachable cases are preserved. No protected Linux or app/Vercel admission.",
			modelChanged: false,
		};
		await writeFile(
			path.join(root, "artifacts.json"),
			`${JSON.stringify(artifacts, null, 2)}\n`,
			{ flag: "wx" },
		);
		await writeFile(
			path.join(root, "report.json"),
			`${JSON.stringify(report, null, 2)}\n`,
			{ flag: "wx" },
		);
		process.stdout.write(`${JSON.stringify(report)}\n`);
	} catch (error) {
		await writeFile(
			path.join(root, "failure.json"),
			`${JSON.stringify({ error: String(error), hostMs: performance.now() - began, partialArtifacts: artifacts })}\n`,
			{ flag: "wx" },
		);
		throw error;
	}
}

await main();
