/** Server-side geometry loader for the offline road-engine candidate. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { lstat, readFile } from "node:fs/promises";
import path from "node:path";
import { gunzipSync } from "node:zlib";
import type { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import {
	decodePackedWords,
	packedWordLayout,
} from "./coarse_osm_packed_codec_v1.ts";
import {
	PAID_GEOMETRY_FILES,
	type PaidGeometryFiles,
	PaidRoadGeometry,
} from "./coarse_osm_paid_geometry_v1.ts";

const sha = (bytes: Uint8Array) =>
	createHash("sha256").update(bytes).digest("hex");

export async function loadPaidGeometry(
	root: string,
	manifestSha256: string,
	graph: PackedCarGraph,
	check: () => void = () => {},
) {
	const began = performance.now();
	const manifestPath = path.join(root, "manifest.json");
	const stat = await lstat(manifestPath);
	assert.ok(stat.isFile() && !stat.isSymbolicLink() && stat.size <= 1048576);
	const bytes = await readFile(manifestPath);
	assert.equal(sha(bytes), manifestSha256);
	const manifest = JSON.parse(bytes.toString("utf8"));
	assert.equal(manifest.format, "packed-integer-delta-byteplanes-gzip-v1");
	assert.deepEqual(
		Object.keys(manifest.fields).sort(),
		[...PAID_GEOMETRY_FILES].sort(),
	);
	let decodedBytes = 0;
	let compressedBytes = 0;
	for (const name of PAID_GEOMETRY_FILES) {
		const field = manifest.fields[name];
		assert.deepEqual(
			{ wordBytes: field.wordBytes, lanes: field.lanes },
			packedWordLayout(name),
		);
		assert.equal(field.file, `fields/${path.basename(name)}.gz`);
		for (const size of [field.rawBytes, field.compressedBytes])
			assert.ok(
				Number.isInteger(size) && size >= 0 && size <= 48 * 1024 * 1024,
			);
		assert.match(field.rawSha256, /^[a-f0-9]{64}$/);
		assert.match(field.compressedSha256, /^[a-f0-9]{64}$/);
		decodedBytes += field.rawBytes;
		compressedBytes += field.compressedBytes;
	}
	assert.ok(
		decodedBytes <= 48 * 1024 * 1024 && compressedBytes <= 48 * 1024 * 1024,
	);
	const files = {} as PaidGeometryFiles;
	for (const name of PAID_GEOMETRY_FILES) {
		const field = manifest.fields[name];
		const filename = path.join(root, field.file);
		const stat = await lstat(filename);
		assert.ok(
			stat.isFile() &&
				!stat.isSymbolicLink() &&
				stat.size === field.compressedBytes,
		);
		const compressed = await readFile(filename);
		assert.equal(sha(compressed), field.compressedSha256);
		const encoded = gunzipSync(compressed, {
			maxOutputLength: Math.max(field.rawBytes, 1),
		});
		assert.equal(encoded.byteLength, field.rawBytes);
		const raw = decodePackedWords(encoded, packedWordLayout(name));
		assert.equal(sha(raw), field.rawSha256);
		files[name] = raw;
		check();
	}
	const geometry = new PaidRoadGeometry(graph, files);
	check();
	return {
		geometry,
		decodedBytes,
		compressedBytes,
		retainedDataBackingBufferBytes: geometry.retainedBackingBufferBytes,
		loadMsIncludingReadsHashesInflateDecodeAndValidation:
			performance.now() - began,
	};
}
