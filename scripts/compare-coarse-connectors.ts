// Offline development comparison; never imported by application routing.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { gzipSync } from "node:zlib";
import type { Origin } from "../src/lib/reachability";
import { decodeGrid } from "../src/server/coarse-data.server";
import {
	estimateGrid,
	type GridData,
	gridAttachments,
	gridCellMinutes,
	gridPosition,
	gridTransitions,
} from "../src/server/coarse-grid";
import {
	type DampedAdmission,
	evaluateDampedGates,
	timingSummary as summary,
} from "./coarse-damped-gates";

const [artifact, output] = process.argv.slice(2);
assert.ok(artifact && output, "Pass a candidate and fresh output directory");
assert.ok(resolve(output).startsWith(`${resolve("data/coarse-quality")}/`));
const hash = (raw: Buffer) => createHash("sha256").update(raw).digest("hex");
const policyRaw = await readFile(
	"docs/evidence/coarse-path-features-2026-10-24/candidate-plan.json",
);
const policySha256 =
	"5a990ab557251ef75fb98b17381c307a32679ddbd3ccf270f775e8d80baf6a81";
assert.equal(hash(policyRaw), policySha256);
const policy = JSON.parse(policyRaw.toString());
for (const [path, expected] of Object.entries(policy.inputs))
	assert.equal(hash(await readFile(path)), expected);
const benchmark = JSON.parse(
	await readFile(
		"docs/evidence/coarse-benchmark-reference-2026-10-24/comparison.json",
		"utf8",
	),
);
assert.equal(benchmark.completedLiveBenchmark, true);
await mkdir(output);

const baselinePath = "src/server/data/coarse-grid-v8.json";
const [raw, baselineRaw] = await Promise.all([
	readFile(artifact),
	readFile(baselinePath),
]);
assert.equal(
	hash(baselineRaw),
	"2beb2fb6d9af6e07f37c5ba53acdeca2da1334c31a5fadd1371efd5453134910",
);
const data = JSON.parse(raw.toString()),
	baselineData = JSON.parse(baselineRaw.toString());
const changed = new Set([
	"version",
	"links",
	"roadDeciseconds",
	"roadSpeedsKph",
	"censusRoadSpeedsKph",
	"roadVisits",
	"supplementalRoadVisits",
	"roadLayer",
	"connectionModel",
	"resolutionModel",
]);
for (const key of Object.keys(baselineData))
	if (!changed.has(key))
		assert.deepEqual(
			data[key],
			baselineData[key],
			`Changed geometry/source: ${key}`,
		);
for (const name of ["roadVisits", "supplementalRoadVisits", "roadLayer"])
	for (const key of Object.keys(baselineData[name]))
		if (key !== "speeds" && key !== "roadDeciseconds")
			assert.deepEqual(
				data[name][key],
				baselineData[name][key],
				`${name}/${key} changed`,
			);
assert.equal(data.calibrationPlanSha256, policySha256);
assert.deepEqual(data.censusRoadSpeedsKph, { S1100: 105, S1200: 85 });
assert.deepEqual(data.roadSpeedsKph, {
	"Major Highway": 105,
	Beltway: 90,
	Bypass: 90,
	"Secondary Highway": 85,
	Road: 55,
});
const baseline = decodeGrid(baselineData),
	candidate = decodeGrid(data);
