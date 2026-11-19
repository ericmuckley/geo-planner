import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import {
	mkdir,
	mkdtemp,
	readFile,
	rm,
	symlink,
	unlink,
	writeFile,
} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { gzipSync } from "node:zlib";
import { loadTurnContexts } from "./coarse_osm_context_loader_v1.ts";
import { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import { fixture } from "./coarse_osm_packed_fixture_v1.ts";
import { contextFiles } from "./coarse_osm_turn_context_fixture_v1.ts";
import { TURN_CONTEXT_FILES } from "./coarse_osm_turn_contexts_v1.ts";

const sha = (bytes: Uint8Array) =>
	createHash("sha256").update(bytes).digest("hex");
type Field = {
	file: string;
	rawBytes: number;
	rawSha256: string;
	compressedBytes: number;
	compressedSha256: string;
};
async function prepared(t: { after: (cleanup: () => Promise<void>) => void }) {
	const root = await mkdtemp(
		path.join(os.tmpdir(), "geo-planner-context-loader-"),
	);
	t.after(() => rm(root, { recursive: true, force: true }));
	const auxRoot = path.join(root, "context"),
		coreRoot = path.join(root, "core");
	await mkdir(path.join(auxRoot, "fields"), { recursive: true });
	await mkdir(coreRoot);
	const arcs = [
		{ tail: 0, head: 1, way: 1 },
		{ tail: 1, head: 2, way: 2 },
		{ tail: 2, head: 3, way: 3 },
	];
	const files = contextFiles(arcs, [[1, 2, 3]]),
		fields: Record<string, Field> = {};
	for (const name of TURN_CONTEXT_FILES) {
		const raw = files[name],
			compressed = gzipSync(raw),
			file = `fields/${path.basename(name)}.gz`;
		await writeFile(path.join(auxRoot, file), compressed);
		fields[name] = {
			file,
			rawBytes: raw.length,
			rawSha256: sha(raw),
			compressedBytes: compressed.length,
			compressedSha256: sha(compressed),
		};
	}
	const core = {
		format: "packed-integer-delta-byteplanes-gzip-v1",
		requiresTurnContextSearch: true,
		contextRecordsReportSha256: "a".repeat(64),
	};
	const packet = {
		format: "static-via-way-context-gzip-v1",
		graphCoreManifestSha256: "",
		contextRecordsReportSha256: core.contextRecordsReportSha256,
		graphArcCount: 3,
		fields,
	};
	const graph = new PackedCarGraph(
		fixture(4, [
			[0, 1, 100],
			[1, 2, 100],
			[2, 3, 100],
		]),
	);
	async function save() {
		const coreBytes = Buffer.from(JSON.stringify(core));
		await writeFile(path.join(coreRoot, "manifest.json"), coreBytes);
		packet.graphCoreManifestSha256 = sha(coreBytes);
		const bytes = Buffer.from(JSON.stringify(packet));
		await writeFile(path.join(auxRoot, "manifest.json"), bytes);
		return { corePin: sha(coreBytes), pin: sha(bytes) };
	}
	async function load() {
		const p = await save();
		return loadTurnContexts(auxRoot, p.pin, coreRoot, p.corePin, graph);
	}
	return { root, auxRoot, coreRoot, core, packet, save, load, graph };
}

test("context packet owns exact buffers and enforces prohibited completion", async (t) => {
	const p = await prepared(t),
		result = await p.load();
	assert.equal(result.retainedDataBackingBufferBytes, result.decodedBytes);
	const state = result.contexts.nextState(0, 1);
	assert.equal(state, 3);
	assert.equal(result.contexts.nextState(state as number, 2), null);
});
test("context packet refuses wrong core, source report and arc domain", async (t) => {
	const p = await prepared(t),
		pins = await p.save();
	await assert.rejects(
		loadTurnContexts(p.auxRoot, pins.pin, p.coreRoot, "0".repeat(64), p.graph),
	);
	p.packet.contextRecordsReportSha256 = "b".repeat(64);
	await assert.rejects(p.load());
	p.packet.contextRecordsReportSha256 = p.core.contextRecordsReportSha256;
	p.packet.graphArcCount++;
	await assert.rejects(p.load());
	p.packet.graphArcCount--;
	p.core.requiresTurnContextSearch = false;
	await assert.rejects(p.load());
});
test("context packet refuses traversal, field roster, size and raw hash drift", async (t) => {
	const p = await prepared(t),
		key = TURN_CONTEXT_FILES[0],
		original = { ...p.packet.fields[key] };
	for (const change of [
		{ file: "../outside" },
		{ rawBytes: 16777217 },
		{ rawSha256: "0".repeat(64) },
	]) {
		p.packet.fields[key] = { ...original, ...change };
		await assert.rejects(p.load());
	}
	p.packet.fields[key] = original;
	delete p.packet.fields[key];
	await assert.rejects(p.load());
});
test("context packet refuses compressed drift, oversized inflation and field symlinks", async (t) => {
	const p = await prepared(t),
		field = p.packet.fields[TURN_CONTEXT_FILES[0]],
		filename = path.join(p.auxRoot, field.file);
	const original = await readFile(filename),
		broken = Buffer.from(original);
	broken[0] ^= 1;
	await writeFile(filename, broken);
	await assert.rejects(p.load());
	const oversized = gzipSync(new Uint8Array(100000));
	field.compressedBytes = oversized.length;
	field.compressedSha256 = sha(oversized);
	await writeFile(filename, oversized);
	await assert.rejects(p.load());
	await writeFile(path.join(p.root, "outside.gz"), oversized);
	await unlink(filename);
	await symlink(path.join(p.root, "outside.gz"), filename);
	await assert.rejects(p.load());
});
