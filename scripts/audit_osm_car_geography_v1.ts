/** Independent Node equality audit of Python-extracted geography vs pinned v9. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { lstat, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { loadOriginGeography } from "./coarse_osm_origin_geography_v1.ts";

const repo = path.resolve(import.meta.dirname, "..");
const sha = (bytes: Uint8Array) =>
	createHash("sha256").update(bytes).digest("hex");
const [recipeName, pin] = process.argv.slice(2);
assert.ok(recipeName && pin);
const began = performance.now();
const recipe = await readFile(path.resolve(repo, recipeName));
assert.equal(sha(recipe), pin);
const plan = JSON.parse(recipe.toString("utf8"));
assert.equal(
	plan.output,
	"docs/evidence/coarse-osm-car-capacity-2026-11-01/car-geography-independent-v1.json",
);
assert.equal(plan.source, "src/server/data/coarse-grid-v9.json");
assert.equal(plan.asset, "data/coarse-quality/us-osm-car-geography-v1");
for (const [name, expected] of Object.entries(plan.bindings))
	assert.equal(sha(await readFile(path.join(repo, name))), expected);
await assert.rejects(lstat(path.join(repo, plan.output)), { code: "ENOENT" });
try {
	const source = await readFile(path.join(repo, plan.source));
	assert.equal(
		sha(source),
		"28271c809a04cdfab41ad735ad66b29e3875179b617198b7b1d4490533439bf6",
	);
	const original = JSON.parse(source.toString("utf8"));
	const loaded = await loadOriginGeography(
		path.join(repo, plan.asset),
		plan.manifestSha256,
	);
	assert.deepEqual(loaded.geography, {
		bounds: original.bounds,
		boundary: original.boundary,
		lakes: original.lakes,
	});
	assert.equal(loaded.points, 27784);
	assert.equal(loaded.rings, 312);
	const result = {
		status: "independent_complete_unchanged_geography_equality_passed",
		recipeSha256: pin,
		sourceSha256: sha(source),
		manifestSha256: plan.manifestSha256,
		boundaryPolygons: 149,
		lakePolygons: 110,
		rings: 312,
		points: 27784,
		rawBytes: loaded.rawBytes,
		compressedBytes: loaded.compressedBytes,
		secondsHostAudit: (performance.now() - began) / 1000,
		producerExecutions: 0,
		sourcePbfReads: 0,
		modelChanged: false,
		scope:
			"Host independent JSON/gzip equality against every pinned original geography coordinate. No finer shore truth, road/connector/ETA/app admission.",
	};
	await writeFile(
		path.join(repo, plan.output),
		`${JSON.stringify(result, null, 2)}\n`,
		{ flag: "wx" },
	);
	process.stdout.write(`${JSON.stringify(result)}\n`);
} catch (error) {
	await writeFile(
		path.join(repo, plan.output),
		`${JSON.stringify({ status: "independent_geography_audit_failed", error: String(error) })}\n`,
		{ flag: "wx" },
	);
	throw error;
}
