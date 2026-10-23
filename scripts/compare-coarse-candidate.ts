import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import type { Origin } from "../src/lib/reachability";
import { decodeGrid } from "../src/server/coarse-data.server";
import {
	attachGrid,
	distanceKm,
	estimateGrid,
	type GridData,
	gridAttachments,
	gridPosition,
} from "../src/server/coarse-grid";

const path = process.argv[2];
assert.ok(path, "Pass an offline candidate artifact path");
const raw = await readFile(path, "utf8");
const data = JSON.parse(raw),
	candidate = decodeGrid(data);
const baselineData = JSON.parse(
	await readFile("src/server/data/coarse-grid-v4.json", "utf8"),
);
const baseline = decodeGrid(baselineData);
assert.deepEqual(data.roadSpeedsKph, baselineData.roadSpeedsKph);
for (const key of [
	"land",
	"traversable",
	"displayLand",
	"anchorOffsets",
	"shoreLinks",
	"roadAccess",
])
	assert.deepEqual(
		data[key],
		baselineData[key],
		`${key} must remain unchanged`,
	);
const preserved = JSON.parse(
	await readFile("docs/evidence/coarse-v4-2026-10-22/comparison.json", "utf8"),
);
type Sample = {
	id: string;
	origin: Origin;
	destination: Origin;
	referenceMinutes: number;
};
const fields = new Map<string, ReturnType<typeof estimateGrid>>();
function measure(
	grid: GridData,
	model: string,
	origin: Origin,
	destination: Origin,
) {
	const key = `${model}/${origin.lat}/${origin.lon}`;
	let field = fields.get(key);
	if (!field) {
		field = estimateGrid(grid, origin, 720);
		fields.set(key, field);
	}
	const cell =
		Math.floor((destination.lat - grid.bounds[1]) / grid.step) * grid.width +
		Math.floor((destination.lon - grid.bounds[0]) / grid.step);
	const value = field.labels[cell];
	const attachments = gridAttachments(grid, destination);
	const pointValue = Math.min(
		...attachments.map(
			(attachment) => field.labels[attachment.cell] + attachment.minutes,
		),
	);
	return {
		cellMinutes: Number.isFinite(value) ? value : null,
		pointMinutes: Number.isFinite(pointValue) ? pointValue : null,
		shaded: Number.isFinite(value) && !!(grid.displayLand ?? grid.land)[cell],
		node: gridPosition(grid, cell),
		destinationAttachments: attachments,
		originAttachment: attachGrid(grid, origin) ?? null,
		straightDestinationAccessMinutes:
			(distanceKm(
				[destination.lon, destination.lat],
				gridPosition(grid, cell),
			) /
				25) *
			60,
	};
}

function compare(samples: Sample[]) {
	const rows = samples.map((s) => ({
		...s,
		baseline: measure(baseline, "v4", s.origin, s.destination),
		candidate: measure(candidate, "candidate", s.origin, s.destination),
	}));
	const finite = rows.filter(
		(r) =>
			r.baseline.pointMinutes !== null && r.candidate.pointMinutes !== null,
	);
	const mean = (model: "baseline" | "candidate") =>
		finite.reduce(
			(sum, r) =>
				sum + Math.abs((r[model].pointMinutes ?? 0) - r.referenceMinutes),
			0,
		) / finite.length;
	return {
		samples: rows,
		summary: {
			cases: rows.length,
			commonFinitePointCases: finite.length,
			baselinePointMeanAbsoluteDifferenceMinutes: mean("baseline"),
			candidatePointMeanAbsoluteDifferenceMinutes: mean("candidate"),
			improvedCommonPointCases: finite.filter(
				(r) =>
					Math.abs((r.candidate.pointMinutes ?? 0) - r.referenceMinutes) <
					Math.abs((r.baseline.pointMinutes ?? 0) - r.referenceMinutes) - 1e-8,
			).length,
			regressedCommonPointCases: finite.filter(
				(r) =>
					Math.abs((r.candidate.pointMinutes ?? 0) - r.referenceMinutes) >
					Math.abs((r.baseline.pointMinutes ?? 0) - r.referenceMinutes) + 1e-8,
			).length,
			unreachedBaselinePointCases: rows.filter(
				(r) => r.baseline.pointMinutes === null,
			).length,
			unreachedCandidatePointCases: rows.filter(
				(r) => r.candidate.pointMinutes === null,
			).length,
			unshadedCandidateDestinations: rows.filter((r) => !r.candidate.shaded)
				.length,
			newlyReached: rows
				.filter(
					(r) =>
						r.baseline.pointMinutes === null &&
						r.candidate.pointMinutes !== null,
				)
				.map((r) => ({
					id: r.id,
					candidatePointMinutes: r.candidate.pointMinutes,
					referenceMinutes: r.referenceMinutes,
				})),
		},
	};
}

const originalReport = compare(preserved.original.samples);
const regionalReport = compare(preserved.regional.samples);
for (const [current, previous] of [
	[originalReport, preserved.original],
	[regionalReport, preserved.regional],
]) {
	for (const sample of current.samples) {
		const recorded = previous.samples.find((s: Sample) => s.id === sample.id);
		assert.ok(recorded);
		assert.equal(sample.baseline.pointMinutes, recorded.candidate.pointMinutes);
	}
}
console.log(
	JSON.stringify(
		{
			artifact: path,
			artifactBytes: Buffer.byteLength(raw),
			artifactSha256: createHash("sha256").update(raw).digest("hex"),
			model: data.version,
			baselineModel: baselineData.version,
			baselineSha256: createHash("sha256")
				.update(await readFile("src/server/data/coarse-grid-v4.json"))
				.digest("hex"),
			roadSpeedsKph: data.roadSpeedsKph,
			shoreLandCells: data.shoreLandCells,
			shoreLocalLinks: data.shoreLocalLinks,
			original: originalReport,
			regional: regionalReport,
			publicRoutingApiCalls: 0,
			localServiceRequests: 0,
			scope:
				"Offline candidate versus preserved v4 on both saved reference sets. Point arrival uses the same charged geography-checked attachment as departure; common-finite means and reachability remain separate. All 35 v4 baseline costs are checked against preserved results. Baseline masks, positions, shore paths and speeds remain unchanged. The reference sets guide refinement and are not new holdouts or national accuracy validation.",
		},
		null,
		2,
	),
);
