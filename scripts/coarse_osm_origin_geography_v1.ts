/** Small immutable coarse geography; no inactive grid/road model is loaded. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { lstat, readFile } from "node:fs/promises";
import path from "node:path";
import { gunzipSync } from "node:zlib";
import { prepareGeography } from "../src/server/coarse-geography.ts";
import type { OriginGeography } from "./coarse_osm_origin_connections_v1.ts";

const sha = (bytes: Uint8Array) =>
	createHash("sha256").update(bytes).digest("hex");

export async function loadOriginGeography(root: string, pin: string) {
	const began = performance.now();
	const manifestPath = path.join(root, "manifest.json");
	const state = await lstat(manifestPath);
	assert.ok(state.isFile() && !state.isSymbolicLink() && state.size < 65536);
	const bytes = await readFile(manifestPath);
	assert.equal(sha(bytes), pin);
	const manifest = JSON.parse(bytes.toString("utf8"));
	assert.equal(manifest.format, "coarse-boundary-lakes-json-gzip-v1");
	assert.equal(manifest.file, "geography.json.gz");
	assert.equal(
		manifest.sourceSha256,
		"28271c809a04cdfab41ad735ad66b29e3875179b617198b7b1d4490533439bf6",
	);
	assert.ok(
		Number.isInteger(manifest.rawBytes) &&
			manifest.rawBytes > 0 &&
			manifest.rawBytes <= 1048576,
	);
	assert.ok(
		Number.isInteger(manifest.compressedBytes) &&
			manifest.compressedBytes > 0 &&
			manifest.compressedBytes <= 1048576,
	);
	const filename = path.join(root, manifest.file);
	const stat = await lstat(filename);
	assert.ok(
		stat.isFile() &&
			!stat.isSymbolicLink() &&
			stat.size === manifest.compressedBytes,
	);
	const compressed = await readFile(filename);
	assert.equal(sha(compressed), manifest.compressedSha256);
	const raw = gunzipSync(compressed, { maxOutputLength: manifest.rawBytes });
	assert.equal(raw.length, manifest.rawBytes);
	assert.equal(sha(raw), manifest.rawSha256);
	const geography = JSON.parse(raw.toString("utf8")) as OriginGeography;
	assert.deepEqual(Object.keys(geography).sort(), [
		"boundary",
		"bounds",
		"lakes",
	]);
	assert.ok(
		Array.isArray(geography.bounds) &&
			geography.bounds.length === 4 &&
			geography.bounds.every(Number.isFinite),
	);
	assert.ok(
		geography.bounds[0] >= -180 &&
			geography.bounds[2] <= 180 &&
			geography.bounds[1] >= -90 &&
			geography.bounds[3] <= 90 &&
			geography.bounds[0] < geography.bounds[2] &&
			geography.bounds[1] < geography.bounds[3],
	);
	let points = 0;
	let rings = 0;
	for (const polygons of [geography.boundary, geography.lakes]) {
		assert.ok(Array.isArray(polygons) && polygons.length <= 1000);
		for (const polygon of polygons) {
			assert.ok(Array.isArray(polygon) && polygon.length > 0);
			for (const ring of polygon) {
				assert.ok(++rings <= 10000 && Array.isArray(ring) && ring.length >= 4);
				points += ring.length;
				assert.ok(points <= 100000);
				for (const point of ring)
					assert.ok(
						Array.isArray(point) &&
							point.length === 2 &&
							point.every(Number.isFinite) &&
							Math.abs(point[0]) <= 180 &&
							Math.abs(point[1]) <= 90,
					);
				assert.deepEqual(ring[0], ring[ring.length - 1]);
			}
		}
	}
	prepareGeography(geography);
	return {
		geography,
		points,
		rings,
		rawBytes: manifest.rawBytes as number,
		compressedBytes: manifest.compressedBytes as number,
		loadMs: performance.now() - began,
	};
}
