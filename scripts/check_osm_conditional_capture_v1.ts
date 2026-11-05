/** Independently compare the TypeScript engine with all82 captured path results. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { lstat, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import {
	PACKED_CAR_FILES,
	type PackedCarFiles,
	PackedCarGraph,
} from "./coarse_osm_packed_car_v1.ts";
import {
	type PackedPoint,
	searchPackedCar,
} from "./coarse_osm_packed_search_v1.ts";

const repo = path.resolve(import.meta.dirname, ".."),
	sha = (bytes: Uint8Array) => createHash("sha256").update(bytes).digest("hex");
const began = performance.now(),
	[recipeName, pin] = process.argv.slice(2);
assert.ok(recipeName && pin);
const recipe = await readFile(path.resolve(repo, recipeName));
assert.equal(sha(recipe), pin);
const plan = JSON.parse(recipe.toString("utf8"));
assert.equal(
	plan.source,
	"data/coarse-quality/us-osm-car-conditional-graph-capture-v1",
);
assert.equal(
	plan.output,
	"docs/evidence/coarse-osm-car-capacity-2026-11-01/conditional-graph-runtime-v1.json",
);
for (const [name, expected] of Object.entries(plan.bindings))
	assert.equal(sha(await readFile(path.join(repo, name))), expected, name);
const closed = JSON.parse(
	await readFile(path.join(repo, plan.closedRecord), "utf8"),
);
assert.equal(closed.root, plan.source);
let inputBytes = 0;
async function bound(name: string) {
	const expected = closed.roster[name];
	assert.ok(expected && !name.includes(".."));
	const filename = path.join(repo, plan.source, name),
		stat = await lstat(filename);
	assert.ok(stat.isFile() && !stat.isSymbolicLink() && stat.size <= 4194304);
	inputBytes += stat.size;
	assert.ok(inputBytes <= 8388608);
	const bytes = await readFile(filename);
	assert.equal(bytes.length, expected.bytes);
	assert.equal(sha(bytes), expected.sha256);
	return Uint8Array.from(bytes);
}
const decode = (b: Uint8Array) => JSON.parse(new TextDecoder().decode(b)),
	assets = decode(await bound("artifacts.json")),
	files = {} as PackedCarFiles;
assert.deepEqual(Object.keys(assets).sort(), [...PACKED_CAR_FILES].sort());
for (const name of PACKED_CAR_FILES) {
	files[name] = await bound(name);
	assert.equal(files[name].length, assets[name].bytes);
	assert.equal(sha(files[name]), assets[name].sha256);
}
const fixtures: {
		source: PackedPoint;
		target: PackedPoint;
		directTicks: number | null;
		expectedTicks: number | null;
	}[] = decode(await bound("query-fixtures.json")),
	report = decode(await bound("report.json"));
assert.equal(fixtures.length, 82);
assert.equal(report.candidateFinite, 77);
assert.equal(report.candidateStillUnreachable, 5);
const graph = new PackedCarGraph(files),
	checks = [];
for (const [index, f] of fixtures.entries()) {
	const result = searchPackedCar(graph, f.source, f.target, {
			check: () => assert.ok(performance.now() - began < 30000),
		}),
		ticks =
			f.directTicks === null
				? result.ticks
				: Math.min(result.ticks ?? Infinity, f.directTicks);
	assert.equal(ticks, f.expectedTicks);
	assert.equal(ticks, report.rows[index].candidateTicks);
	checks.push({ index, ticks, settles: result.settles });
}
const result = {
	status: "independent_typescript_captured_conditional_queries_exact",
	recipeSha256: pin,
	originalCases: 82,
	finite: 77,
	unreachable: 5,
	checks,
	hostMsIncludingHashesReaderAndQueries: performance.now() - began,
	sourcePbfReads: 0,
	providerRequests: 0,
	nationalOrAppQualified: false,
	scope:
		"Independent TypeScript packed query equality with all82 captured Python/source-replayed results. No nationwide ETA/app admission; whole host timing includes inputs/reader/search.",
};
await writeFile(
	path.join(repo, plan.output),
	`${JSON.stringify(result, null, 2)}\n`,
	{ flag: "wx" },
);
console.log(JSON.stringify({ ...result, checks: undefined }));
