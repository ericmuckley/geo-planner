// Offline, single frozen candidate; no environment/DB/provider inputs.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { gzipSync } from "node:zlib";
import type { Origin } from "../src/lib/reachability";
import { attachRoadTimePolicy } from "../src/server/backbone-cost";
import type { Backbone, BackboneGraph } from "../src/server/backbone-geometry";
import { nodePoint, pointCell } from "../src/server/backbone-geometry";
import { pointTiming, searchBackbone } from "../src/server/backbone-routing";
import { decodeGrid } from "../src/server/coarse-data.server";
import { gridPosition } from "../src/server/coarse-grid";
import {
	evaluateDampedGates,
	type TimingRow,
	timingSummary,
} from "./coarse-damped-gates";

const [output, expectedPlanSha256] = process.argv.slice(2);
const hash = (raw: Uint8Array) =>
	createHash("sha256").update(raw).digest("hex");
const json = (value: unknown) => `${JSON.stringify(value, null, 2)}\n`;
assert.ok(
	output && /^[a-f0-9]{64}$/.test(expectedPlanSha256 ?? ""),
	"Pass output and frozen execution-plan SHA",
);
const rawPlan = await readFile(
	"docs/evidence/coarse-road-time-allowance-2026-10-25/execution-plan.json",
);
assert.equal(hash(rawPlan), expectedPlanSha256);
const plan = JSON.parse(rawPlan.toString());
assert.equal(resolve(output), resolve(plan.output));
assert.ok(resolve(output).startsWith(`${resolve("data/coarse-quality")}/`));
for (const [path, expected] of Object.entries(plan.inputs))
	assert.equal(hash(await readFile(path)), expected, path);
await mkdir(output);
await mkdir(join(output, "origins"));
await writeFile(join(output, "execution-plan.json"), rawPlan, { flag: "wx" });
let outboundCalls = 0;
globalThis.fetch = async () => {
	outboundCalls++;
	throw new Error("Unexpected outbound fetch");
};
const { loadBackboneBinary } = await import(
	pathToFileURL(resolve("scripts/backbone-binary-loader.mjs")).href
);
const loaded = loadBackboneBinary(
	pathToFileURL(resolve(plan.binary)),
	plan.binaryManifest,
	decodeGrid,
);
const model: Backbone = {
	base: loaded.base,
	graph: loaded.graph as BackboneGraph,
	originalNodes: loaded.summary.originalNodes,
};
attachRoadTimePolicy(model.base);
const saved = JSON.parse(await readFile(plan.baseline, "utf8"));
type Sample = {
	id: string;
	set: "frontier" | "original" | "regional";
	origin: Origin;
	destination: Origin;
	budgetMinutes: number;
	referenceMinutes: number;
	valhallaMinutes: number | null;
	candidate: TimingRow["baseline"];
};
// Copy only current case inputs; never carry inherited scalar error fields.
const samples: Sample[] = saved.rows.map((r: Sample) => ({
	id: r.id,
	set: r.set,
	origin: r.origin,
	destination: r.destination,
	budgetMinutes: r.budgetMinutes,
	referenceMinutes: r.referenceMinutes,
	valhallaMinutes: r.valhallaMinutes,
	candidate: r.candidate,
}));
assert.equal(samples.length, 83);
assert.equal(samples.filter((s) => s.valhallaMinutes !== null).length, 35);
type Row = TimingRow & Omit<Sample, "candidate">;
const rows: Row[] = [],
	paths: unknown[] = [],
	originResults: unknown[] = [];
const origins = new Map(
	samples.map((s) => [JSON.stringify(s.origin), s.origin]),
);
const write = (name: string, value: unknown) =>
	writeFile(join(output, name), json(value), { flag: "wx" });
