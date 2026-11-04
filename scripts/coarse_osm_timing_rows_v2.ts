/** Preserve every reference case, including unsupported source failures. */
import type { TimingRow } from "./coarse-damped-gates.ts";

export function timingRow<T extends TimingRow>(
	sample: T,
	ticks: number | null,
	shaded: boolean,
	failure: string | null = null,
) {
	const baseline = sample.candidate,
		pointMinutes = ticks === null ? null : ticks / 480;
	const classification =
		Math.abs(sample.referenceMinutes - sample.budgetMinutes) <= 5
			? "ambiguous"
			: shaded === sample.referenceMinutes < sample.budgetMinutes
				? "correct"
				: shaded
					? "falseReachable"
					: "missedReachable";
	if (failure !== null && (pointMinutes !== null || shaded))
		throw new Error("Failed estimate cannot be finite or shaded");
	return {
		...sample,
		baseline,
		candidate: {
			pointMinutes,
			predictedReachable: shaded,
			pathComponents: null,
			classification,
		},
		absoluteErrorChangeMinutes:
			pointMinutes === null || baseline.pointMinutes === null
				? null
				: Math.abs(pointMinutes - sample.referenceMinutes) -
					Math.abs(baseline.pointMinutes - sample.referenceMinutes),
		estimateFailure: failure,
	};
}
