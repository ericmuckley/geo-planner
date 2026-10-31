// One frozen binary cost overlay; no raw source producer, queries or env input.
import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { gunzipSync, gzipSync } from "node:zlib";
import {
	replayCostAttachments,
	repriceRoadCosts,
	sourceRoadTimeFactor,
} from "../src/server/backbone-cost.ts";
import { decodeGrid } from "../src/server/coarse-data.server.ts";
import {
	decodeContainer,
	encodeContainer,
	parseContainer,
	sha256,
} from "./backbone-binary-format.mjs";
import { validateBackbone } from "./backbone-binary-validate.mjs";

const [output, expectedPlanSha256] = process.argv.slice(2);
const started = performance.now();
const planPath =
	"docs/evidence/coarse-road-time-allowance-2026-10-25/preparation-plan.json";
const planRaw = await readFile(planPath);
assert.equal(sha256(planRaw), expectedPlanSha256);
const plan = JSON.parse(planRaw);
assert.equal(resolve(output), resolve(plan.output));
assert.ok(resolve(output).startsWith(`${resolve("data/coarse-quality")}/`));
for (const [path, expected] of Object.entries(plan.inputs))
	assert.equal(sha256(await readFile(path)), expected, path);
assert.equal(sourceRoadTimeFactor, 1.1);
await mkdir(output);
await writeFile(join(output, "preparation-plan.json"), planRaw, { flag: "wx" });
const raw = await readFile(plan.binary);
const source = parseContainer(raw, plan.binarySha256);
const loaded = decodeContainer(raw, plan.binarySha256);
const base = decodeGrid(loaded.kept);
validateBackbone(loaded.graph, loaded.stats, loaded.kept);
const model = {
	graph: loaded.graph,
	base,
	originalNodes: loaded.stats.originalNodes,
};
const proofs = JSON.parse(gunzipSync(await readFile(plan.baseProofs)));
const paths = JSON.parse(gunzipSync(await readFile(plan.savedPaths)));
assert.equal(paths.length, 83);
const endpointReproduction = [];
for (const path of paths) {
	assert.equal(path.direct, null);
	assert.ok(path.edges.length);
	for (const [role, origin, node, expected] of [
		["origin", path.origin, path.edges[0].from, path.components.origin],
		[
			"destination",
			path.destination,
			path.edges.at(-1).target,
			path.components.destination,
		],
	]) {
		const replay = replayCostAttachments(model, origin);
		const seed = replay.seeds.find((s) => s.node === node);
		assert.ok(
			seed && Math.abs(seed.minutes - expected) < 1e-8,
			`${path.id}/${role} attachment mismatch`,
		);
		endpointReproduction.push({
			id: path.id,
			role,
			node,
			expectedMinutes: expected,
			reproducedMinutes: seed.minutes,
		});
	}
}
assert.equal(endpointReproduction.length, 166);
const reproduction = repriceRoadCosts(model, proofs);
const words = Buffer.alloc(base.roadDeciseconds.length * 2);
for (let i = 0; i < base.roadDeciseconds.length; i++)
	words.writeUInt16LE(base.roadDeciseconds[i], i * 2);
const oldOther = { ...loaded.kept };
delete oldOther.roadDeciseconds;
const otherKeptSha256 = sha256(JSON.stringify(oldOther));
loaded.kept.roadDeciseconds = `gzip:${gzipSync(words).toString("base64")}`;
const entries = [];
for (const entry of source.descriptor.entries.filter(
	(e) => e.kind === "graph",
)) {
	let gzip = source.payload.subarray(entry.offset, entry.offset + entry.bytes);
	let rawSha256 = entry.rawSha256;
	if (entry.name === "arcMinutes") {
		const bytes = Buffer.alloc(model.graph.arcMinutes.length * 8);
		for (let i = 0; i < model.graph.arcMinutes.length; i++)
			bytes.writeDoubleLE(model.graph.arcMinutes[i], i * 8);
		gzip = gzipSync(bytes);
		rawSha256 = sha256(bytes);
	}
	entries.push({
		name: entry.name,
		gzip,
		gzipSha256: sha256(gzip),
		rawSha256,
		rawBytes: entry.rawBytes,
		elements: entry.elements,
		typecode: entry.typecode,
	});
}
const policySha256 = sha256(await readFile(plan.policy));
const packed = encodeContainer(loaded.kept, entries, {
	...loaded.stats,
	costPolicy: {
		name: "source-road-time-allowance-v1",
		factor: sourceRoadTimeFactor,
		policySha256,
	},
});
const newOther = { ...loaded.kept };
delete newOther.roadDeciseconds;
assert.equal(sha256(JSON.stringify(newOther)), otherKeptSha256);
const changed = [];
for (let i = 0; i < source.descriptor.entries.length; i++) {
	const before = source.descriptor.entries[i],
		after = packed.descriptor.entries[i];
	assert.equal(after.name, before.name);
	assert.equal(after.rawBytes, before.rawBytes);
	if (after.gzipSha256 !== before.gzipSha256)
		changed.push(`${after.kind}/${after.name}`);
}
assert.deepEqual(changed, ["kept/roadDeciseconds", "graph/arcMinutes"]);
await writeFile(join(output, "backbone.bin"), packed.bytes, { flag: "wx" });
const manifest = {
	bytes: packed.bytes.length,
	sha256: sha256(packed.bytes),
	sourceRoadTimeFactor,
	policySha256,
};
await writeFile(
	join(output, "manifest.json"),
	`${JSON.stringify(manifest, null, 2)}\n`,
	{ flag: "wx" },
);
await writeFile(
	join(output, "control.json"),
	`${JSON.stringify({ reproduction, endpointReproduction, otherKeptSha256, changed, allOther27PayloadsExact: true }, null, 2)}\n`,
	{ flag: "wx" },
);
const report = {
	manifest,
	preparationPlanSha256: expectedPlanSha256,
	reproduction,
	endpointStatesReproduced: 166,
	changed,
	allOther27PayloadsExact: true,
	elapsedMs: performance.now() - started,
	observedRssBytes: process.memoryUsage().rss,
	routingQueries: 0,
	runtimeChanged: false,
	scope:
		"Offline one-artifact cost preparation/control; not app/cloud timing or memory. No source producer/provider/env/DB input.",
};
await writeFile(
	join(output, "report.json"),
	`${JSON.stringify(report, null, 2)}\n`,
	{ flag: "wx" },
);
console.log(JSON.stringify(report, null, 2));