let originIndex = 0;
try {
	for (const [key, origin] of origins) {
		console.error(
			`Comparing generic origin ${++originIndex}/${origins.size}: ${key}`,
		);
		const started = performance.now();
		const field = searchBackbone(model, origin, 900);
		const scope = {
			origin,
			settled: field.settled,
			searchMs: field.searchMs,
			displayArrivalMs: field.displayMs,
			fieldMs: performance.now() - started,
			diagnosticBudgetMinutes: 900,
		};
		await write(`origins/${String(originIndex).padStart(2, "0")}.json`, scope);
		originResults.push(scope);
		for (const sample of samples.filter(
			(s) => JSON.stringify(s.origin) === key,
		)) {
			const measured = pointTiming(model, field, sample.destination);
			const cell = pointCell(model.base, [
				sample.destination.lon,
				sample.destination.lat,
			]);
			const predictedReachable =
				field.cellMinutes[cell] <= sample.budgetMinutes &&
				!!(model.base.displayLand ?? model.base.land)[cell];
			const classification =
				Math.abs(sample.referenceMinutes - sample.budgetMinutes) <= 5
					? "ambiguous"
					: predictedReachable ===
							sample.referenceMinutes < sample.budgetMinutes
						? "correct"
						: predictedReachable
							? "falseReachable"
							: "missedReachable";
			const candidate = {
				pointMinutes: measured?.minutes ?? null,
				predictedReachable,
				pathComponents: measured?.components ?? null,
				classification,
			};
			const baseline = sample.candidate;
			const row: Row = {
				...sample,
				baseline,
				candidate,
				absoluteErrorChangeMinutes:
					measured === null
						? null
						: Math.abs(measured.minutes - sample.referenceMinutes) -
							Math.abs(
								(baseline.pointMinutes ?? Infinity) - sample.referenceMinutes,
							),
			};
			rows.push(row);
			const position = (node: number) =>
				node < model.base.width * model.base.height
					? gridPosition(model.base, node)
					: nodePoint(model.graph, node - model.base.width * model.base.height);
			paths.push({
				id: `${sample.set}/${sample.id}`,
				origin: sample.origin,
				destination: sample.destination,
				pointMinutes: measured?.minutes ?? null,
				components: measured?.components ?? null,
				direct: measured?.direct ?? null,
				edges:
					measured?.edges.map((e) => ({
						...e,
						fromPoint: position(e.from),
						toPoint: position(e.target),
					})) ?? [],
			});
		}
		await write(
			`origins/${String(originIndex).padStart(2, "0")}-rows.json`,
			rows.filter((r) => JSON.stringify(r.origin) === key),
		);
	}
} catch (error) {
	await write("failure.json", {
		message: error instanceof Error ? error.message : String(error),
		completedRows: rows.length,
		completedOrigins: originResults.length,
		outboundCalls,
		plannedRows: 83,
		remainingRowsRetainedAsUnmeasured: true,
	});
	throw error;
}
const thresholds = plan.gates;
const admission = {
	overallMeanAbsoluteMaximum: thresholds.overallMaeMaximum,
	frontierMeanAbsoluteMaximum: thresholds.frontierMaeMaximum,
	setMeansMaximum: {
		original: thresholds.originalMaeMaximum,
		regional: thresholds.regionalMaeMaximum,
	},
	frontierP90Maximum: thresholds.frontierP90Maximum,
	horizonMeansMaximum: Object.fromEntries(
		[360, 600, 720].map((h) => [
			h,
			saved.byHorizon[h].candidate.meanAbsoluteMinutes,
		]),
	),
	horizonP90Maximum: Object.fromEntries(
		[360, 600, 720].map((h) => [
			h,
			saved.byHorizon[h].candidate.p90AbsoluteMinutes,
		]),
	),
	maximumFrontierAbsoluteErrorIncreaseMinutes:
		thresholds.maximumIndividualAbsoluteErrorIncreaseMinutes.frontier,
	maximumOlderAbsoluteErrorIncreaseMinutes:
		thresholds.maximumIndividualAbsoluteErrorIncreaseMinutes.older,
	maximumFrontierDefiniteClassificationErrors:
		thresholds.maximumFrontierDefiniteErrors,
	maximumFrontierMissedReachable: thresholds.maximumFrontierMissed,
	maximum12hMissedReachable: thresholds.maximum12hMissed,
};
const evaluation = evaluateDampedGates(rows, admission);
const summary = (items: Row[]) => ({
	baseline: timingSummary(items, "baseline"),
	candidate: timingSummary(items, "candidate"),
});
const overall = summary(rows);
const sets = Object.fromEntries(
	(["original", "regional", "frontier"] as const).map((set) => [
		set,
		summary(rows.filter((r) => r.set === set)),
	]),
);
const sensitivity = Object.fromEntries(
	(["original", "regional"] as const).map((set) => [
		set,
		summary(
			rows
				.filter((r) => r.set === set)
				.map((r) => ({ ...r, referenceMinutes: r.valhallaMinutes ?? NaN })),
		),
	]),
);
const within = (value: number | null, maximum: number | null) =>
	value !== null &&
	maximum !== null &&
	Number.isFinite(value) &&
	value <= maximum + 1e-10;
