/** Single-use byte-preserving storage encoding of the closed spatial graph. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { lstat, mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { gunzipSync, gzipSync } from "node:zlib";
import { PACKED_CAR_FILES } from "./coarse_osm_packed_car_v1.ts";
import {
	decodePackedWords,
	encodePackedWords,
	packedWordLayout,
} from "./coarse_osm_packed_codec_v1.ts";
import { PAID_GEOMETRY_FILES } from "./coarse_osm_paid_geometry_v1.ts";

const repo = path.resolve(import.meta.dirname, "..");
const sources = {
	core: "data/coarse-quality/us-osm-car-entry-derived-spatial-v1",
	geometry: "data/coarse-quality/us-osm-car-entry-derived-geometry-v1",
} as const;
const namesByKind = {
	core: [
		...PACKED_CAR_FILES,
		"routing/cell-keys.u24",
		"routing/cell-offsets.u24",
	],
	geometry: [...PAID_GEOMETRY_FILES],
};
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
	assert.ok(plan.kind === "core" || plan.kind === "geometry");
	const kind = plan.kind as keyof typeof sources;
	const source = sources[kind],
		output = `data/coarse-quality/us-osm-car-entry-codec-${kind}-v1`;
	const names = namesByKind[kind];
	assert.equal(plan.source, source);
	assert.equal(plan.output, output);
	assert.ok(
		plan.priorReserveBytes +
			plan.newClosedAllocationBytes +
			plan.metadataScratchReserveBytes +
			134217728 <
			68719476736,
	);
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
	await mkdir(path.join(root, "fields"));
	await writeFile(path.join(root, "execution-plan.json"), recipe, {
		flag: "wx",
	});
	const fields: Record<string, object> = {};
	let rawBytes = 0;
	let compressedBytes = 0;
	async function pack(name: string): Promise<void> {
		const expected = closed.roster[name];
		const filename = path.join(repo, source, name);
		const stat = await lstat(filename);
		assert.ok(
			stat.isFile() && !stat.isSymbolicLink() && stat.size <= 67_108_864,
		);
		const raw = await readFile(filename);
		assert.equal(raw.length, expected.bytes);
		assert.equal(sha(raw), expected.sha256);
		rawBytes += raw.length;
		assert.ok(rawBytes <= (kind === "core" ? 201_326_592 : 50_331_648));
		const layout = packedWordLayout(name);
		const encoded = encodePackedWords(raw, layout);
		const compressed = gzipSync(encoded, { level: 9 });
		compressedBytes += compressed.length;
		assert.ok(compressedBytes <= 125_829_120);
		const inflated = gunzipSync(compressed, {
			maxOutputLength: Math.max(raw.length, 1),
		});
		assert.deepEqual(
			decodePackedWords(inflated, layout),
			Uint8Array.from(raw),
			name,
		);
		const destination = `fields/${path.basename(name)}.gz`;
		await writeFile(path.join(root, destination), compressed, { flag: "wx" });
		fields[name] = {
			...layout,
			file: destination,
			rawBytes: raw.length,
			rawSha256: expected.sha256,
			compressedBytes: compressed.length,
			compressedSha256: sha(compressed),
		};
		assert.ok(
			performance.now() - began < 120_000,
			"Packed codec host deadline",
		);
	}
	try {
		for (const name of names) {
			await pack(name);
			global.gc();
		}
		const manifest = {
			format: "packed-integer-delta-byteplanes-gzip-v1",
			fields,
		};
		await writeFile(
			path.join(root, "manifest.json"),
			`${JSON.stringify(manifest, null, 2)}\n`,
			{ flag: "wx" },
		);
		const report = {
			status: "entry_candidate_storage_roundtripped_independent_audit_pending",
			recipeSha256: pin,
			fields: names.length,
			rawBytes,
			compressedBytes,
			compressedHeadroomToCompleteFunctionGate: 70_000_000 - compressedBytes,
			hostMsIncludingBindingsReadHashEncodingGzipRoundtripAndWrites:
				performance.now() - began,
			scope:
				"Host storage encoding only; every field roundtrips to original closed wire bytes. Independent Python decoding, actual loader, candidate load/query/geography/paid snapping/package/first-estimate/accuracy qualification still required.",
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
			`${JSON.stringify({ error: String(error), hostMs: performance.now() - began, partialFields: fields })}\n`,
			{ flag: "wx" },
		);
		throw error;
	}
}

await main();
