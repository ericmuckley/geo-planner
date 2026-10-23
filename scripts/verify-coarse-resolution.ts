import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { gunzipSync } from "node:zlib";
import { decodeGrid } from "../src/server/coarse-data.server";
import { landConnection } from "../src/server/coarse-geography";
import {
	distanceKm,
	estimateGrid,
	gridAttachments,
	gridPosition,
} from "../src/server/coarse-grid";
import { coarseSmokeOrigins } from "./coarse-smoke-cases";

const [artifact, buildPath] = process.argv.slice(2);
assert.ok(
	artifact && buildPath,
	"Pass a candidate artifact and its build report",
);
const sha = (bytes: Uint8Array) =>
	createHash("sha256").update(bytes).digest("hex");
const [raw, reportRaw] = await Promise.all([
	readFile(artifact),
	readFile(buildPath, "utf8"),
]);
const report = JSON.parse(reportRaw),
	data = JSON.parse(raw.toString());
assert.equal(sha(raw), report.artifactSha256);
assert.equal(data.width * data.step, data.bounds[2] - data.bounds[0]);
assert.equal(data.height * data.step, data.bounds[3] - data.bounds[1]);
const started = performance.now();
const grid = decodeGrid(data),
	decodeMs = performance.now() - started;
const proofBytes = await readFile(report.linkProof.path);
assert.equal(sha(proofBytes), report.linkProof.sha256);
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
	kind: "census" | "natural-earth";
};
const proofs = JSON.parse(gunzipSync(proofBytes).toString()) as Edge[];
const keys = new Set<number>();
const kinds = { census: 0, "natural-earth": 0 };
for (const edge of proofs) {
	assert.ok(!keys.has(edge.key));
	keys.add(edge.key);
	assert.equal(grid.roadDeciseconds?.[edge.key], edge.deciseconds);
	assert.equal(grid.links[edge.key], edge.speedKph);
	const [dx, dy] = [
		[1, 0],
		[1, 1],
		[0, 1],
		[-1, 1],
	][edge.key % 4];
	assert.deepEqual(
		[edge.a, edge.b].sort((a, b) => a - b),
		[
			Math.floor(edge.key / 4),
			Math.floor(edge.key / 4) + dy * grid.width + dx,
		].sort((a, b) => a - b),
	);
	const a = gridPosition(grid, edge.a),
		b = gridPosition(grid, edge.b);
	assert.ok(edge.roadKm + 1e-7 >= distanceKm(edge.pointA, edge.pointB));
	assert.ok(
		Math.abs(
			edge.localKm - distanceKm(a, edge.pointA) - distanceKm(edge.pointB, b),
		) < 1e-7,
	);
	assert.ok((edge.deciseconds / 36000) * 105 + 1e-6 >= distanceKm(a, b));
	if (edge.kind === "census") {
		assert.ok(landConnection(grid, a, edge.pointA));
		assert.ok(landConnection(grid, edge.pointB, b));
		assert.equal(
			edge.deciseconds,
			Math.max(
				1,
				Math.ceil((edge.localKm / 25 + edge.roadKm / edge.speedKph) * 36000),
			),
		);
	} else {
		assert.equal(
			edge.deciseconds,
			Math.max(
				1,
				Math.ceil(((edge.localKm + edge.roadKm) / edge.speedKph) * 36000),
			),
		);
	}
	kinds[edge.kind]++;
}
assert.equal(proofs.length, report.roadLinks);
assert.equal(
	[...(grid.roadDeciseconds ?? [])].filter(Boolean).length,
	proofs.length,
);
let shoreLinks = 0;
for (const [cell, bits] of grid.shoreLinks?.entries() ?? [])
	for (let d = 0; d < 4; d++) {
		if (!(bits & (1 << d))) continue;
		const [dx, dy] = [
			[1, 0],
			[1, 1],
			[0, 1],
			[-1, 1],
		][d];
		assert.ok(
			landConnection(
				grid,
				gridPosition(grid, cell),
				gridPosition(grid, cell + dy * grid.width + dx),
			),
		);
		shoreLinks++;
	}
assert.equal(shoreLinks, report.shoreLocalLinks);
let visits = 0,
	points = 0,
	sampledInputs = 0;
for (const [cell, visit] of grid.supplementalRoadVisits ?? []) {
	visits++;
	points += visit.points.length;
	if (cell % 31) continue;
	const point = visit.points[visit.anchorIndex];
	const attachments = gridAttachments(grid, { lon: point[0], lat: point[1] });
	assert.ok(attachments.length);
	for (const attachment of attachments)
		assert.ok(
			(attachment.minutes / 60) * 105 + 1e-6 >=
				distanceKm(point, gridPosition(grid, attachment.cell)),
		);
	sampledInputs++;
}
assert.equal(visits, report.supplementalVisits);
assert.equal(points, report.supplementalPoints);
const samples = [];
for (const [name, lat, lon] of coarseSmokeOrigins) {
	let previous = 0;
	for (const minutes of [360, 600, 720]) {
		const start = performance.now();
		const estimate = estimateGrid(grid, { lat, lon }, minutes);
		assert.ok(estimate.reachedCells >= previous);
		previous = estimate.reachedCells;
		if (name !== "Nantucket")
			assert.ok(estimate.reachedCells >= 10, `${name}/${minutes} collapsed`);
		const geometryBytes = Buffer.byteLength(
			JSON.stringify(estimate.coordinates),
		);
		assert.ok(geometryBytes < 1_000_000);
		const seed =
			Math.floor((lat - grid.bounds[1]) / grid.step) * grid.width +
			Math.floor((lon - grid.bounds[0]) / grid.step);
		let areaKm2 = 0;
		for (let row = 0; row < grid.height; row++) {
			const low = ((grid.bounds[1] + row * grid.step) * Math.PI) / 180,
				high = low + (grid.step * Math.PI) / 180;
			const cellArea =
				6371 ** 2 *
				((grid.step * Math.PI) / 180) *
				(Math.sin(high) - Math.sin(low));
			for (let col = 0; col < grid.width; col++) {
				const cell = row * grid.width + col;
				if (
					cell === seed ||
					((grid.displayLand ?? grid.land)[cell] &&
						estimate.labels[cell] <= minutes)
				)
					areaKm2 += cellArea;
			}
		}
		samples.push({
			name,
			lat,
			lon,
			minutes,
			cells: estimate.reachedCells,
			reachedCellFootprintKm2: areaKm2,
			geometryBytes,
			searchMs: estimate.searchMs,
			contourMs: estimate.contourMs,
			estimateAndStatisticsMs: performance.now() - start,
		});
	}
}
console.log(
	JSON.stringify(
		{
			artifact,
			artifactSha256: sha(raw),
			step: grid.step,
			decodeMs,
			roadLinks: proofs.length,
			sourceKinds: kinds,
			shoreLinks,
			owningVisits: grid.roadVisits?.size,
			supplementalVisits: visits,
			supplementalPoints: points,
			sampledInputs,
			samples,
			memoryUsage: process.memoryUsage(),
			publicRoutingApiCalls: 0,
			scope:
				"Full retained-link proof, full shore-link and load-time visit validation, systematic attachment sample, 42 arbitrary-origin/budget software smoke cases. Cell footprint is approximate spherical whole-cell area, not actual accessible land or an accuracy score. NE legacy transfers retain road-class speed; Census transfers retain strict land checks at 25 km/h. Timings/memory are local process observations, not cloud performance. No services or references.",
		},
		null,
		2,
	),
);