const gates = {
	...evaluation.gates,
	frontierMedian: within(
		sets.frontier.candidate.medianAbsoluteMinutes,
		thresholds.frontierMedianMaximum,
	),
	overallP90NoWorse: within(
		overall.candidate.p90AbsoluteMinutes,
		overall.baseline.p90AbsoluteMinutes,
	),
	originalP90NoWorse: within(
		sets.original.candidate.p90AbsoluteMinutes,
		sets.original.baseline.p90AbsoluteMinutes,
	),
	regionalP90NoWorse: within(
		sets.regional.candidate.p90AbsoluteMinutes,
		sets.regional.baseline.p90AbsoluteMinutes,
	),
	valhallaOriginalNoWorse: within(
		sensitivity.original.candidate.meanAbsoluteMinutes,
		sensitivity.original.baseline.meanAbsoluteMinutes,
	),
	valhallaRegionalNoWorse: within(
		sensitivity.regional.candidate.meanAbsoluteMinutes,
		sensitivity.regional.baseline.meanAbsoluteMinutes,
	),
};
assert.equal(outboundCalls, 0);
const pathRaw = gzipSync(json(paths));
await writeFile(join(output, "paths.json.gz"), pathRaw, { flag: "wx" });
const report = {
	model: "source-road-time-allowance-v1",
	planSha256: expectedPlanSha256,
	binarySha256: plan.binaryManifest.sha256,
	sourceRoadTimeFactor: 1.1,
	overall,
	sets,
	valhallaSensitivity: sensitivity,
	byHorizon: Object.fromEntries(
		[360, 600, 720].map((h) => [
			h,
			summary(
				rows.filter((r) => r.set === "frontier" && r.budgetMinutes === h),
			),
		]),
	),
	worstRegressions: {
		frontier: evaluation.maxFrontierRegression,
		older: evaluation.maxOlderRegression,
	},
	gates,
	accuracyGatesPassed: Object.values(gates).every(Boolean),
	rows,
	originResults,
	pathSha256: hash(pathRaw),
	loadDecodeValidateMs: loaded.summary.loadDecodeValidateMs,
	outboundCalls,
	runtimeChanged: false,
	scope:
		"Saved83 ORS/35 Valhalla development comparison.900min diagnostic fields, whole-cell shading and point times separate. No fresh references, full packaged-query/cloud qualification or activation.",
};
await write("comparison.json", report);
console.log(
	json({
		accuracyGatesPassed: report.accuracyGatesPassed,
		gates,
		overall,
		sets,
		valhallaSensitivity: sensitivity,
		worstRegressions: report.worstRegressions,
		rows: rows.length,
		origins: origins.size,
		outboundCalls,
	}),
);
if (!report.accuracyGatesPassed) process.exitCode = 2;
