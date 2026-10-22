import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { decodeGrid } from "../src/server/coarse-data.server";
import {
	distanceKm,
	estimateGrid,
	gridPosition,
} from "../src/server/coarse-grid";

const path = process.argv[2] ?? "src/server/data/coarse-grid-v2.json";
const raw = await readFile(path, "utf8");
const data = JSON.parse(raw);
const grid = decodeGrid(data);
const baseline = JSON.parse(
	await readFile(
		"docs/evidence/coarse-quality-2026-10-22/comparison.json",
		"utf8",
	),
);
const field = estimateGrid(grid, baseline.origin, 720);
const original = decodeGrid(
	JSON.parse(await readFile("src/server/data/coarse-grid-v1.json", "utf8")),
);
const originalField = estimateGrid(original, baseline.origin, 720);
const samples = baseline.samples.map(
	(sample: {
		name: string;
		destination: { lat: number; lon: number };
		coarseCellMinutes: number;
		coarseLandCell: boolean;
		referenceMinutes: number;
	}) => {
		const cell =
			Math.floor((sample.destination.lat - grid.bounds[1]) / grid.step) *
				grid.width +
			Math.floor((sample.destination.lon - grid.bounds[0]) / grid.step);
		const candidateMinutes = field.labels[cell];
		assert.ok(
			Math.abs(originalField.labels[cell] - sample.coarseCellMinutes) < 1e-8,
		);
		const destination = [sample.destination.lon, sample.destination.lat];
		const baselineAccessMinutes =
			(distanceKm(gridPosition(original, cell), destination) /
				original.localSpeedKph) *
			60;
		const candidateAccessMinutes =
			(distanceKm(gridPosition(grid, cell), destination) / grid.localSpeedKph) *
			60;
		assert.ok(
			Number.isFinite(candidateMinutes),
			`Unreachable comparison: ${sample.name}`,
		);
		return {
			name: sample.name,
			referenceMinutes: sample.referenceMinutes,
			baselineMinutes: sample.coarseCellMinutes,
			candidateMinutes,
			baselineNode: gridPosition(original, cell),
			candidateNode: gridPosition(grid, cell),
			baselineDestinationAccessMinutes: baselineAccessMinutes,
			candidateDestinationAccessMinutes: candidateAccessMinutes,
			baselineWithDestinationAccessMinutes:
				sample.coarseCellMinutes + baselineAccessMinutes,
			candidateWithDestinationAccessMinutes:
				candidateMinutes + candidateAccessMinutes,
			baselinePointAbsoluteDifference: Math.abs(
				sample.coarseCellMinutes +
					baselineAccessMinutes -
					sample.referenceMinutes,
			),
			candidatePointAbsoluteDifference: Math.abs(
				candidateMinutes + candidateAccessMinutes - sample.referenceMinutes,
			),
			baselineAbsoluteDifference: Math.abs(
				sample.coarseCellMinutes - sample.referenceMinutes,
			),
			candidateAbsoluteDifference: Math.abs(
				candidateMinutes - sample.referenceMinutes,
			),
			baselineShadedCell: sample.coarseLandCell,
			candidateShadedCell: !!(grid.displayLand ?? grid.land)[cell],
		};
	},
);
const mean = (
	key:
		| "baselineAbsoluteDifference"
		| "candidateAbsoluteDifference"
		| "baselinePointAbsoluteDifference"
		| "candidatePointAbsoluteDifference",
) =>
	samples.reduce(
		(sum: number, sample: Record<typeof key, number>) => sum + sample[key],
		0,
	) / samples.length;
console.log(
	JSON.stringify(
		{
			model: data.version,
			artifact: path,
			artifactBytes: Buffer.byteLength(raw),
			artifactSha256: createHash("sha256").update(raw).digest("hex"),
			originAttachmentKm: field.attachmentKm,
			roadSpeedsKph: data.roadSpeedsKph,
			samples,
			summary: {
				baselineMeanAbsoluteDifferenceMinutes: mean(
					"baselineAbsoluteDifference",
				),
				candidateMeanAbsoluteDifferenceMinutes: mean(
					"candidateAbsoluteDifference",
				),
				improvedCases: samples.filter(
					(s: {
						baselineAbsoluteDifference: number;
						candidateAbsoluteDifference: number;
					}) => s.candidateAbsoluteDifference < s.baselineAbsoluteDifference,
				).length,
				unshadedDestinations: samples.filter(
					(s: { candidateShadedCell: boolean }) => !s.candidateShadedCell,
				).length,
				baselineMeanWithDestinationAccessDifferenceMinutes: mean(
					"baselinePointAbsoluteDifference",
				),
				candidateMeanWithDestinationAccessDifferenceMinutes: mean(
					"candidatePointAbsoluteDifference",
				),
				improvedWithDestinationAccessCases: samples.filter(
					(s) =>
						s.candidatePointAbsoluteDifference <
						s.baselinePointAbsoluteDifference,
				).length,
			},
			publicRoutingApiCalls: 0,
			scope:
				"Offline candidate comparison against eleven preserved regional static routes. Cell costs compare arrival at different representative positions. The supplementary point comparison adds straight destination access at 25 km/h to both; it is also approximate. No service requests, real-world ETA truth or national accuracy validation.",
		},
		null,
		2,
	),
);
