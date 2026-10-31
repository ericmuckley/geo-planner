// Read captured paths at two existing cost tables; never run a route search.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { gunzipSync, gzipSync } from "node:zlib";
import {
	attachRoadTimePolicy,
	baseRoadPrice,
	sourceRoadTimeFactor,
} from "../src/server/backbone-cost";
import type { Backbone, BackboneGraph } from "../src/server/backbone-geometry";
import {
	type CapturedPath,
	controlledCostChange,
	priceCapturedPath,
	sameStateSequence,
} from "../src/server/backbone-path-control";
import { decodeGrid } from "../src/server/coarse-data.server";

const [output, expectedPlanSha256] = process.argv.slice(2);
const hash = (raw: Uint8Array) =>
	createHash("sha256").update(raw).digest("hex");
const json = (value: unknown) => `${JSON.stringify(value, null, 2)}\n`;
const started = performance.now();
assert.ok(output && /^[a-f0-9]{64}$/.test(expectedPlanSha256 ?? ""));
const planRaw = await readFile(
	"docs/evidence/coarse-road-time-control-2026-10-25/plan.json",
);
assert.equal(hash(planRaw), expectedPlanSha256);
const plan = JSON.parse(planRaw.toString());
assert.equal(resolve(output), resolve(plan.output));
assert.ok(resolve(output).startsWith(`${resolve("data/coarse-quality")}/`));
for (const [path, expected] of Object.entries(plan.inputs))
	assert.equal(hash(await readFile(path)), expected, path);
assert.equal(sourceRoadTimeFactor, 1.1);
await mkdir(output);
await writeFile(join(output, "plan.json"), planRaw, { flag: "wx" });
let outboundCalls = 0;
globalThis.fetch = async () => {
	outboundCalls++;
	throw new Error("Unexpected outbound request");
};
const { loadBackboneBinary } = await import(
	pathToFileURL(resolve("scripts/backbone-binary-loader.mjs")).href
);
function asModel(state: {
	base: Backbone["base"];
	graph: BackboneGraph;
	summary: { originalNodes: number };
}): Backbone {
	return {
		base: state.base,
		graph: state.graph,
		originalNodes: state.summary.originalNodes,
	};
}
const oldModel = asModel(
	loadBackboneBinary(
		pathToFileURL(resolve(plan.oldBinary)),
		plan.oldManifest,
		decodeGrid,
	),
);
const currentModel = asModel(
	loadBackboneBinary(
		pathToFileURL(resolve(plan.currentBinary)),
		plan.currentManifest,
		decodeGrid,
	),
);
attachRoadTimePolicy(currentModel.base);
const captured = async (path: string): Promise<CapturedPath[]> =>
	JSON.parse(gunzipSync(await readFile(path)).toString());
const [oldPaths, newPaths] = await Promise.all([
	captured(plan.oldPaths),
	captured(plan.currentPaths),
]);
const paths = new Map(newPaths.map((path) => [path.id, path]));
type BaseDetail = {
	key: number;
	sourceKind: string;
	minutes: number;
	roadKm: number;
	connectorKm: number;
	sourceRoadMinutes: number;
	connectorMinutes: number;
	speedKph: number;
	connectorSpeedKph: number;
};
const baseDetails: Map<string, BaseDetail[]> = new Map(
	JSON.parse(gunzipSync(await readFile(plan.baseEdgeAudit)).toString()).map(
		(row: { id: string; edges: BaseDetail[] }) => [row.id, row.edges],
	),
);
type Measured = {
	id: string;
	set: "frontier" | "original" | "regional";
	budgetMinutes: number;
	referenceMinutes: number;
	valhallaMinutes: number | null;
	baseline: { pointMinutes: number; classification: string };
	candidate: { pointMinutes: number; classification: string };
	absoluteErrorChangeMinutes: number;
};
const measured: Measured[] = JSON.parse(
	await readFile(plan.comparison, "utf8"),
).rows;
const samples = new Map(measured.map((row) => [`${row.set}/${row.id}`, row]));
assert.equal(oldPaths.length, 83);
assert.equal(paths.size, 83);
assert.equal(samples.size, 83);
assert.equal(measured.filter((r) => r.valhallaMinutes !== null).length, 35);
const rows: Record<string, unknown>[] = [];
const ledger = oldPaths.map((path) => ({ id: path.id, status: "pending" }));
const edgeAudit: unknown[] = [];
const write = (name: string, value: unknown) =>
	writeFile(join(output, name), json(value), { flag: "wx" });
