/** Offline context loader: refuse an auxiliary packet for a different core. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { lstat, readFile } from "node:fs/promises";
import path from "node:path";
import { gunzipSync } from "node:zlib";
import type { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import {
	TURN_CONTEXT_FILES,
	type TurnContextFiles,
	TurnContexts,
} from "./coarse_osm_turn_contexts_v1.ts";

const sha = (bytes: Uint8Array) =>
	createHash("sha256").update(bytes).digest("hex");
async function manifest(root: string, pin: string) {
	const filename = path.join(root, "manifest.json");
	const stat = await lstat(filename);
	assert.ok(stat.isFile() && !stat.isSymbolicLink() && stat.size <= 1048576);
	const bytes = await readFile(filename);
	assert.equal(sha(bytes), pin);
	return JSON.parse(bytes.toString("utf8"));
}

export async function loadTurnContexts(
	root: string,
	manifestSha256: string,
	coreRoot: string,
	coreManifestSha256: string,
	graph: PackedCarGraph,
	check: () => void = () => {},
) {
	const began = performance.now();
	const core = await manifest(coreRoot, coreManifestSha256);
	assert.equal(core.format, "packed-integer-delta-byteplanes-gzip-v1");
	assert.equal(core.requiresTurnContextSearch, true);
	assert.match(core.contextRecordsReportSha256, /^[a-f0-9]{64}$/);
	const packet = await manifest(root, manifestSha256);
	assert.equal(packet.format, "static-via-way-context-gzip-v1");
	assert.equal(packet.graphCoreManifestSha256, coreManifestSha256);
	assert.equal(
		packet.contextRecordsReportSha256,
		core.contextRecordsReportSha256,
	);
	assert.equal(packet.graphArcCount, graph.arcs);
	assert.deepEqual(
		Object.keys(packet.fields).sort(),
		[...TURN_CONTEXT_FILES].sort(),
	);
	let decodedBytes = 0,
		compressedBytes = 0;
	for (const name of TURN_CONTEXT_FILES) {
		const field = packet.fields[name];
		assert.equal(field.file, `fields/${path.basename(name)}.gz`);
		for (const size of [field.rawBytes, field.compressedBytes])
			assert.ok(Number.isInteger(size) && size >= 0 && size <= 16 * 1024 ** 2);
		assert.match(field.rawSha256, /^[a-f0-9]{64}$/);
		assert.match(field.compressedSha256, /^[a-f0-9]{64}$/);
		decodedBytes += field.rawBytes;
		compressedBytes += field.compressedBytes;
	}
	assert.ok(
		decodedBytes <= 16 * 1024 ** 2 && compressedBytes <= 16 * 1024 ** 2,
	);
	const files = {} as TurnContextFiles;
	for (const name of TURN_CONTEXT_FILES) {
		const field = packet.fields[name],
			filename = path.join(root, field.file);
		const stat = await lstat(filename);
		assert.ok(
			stat.isFile() &&
				!stat.isSymbolicLink() &&
				stat.size === field.compressedBytes,
		);
		const compressed = await readFile(filename);
		assert.equal(sha(compressed), field.compressedSha256);
		const raw = gunzipSync(compressed, {
			maxOutputLength: Math.max(field.rawBytes, 1),
		});
		assert.equal(raw.byteLength, field.rawBytes);
		assert.equal(sha(raw), field.rawSha256);
		files[name] = Uint8Array.from(raw);
		check();
	}
	const contexts = new TurnContexts(graph.arcs, files);
	check();
	return {
		contexts,
		decodedBytes,
		compressedBytes,
		retainedDataBackingBufferBytes: contexts.backingBytes,
		loadMsIncludingReadsHashesInflateAndValidation: performance.now() - began,
	};
}
