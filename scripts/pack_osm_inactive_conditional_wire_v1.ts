/** Copy the qualified runtime wire, replace only source-audited node flags. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { lstat, mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { gunzipSync, gzipSync } from "node:zlib";
import {
	decodePackedWords,
	encodePackedWords,
	packedWordLayout,
} from "./coarse_osm_packed_codec_v1.ts";

const repo = path.resolve(import.meta.dirname, "..");
const sha = (raw: Uint8Array) => createHash("sha256").update(raw).digest("hex");
type Field = {
	file: string;
	rawBytes: number;
	rawSha256: string;
	compressedBytes: number;
	compressedSha256: string;
	wordBytes?: number;
	lanes?: number;
};

async function main() {
	const began = performance.now(),
		[recipe, pin] = process.argv.slice(2);
	assert.ok(recipe && pin);
	const raw = await readFile(path.resolve(repo, recipe));
	assert.equal(sha(raw), pin);
	const plan = JSON.parse(raw.toString("utf8"));
	assert.equal(
		plan.output,
		"data/coarse-quality/us-osm-inactive-conditional-wire-v1",
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
	const closed = JSON.parse(
		await readFile(path.join(repo, plan.sourceClosed), "utf8"),
	);
	assert.equal(closed.root, plan.source);
	const overlay = JSON.parse(
		await readFile(path.join(repo, plan.overlayReport), "utf8"),
	);
	assert.equal(overlay.openedVertices, 1488);
	assert.equal(
		overlay.everyIndependentUnconvertedRestrictionContributorRetained,
		true,
	);
	const manifests = {} as Record<
		string,
		{
			format: string;
			fields: Record<string, Field>;
			graphCoreManifestSha256?: string;
			contextRecordsReportSha256: string;
			requiresTurnContextSearch?: boolean;
		}
	>;
	for (const kind of ["core", "context"]) {
		const name = `${kind}/manifest.json`,
			body = await readFile(path.join(repo, plan.source, name));
		assert.equal(sha(body), closed.roster[name].sha256);
		manifests[kind] = JSON.parse(body.toString("utf8"));
	}
	assert.equal(
		manifests.core.format,
		"packed-integer-delta-byteplanes-gzip-v1",
	);
	assert.equal(manifests.context.format, "static-via-way-context-gzip-v1");
	assert.equal(
		manifests.context.graphCoreManifestSha256,
		closed.roster["core/manifest.json"].sha256,
	);
	assert.equal(
		manifests.core.contextRecordsReportSha256,
		manifests.context.contextRecordsReportSha256,
	);
	assert.equal(manifests.core.requiresTurnContextSearch, true);
	const flags = await readFile(path.join(repo, plan.nodeFlags));
	assert.equal(sha(flags), overlay.artifacts["proposed-node-flags.u8"].sha256);
	const root = path.join(repo, plan.output);
	await mkdir(root);
	let written = raw.length;
	const check = () => {
		assert.ok(
			performance.now() - began < 120000 &&
				process.memoryUsage().rss < 4 * 1024 ** 3,
			"Node wire host deadline/RSS",
		);
		assert.ok(written <= plan.maxOwnedBytes, "Node wire owned cap");
	};
	const put = async (name: string, body: Uint8Array) => {
		written += body.length;
		check();
		await writeFile(path.join(root, name), body, { flag: "wx" });
	};
	await writeFile(path.join(root, "execution-plan.json"), raw, { flag: "wx" });
	try {
		let copiedCore = 0,
			copiedContext = 0;
		let coreCompressed = 0,
			contextCompressed = 0;
		for (const kind of ["core", "context"]) {
			await mkdir(path.join(root, kind));
			await mkdir(path.join(root, kind, "fields"));
			const fields: Record<string, Field> = {};
			for (const [name, meta] of Object.entries(manifests[kind].fields)) {
				assert.equal(meta.file, `fields/${path.basename(name)}.gz`);
				const relative = `${kind}/${meta.file}`,
					filename = path.join(repo, plan.source, relative),
					stat = await lstat(filename);
				assert.ok(
					stat.isFile() &&
						!stat.isSymbolicLink() &&
						stat.size === meta.compressedBytes &&
						stat.size <= 67108864,
				);
				let packed = await readFile(filename),
					next = { ...meta };
				assert.equal(sha(packed), meta.compressedSha256);
				assert.equal(sha(packed), closed.roster[relative].sha256);
				if (kind === "core" && name === "routing/node-flags.u8") {
					const layout = packedWordLayout(name);
					assert.deepEqual(
						{ wordBytes: meta.wordBytes, lanes: meta.lanes },
						layout,
					);
					assert.equal(flags.length, meta.rawBytes);
					packed = gzipSync(encodePackedWords(flags, layout), { level: 9 });
					assert.deepEqual(
						decodePackedWords(
							gunzipSync(packed, { maxOutputLength: flags.length }),
							layout,
						),
						Uint8Array.from(flags),
					);
					next = {
						...meta,
						rawSha256: sha(flags),
						compressedBytes: packed.length,
						compressedSha256: sha(packed),
					};
				} else if (kind === "core") copiedCore++;
				else copiedContext++;
				await put(relative, packed);
				fields[name] = next;
				if (kind === "core") coreCompressed += packed.length;
				else contextCompressed += packed.length;
			}
			manifests[kind] = { ...manifests[kind], fields };
		}
		assert.equal(copiedCore, 12);
		assert.equal(copiedContext, 6);
		const overlayPin = sha(await readFile(path.join(repo, plan.overlayReport)));
		const core = Buffer.from(
			`${JSON.stringify({ ...manifests.core, nodeAccessPolicyId: overlay.policy.id, nodeFlagOverlayReportSha256: overlayPin, parentCoreManifestSha256: closed.roster["core/manifest.json"].sha256 }, null, 2)}\n`,
		);
		const context = Buffer.from(
			`${JSON.stringify({ ...manifests.context, graphCoreManifestSha256: sha(core), nodeFlagOverlayReportSha256: overlayPin }, null, 2)}\n`,
		);
		await put("core/manifest.json", core);
		await put("context/manifest.json", context);
		const report = {
			status:
				"source_qualified_incomplete_node_wire_packed_independent_audit_pending",
			recipeSha256: pin,
			copiedCoreFieldsByteIdentical: copiedCore,
			copiedContextFieldsByteIdentical: copiedContext,
			replacedNodeFlagBytes: flags.length,
			coreCompressedBytes: coreCompressed,
			contextCompressedBytes: contextCompressed,
			combinedCoreAndContextCompressedBytes: coreCompressed + contextCompressed,
			coreManifestSha256: sha(core),
			contextManifestSha256: sha(context),
			sourceNodeOverlayReportSha256: overlayPin,
			requiresMatchingContextSearch: true,
			allPhysicalIdsCostsGeometryAndTurnsUnchanged: true,
			hostMsIncludingBindingsCopiesNodeFlagPackingAndRoundtrip:
				performance.now() - began,
			routingQueries: 0,
			sourcePbfReads: 0,
			providerRequests: 0,
			appActivated: false,
			scope:
				"Only the complete source-audited node-flag overlay replaces one physical packet. Twelve other core packets and all six history packets are exact sealed copies; the context manifest is rebound to the new core. Every original cost, ID and signal/reversal bit stays; direct guards and every unconverted restriction contribution retain. Independent Python byte audit and actual loader/query/access/map/accuracy/app/package/first-estimate gates remain. Host RSS/deadline is not cgroup/cloud evidence.",
		};
		await put(
			"report.json",
			Buffer.from(`${JSON.stringify(report, null, 2)}\n`),
		);
		process.stdout.write(`${JSON.stringify(report)}\n`);
	} catch (error) {
		await put(
			"failure.json",
			Buffer.from(`${JSON.stringify({ error: String(error) })}\n`),
		);
		throw error;
	}
}
await main();