try {
	for (const [index, path] of oldPaths.entries()) {
		const actual = paths.get(path.id),
			sample = samples.get(path.id);
		assert.ok(actual && sample, path.id);
		assert.deepEqual(path.origin, actual.origin);
		assert.deepEqual(path.destination, actual.destination);
		assert.equal(actual.pointMinutes, sample.candidate.pointMinutes);
		const old = priceCapturedPath(oldModel, path, true);
		const held = priceCapturedPath(currentModel, path);
		const current = priceCapturedPath(currentModel, actual, true);
		assert.ok(old.maximumStateMinutes <= plan.diagnosticCapMinutes + 1e-8);
		assert.ok(current.maximumStateMinutes <= plan.diagnosticCapMinutes + 1e-8);
		const control = controlledCostChange(
			old.minutes,
			held.minutes,
			current.minutes,
			held.maximumStateMinutes,
			plan.diagnosticCapMinutes,
		);
		const shifts = Object.fromEntries(
			Object.keys(old.components).map((key) => {
				const name = key as keyof typeof old.components;
				return [name, held.components[name] - old.components[name]];
			}),
		);
		const sourceByClass: Record<string, number> = {};
		const addSource = (speed: number, minutes: number) => {
			sourceByClass[speed] = (sourceByClass[speed] ?? 0) + minutes;
		};
		let baseRoundingShift = 0,
			samePairAlternativeShift = 0,
			detailIndex = 0;
		const details = baseDetails.get(path.id);
		assert.ok(details);
		for (const [i, edge] of old.edges.entries()) {
			if (edge.arc !== undefined) {
				addSource(
					oldModel.graph.arcSpeedKph[edge.arc],
					(oldModel.graph.arcRoadKm[edge.arc] /
						oldModel.graph.arcSpeedKph[edge.arc]) *
						60,
				);
			} else if (edge.kind === "road") {
				const detail: BaseDetail = details[detailIndex++];
				assert.ok(detail);
				assert.ok(Math.abs(detail.minutes - edge.minutes) < 1e-8);
				const words = oldModel.base.roadDeciseconds,
					currentWords = currentModel.base.roadDeciseconds;
				assert.ok(words && currentWords);
				assert.equal(words[detail.key] / 600, edge.minutes);
				const proof = {
					key: detail.key,
					roadKm: detail.roadKm,
					localKm: detail.connectorKm,
					speedKph: detail.speedKph,
					connectorSpeedKph: detail.connectorSpeedKph,
					deciseconds: words[detail.key],
					kind: detail.sourceKind,
				};
				assert.equal(baseRoadPrice(proof, 1), words[detail.key]);
				assert.equal(
					baseRoadPrice(proof, sourceRoadTimeFactor),
					currentWords[detail.key],
				);
				addSource(detail.speedKph, detail.sourceRoadMinutes);
				const oldRound =
					edge.minutes - detail.sourceRoadMinutes - detail.connectorMinutes;
				const newRound =
					currentWords[detail.key] / 600 -
					sourceRoadTimeFactor * detail.sourceRoadMinutes -
					detail.connectorMinutes;
				baseRoundingShift += newRound - oldRound;
				samePairAlternativeShift +=
					held.edges[i].minutes - currentWords[detail.key] / 600;
			} else assert.ok(Math.abs(held.edges[i].minutes - edge.minutes) < 1e-8);
		}
		assert.equal(detailIndex, details.length);
		const fullRoadSourceMinutes = Object.values(sourceByClass).reduce(
			(a, b) => a + b,
			0,
		);
		const roadAllowanceShift =
			(sourceRoadTimeFactor - 1) * fullRoadSourceMinutes;
		const endpointShift = shifts.origin + shifts.destination;
		const pricingEquationResidual =
			control.directCostShift -
			roadAllowanceShift -
			baseRoundingShift -
			samePairAlternativeShift -
			endpointShift;
		assert.ok(Math.abs(pricingEquationResidual) < 1e-8);
		assert.ok(
			Math.abs(
				Object.values(shifts).reduce((a, b) => a + b, 0) -
					control.directCostShift,
			) < 1e-8,
		);
		assert.ok(
			Math.abs(
				control.directCostShift -
					control.pathChoiceBenefit -
					control.actualCostShift,
			) < 1e-8,
		);
		assert.ok(current.minutes >= old.minutes - 1e-8);
		const worstLimit =
			sample.set === "frontier"
				? plan.frontierRegressionLimit
				: plan.olderRegressionLimit;
		const missed = sample.candidate.classification === "missedReachable";
		const oldSourceClass = plan.oldClassifications[path.id];
		assert.equal(typeof oldSourceClass, "string");
		rows.push({
			id: path.id,
			set: sample.set,
			budgetMinutes: sample.budgetMinutes,
			referenceMinutes: sample.referenceMinutes,
			valhallaMinutes: sample.valhallaMinutes,
			v9Minutes: sample.baseline.pointMinutes,
			oldSourceMinutes: old.minutes,
			heldStateMinutes: held.minutes,
			actualAllowanceMinutes: current.minutes,
			oldSourceSignedErrorMinutes: old.minutes - sample.referenceMinutes,
			actualSignedErrorMinutes: current.minutes - sample.referenceMinutes,
			...control,
			componentShifts: shifts,
			fullRoadSourceMinutes,
			sourceByClass,
			roadAllowanceShift,
			baseRoundingShift,
			samePairAlternativeShift,
			endpointShift,
			pricingEquationResidual,
			oldComponents: old.components,
			heldComponents: held.components,
			actualComponents: current.components,
			withinStateKindChanges: held.kindChanges,
			sameStateSequence: sameStateSequence(path, actual),
			originStateChanged: path.edges[0].from !== actual.edges[0].from,
			terminalStateChanged:
				path.edges[path.edges.length - 1].target !==
				actual.edges[actual.edges.length - 1].target,
			oldV9Classification: sample.baseline.classification,
			oldSourceClassification: oldSourceClass,
			newClassification: sample.candidate.classification,
			newMissVsV9:
				missed && sample.baseline.classification !== "missedReachable",
			newMissVsSource: missed && oldSourceClass !== "missedReachable",
			persistentSourceMiss: missed && oldSourceClass === "missedReachable",
			originalRegressionGateExceeded:
				sample.absoluteErrorChangeMinutes > worstLimit + 1e-10,
		});
		edgeAudit.push({
			id: path.id,
			oldEdges: old.edges,
			heldEdges: held.edges,
			actualEdges: current.edges,
		});
		ledger[index].status = control.capLimited
			? "cap_limited"
			: "bound_verified";
		console.error(`Controlled saved path ${index + 1}/83: ${path.id}`);
	}
} catch (error) {
	const next = ledger.findIndex((row) => row.status === "pending");
	if (next >= 0) {
		ledger[next].status = "failed";
		for (let i = next + 1; i < ledger.length; i++)
			ledger[i].status = "unmeasured_after_failure";
	}
	await write("failure.json", {
		message: error instanceof Error ? error.message : String(error),
		completedRows: rows.length,
		ledger,
		routeSearches: 0,
		outboundCalls,
	});
	throw error;
}
assert.equal(rows.length, 83);
assert.equal(outboundCalls, 0);
const mean = (items: Record<string, unknown>[], key: string) =>
	items.length
		? items.reduce((a, row) => a + Number(row[key]), 0) / items.length
		: null;
