import assert from "node:assert/strict";
import test from "node:test";
import { numericalGates } from "./coarse_osm_display_gates_v1.ts";
import type { TimingRow } from "./coarse-damped-gates.ts";

function rows() {
	return Array.from(
		{ length: 83 },
		(_, i): TimingRow & { valhallaMinutes: number | null } => ({
			set: i < 11 ? "original" : i < 35 ? "regional" : "frontier",
			budgetMinutes: i < 35 ? 720 : [360, 600, 720][Math.floor((i - 35) / 16)],
			referenceMinutes: 100,
			valhallaMinutes: i < 35 ? 100 : null,
			absoluteErrorChangeMinutes: -10,
			baseline: {
				pointMinutes: 110,
				predictedReachable: true,
				pathComponents: null,
				classification: "correct",
			},
			candidate: {
				pointMinutes: 100,
				predictedReachable: true,
				pathComponents: null,
				classification: "correct",
			},
		}),
	);
}
test("numerical screen requires all83/35 but leaves full path gates explicitly separate", () => {
	const result = numericalGates(rows());
	assert.ok(result.numericalGatesPassed);
	assert.equal(result.overall.candidate.pathSumsReconstructed, 0);
	assert.equal(result.overall.candidate.pairedFinite, 83);
	const incomplete = rows().slice(1);
	assert.equal(numericalGates(incomplete).gates.all83Finite, false);
	assert.equal(numericalGates(incomplete).gates.all35OlderShaded, false);
});
test("null route cases cannot disappear from finite means or classification failures", () => {
	const cases = rows();
	for (let i = 35; i < 38; i++) {
		cases[i].candidate.pointMinutes = null;
		cases[i].candidate.predictedReachable = false;
		cases[i].candidate.classification = "missedReachable";
		cases[i].absoluteErrorChangeMinutes = null;
	}
	const result = numericalGates(cases);
	assert.equal(result.gates.all83Finite, false);
	assert.equal(result.gates.frontierMissed, false);
	assert.equal(result.gates.frontierWorstRegression, false);
	assert.equal(result.frontierClassificationsAllCases.missedReachable, 3);
	assert.equal(result.overall.candidate.unreached, 3);
	assert.equal(result.numericalGatesPassed, false);
});
test("older shading, individual losses and both Valhalla groups retain their original gates", () => {
	let cases = rows();
	cases[0].candidate.predictedReachable = false;
	assert.equal(numericalGates(cases).gates.all35OlderShaded, false);
	cases = rows();
	cases[0].absoluteErrorChangeMinutes = 5.01;
	assert.equal(numericalGates(cases).gates.olderWorstRegression, false);
	cases = rows();
	cases[35].absoluteErrorChangeMinutes = 20.01;
	assert.equal(numericalGates(cases).gates.frontierWorstRegression, false);
	cases = rows();
	for (const row of cases)
		if (row.valhallaMinutes !== null) row.valhallaMinutes = 120;
	const result = numericalGates(cases);
	assert.equal(result.gates.valhallaOriginalMean, false);
	assert.equal(result.gates.valhallaRegionalMean, false);
	assert.ok(result.gates.overallMean);
});
