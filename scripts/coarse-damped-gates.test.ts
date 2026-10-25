import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import {
	type DampedAdmission,
	evaluateDampedGates,
	type TimingRow,
} from "./coarse-damped-gates";

const policy = JSON.parse(
	await readFile(
		"docs/evidence/coarse-damped-calibration-2026-10-24/plan.json",
		"utf8",
	),
);
const admission = policy.admission as DampedAdmission;
function fixtures(): TimingRow[] {
	return (
		[
			...Array(11).fill("original"),
			...Array(24).fill("regional"),
			...Array(48).fill("frontier"),
		] as TimingRow["set"][]
	).map((set, i) => {
		const budgetMinutes =
			set === "frontier" ? [360, 600, 720][Math.floor((i - 35) / 16)] : 720;
		const referenceMinutes = set === "frontier" ? budgetMinutes - 20 : 100;
		const measured = (error: number) => ({
			pointMinutes: referenceMinutes + error,
			predictedReachable: true,
			pathComponents: { road: referenceMinutes + error },
			classification: "correct",
		});
		return {
			set,
			budgetMinutes,
			referenceMinutes,
			baseline: measured(10),
			candidate: measured(5),
			absoluteErrorChangeMinutes: -5,
		};
	});
}
function change(row: TimingRow, error: number) {
	row.candidate.pointMinutes = row.referenceMinutes + error;
	row.candidate.pathComponents = { road: row.referenceMinutes + error };
	row.absoluteErrorChangeMinutes = Math.abs(error) - 10;
}
test("complete finite improved fixture passes all prospective gates", () => {
	const result = evaluateDampedGates(fixtures(), admission);
	assert.equal(result.passed, true);
	assert.equal(result.gates.all166PathSums, true);
});
test("favorable combined mean cannot hide a regional-set regression", () => {
	const rows = fixtures();
	for (const row of rows.filter((r) => r.set === "original")) change(row, 12);
	const result = evaluateDampedGates(rows, admission);
	assert.equal(result.gates.overallMean, true);
	assert.equal(result.gates.originalMean, false);
	assert.equal(result.passed, false);
});
test("individual-loss caps are enforced even when averages pass", () => {
	for (const [index, loss, gate] of [
		[35, 41, "frontierWorstRegression"],
		[0, 11, "olderWorstRegression"],
	] as const) {
		const rows = fixtures();
		change(rows[index], 10 + loss);
		const result = evaluateDampedGates(rows, admission);
		assert.equal(result.gates.overallMean, true);
		assert.equal(result.gates[gate], false);
		assert.equal(result.passed, false);
	}
});
test("horizon tail failure remains visible with improved horizon mean", () => {
	const rows = fixtures();
	change(rows[35], 20);
	change(rows[36], 20);
	const result = evaluateDampedGates(rows, {
		...admission,
		horizonP90Maximum: { ...admission.horizonP90Maximum, 360: 10 },
	});
	assert.equal(result.gates.horizonMeans, true);
	assert.equal(result.gates.horizonP90, false);
});
test("missed-reachable limits apply overall and at12h", () => {
	const rows = fixtures();
	for (const row of rows.slice(-7)) {
		row.candidate.classification = "missedReachable";
		row.candidate.predictedReachable = false;
	}
	const result = evaluateDampedGates(rows, admission);
	assert.equal(result.gates.frontierMissed, false);
	assert.equal(result.gates.twelveHourMissed, false);
});
test("missing labels, invalid path sums and lost older shading cannot qualify", () => {
	const rows = fixtures();
	rows[0].candidate.pointMinutes = null;
	rows[0].candidate.pathComponents = null;
	rows[1].candidate.predictedReachable = false;
	const result = evaluateDampedGates(rows, admission);
	assert.equal(result.gates.all83Paired, false);
	assert.equal(result.gates.all166PathSums, false);
	assert.equal(result.gates.all35StillShaded, false);
	const mismatch = fixtures();
	mismatch[0].candidate.pathComponents = { road: 1 };
	assert.equal(
		evaluateDampedGates(mismatch, admission).gates.all166PathSums,
		false,
	);
});
