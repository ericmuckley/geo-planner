import assert from "node:assert/strict";
import test from "node:test";
import { timingRow } from "./coarse_osm_timing_rows_v2.ts";
import type { TimingRow } from "./coarse-damped-gates.ts";

const sample: TimingRow & { id: string } = {
	id: "same-case",
	set: "regional",
	budgetMinutes: 720,
	referenceMinutes: 100,
	baseline: {
		pointMinutes: 90,
		predictedReachable: true,
		pathComponents: { road: 90 },
		classification: "correct",
	},
	candidate: {
		pointMinutes: 110,
		predictedReachable: true,
		pathComponents: { road: 110 },
		classification: "correct",
	},
	absoluteErrorChangeMinutes: 0,
};
test("unsupported source rows retain identity, nulls and failed classification", () => {
	const result = timingRow(sample, null, false, "outside-geography-mask");
	assert.equal(result.id, sample.id);
	assert.equal(result.estimateFailure, "outside-geography-mask");
	assert.equal(result.candidate.pointMinutes, null);
	assert.equal(result.candidate.classification, "missedReachable");
	assert.equal(result.absoluteErrorChangeMinutes, null);
	assert.deepEqual(result.baseline, sample.candidate);
	assert.throws(() => timingRow(sample, 0, false, "bad-source"));
	assert.throws(() => timingRow(sample, null, true, "bad-source"));
});
test("valid timing rows preserve the frozen v1 classification and baseline policy", () => {
	const finite = timingRow(sample, 100 * 480, true);
	assert.equal(finite.candidate.pointMinutes, 100);
	assert.equal(finite.candidate.classification, "correct");
	assert.equal(finite.absoluteErrorChangeMinutes, -10);
	assert.equal(finite.estimateFailure, null);
	const outside = timingRow({ ...sample, budgetMinutes: 80 }, 120 * 480, true);
	assert.equal(outside.candidate.classification, "falseReachable");
	const ambiguous = timingRow(
		{ ...sample, budgetMinutes: 102 },
		120 * 480,
		false,
	);
	assert.equal(ambiguous.candidate.classification, "ambiguous");
});
