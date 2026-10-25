export type MeasuredTiming = {
	pointMinutes: number | null;
	predictedReachable: boolean;
	pathComponents: Record<string, number> | null;
	classification: string;
};
export type TimingRow = {
	set: "original" | "regional" | "frontier";
	budgetMinutes: number;
	referenceMinutes: number;
	baseline: MeasuredTiming;
	candidate: MeasuredTiming;
	absoluteErrorChangeMinutes: number | null;
};
export type DampedAdmission = {
	overallMeanAbsoluteMaximum: number;
	frontierMeanAbsoluteMaximum: number;
	setMeansMaximum: Record<string, number>;
	frontierP90Maximum: number;
	horizonMeansMaximum: Record<string, number>;
	horizonP90Maximum: Record<string, number>;
	maximumFrontierAbsoluteErrorIncreaseMinutes: number;
	maximumOlderAbsoluteErrorIncreaseMinutes: number;
	maximumFrontierDefiniteClassificationErrors: number;
	maximumFrontierMissedReachable: number;
	maximum12hMissedReachable: number;
};

export function timingSummary(
	items: TimingRow[],
	model: "baseline" | "candidate",
) {
	const finite = items.filter((r) => r[model].pointMinutes !== null);
	const errors = finite
		.map((r) => Math.abs((r[model].pointMinutes ?? 0) - r.referenceMinutes))
		.sort((a, b) => a - b);
	const n = errors.length;
	return {
		planned: items.length,
		pairedFinite: n,
		unreached: items.length - n,
		meanAbsoluteMinutes: n ? errors.reduce((a, b) => a + b, 0) / n : null,
		medianAbsoluteMinutes: n
			? (errors[Math.floor((n - 1) / 2)] + errors[Math.floor(n / 2)]) / 2
			: null,
		p90AbsoluteMinutes: n ? errors[Math.ceil(n * 0.9) - 1] : null,
		classifications: Object.fromEntries(
			["correct", "falseReachable", "missedReachable", "ambiguous"].map((c) => [
				c,
				finite.filter((r) => r[model].classification === c).length,
			]),
		),
		pathSumsReconstructed: finite.filter(
			(r) =>
				r[model].pathComponents !== null &&
				Math.abs(
					Object.values(r[model].pathComponents ?? {}).reduce(
						(a, b) => a + b,
						0,
					) - (r[model].pointMinutes ?? 0),
				) < 1e-8,
		).length,
	};
}

export function evaluateDampedGates(
	rows: TimingRow[],
	admission: DampedAdmission,
) {
	const subset = (set: string) => rows.filter((r) => r.set === set);
	const frontier = subset("frontier"),
		older = rows.filter((r) => r.set !== "frontier");
	const summary = (items: TimingRow[]) => timingSummary(items, "candidate");
	const total = summary(rows),
		f = summary(frontier);
	const maxIncrease = (items: TimingRow[]) =>
		Math.max(...items.map((r) => r.absoluteErrorChangeMinutes ?? Infinity));
	const within = (value: number | null, maximum: number) =>
		value !== null && Number.isFinite(value) && value <= maximum + 1e-10;
	const horizon = (h: string) =>
		summary(frontier.filter((r) => r.budgetMinutes === Number(h)));
	const gates = {
		overallMean: within(
			total.meanAbsoluteMinutes,
			admission.overallMeanAbsoluteMaximum,
		),
		frontierMean: within(
			f.meanAbsoluteMinutes,
			admission.frontierMeanAbsoluteMaximum,
		),
		originalMean: within(
			summary(subset("original")).meanAbsoluteMinutes,
			admission.setMeansMaximum.original,
		),
		regionalMean: within(
			summary(subset("regional")).meanAbsoluteMinutes,
			admission.setMeansMaximum.regional,
		),
		frontierP90: within(f.p90AbsoluteMinutes, admission.frontierP90Maximum),
		horizonMeans: Object.entries(admission.horizonMeansMaximum).every(
			([h, maximum]) => within(horizon(h).meanAbsoluteMinutes, maximum),
		),
		horizonP90: Object.entries(admission.horizonP90Maximum).every(
			([h, maximum]) => within(horizon(h).p90AbsoluteMinutes, maximum),
		),
		frontierWorstRegression: within(
			maxIncrease(frontier),
			admission.maximumFrontierAbsoluteErrorIncreaseMinutes,
		),
		olderWorstRegression: within(
			maxIncrease(older),
			admission.maximumOlderAbsoluteErrorIncreaseMinutes,
		),
		frontierDefiniteClassificationErrors:
			f.classifications.falseReachable + f.classifications.missedReachable <=
			admission.maximumFrontierDefiniteClassificationErrors,
		frontierMissed:
			f.classifications.missedReachable <=
			admission.maximumFrontierMissedReachable,
		twelveHourMissed:
			horizon("720").classifications.missedReachable <=
			admission.maximum12hMissedReachable,
		all83Paired: rows.length === 83 && total.pairedFinite === 83,
		all166PathSums:
			timingSummary(rows, "baseline").pathSumsReconstructed === 83 &&
			total.pathSumsReconstructed === 83,
		all35StillShaded:
			older.length === 35 && older.every((r) => r.candidate.predictedReachable),
	};
	return {
		gates,
		passed: Object.values(gates).every(Boolean),
		maxFrontierRegression: maxIncrease(frontier),
		maxOlderRegression: maxIncrease(older),
	};
}
