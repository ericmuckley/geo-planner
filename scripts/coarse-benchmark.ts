import assert from "node:assert/strict";
import { replayBenchmarkRun } from "./coarse-benchmark-capture";
import { planSha256, readBenchmarkPlan } from "./coarse-benchmark-plan";

type Run = Awaited<ReturnType<typeof replayBenchmarkRun>>;
type Ors = NonNullable<Run["cases"][number]["ors"]>;
type Inputs = Awaited<ReturnType<typeof readBenchmarkPlan>>;
type Model = Inputs["records"][number]["baseline"];
const mean = (values: number[]) =>
	values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
function metrics(values: number[]) {
	const absolute = values.map(Math.abs).sort((a, b) => a - b);
	const n = absolute.length;
	return {
		meanSignedMinutes: mean(values),
		meanAbsoluteMinutes: mean(absolute),
		medianAbsoluteMinutes: n
			? (absolute[Math.floor((n - 1) / 2)] + absolute[Math.floor(n / 2)]) / 2
			: null,
		p90AbsoluteMinutes: n ? absolute[Math.ceil(n * 0.9) - 1] : null,
	};
}
function difference(
	model: Model,
	reference: Ors | null,
	budget: number,
	frontier: boolean,
) {
	if (!reference) return null;
	const signed = model.pointMinutes - reference.minutes;
	return {
		signedMinutes: signed,
		absoluteMinutes: Math.abs(signed),
		signedPercent: (signed / reference.minutes) * 100,
		classification: !frontier
			? null
			: Math.abs(reference.minutes - budget) <= 5
				? "ambiguous"
				: model.predictedReachable === reference.minutes < budget
					? "correct"
					: model.predictedReachable
						? "falseReachable"
						: "missedReachable",
	};
}
function engineKey(reference: Ors | null) {
	const e = reference?.engine;
	const values = [e?.version, e?.build_date, e?.graph_date, e?.osm_date];
	return values.every((v) => typeof v === "string" && v.length > 0)
		? JSON.stringify(values)
		: null;
}

