import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { gunzipSync } from "node:zlib";
import { decodeGrid } from "../src/server/coarse-data.server";
import { landConnection } from "../src/server/coarse-geography";
import {
	distanceKm,
	estimateGrid,
	gridCellMinutes,
	gridPosition,
	gridTransitions,
} from "../src/server/coarse-grid";
import { coarseSmokeOrigins } from "./coarse-smoke-cases";

const [artifact, reportPath] = process.argv.slice(2);
assert.ok(
	artifact && reportPath,
	"Pass a candidate artifact and its build report",
);
const hash = (raw: Uint8Array) =>
	createHash("sha256").update(raw).digest("hex");
const report = JSON.parse(await readFile(reportPath, "utf8"));
const [raw, baseRaw] = await Promise.all([
	readFile(artifact),
	readFile(report.baseArtifact ?? "src/server/data/coarse-grid-v6.json"),
]);
const data = JSON.parse(raw.toString()),
	base = JSON.parse(baseRaw.toString());
assert.equal(hash(raw), report.artifactSha256);
assert.equal(hash(baseRaw), report.baseSha256);
for (const key of Object.keys(base))
	if (key !== "version")
		assert.deepEqual(data[key], base[key], `Changed base field: ${key}`);
const start = performance.now(),
	grid = decodeGrid(data),
	decodeMs = performance.now() - start;
const layer = grid.roadLayer;
assert.ok(layer);
const size = grid.width * grid.height;
let states = 0;
for (let cell = 0; cell < size; cell++) {
	if (!layer.transferDeciseconds[cell]) continue;
	states++;
	const a = gridPosition(grid, cell),
		b = gridPosition(grid, size + cell);
	assert.ok(landConnection(grid, a, b));
	assert.equal(
		layer.transferDeciseconds[cell],
		Math.max(1, Math.ceil((distanceKm(a, b) / grid.localSpeedKph) * 36000)),
	);
}
assert.equal(states, report.roadStates);
const proofRaw = await readFile(report.linkProof.path);
assert.equal(hash(proofRaw), report.linkProof.sha256);
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
const edges = JSON.parse(gunzipSync(proofRaw).toString()) as Edge[];
const keys = new Set<number>();
let connectorMinutes = 0,
	sourceRoadMinutes = 0;
for (const edge of edges) {
	assert.ok(!keys.has(edge.key));
	keys.add(edge.key);
	assert.equal(layer.roadDeciseconds[edge.key], edge.deciseconds);
	const [dx, dy] = [
			[1, 0],
			[1, 1],
			[0, 1],
			[-1, 1],
		][edge.key % 4],
		cell = Math.floor(edge.key / 4);
	assert.deepEqual(
		[edge.a, edge.b].sort((a, b) => a - b),
		[cell, cell + dy * grid.width + dx].sort((a, b) => a - b),
	);
	const a = gridPosition(grid, size + edge.a),
		b = gridPosition(grid, size + edge.b);
	assert.ok(landConnection(grid, a, edge.pointA));
	assert.ok(landConnection(grid, edge.pointB, b));
	assert.ok(edge.roadKm + 1e-7 >= distanceKm(edge.pointA, edge.pointB));
	assert.ok(
		Math.abs(
			edge.localKm - distanceKm(a, edge.pointA) - distanceKm(edge.pointB, b),
		) < 1e-7,
	);
	assert.equal(
		edge.deciseconds,
		Math.max(
			1,
			Math.ceil((edge.localKm / 25 + edge.roadKm / edge.speedKph) * 36000),
		),
	);
	assert.ok((edge.deciseconds / 36000) * 105 + 1e-6 >= distanceKm(a, b));
	assert.ok([80, 105].includes(edge.speedKph));
	connectorMinutes += (edge.localKm / 25) * 60;
	sourceRoadMinutes += (edge.roadKm / edge.speedKph) * 60;
}
assert.equal(keys.size, report.roadLinks);
let links = 0;
for (const time of layer.roadDeciseconds) if (time) links++;
assert.equal(links, keys.size);
const prior = JSON.parse(
	await readFile(
		"docs/evidence/coarse-resolution-2026-10-23/national-api.json",
		"utf8",
	),
);
const samples = [];
for (const [name, lat, lon] of coarseSmokeOrigins) {
	let previous = 0;
	for (const minutes of [360, 600, 720]) {
		const t = performance.now(),
			estimate = estimateGrid(grid, { lat, lon }, minutes),
			estimateAndContourMs = performance.now() - t;
		const baseline = prior.samples.find(
			(s: { name: string; minutes: number }) =>
				s.name === name && s.minutes === minutes,
		);
		assert.ok(baseline);
		assert.ok(
			grid.step !== 0.05 || estimate.reachedCells >= baseline.cells,
			`${name}/${minutes} lost v6 cells`,
		);
		assert.ok(estimate.reachedCells >= previous);
		previous = estimate.reachedCells;
		const geometryBytes = Buffer.byteLength(
			JSON.stringify(estimate.coordinates),
		);
		assert.ok(geometryBytes < 1_000_000);
		// Every finite state inside the horizon is at least as far away physically
		// as its charged 105 km/h maximum-speed lower bound permits.
		const origin = [lon, lat];
		for (let node = 0; node < estimate.labels.length; node += 31) {
			if (
				!Number.isFinite(estimate.labels[node]) ||
				estimate.labels[node] > minutes
			)
				continue;
			assert.ok(
				(estimate.labels[node] / 60) * 105 + 1e-5 >=
					distanceKm(origin, gridPosition(grid, node)),
			);
		}
		const originCell =
			Math.floor((lat - grid.bounds[1]) / grid.step) * grid.width +
			Math.floor((lon - grid.bounds[0]) / grid.step);
		assert.ok(gridCellMinutes(grid, estimate.labels, originCell) >= 0);
		const outgoing = [...gridTransitions(grid, size + originCell)];
		assert.ok(outgoing.every((e) => e.minutes > 0));
		samples.push({
			name,
			minutes,
			cells: estimate.reachedCells,
			baselineV6Cells: grid.step === 0.05 ? baseline.cells : undefined,
			geometryBytes,
			searchMs: estimate.searchMs,
			contourMs: estimate.contourMs,
			estimateAndContourMs,
		});
	}
}
console.log(
	JSON.stringify(
		{
			artifact,
			artifactSha256: hash(raw),
			baseSha256: hash(baseRaw),
			decodeMs,
			roadStates: states,
			roadLinks: links,
			summedConnectorShare:
				connectorMinutes / (connectorMinutes + sourceRoadMinutes),
			samples,
			memoryUsage: process.memoryUsage(),
			publicRoutingApiCalls: 0,
			scope:
				"All input base fields preserved; full new-link and state-transfer physical/land/cost proof. Forty-two horizon-monotonic software cases (v6 counts compared only at the same resolution) and sampled whole-path speed lower bounds. Summed connector share is an unweighted graph statistic, not typical-trip delay or isolated real-world error. Local process observations, not cloud performance/national accuracy. No reference/provider/database calls.",
		},
		null,
		2,
	),
);
