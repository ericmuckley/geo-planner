// Runs only against an isolated generated handler, with no credentials/network.
import assert from "node:assert/strict";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

assert.ok(globalThis.gc, "Run with --expose-gc");
delete process.env.DATABASE_URL;
delete process.env.ORS_API_KEY;
process.env.VERCEL = "1";
process.env.LOCAL_ROUTING_EXPERIMENT = "1";
let outboundCalls = 0;
globalThis.fetch = async () => {
	outboundCalls++;
	throw new Error("Unexpected outbound fetch");
};
const moduleStarted = performance.now();
const handler = (
	await import(
		pathToFileURL(
			resolve(
				process.argv[2],
				".vercel/output/functions/__server.func/index.mjs",
			),
		).href
	)
).default;
const request = (path, options) =>
	handler.fetch(new Request(`http://localhost${path}`, options));
const configResponse = await request("/api/estimate");
assert.equal(configResponse.status, 200);
const config = await configResponse.json();
assert.equal(config.configured, false);
assert.equal(config.health, "unconfigured");
assert.equal(config.engineVersion, "backbone-packaging-probe");
const moduleAndConfigMs = performance.now() - moduleStarted;
async function collect() {
	for (let i = 0; i < 3; i++) {
		globalThis.gc();
		await new Promise((resolve) => setImmediate(resolve));
	}
	return process.memoryUsage();
}
const baseline = await collect();
const started = performance.now();
const response = await request("/api/backbone-probe");
assert.equal(response.status, 200);
assert.equal(response.headers.get("cache-control"), "no-store");
const body = await response.text();
assert.ok(Buffer.byteLength(body) < 1_000_000);
const summary = JSON.parse(body);
const firstLocalHandlerMs = performance.now() - started;
const after = await collect();
const retainedHeapDelta = after.heapUsed - baseline.heapUsed;
const retainedArrayBufferDelta = after.arrayBuffers - baseline.arrayBuffers;
const retainedDecodedBytes = retainedHeapDelta + retainedArrayBufferDelta;
assert.equal(summary.loads, 1);
assert.equal(summary.graphArrays, 17);
assert.equal(summary.keptBlobs, 12);
assert.equal(summary.nodes, 978572);
assert.equal(summary.arcs, 1234223);
assert.equal(summary.retainedGraphBytes, 92126186);
assert.equal(summary.baseRoadVisits, 123116);
assert.equal(summary.routingAvailable, false);
assert.equal(summary.probeOnly, true);
assert.equal(summary.allGzipAndRawHashes, true);
assert.equal(summary.allFormatAndIndexChecks, true);
assert.equal(
	summary.binarySha256,
	"4d455bec6c02f3da5a189dd8bbe36b4e2da98be124cd4c45d8309f0234de4b20",
);
assert.equal(
	summary.keptJsonSha256,
	"7ddd09269b1f4bcc19ef7d4ace039e010a3cbafeaf96c5221a57118a9a9a0454",
);
const second = await request("/api/backbone-probe");
assert.equal(second.status, 200);
assert.deepEqual(await second.json(), summary);
assert.equal(
	(
		await request("/api/estimate", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: "{}",
		})
	).status,
	503,
);
assert.equal((await request("/api/experiment")).status, 503);
const history = await request("/api/saved-runs");
assert.equal(history.status, 200);
assert.deepEqual(await history.json(), { configured: false, runs: [] });
assert.equal(
	(await request("/api/saved-runs", { method: "POST", body: "[]" })).status,
	503,
);
assert.equal((await request("/server-data/backbone.bin")).status, 404);
assert.equal(outboundCalls, 0);
const gates = {
	firstLocalHandler: firstLocalHandlerMs <= 3000,
	loadDecodeValidate: summary.loadDecodeValidateMs <= 3000,
	retainedDecodedStorage: retainedDecodedBytes <= 162238546,
};
console.log(
	JSON.stringify(
		{
			summary,
			moduleAndConfigMs,
			firstLocalHandlerMs,
			baseline,
			after,
			retainedHeapDelta,
			retainedArrayBufferDelta,
			retainedDecodedBytes,
			outboundCalls,
			disabledExperiment: true,
			missingDatabaseFallback: true,
			contoursUnavailable: true,
			publicBinaryUnavailable: true,
			gates,
			passed: Object.values(gates).every(Boolean),
			scope:
				"Generated Vercel handler invoked locally; three forced GC cycles with event-loop yields before/after first load. Heap+arrayBuffers delta retains every graph/base buffer. RSS is observed, not peak memory. Module/config time separate; no query/cloud timing or accuracy claim.",
		},
		null,
		2,
	),
);
if (!Object.values(gates).every(Boolean)) process.exitCode = 1;
