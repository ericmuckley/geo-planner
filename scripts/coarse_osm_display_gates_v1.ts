/** Numerical screen only; complete physical/path/package admission stays separate. */

import assert from "node:assert/strict";
import { type TimingRow, timingSummary } from "./coarse-damped-gates.ts";

type Sample = TimingRow & { valhallaMinutes: number | null };

export function numericalGates(rows: Sample[]) {
	const summary = (items: Sample[], model: "baseline" | "candidate") =>
		timingSummary(items, model);
	const group = (set: string) => rows.filter((r) => r.set === set),
		frontier = group("frontier"),
		older = rows.filter((r) => r.set !== "frontier");
	const within = (value: number | null, maximum: number | null) =>
		value !== null &&
		maximum !== null &&
		Number.isFinite(value) &&
		value <= maximum + 1e-10;
	const byHorizon = (h: number) =>
		frontier.filter((r) => r.budgetMinutes === h);
	const before = summary(rows, "baseline"),
		after = summary(rows, "candidate"),
		bfront = summary(frontier, "baseline"),
		afront = summary(frontier, "candidate");
	const misses = (items: Sample[]) =>
		items.filter((r) => r.candidate.classification === "missedReachable")
			.length;
	const errors = frontier.filter((r) =>
		["falseReachable", "missedReachable"].includes(r.candidate.classification),
	).length;
	const valhalla = (set: string, model: "baseline" | "candidate") =>
		summary(
			group(set).map((r) => {
				assert.ok(r.valhallaMinutes !== null);
				return { ...r, referenceMinutes: r.valhallaMinutes };
			}),
			model,
		);
	const gates = {
		overallMean: within(
			after.meanAbsoluteMinutes,
			(before.meanAbsoluteMinutes ?? 0) * 0.9,
		),
		frontierMean: within(
			afront.meanAbsoluteMinutes,
			(bfront.meanAbsoluteMinutes ?? 0) * 0.9,
		),
		originalMean: within(
			summary(group("original"), "candidate").meanAbsoluteMinutes,
			summary(group("original"), "baseline").meanAbsoluteMinutes,
		),
		regionalMean: within(
			summary(group("regional"), "candidate").meanAbsoluteMinutes,
			summary(group("regional"), "baseline").meanAbsoluteMinutes,
		),
		originalP90: within(
			summary(group("original"), "candidate").p90AbsoluteMinutes,
			summary(group("original"), "baseline").p90AbsoluteMinutes,
		),
		regionalP90: within(
			summary(group("regional"), "candidate").p90AbsoluteMinutes,
			summary(group("regional"), "baseline").p90AbsoluteMinutes,
		),
		frontierMedian: within(
			afront.medianAbsoluteMinutes,
			bfront.medianAbsoluteMinutes,
		),
		frontierP90: within(afront.p90AbsoluteMinutes, bfront.p90AbsoluteMinutes),
		horizonMeans: [360, 600, 720].every((h) =>
			within(
				summary(byHorizon(h), "candidate").meanAbsoluteMinutes,
				summary(byHorizon(h), "baseline").meanAbsoluteMinutes,
			),
		),
		horizonP90: [360, 600, 720].every((h) =>
			within(
				summary(byHorizon(h), "candidate").p90AbsoluteMinutes,
				summary(byHorizon(h), "baseline").p90AbsoluteMinutes,
			),
		),
		valhallaOriginalMean: within(
			valhalla("original", "candidate").meanAbsoluteMinutes,
			valhalla("original", "baseline").meanAbsoluteMinutes,
		),
		valhallaRegionalMean: within(
			valhalla("regional", "candidate").meanAbsoluteMinutes,
			valhalla("regional", "baseline").meanAbsoluteMinutes,
		),
		frontierWorstRegression:
			Math.max(
				...frontier.map((r) => r.absoluteErrorChangeMinutes ?? Infinity),
			) <=
			20 + 1e-10,
		olderWorstRegression:
			Math.max(...older.map((r) => r.absoluteErrorChangeMinutes ?? Infinity)) <=
			5 + 1e-10,
		frontierDefiniteErrors: errors <= 12,
		frontierMissed: misses(frontier) <= 2,
		twelveHourMissed: misses(byHorizon(720)) <= 1,
		all83Finite:
			rows.length === 83 &&
			rows.every((r) => r.candidate.pointMinutes !== null),
		all35OlderShaded:
			older.length === 35 && older.every((r) => r.candidate.predictedReachable),
	};
	return {
		gates,
		numericalGatesPassed: Object.values(gates).every(Boolean),
		overall: { baseline: before, candidate: after },
		sets: Object.fromEntries(
			["original", "regional", "frontier"].map((set) => [
				set,
				{
					baseline: summary(group(set), "baseline"),
					candidate: summary(group(set), "candidate"),
				},
			]),
		),
		frontierClassificationsAllCases: Object.fromEntries(
			["correct", "falseReachable", "missedReachable", "ambiguous"].map((c) => [
				c,
				frontier.filter((r) => r.candidate.classification === c).length,
			]),
		),
		valhallaSensitivity: Object.fromEntries(
			["original", "regional"].map((set) => [
				set,
				{
					baseline: valhalla(set, "baseline"),
					candidate: valhalla(set, "candidate"),
				},
			]),
		),
	};
}