const cohort = (items: Record<string, unknown>[]) => ({
	cases: items.length,
	meanDirectCostShift: mean(items, "directCostShift"),
	meanPathChoiceBenefit: mean(items, "pathChoiceBenefit"),
	meanActualCostShift: mean(items, "actualCostShift"),
	meanOldSourceSignedError: mean(items, "oldSourceSignedErrorMinutes"),
	meanActualSignedError: mean(items, "actualSignedErrorMinutes"),
	meanRoadAllowanceShift: mean(items, "roadAllowanceShift"),
	meanBaseRoundingShift: mean(items, "baseRoundingShift"),
	meanSamePairAlternativeShift: mean(items, "samePairAlternativeShift"),
	meanEndpointShift: mean(items, "endpointShift"),
	stateSequencesChanged: items.filter((r) => !r.sameStateSequence).length,
	capLimited: items.filter((r) => r.capLimited).length,
	nontrivialPathChoiceBenefit: items.filter(
		(r) => Number(r.pathChoiceBenefit) > 1e-8,
	).length,
});
const cohorts = {
	all: rows,
	frontier: rows.filter((r) => r.set === "frontier"),
	original: rows.filter((r) => r.set === "original"),
	regional: rows.filter((r) => r.set === "regional"),
	newMissVsV9: rows.filter((r) => r.newMissVsV9),
	newMissVsSource: rows.filter((r) => r.newMissVsSource),
	persistentSourceMiss: rows.filter((r) => r.persistentSourceMiss),
	originalRegressionGateExceeded: rows.filter(
		(r) => r.originalRegressionGateExceeded,
	),
};
const report = {
	planSha256: expectedPlanSha256,
	sourceRoadTimeFactor: 1.1,
	plannedCases: 83,
	valhallaSensitivities: 35,
	allOldAndCurrentCapturedPricesReproduced: true,
	allHeldTransitionsEligible: true,
	allComponentEquationsReconcile: true,
	boundVerified: ledger.filter((r) => r.status === "bound_verified").length,
	capLimited: ledger.filter((r) => r.status === "cap_limited").length,
	summary: Object.fromEntries(
		Object.entries(cohorts).map(([key, items]) => [key, cohort(items)]),
	),
	rows,
	ledger,
	routeSearches: 0,
	outboundCalls,
	runtimeChanged: false,
	elapsedMs: performance.now() - started,
	observedRssBytes: process.memoryUsage().rss,
	scope:
		"Saved graph-state/source-arc control, not literally fixed attachment/base-alternative geometry. No new field, contour, factor, provider or accepted candidate. Prefix cap applies before final point attachment. Observed development data; descriptive cost/path-choice accounting, not traffic/national truth or app/cloud measurement.",
};
await write("report.json", report);
await writeFile(join(output, "edge-audit.json.gz"), gzipSync(json(edgeAudit)), {
	flag: "wx",
});
console.log(json({ ...report, rows: undefined, ledger: undefined }));
