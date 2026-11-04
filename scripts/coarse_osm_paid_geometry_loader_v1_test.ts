import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, mkdir, writeFile, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { gzipSync } from "node:zlib";
import { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import {
	encodePackedWords,
	packedWordLayout,
} from "./coarse_osm_packed_codec_v1.ts";
import { fixture } from "./coarse_osm_packed_fixture_v1.ts";
import { PAID_GEOMETRY_FILES } from "./coarse_osm_paid_geometry_v1.ts";
import { loadPaidGeometry } from "./coarse_osm_paid_geometry_loader_v1.ts";

const sha = (bytes: Uint8Array) =>
	createHash("sha256").update(bytes).digest("hex");
type Field = {
	wordBytes: number;
	lanes: number;
	file: string;
	rawBytes: number;
	rawSha256: string;
	compressedBytes: number;
	compressedSha256: string;
};

async function prepared(t: { after: (cleanup: () => Promise<void>) => void }) {
	const root = await mkdtemp(
		path.join(os.tmpdir(), "geo-planner-paid-loader-"),
	);
	t.after(() => rm(root, { recursive: true, force: true }));
	await mkdir(path.join(root, "fields"));
	const fields: Record<string, Field> = {};
	for (const name of PAID_GEOMETRY_FILES) {
		const raw = new Uint8Array(name.endsWith("curve-offsets.u32") ? 4 : 0);
		const layout = packedWordLayout(name);
		const compressed = gzipSync(encodePackedWords(raw, layout));
		const file = `fields/${path.basename(name)}.gz`;
		await writeFile(path.join(root, file), compressed);
		fields[name] = {
			...layout,
			file,
			rawBytes: raw.length,
			rawSha256: sha(raw),
			compressedBytes: compressed.length,
			compressedSha256: sha(compressed),
		};
	}
	const manifest = {
		format: "packed-integer-delta-byteplanes-gzip-v1",
		fields,
	};
	async function save() {
		const bytes = Buffer.from(JSON.stringify(manifest));
		await writeFile(path.join(root, "manifest.json"), bytes);
		return sha(bytes);
	}
	return {
		root,
		manifest,
		save,
		graph: new PackedCarGraph(fixture(2, [[0, 1, 100]])),
	};
}

test("filesystem load owns exact decoded bytes and validates straight geometry", async (t) => {
	const p = await prepared(t);
	const loaded = await loadPaidGeometry(p.root, await p.save(), p.graph);
	assert.equal(loaded.decodedBytes, 4);
	assert.equal(loaded.retainedDataBackingBufferBytes, 4);
	assert.equal(loaded.geometry.lengthUpperMeters(0), 1000);
});

test("manifest and compressed hashes refuse drift", async (t) => {
	const p = await prepared(t);
	await assert.rejects(loadPaidGeometry(p.root, "0".repeat(64), p.graph));
	const pin = await p.save();
	const filename = path.join(
		p.root,
		p.manifest.fields[PAID_GEOMETRY_FILES[0]].file,
	);
	const raw = await readFile(filename);
	raw[0] ^= 1;
	await writeFile(filename, raw);
	await assert.rejects(loadPaidGeometry(p.root, pin, p.graph));
});

test("wrong roster, traversal, layout and decoded hash refuse", async (t) => {
	const p = await prepared(t);
	const key = PAID_GEOMETRY_FILES[0];
	const original = { ...p.manifest.fields[key] };
	for (const change of [
		{ file: "../outside" },
		{ wordBytes: 4 },
		{ rawSha256: "0".repeat(64) },
		{ rawBytes: 50331649 },
	]) {
		p.manifest.fields[key] = { ...original, ...change };
		await assert.rejects(loadPaidGeometry(p.root, await p.save(), p.graph));
	}

	p.manifest.fields[key] = original;
	delete p.manifest.fields[key];
	await assert.rejects(loadPaidGeometry(p.root, await p.save(), p.graph));
});

test("bounded inflation refuses a small declared field with larger payload", async (t) => {
	const p = await prepared(t);
	const field = p.manifest.fields["geometry/curve-offsets.u32"];
	const compressed = gzipSync(new Uint8Array(100000));
	field.compressedBytes = compressed.length;
	field.compressedSha256 = sha(compressed);
	await writeFile(path.join(p.root, field.file), compressed);
	await assert.rejects(loadPaidGeometry(p.root, await p.save(), p.graph));
});
