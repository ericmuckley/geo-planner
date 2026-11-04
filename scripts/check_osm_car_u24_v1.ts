/** Bounded conversion proof of the closed captured graph; no graph rebuild or routing call. */
import { createHash } from "node:crypto";
import { lstat, mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { MAX_UINT24, packUint24, Uint24View } from "./coarse_osm_u24_v1.ts";

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const source = "data/coarse-quality/us-osm-car-run-v1";
const output = "data/coarse-quality/us-osm-car-packed-v1";
const indexFields = new Set([
	"routing/offsets.u32",
	"routing/targets.u32",
	"routing/cost-overflow-arcs.u32",
	"routing/reverse-overflow-arcs.u32",
	"routing/reverse-overflow-targets.u32",
	"routing/forbidden-turns.u32",
]);
const unchangedFields = new Set([
	"routing/xy.i32",
	"routing/costs.u16",
	"routing/cost-overflow-ticks.u32",
	"routing/reverse.u8",
	"routing/node-flags.u8",
]);
const sha = (bytes: Uint8Array) =>
	createHash("sha256").update(bytes).digest("hex");
function require(valid: unknown, message: string): asserts valid {
	if (!valid) throw new Error(message);
}

async function main() {
	const began = performance.now();
	const [recipeName, pin] = process.argv.slice(2);
	require(recipeName && pin, "Supply one frozen recipe and its SHA256");
	const recipeBytes = await readFile(path.resolve(repo, recipeName));
	require(sha(recipeBytes) === pin, "Packed index recipe drift");
	const plan = JSON.parse(recipeBytes.toString("utf8"));
	require(plan.source === source &&
		plan.output === output, "Packed index exact scope");
	for (const [name, expected] of Object.entries(plan.codeBindings)) {
		require(name.startsWith("scripts/"), "Packed index code scope");
		require(sha(await readFile(path.join(repo, name))) ===
			expected, "Packed index code drift");
	}
	async function boundFile(name: string, expected: string): Promise<Buffer> {
		const target = path.join(repo, source, name);
		const stat = await lstat(target);
		require(stat.isFile() &&
			!stat.isSymbolicLink() &&
			stat.size <= 4194304, "Packed index input type/size");
		const bytes = await readFile(target);
		require(sha(bytes) === expected, "Packed index input checksum");
		return bytes;
	}
	const roster = JSON.parse(
		(await boundFile("artifacts.json", plan.artifactsSha256)).toString("utf8"),
	);
	const original = JSON.parse(
		(await boundFile("report.json", plan.reportSha256)).toString("utf8"),
	);
	require(original.payload.vertices <= MAX_UINT24 &&
		original.payload.arcs <= MAX_UINT24, "Packed index domain exceeds uint24");
	require(Object.keys(roster).length ===
		indexFields.size + unchangedFields.size, "Packed index field roster");
	const retained: Uint8Array[] = [];
	const converted: { name: string; bytes: Uint8Array }[] = [];
	const artifacts: Record<string, { bytes: number; sha256: string }> = {};
	let inputBytes = 0;
	let indicesChecked = 0;
	for (const name of Object.keys(roster).sort()) {
		require(indexFields.has(name) ||
			unchangedFields.has(name), "Packed index unexpected source field");
		const raw = await boundFile(name, roster[name].sha256);
		require(raw.byteLength === roster[name].bytes, "Packed index field length");
		inputBytes += raw.byteLength;
		require(inputBytes <= 8388608, "Packed index aggregate input cap");
		let bytes: Uint8Array = raw;
		let destination = name;
		if (indexFields.has(name)) {
			require(raw.length % 4 === 0, "Packed index original word alignment");
			const values = Uint32Array.from({ length: raw.length / 4 }, (_, i) =>
				raw.readUInt32LE(4 * i),
			);
			bytes = packUint24(values);
			const view = new Uint24View(bytes);
			for (let i = 0; i < values.length; i++)
				require(view.at(i) ===
					values[i], "Packed index independent word roundtrip");
			indicesChecked += values.length;
			destination = name.replace(/\.u32$/, ".u24");
		}
		retained.push(bytes);
		converted.push({ name: destination, bytes });
		artifacts[destination] = { bytes: bytes.byteLength, sha256: sha(bytes) };
		require(performance.now() - began < 30000, "Packed index deadline");
	}
	const payloadBytes = retained.reduce(
		(sum, bytes) => sum + bytes.byteLength,
		0,
	);
	const buffers = new Set(retained.map((bytes) => bytes.buffer));
	const backingBufferBytes = [...buffers].reduce(
		(sum, buffer) => sum + buffer.byteLength,
		0,
	);
	require(inputBytes === original.payload.payloadBytes &&
		payloadBytes <= inputBytes, "Packed index complete payload accounting");
	const target = path.join(repo, output);
	await mkdir(target);
	await mkdir(path.join(target, "routing"));
	await writeFile(path.join(target, "execution-plan.json"), recipeBytes, {
		flag: "wx",
	});
	for (const item of converted)
		await writeFile(path.join(target, item.name), item.bytes, { flag: "wx" });
	await writeFile(
		path.join(target, "artifacts.json"),
		`${JSON.stringify(artifacts, null, 2)}\n`,
		{ flag: "wx" },
	);
	const report = {
		status: "passed_complete_captured_uint24_conversion",
		sourceReportSha256: plan.reportSha256,
		sourceArtifactsSha256: plan.artifactsSha256,
		vertices: original.payload.vertices,
		arcs: original.payload.arcs,
		indicesChecked,
		originalPayloadBytes: inputBytes,
		packedPayloadBytes: payloadBytes,
		savedBytes: inputBytes - payloadBytes,
		retainedBackingBufferBytes: backingBufferBytes,
		secondsIncludingInputsPackingAndExclusiveOutput:
			(performance.now() - began) / 1000,
		scope:
			"Host functional encoding check, not Linux resource qualification. All integer indices exact; costs/coordinates/native IDs unchanged. Buffer accounting excludes JS object headers, queries, snapping/geography/app/package overhead. No national extrapolation or ETA/model admission.",
		networkRequests: 0,
		applicationDbReads: 0,
		sourcePbfReads: 0,
		modelChanged: false,
	};
	await writeFile(
		path.join(target, "report.json"),
		`${JSON.stringify(report, null, 2)}\n`,
		{ flag: "wx" },
	);
	console.log(JSON.stringify(report));
}
await main();
