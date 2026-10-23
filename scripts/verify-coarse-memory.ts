import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { decodeGrid } from "../src/server/coarse-data.server";
import { gridAttachments } from "../src/server/coarse-grid";

const artifact = process.argv[2];
const anchorInputs = process.argv.includes("--anchor-inputs");
assert.ok(
	artifact && global.gc,
	"Run with --expose-gc and a candidate artifact path",
);
const raw = await readFile(artifact);
const data = JSON.parse(raw.toString());
const snapshot = () => {
	global.gc?.();
	return process.memoryUsage();
};
const before = snapshot();
const started = performance.now();
const grid = decodeGrid(data);
const decodeMs = performance.now() - started;
const decoded = snapshot();
assert.ok(grid.supplementalRoadVisits?.size, "Expected supplemental visits");
const heapDelta = decoded.heapUsed - before.heapUsed;
const bufferDelta = decoded.arrayBuffers - before.arrayBuffers;
// The fixed, finer latitude index retains small per-band views. Eagerly
// expanding all source visits would exceed this heap allowance by orders of magnitude.
const loadHeapBudgetBytes = 4 * 1024 * 1024;
assert.ok(
	heapDelta < loadHeapBudgetBytes,
	"Packed geometry expanded eagerly on load",
);

function sweep() {
	let inputs = 0;
	let attachments = 0;
	let points = 0;
	const timings: number[] = [];
	for (const [, visit] of grid.supplementalRoadVisits ?? []) {
		const point = visit.points[anchorInputs ? visit.anchorIndex : 0];
		const start = performance.now();
		const result = gridAttachments(grid, { lon: point[0], lat: point[1] });
		timings.push(performance.now() - start);
		attachments += result.length;
		points += visit.points.length;
		inputs++;
	}
	timings.sort((a, b) => a - b);
	return {
		inputs,
		attachments,
		points,
		attachmentMedianMs: timings[Math.floor(timings.length / 2)],
		attachmentMaxMs: timings.at(-1),
	};
}

const sweeps = [];
for (let i = 0; i < 3; i++) {
	const measured = sweep();
	assert.equal(measured.inputs, grid.supplementalRoadVisits.size);
	const memory = snapshot();
	const heapGrowthBytes = memory.heapUsed - decoded.heapUsed;
	const bufferGrowthBytes = memory.arrayBuffers - decoded.arrayBuffers;
	// Allow small engine bookkeeping noise after GC; retaining decoded visits
	// for this complete input sweep would exceed this by tens of megabytes.
	assert.ok(
		heapGrowthBytes < 2 * 1024 * 1024,
		"Queries retained decoded visit objects",
	);
	assert.ok(
		bufferGrowthBytes < 64 * 1024,
		"Queries retained additional buffers",
	);
	sweeps.push({ ...measured, memory, heapGrowthBytes, bufferGrowthBytes });
}

console.log(
	JSON.stringify(
		{
			artifact,
			inputSelection: anchorInputs
				? "Validated on-land source-visit anchors"
				: "First retained source vertices (may include generalized water)",
			artifactSha256: createHash("sha256").update(raw).digest("hex"),
			decodeMs,
			loadHeapBudgetBytes,
			before,
			decoded,
			retainedHeapDeltaBytes: heapDelta,
			retainedArrayBufferDeltaBytes: bufferDelta,
			retainedHeapAndBufferDeltaBytes: heapDelta + bufferDelta,
			sweeps,
			processMaxRssKiB: process.resourceUsage().maxRSS,
			scope:
				"Local explicit-GC observations in one Node process, with already-parsed encoded input retained. Load checks less than 2 MiB retained heap beyond packed buffers; three complete supplemental-input sweeps check bounded retained growth (2 MiB heap / 64 KiB buffers allowance), not Vercel memory, a cloud capacity budget, latency percentiles or a nationwide forecast. RSS is whole-process lifetime, not isolated decoder/query peak.",
		},
		null,
		2,
	),
);
