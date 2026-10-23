// Compare geographic points across grids; cell IDs/anchors need not coincide.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import type { Origin } from "../src/lib/reachability";
import { decodeGrid } from "../src/server/coarse-data.server";
import {
	estimateGrid,
	type GridData,
	gridAttachments,
} from "../src/server/coarse-grid";

const artifact = process.argv[2];
assert.ok(artifact, "Pass a fresh resolution candidate artifact");
const baselinePath = "src/server/data/coarse-grid-v5.json";
const [raw, baselineRaw, preservedRaw] = await Promise.all([
	readFile(artifact),
	readFile(baselinePath),
	readFile("docs/evidence/coarse-v5-2026-10-22/comparison.json", "utf8"),
]);
const data = JSON.parse(raw.toString());
const baselineData = JSON.parse(baselineRaw.toString());
const candidate = decodeGrid(data),
	baseline = decodeGrid(baselineData);
assert.deepEqual(candidate.bounds, baseline.bounds);
assert.ok(candidate.step < baseline.step);
assert.deepEqual(data.roadSpeedsKph, baselineData.roadSpeedsKph);
assert.deepEqual(data.censusRoadSpeedsKph, baselineData.censusRoadSpeedsKph);
assert.deepEqual(data.sources, baselineData.sources);
assert.equal(
	data.censusSourceManifestSha256,
	baselineData.censusSourceManifestSha256,
);
const preserved = JSON.parse(preservedRaw);
type Sample = {
	id: string;
	origin: Origin;
	destination: Origin;
	referenceMinutes: number;
	candidate: { pointMinutes: number | null };
};
const fields = new Map<string, ReturnType<typeof estimateGrid>>();
function measure(grid: GridData, model: string, sample: Sample) {
	const { origin, destination } = sample;
	const key = `${model}/${origin.lat}/${origin.lon}`;
	let field = fields.get(key);
	if (!field) {
		field = estimateGrid(grid, origin, 720);
		fields.set(key, field);
	}
	const x = Math.floor((destination.lon - grid.bounds[0]) / grid.step);
	const y = Math.floor((destination.lat - grid.bounds[1]) / grid.step);
	const cell = y * grid.width + x;
	const attachments = gridAttachments(grid, destination);
	const point = Math.min(
		...attachments.map((a) => field.labels[a.cell] + a.minutes),
	);
	return {
		pointMinutes: Number.isFinite(point) ? point : null,
		cellMinutes: Number.isFinite(field.labels[cell])
			? field.labels[cell]
			: null,
		shaded:
			Number.isFinite(field.labels[cell]) &&
			!!(grid.displayLand ?? grid.land)[cell],
		attachments,
	};
}
const mean = (values: number[]) =>
	values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
const median = (values: number[]) => {
	if (!values.length) return null;
	const sorted = [...values].sort((a, b) => a - b),
		m = Math.floor(sorted.length / 2);
	return sorted.length % 2 ? sorted[m] : (sorted[m - 1] + sorted[m]) / 2;
};
function compare(samples: Sample[]) {
	const rows = samples.map((sample) => {
		const base = measure(baseline, "baseline", sample),
			next = measure(candidate, "candidate", sample);
		assert.equal(
			base.pointMinutes,
			sample.candidate.pointMinutes,
			`Changed preserved v5 cost: ${sample.id}`,
		);
		const error = (value: number | null) =>
			value === null ? null : value - sample.referenceMinutes;
		const baselineErrorMinutes = error(base.pointMinutes),
			candidateErrorMinutes = error(next.pointMinutes);
		return {
			id: sample.id,
			origin: sample.origin,
			destination: sample.destination,
			referenceMinutes: sample.referenceMinutes,
			baseline: base,
			candidate: next,
			baselineErrorMinutes,
			candidateErrorMinutes,
			absoluteErrorChangeMinutes:
				baselineErrorMinutes === null || candidateErrorMinutes === null
					? null
					: Math.abs(candidateErrorMinutes) - Math.abs(baselineErrorMinutes),
		};
	});
	const paired = rows.filter((r) => r.absoluteErrorChangeMinutes !== null);
	return {
		samples: rows,
		summary: {
			cases: rows.length,
			commonFiniteCases: paired.length,
			baselineMeanAbsoluteErrorMinutes: mean(
				paired.map((r) => Math.abs(r.baselineErrorMinutes ?? 0)),
			),
			candidateMeanAbsoluteErrorMinutes: mean(
				paired.map((r) => Math.abs(r.candidateErrorMinutes ?? 0)),
			),
			baselineMedianAbsoluteErrorMinutes: median(
				paired.map((r) => Math.abs(r.baselineErrorMinutes ?? 0)),
			),
			candidateMedianAbsoluteErrorMinutes: median(
				paired.map((r) => Math.abs(r.candidateErrorMinutes ?? 0)),
			),
			improved: paired.filter(
				(r) => (r.absoluteErrorChangeMinutes ?? 0) < -1e-8,
			).length,
			regressed: paired.filter(
				(r) => (r.absoluteErrorChangeMinutes ?? 0) > 1e-8,
			).length,
			unchanged: paired.filter(
				(r) => Math.abs(r.absoluteErrorChangeMinutes ?? 0) <= 1e-8,
			).length,
			unreachedBaseline: rows
				.filter((r) => r.baseline.pointMinutes === null)
				.map((r) => r.id),
			unreachedCandidate: rows
				.filter((r) => r.candidate.pointMinutes === null)
				.map((r) => r.id),
			unshadedCandidateDestinations: rows
				.filter((r) => !r.candidate.shaded)
				.map((r) => r.id),
			worstRegressions: [...paired]
				.filter((r) => (r.absoluteErrorChangeMinutes ?? 0) > 1e-8)
				.sort(
					(a, b) =>
						(b.absoluteErrorChangeMinutes ?? 0) -
						(a.absoluteErrorChangeMinutes ?? 0),
				)
				.slice(0, 5)
				.map((r) => ({
					id: r.id,
					absoluteErrorChangeMinutes: r.absoluteErrorChangeMinutes,
					baselineErrorMinutes: r.baselineErrorMinutes,
					candidateErrorMinutes: r.candidateErrorMinutes,
				})),
		},
	};
}
console.log(
	JSON.stringify(
		{
			artifact,
			artifactSha256: createHash("sha256").update(raw).digest("hex"),
			artifactBytes: raw.length,
			baselinePath,
			baselineSha256: createHash("sha256").update(baselineRaw).digest("hex"),
			model: data.version,
			baselineStep: baseline.step,
			candidateStep: candidate.step,
			original: compare(preserved.original.samples),
			regional: compare(preserved.regional.samples),
			publicRoutingApiCalls: 0,
			localServiceRequests: 0,
			scope:
				"Same geographic queries across independently rebuilt resolutions, all preserved v5 point costs checked exactly. Paired finite errors and all unreached/unshaded outcomes reported separately. Reused regional development references are not national driving accuracy or frontier validation. No provider, database or source request.",
		},
		null,
		2,
	),
);
