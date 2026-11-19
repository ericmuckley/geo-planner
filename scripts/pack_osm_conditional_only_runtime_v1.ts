/** Package the audited graph with the existing runtime codecs and loaders. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { lstat, mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { gzipSync } from "node:zlib";
import { loadTurnContexts } from "./coarse_osm_context_loader_v1.ts";
import { PACKED_CAR_FILES } from "./coarse_osm_packed_car_v1.ts";
import {
	encodePackedWords,
	packedWordLayout,
} from "./coarse_osm_packed_codec_v1.ts";
import { loadPackedCar } from "./coarse_osm_packed_loader_v1.ts";
import { PAID_GEOMETRY_FILES } from "./coarse_osm_paid_geometry_v1.ts";
import { loadPaidGeometry } from "./coarse_osm_paid_geometry_loader_v1.ts";
import { TURN_CONTEXT_FILES } from "./coarse_osm_turn_contexts_v1.ts";

const repo = path.resolve(import.meta.dirname, "..");
const sha = (bytes: Uint8Array) =>
	createHash("sha256").update(bytes).digest("hex");
const read = (name: string) => readFile(path.resolve(repo, name));
const output = "data/coarse-quality/us-osm-conditional-only-runtime-v1";
const began = performance.now();
const [recipe, pin] = process.argv.slice(2);
assert.ok(recipe && pin && global.gc);
const recipeBytes = await read(recipe);
assert.equal(sha(recipeBytes), pin);
const plan = JSON.parse(recipeBytes.toString("utf8"));
assert.equal(plan.output, output);
const outputCap = 64 * 1024 ** 2;
assert.ok(
	plan.priorReserveBytes +
		plan.newClosedAllocationBytes +
		plan.metadataScratchReserveBytes +
		outputCap <
		72 * 1024 ** 3,
);
for (const [name, digest] of Object.entries(plan.bindings))
	assert.equal(sha(await read(name)), digest, name);

const root = path.join(repo, output);
await mkdir(root);
let written = 0;
const check = () => {
	assert.ok(performance.now() - began < 180_000, "Runtime pack deadline");
	assert.ok(process.memoryUsage().rss < 4 * 1024 ** 3, "Runtime pack RSS");
	assert.ok(written <= outputCap, "Runtime pack output limit");
};
async function put(name: string, raw: Uint8Array) {
	written += raw.length;
	check();
	await writeFile(path.join(root, name), raw, { flag: "wx" });
}
const json = (value: unknown) =>
	Buffer.from(`${JSON.stringify(value, null, 2)}\n`);
await put("execution-plan.json", recipeBytes);

type Asset = { bytes: number; sha256: string };
type Closed = {
	root: string;
	roster: Record<string, Asset>;
	terminalRecord: string;
};
async function closed(
	kind: "spatial" | "geometry" | "context",
): Promise<Closed> {
	const record = JSON.parse((await read(plan.closed[kind])).toString("utf8"));
	assert.equal(record.terminalRecord, "report.json");
	return record;
}
async function source(record: Closed, name: string) {
	const asset = record.roster[name];
	assert.ok(asset && asset.bytes <= 64 * 1024 ** 2);
	const filename = path.join(repo, record.root, name);
	const stat = await lstat(filename);
	assert.ok(stat.isFile() && !stat.isSymbolicLink());
	assert.equal(stat.size, asset.bytes);
	const raw = await readFile(filename);
	assert.equal(sha(raw), asset.sha256, name);
	return raw;
}
type Kind = "core" | "geometry" | "context";
async function pack(
	kind: Kind,
	names: readonly string[],
	getSource: (name: string) => Promise<Buffer>,
	metadata: Record<string, unknown> = {},
) {
	await mkdir(path.join(root, kind, "fields"), { recursive: true });
	const fields: Record<string, object> = {};
	let rawBytes = 0;
	let compressedBytes = 0;
	for (const name of names) {
		const raw = await getSource(name);
		const layout = kind === "context" ? undefined : packedWordLayout(name);
		const encoded = layout ? encodePackedWords(raw, layout) : raw;
		const compressed = gzipSync(encoded, { level: 9 });
		const file = `fields/${path.basename(name)}.gz`;
		await put(`${kind}/${file}`, compressed);
		fields[name] = {
			...layout,
			file,
			rawBytes: raw.length,
			rawSha256: sha(raw),
			compressedBytes: compressed.length,
			compressedSha256: sha(compressed),
		};
		rawBytes += raw.length;
		compressedBytes += compressed.length;
	}
	const manifest = json({
		format:
			kind === "context"
				? "static-via-way-context-gzip-v1"
				: "packed-integer-delta-byteplanes-gzip-v1",
		fields,
		...metadata,
	});
	await put(`${kind}/manifest.json`, manifest);
	return {
		manifestSha256: sha(manifest),
		fields: names.length,
		rawBytes,
		compressedBytes,
	};
}

try {
	const [spatial, geometry, context] = await Promise.all([
		closed("spatial"),
		closed("geometry"),
		closed("context"),
	]);
	const contextReport = await source(context, "report.json");
	const history = JSON.parse(contextReport.toString("utf8"));
	assert.equal(history.requiresTurnContextSearch, true);
	assert.equal(history.retainedArcsMapped, 9853924);
	assert.equal(history.finalForbiddenUnionPairsChecked, 260017);
	const contextRecordsReportSha256 = sha(contextReport);
	const core = await pack(
		"core",
		[...PACKED_CAR_FILES, "routing/cell-keys.u24", "routing/cell-offsets.u24"],
		(name) =>
			name === "routing/forbidden-turns.u24"
				? source(context, `records/${name}`)
				: source(spatial, name),
		{ requiresTurnContextSearch: true, contextRecordsReportSha256 },
	);
	const paid = await pack("geometry", PAID_GEOMETRY_FILES, (name) =>
		source(geometry, name),
	);
	const contexts = await pack(
		"context",
		TURN_CONTEXT_FILES,
		(name) => source(context, `records/${name}`),
		{
			graphCoreManifestSha256: core.manifestSha256,
			contextRecordsReportSha256,
			graphArcCount: history.retainedArcsMapped,
		},
	);
	assert.equal(contexts.rawBytes, history.contextRuntimeBackingBytes);
	global.gc();
	const coreRoot = path.join(root, "core");
	const loaded = await loadPackedCar(coreRoot, core.manifestSha256, check);
	assert.equal(loaded.graph.arcs, 9853924);
	const loadedGeometry = await loadPaidGeometry(
		path.join(root, "geometry"),
		paid.manifestSha256,
		loaded.graph,
		check,
	);
	const loadedContexts = await loadTurnContexts(
		path.join(root, "context"),
		contexts.manifestSha256,
		coreRoot,
		core.manifestSha256,
		loaded.graph,
		check,
	);
	assert.equal(
		loadedContexts.retainedDataBackingBufferBytes,
		history.contextRuntimeBackingBytes,
	);
	const report = {
		status: "mandatory_runtime_packed_and_verified_by_existing_loaders",
		recipeSha256: pin,
		core,
		geometry: paid,
		context: contexts,
		graphArcs: loaded.graph.arcs,
		contextStates: loadedContexts.contexts.states,
		contextDataBackingBytes: loadedContexts.retainedDataBackingBufferBytes,
		combinedCompressedBytes:
			core.compressedBytes + paid.compressedBytes + contexts.compressedBytes,
		componentBackingBytes:
			loaded.retainedDataBackingBufferBytes +
			loadedGeometry.retainedDataBackingBufferBytes +
			loadedContexts.retainedDataBackingBufferBytes,
		hostMsIncludingEncodingAndLoaderVerification: performance.now() - began,
		routingQueries: 0,
		providerRequests: 0,
		appActivated: false,
	};
	await put("report.json", json(report));
	process.stdout.write(`${JSON.stringify(report)}\n`);
} catch (error) {
	await writeFile(
		path.join(root, "failure.json"),
		json({ error: String(error) }),
		{ flag: "wx" },
	);
	throw error;
}
