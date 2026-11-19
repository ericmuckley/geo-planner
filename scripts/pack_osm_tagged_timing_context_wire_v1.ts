/** Copy the sealed core, replacing only its turn field, and pack required histories. */
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
import { TURN_CONTEXT_FILES } from "./coarse_osm_turn_contexts_v1.ts";

const repo = path.resolve(import.meta.dirname, "..");
const sha = (bytes: Uint8Array) =>
	createHash("sha256").update(bytes).digest("hex");
const names = [
	...PACKED_CAR_FILES,
	"routing/cell-keys.u24",
	"routing/cell-offsets.u24",
];

async function main() {
	const began = performance.now(),
		[recipeName, pin] = process.argv.slice(2);
	assert.ok(recipeName && pin);
	const rawRecipe = await readFile(path.resolve(repo, recipeName));
	assert.equal(sha(rawRecipe), pin);
	const plan = JSON.parse(rawRecipe.toString("utf8"));
	assert.equal(
		plan.output,
		"data/coarse-quality/us-osm-tagged-timing-context-wire-v1",
	);
	assert.equal(plan.maxOwnedBytes, 67108864);
	assert.ok(
		plan.priorReserveBytes +
			plan.newClosedAllocationBytes +
			plan.metadataScratchReserveBytes +
			plan.maxOwnedBytes <
			72 * 1024 ** 3,
	);
	for (const [name, expected] of Object.entries(plan.bindings))
		assert.equal(sha(await readFile(path.join(repo, name))), expected, name);
	const parent = JSON.parse(
		await readFile(path.join(repo, plan.sourceCoreClosed), "utf8"),
	);
	const records = JSON.parse(
		await readFile(path.join(repo, plan.sourceRecordsClosed), "utf8"),
	);
	assert.equal(parent.root, plan.sourceCore);
	assert.equal(records.root, plan.sourceRecords);
	const sourceManifestRaw = await readFile(
		path.join(repo, plan.sourceCore, "manifest.json"),
	);
	assert.equal(sha(sourceManifestRaw), parent.roster["manifest.json"].sha256);
	const sourceManifest = JSON.parse(sourceManifestRaw.toString("utf8"));
	assert.equal(
		sourceManifest.format,
		"packed-integer-delta-byteplanes-gzip-v1",
	);
	assert.deepEqual(
		Object.keys(sourceManifest.fields).sort(),
		[...names].sort(),
	);
	const recordRaw = await readFile(
		path.join(repo, plan.sourceRecords, "report.json"),
	);
	assert.equal(sha(recordRaw), records.roster["report.json"].sha256);
	const recordReport = JSON.parse(recordRaw.toString("utf8"));
	assert.equal(
		recordReport.status,
		"multiway_static_bans_and_single_via_context_records_source_audited",
	);
	assert.equal(recordReport.requiresTurnContextSearch, true);
	const root = path.join(repo, plan.output);
	await mkdir(root);
	await writeFile(path.join(root, "execution-plan.json"), rawRecipe, {
		flag: "wx",
	});
	for (const kind of ["core", "context"]) {
		await mkdir(path.join(root, kind));
		await mkdir(path.join(root, kind, "fields"));
	}
	let written = rawRecipe.length;
	const check = () => {
		assert.ok(performance.now() - began < 120000, "Context wire host deadline");
		assert.ok(process.memoryUsage().rss < 4 * 1024 ** 3, "Context wire RSS");
		assert.ok(written <= plan.maxOwnedBytes, "Context wire owned bytes");
	};
	const bound = async (
		source: string,
		name: string,
		expected: { bytes: number; sha256: string },
	) => {
		const filename = path.join(repo, source, name),
			stat = await lstat(filename);
		assert.ok(
			stat.isFile() &&
				!stat.isSymbolicLink() &&
				stat.size === expected.bytes &&
				stat.size <= 67108864,
		);
		const raw = await readFile(filename);
		assert.equal(sha(raw), expected.sha256);
		return raw;
	};
	const put = async (name: string, raw: Uint8Array) => {
		written += raw.length;
		check();
		await writeFile(path.join(root, name), raw, { flag: "wx" });
	};
	try {
		const coreFields: Record<string, object> = {};
		let copied = 0,
			coreCompressed = 0,
			coreRaw = 0;
		for (const name of names) {
			const field = sourceManifest.fields[name];
			assert.equal(field.file, `fields/${path.basename(name)}.gz`);
			const original = await bound(
				plan.sourceCore,
				field.file,
				parent.roster[field.file],
			);
			assert.equal(original.length, field.compressedBytes);
			assert.equal(sha(original), field.compressedSha256);
			let packed = original,
				next = { ...field };
			if (name === "routing/forbidden-turns.u24") {
				const raw = await bound(
					plan.sourceRecords,
					`records/${name}`,
					records.roster[`records/${name}`],
				);
				const layout = packedWordLayout(name);
				packed = gzipSync(encodePackedWords(raw, layout), { level: 9 });
				assert.deepEqual(
					decodePackedWords(
						gunzipSync(packed, { maxOutputLength: raw.length }),
						layout,
					),
					Uint8Array.from(raw),
				);
				next = {
					...layout,
					file: field.file,
					rawBytes: raw.length,
					rawSha256: sha(raw),
					compressedBytes: packed.length,
					compressedSha256: sha(packed),
				};
			} else copied++;
			await put(`core/${field.file}`, packed);
			coreFields[name] = next;
			coreCompressed += packed.length;
			coreRaw += next.rawBytes;
		}
		assert.equal(copied, 12);
		const coreManifest = Buffer.from(
			`${JSON.stringify({ format: sourceManifest.format, fields: coreFields, requiresTurnContextSearch: true, contextRecordsReportSha256: sha(recordRaw) }, null, 2)}\n`,
		);
		await put("core/manifest.json", coreManifest);
		const contextFields: Record<string, object> = {};
		let contextRaw = 0,
			contextCompressed = 0;
		for (const name of TURN_CONTEXT_FILES) {
			const raw = await bound(
				plan.sourceRecords,
				`records/${name}`,
				records.roster[`records/${name}`],
			);
			const packed = gzipSync(raw, { level: 9 }),
				file = `fields/${path.basename(name)}.gz`;
			assert.deepEqual(
				gunzipSync(packed, { maxOutputLength: Math.max(raw.length, 1) }),
				raw,
			);
			await put(`context/${file}`, packed);
			contextFields[name] = {
				file,
				rawBytes: raw.length,
				rawSha256: sha(raw),
				compressedBytes: packed.length,
				compressedSha256: sha(packed),
			};
			contextRaw += raw.length;
			contextCompressed += packed.length;
		}
		assert.equal(contextRaw, recordReport.contextRuntimeBackingBytes);
		const contextManifest = Buffer.from(
			`${JSON.stringify({ format: "static-via-way-context-gzip-v1", graphCoreManifestSha256: sha(coreManifest), contextRecordsReportSha256: sha(recordRaw), graphArcCount: recordReport.retainedArcsMapped, fields: contextFields }, null, 2)}\n`,
		);
		await put("context/manifest.json", contextManifest);
		const report = {
			status: "tagged_timing_context_wire_packed_independent_audit_pending",
			recipeSha256: pin,
			copiedCoreFieldsByteIdentical: copied,
			replacedCoreFields: 1,
			coreRawBytes: coreRaw,
			coreCompressedBytes: coreCompressed,
			contextRawBytes: contextRaw,
			contextCompressedBytes: contextCompressed,
			combinedCoreAndContextCompressedBytes: coreCompressed + contextCompressed,
			coreManifestSha256: sha(coreManifest),
			contextManifestSha256: sha(contextManifest),
			hostMsIncludingBindingsCopiesPackingRoundtripsAndWrites:
				performance.now() - began,
			providerRequests: 0,
			routingQueries: 0,
			sourcePbfReads: 0,
			appActivated: false,
			scope:
				"Host storage only. Twelve compressed core fields are exact sealed copies; only the independently audited static source-supported plus multi-via entry turn field replaces the old entry union. The new core requires the bound context packet/search. No physical IDs, costs, flags, geometry or access data change. Independent Python bytes/actual loader/query/memory/paid-progress/accuracy/app/package/first-estimate gates remain.",
		};
		await put(
			"report.json",
			Buffer.from(`${JSON.stringify(report, null, 2)}\n`),
		);
		process.stdout.write(`${JSON.stringify(report)}\n`);
	} catch (error) {
		await writeFile(
			path.join(root, "failure.json"),
			`${JSON.stringify({ error: String(error), hostMs: performance.now() - began }, null, 2)}\n`,
			{ flag: "wx" },
		);
		throw error;
	}
}
await main();
