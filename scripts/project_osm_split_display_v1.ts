/** Saved-frame capacity arithmetic only; no new grid, route or map is rendered. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { type Frame, makeFrame } from "./coarse_osm_display_grid_v1.ts";
import {
	DISPLAY_CAP_BYTES,
	maximumSplitDisplayCells,
	splitDisplayBytes,
} from "./coarse_osm_split_display_budget_v1.ts";

const repo = path.resolve(import.meta.dirname, "..");
const [name, pin] = process.argv.slice(2);
assert.ok(name && pin);
const sha = (b: Uint8Array) => createHash("sha256").update(b).digest("hex");
const raw = await readFile(path.resolve(repo, name));
assert.equal(sha(raw), pin);
const plan = JSON.parse(raw.toString("utf8"));
for (const [file, checksum] of Object.entries(plan.bindings))
	assert.equal(sha(await readFile(path.join(repo, file))), checksum, file);
assert.ok(
	plan.priorReserveBytes +
		plan.newClosedAllocationBytes +
		plan.metadataScratchReserveBytes <
		72 * 1024 ** 3,
);
type Display = {
	frame: Frame;
	fieldStats: { maximumBackingBufferBytes: number };
};
const candidate = JSON.parse(
	await readFile(path.join(repo, plan.candidate), "utf8"),
) as {
	phases: {
		diagnostic: Display;
		productions: (Display & { minutes: number })[];
	}[];
};
const rows = [];
for (const [index, phase] of candidate.phases.entries()) {
	for (const display of [
		{ ...phase.diagnostic, minutes: 900 },
		...phase.productions,
	]) {
		const old = display.frame;
		const outer = [
			old.west / 1e6,
			old.south / 1e6,
			(old.west + old.width * old.step) / 1e6,
			(old.south + old.height * old.step) / 1e6,
		];
		let step = 5000;
		let frame = makeFrame(outer, step);
		let input = {
			fieldPeakBytes: display.fieldStats.maximumBackingBufferBytes,
			maxWidth: frame.width,
			maxHeight: frame.height,
			heapEntries: 1000000,
		};
		let bytes = splitDisplayBytes(input, frame.width * frame.height);
		while (bytes.seed > DISPLAY_CAP_BYTES || bytes.fill > DISPLAY_CAP_BYTES) {
			assert.ok(++step <= 25000, "Split projection cannot fit existing limits");
			frame = makeFrame(outer, step);
			input = { ...input, maxWidth: frame.width, maxHeight: frame.height };
			bytes = splitDisplayBytes(input, frame.width * frame.height);
		}
		rows.push({
			originIndex: index,
			minutes: display.minutes,
			oldStepE6: old.step,
			projectedStepE6: step,
			oldCells: old.width * old.height,
			projectedCells: frame.width * frame.height,
			projectedFrame: frame,
			fieldPeakBytes: input.fieldPeakBytes,
			maximumCellsAtProjectedFrameDimensions: maximumSplitDisplayCells(input),
			projectedSeedPhaseBytes: bytes.seed,
			projectedFillPhaseBytes: bytes.fill,
		});
	}
}
assert.equal(rows.length, 58);
assert.equal(candidate.phases.length, 21);
const report = {
	status: "split_display_saved58frame_capacity_projection_complete",
	recipeSha256: pin,
	rows,
	finerProjectedFrames: rows.filter((r) => r.projectedStepE6 < r.oldStepE6)
		.length,
	finestExistingStepProjectedFrames: rows.filter(
		(r) => r.projectedStepE6 === 5000,
	).length,
	maximumProjectedCells: Math.max(...rows.map((r) => r.projectedCells)),
	maximumProjectedSeedPhaseBytes: Math.max(
		...rows.map((r) => r.projectedSeedPhaseBytes),
	),
	maximumProjectedFillPhaseBytes: Math.max(
		...rows.map((r) => r.projectedFillPhaseBytes),
	),
	graphQueries: 0,
	newMaps: 0,
	providerRequests: 0,
	isMemoryMeasurementOrAccuracyEvaluation: false,
	prototypeImplemented: false,
	scope: plan.scope,
};
await writeFile(
	path.join(repo, plan.output),
	`${JSON.stringify(report, null, 2)}\n`,
	{
		flag: "wx",
	},
);
process.stdout.write(
	`${JSON.stringify({ ...report, rows: undefined, scope: undefined })}\n`,
);
