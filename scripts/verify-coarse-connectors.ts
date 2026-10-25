// Independent component/land/physical checks for the prospective connector55 rule.
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
assert.ok(artifact && buildPath);
const hash = (raw: Uint8Array) =>
	createHash("sha256").update(raw).digest("hex");
const raw = await readFile(artifact);
const data = JSON.parse(raw.toString());
const report = JSON.parse(await readFile(buildPath, "utf8"));
assert.equal(hash(raw), report.artifactSha256);
assert.equal(
	report.planSha256,
	"5a990ab557251ef75fb98b17381c307a32679ddbd3ccf270f775e8d80baf6a81",
);
const grid = decodeGrid(data),
	layer = grid.roadLayer;
assert.ok(layer && grid.roadDeciseconds);
const size = grid.width * grid.height;
type Edge = {
	key: number;
	a: number;
	b: number;
	pointA: number[];
	pointB: number[];
	roadKm: number;
	localKm: number;
	speedKph: number;
	connectorSpeedKph: number;
	deciseconds: number;
	kind: string;
};
const counts: Record<string, number> = {};
for (const name of ["base", "layer"] as const) {
	const binding = report.proofs[name];
	const bytes = await readFile(binding.path);
	assert.equal(hash(bytes), binding.sha256);
	const edges = JSON.parse(gunzipSync(bytes).toString()) as Edge[];
	const keys = new Set<number>();
	const costs: Uint16Array =
		name === "base" ? grid.roadDeciseconds : layer.roadDeciseconds;
	for (const edge of edges) {
		assert.ok(!keys.has(edge.key));
		keys.add(edge.key);
		assert.equal(costs[edge.key], edge.deciseconds);
		if (name === "base") assert.equal(grid.links[edge.key], edge.speedKph);
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
		const offset = name === "layer" ? size : 0;
		const a = gridPosition(grid, edge.a + offset),
			b = gridPosition(grid, edge.b + offset);
		assert.ok(edge.roadKm + 1e-7 >= distanceKm(edge.pointA, edge.pointB));
		assert.ok(
			Math.abs(
				edge.localKm - distanceKm(a, edge.pointA) - distanceKm(edge.pointB, b),
			) < 1e-7,
		);
		const connectorSpeed = edge.kind === "natural-earth" ? 55 : 25;
		assert.equal(edge.connectorSpeedKph, connectorSpeed);
		assert.equal(
			edge.deciseconds,
			Math.max(
				1,
				Math.ceil(
					(edge.roadKm / edge.speedKph + edge.localKm / connectorSpeed) * 36000,
				),
			),
		);
		assert.ok([55, 85, 90, 105].includes(edge.speedKph));
		assert.ok((edge.deciseconds / 36000) * 105 + 1e-6 >= distanceKm(a, b));
		if (edge.kind !== "natural-earth") {
			assert.ok(landConnection(grid, a, edge.pointA));
			assert.ok(landConnection(grid, edge.pointB, b));
		}
	}
	assert.equal(keys.size, binding.links);
	assert.equal([...costs].filter(Boolean).length, keys.size);
	counts[name] = keys.size;
}
let states = 0,
	shoreLinks = 0,
	sampledAttachments = 0;
for (let cell = 0; cell < size; cell++) {
	if (!layer.transferDeciseconds[cell]) continue;
	states++;
	const a = gridPosition(grid, cell),
		b = gridPosition(grid, size + cell);
	assert.ok(landConnection(grid, a, b));
	assert.equal(
		layer.transferDeciseconds[cell],
		Math.max(1, Math.ceil((distanceKm(a, b) / 25) * 36000)),
	);
}
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
for (const [cell, visit] of grid.supplementalRoadVisits ?? []) {
	if (cell % 31) continue;
	const point = visit.points[visit.anchorIndex],
		attachments = gridAttachments(grid, { lon: point[0], lat: point[1] });
	assert.ok(attachments.length);
	for (const a of attachments)
		assert.ok(
			(a.minutes / 60) * 105 + 1e-6 >=
				distanceKm(point, gridPosition(grid, a.cell)),
		);
	sampledAttachments++;
}
assert.equal(states, grid.supplementalRoadVisits?.size);
assert.equal(shoreLinks, data.shoreLocalLinks);
const samples = [];
for (const [name, lat, lon] of coarseSmokeOrigins) {
	let previous = 0;
	for (const minutes of [360, 600, 720]) {
		const e = estimateGrid(grid, { lat, lon }, minutes);
		assert.ok(e.reachedCells >= previous);
		previous = e.reachedCells;
		if (name !== "Nantucket") assert.ok(e.reachedCells >= 10);
		const geometryBytes = Buffer.byteLength(JSON.stringify(e.coordinates));
		assert.ok(geometryBytes < 1_000_000);
		for (let node = 0; node < e.labels.length; node += 31)
			if (Number.isFinite(e.labels[node]) && e.labels[node] <= minutes)
				assert.ok(
					(e.labels[node] / 60) * 105 + 1e-5 >=
						distanceKm([lon, lat], gridPosition(grid, node)),
				);
		samples.push({
			name,
			lat,
			lon,
			minutes,
			cells: e.reachedCells,
			geometryBytes,
			searchMs: e.searchMs,
			contourMs: e.contourMs,
		});
	}
}
console.log(
	JSON.stringify(
		{
			artifact,
			artifactSha256: hash(raw),
			links: counts,
			states,
			shoreLinks,
			sampledAttachments,
			owningVisits: grid.roadVisits?.size,
			supplementalVisits: grid.supplementalRoadVisits?.size,
			samples,
			providerRequests: 0,
			scope:
				"Full retained-link source/connector/price/physical proof; full Census-transfer/shore-land checks and decode-time visit validation; systematic attachments and42 arbitrary-origin horizon/payload/physical smoke checks. NE artificial connections retain old eligibility with new55 charging; they are not verified drivable roads. Local software/geometry checks, not national accuracy or cloud performance.",
		},
		null,
		2,
	),
);
