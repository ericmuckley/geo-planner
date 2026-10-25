import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import {
	type DampedAdmission,
	evaluateDampedGates,
	type TimingRow,
} from "./coarse-damped-gates";

const plan = JSON.parse(
	await readFile(
		"docs/evidence/coarse-path-features-2026-10-24/candidate-plan.json",
		"utf8",
	),
);
const admission = plan.admission as DampedAdmission;
function rows(): TimingRow[] {
	return [...Array(83)].map((_, i) => {
		const set = i < 11 ? "original" : i < 35 ? "regional" : "frontier";
		const measured = {
			pointMinutes: 105,
			predictedReachable: true,
			pathComponents: { road: 105 },
			classification: "correct",
		};
		return {
			set,
			budgetMinutes: i >= 67 ? 720 : 600,
			referenceMinutes: 100,
			baseline: {
				...measured,
				pointMinutes: 110,
				pathComponents: { road: 110 },
			},
			candidate: { ...measured },
			absoluteErrorChangeMinutes: -5,
		};
	});
}
test("new plan retains v8 missed limits5 overall and2 at12h", () => {
	assert.equal(admission.maximumFrontierMissedReachable, 5);
	assert.equal(admission.maximum12hMissedReachable, 2);
});
test("five missed with two at12h pass the directional guards; a sixth fails", () => {
	const fixtures = rows();
	for (const i of [35, 36, 37, 67, 68])
		fixtures[i].candidate.classification = "missedReachable";
	const result = evaluateDampedGates(fixtures, admission);
	assert.equal(result.gates.frontierMissed, true);
	assert.equal(result.gates.twelveHourMissed, true);
	fixtures[38].candidate.classification = "missedReachable";
	assert.equal(
		evaluateDampedGates(fixtures, admission).gates.frontierMissed,
		false,
	);
});
test("a third12h miss fails even with only three overall", () => {
	const fixtures = rows();
	for (const i of [67, 68, 69])
		fixtures[i].candidate.classification = "missedReachable";
	const result = evaluateDampedGates(fixtures, admission);
	assert.equal(result.gates.frontierMissed, true);
	assert.equal(result.gates.twelveHourMissed, false);
});
