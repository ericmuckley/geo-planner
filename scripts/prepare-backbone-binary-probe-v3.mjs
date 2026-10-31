// Preserve v2; enable emitted server assets that Vite otherwise discards.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { sha256 } from "./backbone-binary-format.mjs";

const planSha256 =
	"54d29cdf431822f7253f3e7258289dcfc8e7bec852075f28ea48745d9ce562e5";
const raw = await readFile(
	"docs/evidence/coarse-backbone-binary-2026-10-25/plan-v3.json",
);
assert.equal(sha256(raw), planSha256);
const plan = JSON.parse(raw);
for (const [path, hash] of Object.entries({
	...plan.inputs,
	...plan.runtimeArrayInputs,
}))
	assert.equal(sha256(await readFile(path)), hash, path);
const [output] = process.argv.slice(2);
assert.ok(output);
execFileSync(
	process.execPath,
	["scripts/prepare-backbone-binary-probe-v2.mjs", output],
	{ stdio: "pipe" },
);
const configPath = join(output, "vite.config.ts");
const config = await readFile(configPath, "utf8");
assert.ok(config.includes("const config = defineConfig({"));
await writeFile(
	configPath,
	config.replace(
		"const config = defineConfig({",
		"const config = defineConfig({\n environments:{nitro:{build:{emitAssets:true}}},",
	),
);
const manifestPath = join(output, "probe/manifest.json");
const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
manifest.planSha256 = planSha256;
await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
const recordPath = join(output, "probe.json");
const record = JSON.parse(await readFile(recordPath, "utf8"));
record.previousPlanSha256 = record.planSha256;
record.planSha256 = planSha256;
record.container = manifest;
record.toolSources["scripts/prepare-backbone-binary-probe-v3.mjs"] = sha256(
	await readFile("scripts/prepare-backbone-binary-probe-v3.mjs"),
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
