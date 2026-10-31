// Correct only the isolated probe's bundler registration; preserve v1 evidence.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { sha256 } from "./backbone-binary-format.mjs";

const planPath = "docs/evidence/coarse-backbone-binary-2026-10-25/plan-v2.json";
const planSha256 =
	"9017c5da08753cfb44ffb1d2fc35d69f555e00b2df9b9bb9fca8271fd3cb41cd";
const planRaw = await readFile(planPath);
assert.equal(sha256(planRaw), planSha256);
const plan = JSON.parse(planRaw);
for (const [path, hash] of Object.entries({
	...plan.inputs,
	...plan.runtimeArrayInputs,
}))
	assert.equal(sha256(await readFile(path)), hash, path);
const [output] = process.argv.slice(2);
assert.ok(output);
execFileSync(
	process.execPath,
	["scripts/prepare-backbone-binary-probe.mjs", output],
	{ stdio: "pipe" },
);
const config = await readFile("vite.config.ts", "utf8");
assert.ok(config.includes("plugins: [devtools(), nitro(),"));
const plugin = `{...backboneBinaryAsset(resolve("probe/backbone.bin")),enforce:"pre" as const,
 applyToEnvironment:(environment:{name:string})=>environment.name==="nitro"}`;
await writeFile(
	join(output, "vite.config.ts"),
	`import {resolve} from "node:path";\nimport {backboneBinaryAsset} from "./probe/backbone-binary-asset.mjs";\n${config}`.replace(
		"plugins: [devtools(), nitro(),",
		`plugins: [${plugin}, devtools(), nitro({handlers:[{route:"/api/backbone-probe",method:"get",handler:resolve("probe/handler.mjs")}]}),`,
	),
);
const manifestPath = join(output, "probe/manifest.json");
const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
manifest.planSha256 = planSha256;
assert.equal(
	manifest.sha256,
	"4d455bec6c02f3da5a189dd8bbe36b4e2da98be124cd4c45d8309f0234de4b20",
);
await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
const recordPath = join(output, "probe.json");
const record = JSON.parse(await readFile(recordPath, "utf8"));
record.previousPlanSha256 = record.planSha256;
record.planSha256 = planSha256;
record.container = manifest;
record.toolSources["scripts/prepare-backbone-binary-probe-v2.mjs"] = sha256(
	await readFile("scripts/prepare-backbone-binary-probe-v2.mjs"),
);
record.integrationCorrection = plan.mechanism;
await writeFile(recordPath, `${JSON.stringify(record, null, 2)}\n`);
console.log(
	JSON.stringify(
		{
			output,
			container: manifest,
			graphArrays: 17,
			keptBlobs: 12,
			routingAvailable: false,
		},
		null,
		2,
	),
);
