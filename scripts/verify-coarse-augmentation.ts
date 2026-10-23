import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { decodeGrid } from "../src/server/coarse-data.server";
import { landConnection } from "../src/server/coarse-geography";
import {
	distanceKm,
	gridAttachments,
	gridPosition,
} from "../src/server/coarse-grid";

const [artifact, buildReport] = process.argv.slice(2);
const anchorInputs = process.argv.includes("--anchor-inputs");
assert.ok(
	artifact && buildReport,
	"Pass candidate artifact and build-report paths",
);
const raw = await readFile(artifact);
const report = JSON.parse(await readFile(buildReport, "utf8"));
assert.equal(
	createHash("sha256").update(raw).digest("hex"),
	report.artifactSha256,
);
const before = process.memoryUsage();
const started = performance.now();
const candidate = decodeGrid(JSON.parse(raw.toString()));
const decodeMs = performance.now() - started;
const after = process.memoryUsage();
const baseline = decodeGrid(
	JSON.parse(await readFile("src/server/data/coarse-grid-v4.json", "utf8")),
);
assert.equal(candidate.roadVisits?.size, baseline.roadVisits?.size);
for (const [cell, visit] of candidate.roadVisits ?? [])
	assert.deepEqual(visit, baseline.roadVisits?.get(cell));
for (const key of [
	"land",
	"traversable",
	"displayLand",
	"anchorOffsets",
	"shoreLinks",
	"roadAccess",
] as const)
	assert.deepEqual(candidate[key], baseline[key]);

type Edge = {
	key: number;
	a: number;
	b: number;
	pointA: number[];
	pointB: number[];
	roadKm: number;
	localKm: number;
	speedKph: number;
	deciseconds: number;
};
const changed = new Map<number, Edge>(
	report.changedLinks.map((edge: Edge) => [edge.key, edge]),
);
let newLinks = 0;
for (const [key, cost] of candidate.roadDeciseconds?.entries() ?? []) {
	const original = baseline.roadDeciseconds?.[key] ?? 0;
	assert.ok(!original || (cost > 0 && cost <= original), `Lost road at ${key}`);
	if (cost === original) {
		assert.equal(candidate.links[key], baseline.links[key]);
		assert.ok(!changed.has(key));
		continue;
	}
	if (!original) newLinks++;
	const edge = changed.get(key);
	assert.ok(edge, `Missing changed-link provenance ${key}`);
	const origin = Math.floor(key / 4);
	const [dx, dy] = [
		[1, 0],
		[1, 1],
		[0, 1],
		[-1, 1],
	][key % 4];
	const target = origin + dy * candidate.width + dx;
	assert.deepEqual([edge.a, edge.b].sort(), [origin, target].sort());
	const a = gridPosition(candidate, edge.a);
	const b = gridPosition(candidate, edge.b);
	assert.ok(landConnection(candidate, a, edge.pointA));
	assert.ok(landConnection(candidate, edge.pointB, b));
	assert.ok(edge.roadKm + 1e-7 >= distanceKm(edge.pointA, edge.pointB));
	assert.ok(
		Math.abs(
			edge.localKm - distanceKm(a, edge.pointA) - distanceKm(edge.pointB, b),
		) < 1e-7,
	);
	assert.equal(
		cost,
		Math.ceil((edge.localKm / 25 + edge.roadKm / edge.speedKph) * 36000),
	);
	assert.equal(cost, edge.deciseconds);
	assert.equal(candidate.links[key], edge.speedKph);
	assert.ok(cost / 36000 + 1e-8 >= distanceKm(a, b) / 105);
}
assert.equal(newLinks, report.newLinkSlots);
assert.equal(changed.size, newLinks + report.improvedExistingLinkSlots);

const timings: number[] = [];
let supplementalPoints = 0;
let sampledAttachments = 0;
let maxPointsInVisit = 0;
for (const [cell, visit] of candidate.supplementalRoadVisits ?? []) {
	const anchor = gridPosition(candidate, cell);
	assert.equal(
		visit.transferKm,
		distanceKm(anchor, visit.points[visit.anchorIndex]),
	);
	supplementalPoints += visit.points.length;
	maxPointsInVisit = Math.max(maxPointsInVisit, visit.points.length);
	// Systematic dataset-wide sampling, with no city/region exceptions.
	if (cell % 31 !== 0) continue;
	const point = visit.points[anchorInputs ? visit.anchorIndex : 0];
	const start = performance.now();
	const attachments = gridAttachments(candidate, {
		lon: point[0],
		lat: point[1],
	});
	timings.push(performance.now() - start);
	for (const attachment of attachments) {
		const chord = distanceKm(point, gridPosition(candidate, attachment.cell));
		assert.ok(attachment.distanceKm + 1e-7 >= chord);
		assert.ok(attachment.minutes + 1e-7 >= (chord / 105) * 60);
		sampledAttachments++;
	}
}
assert.equal(supplementalPoints, report.geometry.supplementalPoints);
timings.sort((a, b) => a - b);
console.log(
	JSON.stringify(
		{
			artifact,
			inputSelection: anchorInputs
				? "Validated on-land source-visit anchors"
				: "First retained source vertices (may include generalized water)",
			artifactSha256: report.artifactSha256,
			unchangedBaseVisits: candidate.roadVisits?.size,
			changedLinks: changed.size,
			newLinks,
			supplementalVisits: candidate.supplementalRoadVisits?.size,
			supplementalPoints,
			maxPointsInVisit,
			sampledInputs: timings.length,
			sampledAttachments,
			decodeMs,
			observedDecodeHeapDeltaBytes: after.heapUsed - before.heapUsed,
			observedDecodeRssDeltaBytes: after.rss - before.rss,
			attachmentMedianMs: timings[Math.floor(timings.length / 2)],
			attachmentMaxMs: timings.at(-1),
			scope:
				"Offline structural/physical checks and local one-process observations, not cloud peak memory, a load test or a nationwide size/accuracy forecast. All original road costs retained or lowered; all changed links pay source arcs and land-checked local transfers. Packed v4 visits decode exactly. Systematically sampled supplemental attachments pay physical distance/time.",
		},
		null,
		2,
	),
);
