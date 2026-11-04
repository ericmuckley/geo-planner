import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import {
	mkdir,
	mkdtemp,
	readFile,
	rename,
	rm,
	symlink,
	writeFile,
} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test, { type TestContext } from "node:test";
import { gzipSync } from "node:zlib";
import {
	encodePackedWords,
	packedWordLayout,
} from "./coarse_osm_packed_codec_v1.ts";
import { fixture, words } from "./coarse_osm_packed_fixture_v1.ts";
import { loadPackedCar } from "./coarse_osm_packed_loader_v1.ts";
import { searchPackedCar } from "./coarse_osm_packed_search_v1.ts";
import { packUint24 } from "./coarse_osm_u24_v1.ts";

const sha = (bytes: Uint8Array) =>
	createHash("sha256").update(bytes).digest("hex");

async function prepared(t: TestContext) {
	const root = await mkdtemp(path.join(os.tmpdir(), "geo-packed-loader-"));
	t.after(() => rm(root, { recursive: true, force: true }));
	const fields: Record<string, Uint8Array> = fixture(
		3,
		[
			[0, 1, 1, 1],
			[1, 0, 1, 0],
			[1, 2, 1],
		],
		[4, 6, 4],
	);
	fields["routing/xy.i32"] = words(
		Array.from({ length: 3 }, () => [-1800000000, -900000000]).flat(),
		4,
		true,
	);
	fields["routing/cell-keys.u24"] = packUint24([0]);
	fields["routing/cell-offsets.u24"] = packUint24([0, 3]);
	const entries: Record<
		string,
		{
			wordBytes: number;
			lanes: number;
			file: string;
			rawBytes: number;
			rawSha256: string;
			compressedBytes: number;
			compressedSha256: string;
		}
	> = {};
	await mkdir(path.join(root, "fields"));
	for (const [name, raw] of Object.entries(fields)) {
		const layout = packedWordLayout(name);
		const compressed = gzipSync(encodePackedWords(raw, layout));
		const file = `fields/${path.basename(name)}.gz`;
		await writeFile(path.join(root, file), compressed);
		entries[name] = {
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
		fields: entries,
	};
	async function save() {
		const bytes = Buffer.from(JSON.stringify(manifest));
		await writeFile(path.join(root, "manifest.json"), bytes);
		return sha(bytes);
	}
	return { root, manifest, save };
}

test("loads independently owned words and preserves signal/one-way search", async (t) => {
	const { root, save } = await prepared(t);
	const result = await loadPackedCar(root, await save());
	assert.equal(result.graph.vertices, 3);
	assert.equal(result.keys.length, 1);
	assert.equal(
		searchPackedCar(
			result.graph,
			{ vertex: 0 },
			{ vertex: 2 },
			{ maxHeapEntries: 10 },
		).ticks,
		42,
	);
	assert.equal(
		searchPackedCar(
			result.graph,
			{ vertex: 2 },
			{ vertex: 0 },
			{ maxHeapEntries: 10 },
		).ticks,
		null,
	);
});

test("rejects manifest drift, unsafe field paths and excessive allocation", async (t) => {
	const { root, manifest, save } = await prepared(t);
	await save();
	await assert.rejects(loadPackedCar(root, "0".repeat(64)));
	manifest.fields["routing/xy.i32"].file = "../outside.gz";
	await assert.rejects(loadPackedCar(root, await save()));
	manifest.fields["routing/xy.i32"].file = "fields/xy.i32.gz";
	manifest.fields["routing/xy.i32"].rawBytes = 67_108_865;
	await assert.rejects(loadPackedCar(root, await save()));
});

test("rejects damaged compressed bytes even when their manifest hash matches", async (t) => {
	const { root, manifest, save } = await prepared(t);
	const meta = manifest.fields["routing/xy.i32"];
	const file = path.join(root, meta.file);
	const damaged = (await readFile(file)).subarray(0, 8);
	await writeFile(file, damaged);
	meta.compressedBytes = damaged.length;
	meta.compressedSha256 = sha(damaged);
	await assert.rejects(loadPackedCar(root, await save()));
});

test("rejects restored-byte checksum drift and size mismatch", async (t) => {
	const { root, manifest, save } = await prepared(t);
	const meta = manifest.fields["routing/xy.i32"];
	const original = meta.rawSha256;
	meta.rawSha256 = "0".repeat(64);
	await assert.rejects(loadPackedCar(root, await save()));
	meta.rawSha256 = original;
	meta.rawBytes--;
	await assert.rejects(loadPackedCar(root, await save()));
});

test("rejects symlink field inputs", async (t) => {
	const { root, manifest, save } = await prepared(t);
	const file = path.join(root, manifest.fields["routing/xy.i32"].file);
	await rename(file, path.join(root, "original.gz"));
	await symlink(path.join(root, "original.gz"), file);
	await assert.rejects(loadPackedCar(root, await save()));
});
