/** Offline server-side candidate loader; retains decoded routing/index bytes only. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { lstat, readFile } from "node:fs/promises";
import path from "node:path";
import { gunzipSync } from "node:zlib";
import {
	PACKED_CAR_FILES,
	type PackedCarFiles,
	PackedCarGraph,
} from "./coarse_osm_packed_car_v1.ts";
import {
	decodePackedWords,
	packedWordLayout,
} from "./coarse_osm_packed_codec_v1.ts";
import { Uint24View } from "./coarse_osm_u24_v1.ts";

const sha = (bytes: Uint8Array) =>
	createHash("sha256").update(bytes).digest("hex");
const names = [
	...PACKED_CAR_FILES,
	"routing/cell-keys.u24",
	"routing/cell-offsets.u24",
];

export async function loadPackedCar(
	root: string,
	manifestSha256: string,
	check: () => void = () => {},
) {
	const began = performance.now();
	const manifestPath = path.join(root, "manifest.json");
	const stat = await lstat(manifestPath);
	assert.ok(stat.isFile() && !stat.isSymbolicLink() && stat.size <= 1_048_576);
	const bytes = await readFile(manifestPath);
	assert.equal(sha(bytes), manifestSha256);
	const manifest = JSON.parse(bytes.toString("utf8"));
	assert.equal(manifest.format, "packed-integer-delta-byteplanes-gzip-v1");
	assert.deepEqual(Object.keys(manifest.fields).sort(), [...names].sort());
	let decodedBytes = 0;
	let compressedBytes = 0;
	for (const name of names) {
		const field = manifest.fields[name];
		assert.deepEqual(
			{ wordBytes: field.wordBytes, lanes: field.lanes },
			packedWordLayout(name),
		);
		assert.equal(field.file, `fields/${path.basename(name)}.gz`);
		for (const size of [field.rawBytes, field.compressedBytes])
			assert.ok(Number.isInteger(size) && size >= 0 && size <= 67_108_864);
		assert.match(field.rawSha256, /^[a-f0-9]{64}$/);
		assert.match(field.compressedSha256, /^[a-f0-9]{64}$/);
		decodedBytes += field.rawBytes;
		compressedBytes += field.compressedBytes;
	}
	assert.ok(decodedBytes <= 201_326_592 && compressedBytes <= 201_326_592);
	async function field(name: string): Promise<Uint8Array> {
		const meta = manifest.fields[name];
		const filename = path.join(root, meta.file);
		const stat = await lstat(filename);
		assert.ok(
			stat.isFile() &&
				!stat.isSymbolicLink() &&
				stat.size === meta.compressedBytes,
		);
		const compressed = await readFile(filename);
		assert.equal(sha(compressed), meta.compressedSha256);
		const encoded = gunzipSync(compressed, {
			maxOutputLength: Math.max(meta.rawBytes, 1),
		});
		assert.equal(encoded.length, meta.rawBytes);
		const raw = decodePackedWords(encoded, packedWordLayout(name));
		assert.equal(sha(raw), meta.rawSha256);
		check();
		return raw;
	}
	const files = {} as PackedCarFiles;
	for (const name of PACKED_CAR_FILES) files[name] = await field(name);
	const cellBytes = await field("routing/cell-keys.u24");
	const startBytes = await field("routing/cell-offsets.u24");
	const graph = new PackedCarGraph(files);
	const keys = new Uint24View(cellBytes);
	const starts = new Uint24View(startBytes);
	assert.equal(starts.length, keys.length + 1);
	assert.equal(starts.at(0), 0);
	assert.equal(starts.at(keys.length), graph.vertices);
	for (let i = 0; i < keys.length; i++)
		assert.ok(
			(i === 0 || keys.at(i - 1) < keys.at(i)) &&
				starts.at(i) < starts.at(i + 1),
		);
	check();
	return {
		graph,
		keys,
		starts,
		compressedBytes,
		decodedBytes,
		retainedDataBackingBufferBytes:
			graph.retainedBackingBufferBytes +
			cellBytes.byteLength +
			startBytes.byteLength,
		loadMsIncludingReadsHashesInflateDecodeAndValidation:
			performance.now() - began,
	};
}
