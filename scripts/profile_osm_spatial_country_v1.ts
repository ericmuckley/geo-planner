/** Host profile of spatial routing/index bytes and unchanged physical query cases. */
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
import { Uint24View } from "./coarse_osm_u24_v1.ts";

const repo = path.resolve(import.meta.dirname, "..");
const source = "data/coarse-quality/us-osm-car-spatial-country-run-v1";
const output = "data/coarse-quality/us-osm-car-spatial-country-profile-v1";
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
		assert.ok(
			performance.now() - began < 120_000,
			"Spatial host profile deadline",
		);
	const artifacts: Record<string, { bytes: number; sha256: string }> = {};
	let inputBytes = 0;
	async function bound(name: string): Promise<Buffer> {
		const expected = closed.roster[name];
		assert.ok(expected && !name.includes(".."));
		const filename = path.join(repo, source, name);
		const stat = await lstat(filename);
		assert.ok(
			stat.isFile() && !stat.isSymbolicLink() && stat.size <= 67_108_864,
		);
		inputBytes += stat.size;
		assert.ok(inputBytes <= 268_435_456);
		const raw = await readFile(filename);
		assert.equal(raw.length, expected.bytes);
		assert.equal(sha(raw), expected.sha256);
		return raw;
	}
	try {
		// The inverse table is offline only. Keep eight mapped query indices, then
		// release its backing buffer before measuring retained runtime data.
		async function mappedCases() {
			const previous = JSON.parse(
				(await readFile(path.join(repo, plan.queryReference))).toString("utf8"),
			);
			assert.equal(previous.queries.length, 4);
			const needed = new Map<number, number>();
			for (const value of previous.queries) {
				needed.set(value.sourceVertex, -1);
				needed.set(value.targetVertex, -1);
			}
			const order = await bound("routing/new-vertex-to-old.u32");
			assert.equal(order.length % 4, 0);
			for (let vertex = 0; vertex < order.length / 4; vertex++) {
				const old = order.readUInt32LE(4 * vertex);
				if (needed.has(old)) needed.set(old, vertex);
			}
			assert.ok([...needed.values()].every((value) => value >= 0));
			return previous.queries.map(
				(value: {
					index: number;
					sourceVertex: number;
					targetVertex: number;
					ticks: number | null;
				}) => ({
					index: value.index,
					oldSourceVertex: value.sourceVertex,
					oldTargetVertex: value.targetVertex,
					sourceVertex: needed.get(value.sourceVertex) as number,
					targetVertex: needed.get(value.targetVertex) as number,
					expectedTicks: value.ticks,
				}),
			);
		}
		const cases = await mappedCases();
		global.gc();
		const baseline = process.memoryUsage();
		const files = {} as PackedCarFiles;
		let wireBytes = 0;
		let compressedBytes = 0;
		let compressionMs = 0;
		async function loadAndCompress(name: string): Promise<Uint8Array> {
			const raw = await bound(name);
			const bytes = Uint8Array.from(raw);
			const start = performance.now();
			const compressed = gzipSync(raw, { level: 9 });
			compressionMs += performance.now() - start;
			wireBytes += raw.length;
			compressedBytes += compressed.length;
			assert.ok(wireBytes <= 201_326_592 && compressedBytes <= 201_326_592);
			const nameOut = `${path.basename(name)}.gz`;
			await writeFile(path.join(root, nameOut), compressed, { flag: "wx" });
			artifacts[nameOut] = {
				bytes: compressed.length,
				sha256: sha(compressed),
			};
			check();
			return bytes;
		}
		const loadBegan = performance.now();
		for (const name of PACKED_CAR_FILES)
			files[name] = await loadAndCompress(name);
		const cellBytes = await loadAndCompress("routing/cell-keys.u24");
		const startBytes = await loadAndCompress("routing/cell-offsets.u24");
		const readHashCopyAndCompressionMs = performance.now() - loadBegan;
		const validateBegan = performance.now();
		const graph = new PackedCarGraph(files);
		const keys = new Uint24View(cellBytes);
		const starts = new Uint24View(startBytes);
		assert.equal(starts.length, keys.length + 1);
		assert.equal(starts.at(0), 0);
		assert.equal(starts.at(keys.length), graph.vertices);
		for (let i = 0; i < keys.length; i++) {
			assert.ok(
				(i === 0 || keys.at(i - 1) < keys.at(i)) &&
					starts.at(i) < starts.at(i + 1),
			);
		}
		const readerAndIndexValidationMs = performance.now() - validateBegan;
		global.gc();
		const retained = process.memoryUsage();
		const queries = [];
		for (const value of cases) {
			const start = performance.now();
			const result = searchPackedCar(
				graph,
				{ vertex: value.sourceVertex },
				{ vertex: value.targetVertex },
				{ check },
			);
			assert.equal(
				result.ticks,
				value.expectedTicks,
				`Preserved national query ${value.index}`,
			);
			global.gc();
			queries.push({
				...value,
				...result,
				hostQueryMsIncludingPostQueryGc: performance.now() - start,
			});
		}
		global.gc();
		const report = {
			status: "host_national_spatial_profile_and_original_queries_passed",
			recipeSha256: pin,
			vertices: graph.vertices,
			arcs: graph.arcs,
			spatialCells: keys.length,
			routingAndSpatialWireBytes: wireBytes,
			routingAndSpatialCompressedBytes: compressedBytes,
			coreRetainedBackingBufferBytes: graph.retainedBackingBufferBytes,
			spatialRetainedBackingBufferBytes:
				cellBytes.byteLength + startBytes.byteLength,
			retainedDataBackingBufferBytes:
				graph.retainedBackingBufferBytes +
				cellBytes.byteLength +
				startBytes.byteLength,
			baseline,
			retained,
			afterQueries: process.memoryUsage(),
			compressionMs,
			readHashCopyAndCompressionMs,
			readerAndIndexValidationMs,
			queries,
			compressedHeadroomToCompleteFunctionGate: 70_000_000 - compressedBytes,
			hostTotalMs: performance.now() - began,
			scope:
				"Host-only core routing/index profile and exactly preserved V1 physical vertex-pair cases. Offline permutation tables are released/excluded. No arbitrary-coordinate snapping, paid geometry, display/geography, packaged first estimate, full app/peak memory, protected Linux or Vercel qualification.",
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