for (const [before, after] of [
	[baseline.roadDeciseconds, candidate.roadDeciseconds],
	[baseline.roadLayer?.roadDeciseconds, candidate.roadLayer?.roadDeciseconds],
]) {
	assert.ok(before && after && before.length === after.length);
	for (let i = 0; i < before.length; i++)
		assert.equal(
			Boolean(before[i]),
			Boolean(after[i]),
			`Topology changed at${i}`,
		);
}
const admission = policy.admission as DampedAdmission;
type Sample = {
	id: string;
	set: "frontier" | "original" | "regional";
	origin: Origin;
	destination: Origin;
	budgetMinutes: number;
	referenceMinutes: number;
	baselinePointMinutes: number;
	expectedMapReachable?: boolean;
	valhallaMinutes: number | null;
};
const samples: Sample[] = benchmark.cases.map(
	(row: {
		id: string;
		set: Sample["set"];
		origin: Origin;
		destination: Origin;
		budgetMinutes: number;
		ors: { minutes: number };
		v8Model: { pointMinutes: number; predictedReachable: boolean };
		valhalla: { minutes: number } | null;
	}) => ({
		id: row.id.slice(row.id.indexOf("/") + 1),
		set: row.set,
		origin: row.origin,
		destination: row.destination,
		budgetMinutes: row.budgetMinutes,
		referenceMinutes: row.ors.minutes,
		baselinePointMinutes: row.v8Model.pointMinutes,
		expectedMapReachable: row.v8Model.predictedReachable,
		valhallaMinutes: row.valhalla?.minutes ?? null,
	}),
);
assert.equal(samples.length, 83);
const paths: Array<{ id: string; model: string; nodes: number[][] }> = [];
function measure(
	grid: GridData,
	field: ReturnType<typeof estimateGrid>,
	sample: Sample,
	model: string,
) {
	const { destination, origin, budgetMinutes } = sample;
	const cell =
		Math.floor((destination.lat - grid.bounds[1]) / grid.step) * grid.width +
		Math.floor((destination.lon - grid.bounds[0]) / grid.step);
	const cellCost = gridCellMinutes(grid, field.labels, cell);
	const point = gridAttachments(grid, destination)
		.map((a) => ({ ...a, total: field.labels[a.cell] + a.minutes }))
		.sort((a, b) => a.total - b.total)[0];
	const pointMinutes =
		point && Number.isFinite(point.total) ? point.total : null;
	const predictedReachable =
		cellCost <= budgetMinutes && Boolean((grid.displayLand ?? grid.land)[cell]);
	let pathComponents: {
		origin: number;
		road: number;
		local: number;
		transfer: number;
		destination: number;
	} | null = null;
	if (pointMinutes !== null) {
		const seeds = gridAttachments(grid, origin);
		let node = point.cell;
		const edges = [];
		let seed: (typeof seeds)[number] | undefined;
		while (edges.length < field.labels.length) {
			seed = seeds.find(
				(s) =>
					s.cell === node && Math.abs(field.labels[node] - s.minutes) < 1e-8,
			);
			if (seed) break;
			const edge = [...gridTransitions(grid, node)].find(
				(e) =>
					e &&
					field.labels[e.target] < field.labels[node] &&
					Math.abs(field.labels[e.target] + e.minutes - field.labels[node]) <
						1e-8,
			);
			assert.ok(edge, `Missing predecessor: ${sample.id}/${model}/${node}`);
			edges.push(edge);
			node = edge.target;
		}
		assert.ok(seed);
		pathComponents = {
			origin: seed.minutes,
			road: 0,
			local: 0,
			transfer: 0,
			destination: point.minutes,
		};
		for (const edge of edges) pathComponents[edge.kind] += edge.minutes;
		assert.ok(
			Math.abs(
				Object.values(pathComponents).reduce((a, b) => a + b, 0) - pointMinutes,
			) < 1e-8,
		);
		paths.push({
			id: `${sample.set}/${sample.id}`,
			model,
			nodes: [
				[origin.lon, origin.lat],
				gridPosition(grid, node),
				...edges.reverse().map((e) => gridPosition(grid, e.cell)),
				[destination.lon, destination.lat],
			],
		});
	}
	const classification =
		Math.abs(sample.referenceMinutes - budgetMinutes) <= 5
			? "ambiguous"
			: predictedReachable === sample.referenceMinutes < budgetMinutes
				? "correct"
				: predictedReachable
					? "falseReachable"
					: "missedReachable";
	return {
		pointMinutes,
		cellMinutes: Number.isFinite(cellCost) ? cellCost : null,
		predictedReachable,
		pathComponents,
		classification,
	};
}
type Row = Sample & {
	baseline: ReturnType<typeof measure>;
	candidate: ReturnType<typeof measure>;
	baselineErrorMinutes: number | null;
	candidateErrorMinutes: number | null;
	absoluteErrorChangeMinutes: number | null;
};
const rows: Row[] = [];
// Keep only one origin's label arrays at a time; no per-query retained cache.
const origins = new Map(
	samples.map((s) => [JSON.stringify(s.origin), s.origin]),
);
for (const [key, origin] of origins) {
	console.error(`Comparing origin ${key}`);
	const baselineField = estimateGrid(baseline, origin, 900),
		candidateField = estimateGrid(candidate, origin, 900);
	for (const sample of samples.filter(
		(s) => JSON.stringify(s.origin) === key,
	)) {
		const before = measure(baseline, baselineField, sample, "v8"),
			after = measure(candidate, candidateField, sample, "candidate");
		assert.ok(
			before.pointMinutes !== null &&
				Math.abs(before.pointMinutes - sample.baselinePointMinutes) < 1e-8,
			`Frozen v8 cost changed:${sample.id}`,
		);
		assert.equal(before.predictedReachable, sample.expectedMapReachable);
		const baselineErrorMinutes = before.pointMinutes - sample.referenceMinutes;
		const candidateErrorMinutes =
			after.pointMinutes === null
				? null
				: after.pointMinutes - sample.referenceMinutes;
		rows.push({
			...sample,
			baseline: before,
			candidate: after,
			baselineErrorMinutes,
			candidateErrorMinutes,
			absoluteErrorChangeMinutes:
				candidateErrorMinutes === null
					? null
					: Math.abs(candidateErrorMinutes) - Math.abs(baselineErrorMinutes),
		});
	}
}
const sets = Object.fromEntries(
	(["frontier", "original", "regional"] as const).map((set) => {
		const selected = rows.filter((r) => r.set === set);
		return [
			set,
			{
				baseline: summary(selected, "baseline"),
				candidate: summary(selected, "candidate"),
				improved: selected.filter(
					(r) => (r.absoluteErrorChangeMinutes ?? 0) < -1e-8,
				).length,
				regressed: selected.filter(
					(r) => (r.absoluteErrorChangeMinutes ?? 0) > 1e-8,
				).length,
				unchanged: selected.filter(
					(r) =>
						r.absoluteErrorChangeMinutes !== null &&
						Math.abs(r.absoluteErrorChangeMinutes) <= 1e-8,
				).length,
			},
		];
	}),
);
const result = evaluateDampedGates(rows, admission);
const gates = result.gates;
const pathBytes = gzipSync(`${JSON.stringify(paths)}\n`);
await writeFile(join(output, "paths.json.gz"), pathBytes, { flag: "wx" });
const report = {
	artifact,
	artifactSha256: hash(raw),
	baselineSha256: hash(baselineRaw),
	model: data.version,
	speedPolicy: {
		naturalEarth: data.roadSpeedsKph,
		census: data.censusRoadSpeedsKph,
	},
	planSha256: policySha256,
	benchmarkSha256:
		policy.inputs[
			"docs/evidence/coarse-benchmark-reference-2026-10-24/comparison.json"
		],
	overall: {
		baseline: summary(rows, "baseline"),
		candidate: summary(rows, "candidate"),
	},
	valhallaSensitivity: Object.fromEntries(
		(["original", "regional"] as const).map((set) => {
			const items = rows
				.filter((r) => r.set === set)
				.map((r) => {
					assert.ok(r.valhallaMinutes !== null);
					return { ...r, referenceMinutes: r.valhallaMinutes };
				});
			return [
				set,
				{
					baseline: summary(items, "baseline"),
					candidate: summary(items, "candidate"),
				},
			];
		}),
	),
	worstRegressions: {
		frontier: result.maxFrontierRegression,
		older: result.maxOlderRegression,
	},
	sets,
	gates,
	accuracyGatesPassed: Object.values(gates).every(Boolean),
	byHorizon: Object.fromEntries(
		[360, 600, 720].map((h) => {
			const selected = rows.filter(
				(r) => r.set === "frontier" && r.budgetMinutes === h,
			);
			return [
				h,
				{
					baseline: summary(selected, "baseline"),
					candidate: summary(selected, "candidate"),
				},
			];
		}),
	),
	rows,
	pathSha256: hash(pathBytes),
	providerRequests: 0,
	scope:
		"New road105/85 plusNE-connector55 comparison on all83 frozen ORS development routes; old35 Valhalla results remain separate sensitivity and historical failed gates unchanged. All frozen v8 point costs and frontier cell classifications checked; path sums reconstructed for every finite result. Diagnostic900-minute labels cover outside720 probes; the public API limit is unchanged. No provider/key/env/DB read or activation. Accuracy gates are necessary before activation, not nationwide or fresh-holdout qualification; runtime/physical gates remain separate.",
};
await writeFile(
	join(output, "comparison.json"),
	`${JSON.stringify(report, null, 2)}\n`,
	{ flag: "wx" },
);
console.log(
	JSON.stringify(
		{ output, sets, gates, accuracyGatesPassed: report.accuracyGatesPassed },
		null,
		2,
	),
);
