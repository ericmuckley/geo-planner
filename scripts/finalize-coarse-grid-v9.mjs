// Version-only activation of the separately qualified connector-timing artifact.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";

const evidence = "docs/evidence/coarse-path-features-2026-10-24";
const digest = (bytes) => createHash("sha256").update(bytes).digest("hex");
const load = async (name) => JSON.parse(await readFile(`${evidence}/${name}`));
const plan = await readFile(`${evidence}/candidate-plan.json`);
assert.equal(
	digest(plan),
	"5a990ab557251ef75fb98b17381c307a32679ddbd3ccf270f775e8d80baf6a81",
);
const report = await load("comparison.json");
assert.equal(report.planSha256, digest(plan));
assert.equal(report.accuracyGatesPassed, true);
assert.ok(Object.values(report.gates).every((passed) => passed === true));
const audit = await load("audit.json");
assert.equal(audit.accepted, true);
assert.equal(audit.cases, 83);
assert.equal(audit.pathSums, 166);
const bytes = await readFile(report.artifact);
assert.equal(digest(bytes), report.artifactSha256);
assert.equal(
	digest(bytes),
	"2904d0b72e4f15537abd69f5bb9cbc05358c1dacb18d041360e7df10c131b39b",
);
const physical = await load("physical.json");
assert.equal(physical.artifactSha256, digest(bytes));
assert.equal(physical.samples.length, 42);
assert.equal(physical.sampledAttachments, 10185);
const memory = await load("memory.json");
assert.equal(memory.artifactSha256, digest(bytes));
assert.ok(memory.retainedHeapAndBufferDeltaBytes <= 162238546);
assert.ok(
	memory.sweeps.every(
		(s) => s.heapGrowthBytes <= 2097152 && s.bufferGrowthBytes <= 65536,
	),
);
const packaged = await load("package-handler.json");
assert.ok(packaged.functionBytes <= 70_000_000);
assert.ok(packaged.samples[0].localHandlerMs <= 5000);
assert.equal(packaged.outboundCalls, 0);
assert.equal((await load("visual.json")).passed, true);
const candidate = JSON.parse(bytes);
assert.equal(
	candidate.version,
	"natural-earth-census-2026-connector-calibration-v1",
);
const version = "natural-earth-census-2026-grid-v9";
const finalized = Buffer.from(
	bytes
		.toString()
		.replace(`"version":"${candidate.version}"`, `"version":"${version}"`),
);
assert.equal(JSON.parse(finalized).version, version);
assert.deepEqual(JSON.parse(finalized), { ...candidate, version });
const output = "src/server/data/coarse-grid-v9.json";
await writeFile(output, finalized, { flag: "wx" });
console.log(
	JSON.stringify(
		{
			output,
			bytes: finalized.length,
			sha256: digest(finalized),
			candidateSha256: digest(bytes),
			versionOnly: true,
			activation: "local only",
		},
		null,
		2,
	),
);
