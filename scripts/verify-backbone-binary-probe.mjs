import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readdir, readFile, stat, writeFile } from "node:fs/promises";
import { join, relative, resolve } from "node:path";
import { parseContainer, sha256 } from "./backbone-binary-format.mjs";

const [input, output] = process.argv.slice(2);
assert.ok(input && output);
const root = resolve(input);
const destination = resolve(output);
assert.ok(
	destination.startsWith(
		`${resolve("docs/evidence/coarse-backbone-binary-2026-10-25")}/`,
	),
);
const record = JSON.parse(await readFile(join(root, "probe.json"), "utf8"));
for (const [path, hash] of Object.entries(record.toolSources))
	assert.equal(sha256(await readFile(path)), hash, path);
const source = await readFile(join(root, "probe/backbone.bin"));
const { descriptor, payload } = parseContainer(source, record.container.sha256);
const markers = descriptor.entries
	.filter((e) => e.bytes >= 96)
	.map((e) => payload.subarray(e.offset, e.offset + 96).toString("base64"));
async function files(directory) {
	const result = [];
	for (const entry of await readdir(directory, { withFileTypes: true })) {
		assert.ok(!entry.name.startsWith(".env"), entry.name);
		assert.ok(
			!/\.(zip|pbf|osm|csr|gph|pmtiles|py)$/.test(entry.name),
			entry.name,
		);
		assert.ok(!entry.isSymbolicLink(), entry.name);
		const path = join(directory, entry.name);
		if (entry.isDirectory()) result.push(...(await files(path)));
		else result.push(path);
	}
	return result;
}
const functionDir = join(root, ".vercel/output/functions/__server.func");
const paths = await files(functionDir);
const manifest = {};
let functionBytes = 0,
	binaryFiles = 0;
for (const path of paths) {
	const content = await readFile(path);
	const name = relative(functionDir, path);
	functionBytes += (await stat(path)).size;
	manifest[name] = { bytes: content.length, sha256: sha256(content) };
	if (name === "server-data/backbone.bin") {
		binaryFiles++;
		assert.equal(content.length, record.container.bytes);
		assert.equal(sha256(content), record.container.sha256);
	} else {
		assert.ok(!path.endsWith(".bin"), name);
		for (const marker of markers)
			assert.ok(!content.includes(marker), `Inline payload: ${name}`);
	}
}
assert.equal(binaryFiles, 1);
const publicPaths = await files(join(root, ".vercel/output/static"));
for (const path of publicPaths) {
	const content = await readFile(path);
	assert.ok(!path.endsWith(".bin"), path);
	assert.ok(!content.includes("GEOBBP01"), path);
	assert.ok(!content.includes("server-data/backbone.bin"), path);
	for (const marker of markers)
		assert.ok(!content.includes(marker), `Public payload: ${path}`);
}
assert.ok(!(await readdir(root)).some((name) => name.startsWith(".env")));
const packaging = {
	functionBytes,
	functionFiles: paths.length,
	integrationReserve: 4194304,
	totalWithReserve: functionBytes + 4194304,
	maximumWithReserve: 70000000,
	binaryBytes: source.length,
	binarySha256: record.container.sha256,
	binaryFiles,
	publicFiles: publicPaths.length,
	all29PayloadsCompared: markers.length,
	serverOnly: true,
	noInlinePayloads: true,
	noRawOrEnvFiles: true,
	credentialInputs: false,
	passed: functionBytes + 4194304 <= 70000000,
	files: manifest,
};
await writeFile(
	join(destination, "packaging-v2.json"),
	`${JSON.stringify(packaging, null, 2)}\n`,
	{ flag: "wx" },
);
assert.ok(packaging.passed, "Function + reserve exceeds frozen byte gate");
const workers = [];
for (let index = 1; index <= 3; index++) {
	const child = spawnSync(
		process.execPath,
		["--expose-gc", resolve("scripts/backbone-binary-worker.mjs"), root],
		{
			cwd: root,
			env: {
				PATH: process.env.PATH,
				NODE_ENV: "production",
				VERCEL: "1",
				LOCAL_ROUTING_EXPERIMENT: "1",
			},
			encoding: "utf8",
			timeout: 30000,
			maxBuffer: 2000000,
		},
	);
	await writeFile(
		join(destination, `load-v2-${index}.json`),
		child.stdout ?? "",
		{ flag: "wx" },
	);
	await writeFile(
		join(destination, `load-v2-${index}.log`),
		child.stderr ?? "",
		{ flag: "wx" },
	);
	assert.equal(
		child.status,
		0,
		`Fresh process ${index} failed; original stdout/stderr preserved. ${child.error ?? ""}`,
	);
	workers.push(JSON.parse(child.stdout));
}
const result = {
	planSha256: record.planSha256,
	packagingPassed: packaging.passed,
	processes: workers.length,
	allLoadsPassed: workers.every((w) => w.passed),
	firstLocalHandlerMs: workers.map((w) => w.firstLocalHandlerMs),
	loadDecodeValidateMs: workers.map((w) => w.summary.loadDecodeValidateMs),
	retainedDecodedBytes: workers.map((w) => w.retainedDecodedBytes),
	outboundCalls: workers.reduce((n, w) => n + w.outboundCalls, 0),
	routingAvailable: false,
	runtimeChanged: false,
	scope:
		"One binary package/load probe; no search, new accuracy result or deployed model change.",
};
await writeFile(
	join(destination, "result-v2.json"),
	`${JSON.stringify(result, null, 2)}\n`,
	{ flag: "wx" },
);
console.log(JSON.stringify(result, null, 2));
