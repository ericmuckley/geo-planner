import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { decodeGrid } from "../src/server/coarse-data.server";
import { estimateGrid } from "../src/server/coarse-grid";
import { coarseSmokeOrigins } from "./coarse-smoke-cases";

const artifact = process.argv[2];
assert.ok(artifact, "Pass an offline candidate artifact path");
const raw = await readFile(artifact);
const started = performance.now();
const grid = decodeGrid(JSON.parse(raw.toString()));
const decodeAndParseMs = performance.now() - started;
const baseline = JSON.parse(
	await readFile(
		"docs/evidence/coarse-v4-2026-10-22/national-smoke.json",
		"utf8",
	),
);
const samples = [];
for (const [name, lat, lon] of coarseSmokeOrigins) {
	let previous = 0;
	for (const minutes of [360, 600, 720]) {
		const start = performance.now();
		const estimate = estimateGrid(grid, { lat, lon }, minutes);
		const estimateAndContourMs = performance.now() - start;
		const original = baseline.samples.find(
			(s: { name: string; minutes: number }) =>
				s.name === name && s.minutes === minutes,
		);
		assert.ok(original);
		assert.ok(
			estimate.reachedCells >= original.cells,
			`Lost v4 reachability: ${name}/${minutes}`,
		);
		assert.ok(estimate.reachedCells >= previous);
		if (name !== "Nantucket") assert.ok(estimate.reachedCells >= 10);
		const geometryBytes = Buffer.byteLength(
			JSON.stringify(estimate.coordinates),
		);
		assert.ok(geometryBytes < 1_000_000);
		previous = estimate.reachedCells;
		samples.push({
			name,
			minutes,
			cells: estimate.reachedCells,
			baselineV4Cells: original.cells,
			geometryBytes,
			estimateAndContourMs,
			searchMs: estimate.searchMs,
			contourMs: estimate.contourMs,
		});
	}
}
console.log(
	JSON.stringify(
		{
			artifact,
			artifactSha256: createHash("sha256").update(raw).digest("hex"),
			decodeAndParseMs,
			samples,
			memoryUsage: process.memoryUsage(),
			publicRoutingApiCalls: 0,
			scope:
				"Offline 42-case candidate grid/contour smoke against preserved v4 counts at the shared validation inputs. Budget monotonicity, connected samples and geometry-size checks are not travel-time accuracy proof. Parse/decode, estimate/contour, whole-process memory and cloud/HTTP scopes remain separate. No provider, database, service or deployment.",
		},
		null,
		2,
	),
);
