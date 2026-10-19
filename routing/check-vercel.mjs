import assert from "node:assert/strict";
import { mkdir, readdir, readFile, stat, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import {
	defaultQuery,
	engineConfigSchema,
	resultSchema,
} from "../src/lib/reachability.ts";
import { dataDir, manifest, root } from "./settings.mjs";

const output = join(root, ".vercel/output");
const config = JSON.parse(await readFile(join(output, "config.json"), "utf8"));
assert.ok(
	config.routes.some((r) => r.dest === "/__server"),
	"Expected fullstack server catch-all",
);
const functionDir = join(output, "functions/__server.func");
const runtime = JSON.parse(
	await readFile(join(functionDir, ".vc-config.json"), "utf8"),
);
assert.match(runtime.runtime, /^nodejs/);
let functionBytes = 0;
let functionFiles = 0;
async function inspect(path) {
	for (const entry of await readdir(path, { withFileTypes: true })) {
		const child = join(path, entry.name);
		assert.ok(
			!/\.(gph|tar|pbf|pmtiles)$/.test(entry.name) &&
				!entry.name.startsWith(".env"),
			`Data/secret file in function: ${entry.name}`,
		);
		if (entry.isDirectory()) await inspect(child);
		else {
			functionBytes += (await stat(child)).size;
			functionFiles++;
		}
	}
}
await inspect(functionDir);
const handler = (
	await import(pathToFileURL(join(functionDir, "index.mjs")).href)
).default;
const healthResponse = await handler.fetch(
	new Request("http://localhost/api/reachability"),
);
assert.equal(healthResponse.status, 200);
const health = engineConfigSchema.parse(await healthResponse.json());
assert.equal(health.health, "ready");
assert.equal(health.graphVersion, manifest.id);
const response = await handler.fetch(
	new Request("http://localhost/api/reachability", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(defaultQuery),
	}),
);
assert.equal(response.status, 200);
const result = resultSchema.parse(await response.json());
assert.equal(result.metadata.graphVersion, manifest.id);
assert.equal(result.metadata.engineVersion, manifest.engineVersion);
const report = {
	checkedAt: new Date().toISOString(),
	runtime,
	functionBytes,
	functionFiles,
	config,
	health,
	result: {
		id: result.id,
		query: result.query,
		metadata: result.metadata,
		featureCount: result.contours.features.length,
	},
	limitations:
		"Invoked generated Vercel handler locally with the local graph service. Cloud deployment, Linux native bindings, provider credentials, and worldwide routing were not verified.",
};
await mkdir(dataDir, { recursive: true });
await writeFile(
	join(dataDir, "vercel-verification.json"),
	JSON.stringify(report, null, 2),
);
console.log(JSON.stringify(report, null, 2));