/** Join exactly 29 new outcomes with 54 sealed live results; never calls a service. */
export async function joinBenchmarkReport(run: Run) {
	const inputs = await readBenchmarkPlan();
	assert.equal(run.planSha256, planSha256);
	assert.equal(run.cases.length, 29);
	assert.deepEqual(
		run.cases.map((r) => r.id),
		inputs.queries.map((r) => r.id),
	);
	const refs = new Map<
		string,
		{
			source: string;
			reference: Ors | null;
			outcome: string;
			status: number | null;
		}
	>();
	for (const r of inputs.control.cases)
		refs.set(r.id, {
			source: "saved-control",
			reference: r.ors,
			outcome: r.outcome,
			status: r.status,
		});
	for (const r of inputs.frontier.cases)
		refs.set(`frontier/${r.id}`, {
			source: "saved-frontier",
			reference: r.reference,
			outcome: r.outcome,
			status: r.status,
		});
	for (const r of run.cases) {
		assert.ok(!refs.has(r.id), "New reference replaces a saved reference");
		refs.set(r.id, {
			source: run.transport === "live" ? "new-live" : "new-synthetic",
			reference: r.ors,
			outcome: r.outcome,
			status: r.status,
		});
	}
	assert.equal(refs.size, 83);
	const cases = inputs.records.map((row) => {
		const saved = refs.get(row.id);
		assert.ok(saved);
		const v8 = difference(
			row.baseline,
			saved.reference,
			row.budgetMinutes,
			row.set === "frontier",
		);
		const candidate = difference(
			row.candidate,
			saved.reference,
			row.budgetMinutes,
			row.set === "frontier",
		);
		const olderGap =
			saved.reference && row.valhalla
				? saved.reference.minutes - row.valhalla.minutes
				: null;
		return {
			id: row.id,
			set: row.set,
			origin: row.origin,
			destination: row.destination,
			budgetMinutes: row.budgetMinutes,
			source: saved.source,
			status: saved.status,
			outcome: saved.outcome,
			ors: saved.reference,
			v8Model: row.baseline,
			rejectedCandidateModel: row.candidate,
			v8,
			rejectedCandidate: candidate,
			absoluteErrorChangeMinutes:
				v8 && candidate ? candidate.absoluteMinutes - v8.absoluteMinutes : null,
			valhalla: row.valhalla,
			orsMinusValhalla:
				olderGap === null || !row.valhalla || !saved.reference
					? null
					: {
							signedMinutes: olderGap,
							absoluteMinutes: Math.abs(olderGap),
							signedPercent: (olderGap / row.valhalla.minutes) * 100,
							distanceDifferenceKm:
								saved.reference.distanceKm - row.valhalla.distanceKm,
						},
		};
	});
	type Row = (typeof cases)[number];
	function summarize(rows: Row[]) {
		const paired = rows.filter((r) => r.ors !== null);
		const models = Object.fromEntries(
			(["v8", "rejectedCandidate"] as const).map((name) => {
				const values = paired.map((r) => {
					assert.ok(r[name]);
					return r[name];
				});
				return [
					name,
					{
						...metrics(values.map((v) => v.signedMinutes)),
						meanAbsolutePercent: mean(
							values.map((v) => Math.abs(v.signedPercent)),
						),
						classification: Object.fromEntries(
							["correct", "falseReachable", "missedReachable", "ambiguous"].map(
								(c) => [c, values.filter((v) => v.classification === c).length],
							),
						),
					},
				];
			}),
		);
		return {
			planned: rows.length,
			pairedFinite: paired.length,
			unpaired: rows.length - paired.length,
			snapOver100m: paired.filter((r) => r.ors?.snapOver100m).length,
			models,
			candidateChanges: {
				improve: paired.filter(
					(r) => (r.absoluteErrorChangeMinutes ?? 0) < -1e-9,
				).length,
				regress: paired.filter(
					(r) => (r.absoluteErrorChangeMinutes ?? 0) > 1e-9,
				).length,
				unchanged: paired.filter(
					(r) => Math.abs(r.absoluteErrorChangeMinutes ?? 0) <= 1e-9,
				).length,
			},
		};
	}
	function groups(rows: Row[]) {
		return {
			overall: summarize(rows),
			bySet: Object.fromEntries(
				["original", "regional", "frontier"].map((set) => [
					set,
					summarize(rows.filter((r) => r.set === set)),
				]),
			),
			frontierByHorizon: Object.fromEntries(
				[360, 600, 720].map((h) => [
					h,
					summarize(
						rows.filter((r) => r.set === "frontier" && r.budgetMinutes === h),
					),
				]),
			),
			frontierByOrigin: Object.fromEntries(
				[
					...new Set(
						rows
							.filter((r) => r.set === "frontier")
							.map((r) => JSON.stringify(r.origin)),
					),
				]
					.sort()
					.map((origin) => [
						origin,
						summarize(
							rows.filter(
								(r) =>
									r.set === "frontier" && JSON.stringify(r.origin) === origin,
							),
						),
					]),
			),
		};
	}
	const cohortKeys = [
		...new Set(cases.filter((r) => r.ors).map((r) => engineKey(r.ors))),
	].sort();
	const savedKeys = new Set(
		cases
			.filter((r) => r.source.startsWith("saved"))
			.map((r) => engineKey(r.ors)),
	);
	assert.equal(savedKeys.size, 1);
	assert.ok(!savedKeys.has(null));
	const unpaired = cases.filter((r) => !r.ors).length;
	const compatible =
		cohortKeys.length === 1 &&
		cohortKeys[0] !== null &&
		savedKeys.has(cohortKeys[0]);
	const completeAndCompatible = unpaired === 0 && compatible;
	const older = cases.filter((r) => r.valhalla !== null);
	function valhallaSensitivity(rows: Row[]) {
		return {
			planned: rows.length,
			v8: metrics(
				rows.map((r) => {
					assert.ok(r.valhalla);
					return r.v8Model.pointMinutes - r.valhalla.minutes;
				}),
			),
			rejectedCandidate: metrics(
				rows.map((r) => {
					assert.ok(r.valhalla);
					return r.rejectedCandidateModel.pointMinutes - r.valhalla.minutes;
				}),
			),
		};
	}
	return {
		planSha256,
		transport: run.transport,
		attemptedNewRequests: run.attempted,
		stopReason: run.stopReason,
		denominators: {
			plannedTotal: 83,
			savedFrontier: 48,
			savedControls: 6,
			newPlanned: 29,
			olderTotal: 35,
			pairedFinite: 83 - unpaired,
			unpaired,
		},
		compatibility: {
			completeFinite: unpaired === 0,
			matchesSavedEngineBuildGraphOsm: compatible,
			missingMetadata: cases.filter((r) => r.ors && engineKey(r.ors) === null)
				.length,
			cohortCount: cohortKeys.length,
		},
		completedLiveBenchmark: completeAndCompatible && run.transport === "live",
		primary: completeAndCompatible ? groups(cases) : null,
		snapAtMost100mSensitivity: completeAndCompatible
			? {
					plannedTotal: 83,
					excludedUnpaired: unpaired,
					excludedSnapOver100m: cases.filter((r) => r.ors?.snapOver100m).length,
					...groups(cases.filter((r) => r.ors && !r.ors.snapOver100m)),
				}
			: null,
		cohorts: cohortKeys.map((key) => ({
			engineBuildGraphOsm: key ? JSON.parse(key) : null,
			...groups(cases.filter((r) => r.ors && engineKey(r.ors) === key)),
			snapAtMost100mSensitivity: groups(
				cases.filter(
					(r) => r.ors && engineKey(r.ors) === key && !r.ors.snapOver100m,
				),
			),
		})),
		olderOrsMinusValhalla: {
			planned: 35,
			paired: older.filter((r) => r.orsMinusValhalla).length,
			...metrics(
				older.flatMap((r) =>
					r.orsMinusValhalla ? [r.orsMinusValhalla.signedMinutes] : [],
				),
			),
			meanAbsolutePercent: mean(
				older.flatMap((r) =>
					r.orsMinusValhalla
						? [Math.abs(r.orsMinusValhalla.signedPercent)]
						: [],
				),
			),
		},
		savedValhallaSensitivity: {
			...valhallaSensitivity(older),
			metadata: inputs.control.valhallaMetadata,
			bySet: Object.fromEntries(
				["original", "regional"].map((set) => [
					set,
					valhallaSensitivity(older.filter((r) => r.set === set)),
				]),
			),
		},
		savedFrontierV8Summary: inputs.frontier.overall,
		cases,
		scope:
			"All83 are observed development cases, not national/area accuracy, traffic truth or a fresh holdout. Original candidate rejection/gates are unchanged. Primary pooling requires all83 finite and identical complete engine/build/graph/OSM metadata matching saved references; otherwise use cohorts and case ledger. Synthetic/mixed reports never qualify as live. No new correction or acceptance gate fitted. HTTP-plus-body elapsed is not engine search time.",
	};
}

export async function compareBenchmarkRun(directory: string) {
	return joinBenchmarkReport(await replayBenchmarkRun(directory));
}
