import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import type { Origin } from "../src/lib/reachability";
import { decodeGrid } from "../src/server/coarse-data.server";
import {
	distanceKm,
	estimateGrid,
	gridAttachments,
	gridPosition,
} from "../src/server/coarse-grid";

const artifact = process.argv[2] ?? "src/server/data/coarse-grid-v3.json";
const artifactBytes = await readFile(artifact);
const data = JSON.parse(artifactBytes.toString());
const grid = decodeGrid(data);
const report = JSON.parse(
	await readFile(
		process.argv[3] ?? "docs/evidence/coarse-v3-2026-10-22/comparison.json",
		"utf8",
	),
);
assert.equal(
	createHash("sha256").update(artifactBytes).digest("hex"),
	report.artifactSha256,
);

type Sample = {
	id: string;
	origin: Origin;
	destination: Origin;
	referenceMinutes: number;
	candidate: { pointMinutes: number };
};
const directions = [
	[1, 0],
	[1, 1],
	[0, 1],
	[-1, 1],
	[-1, 0],
	[-1, -1],
	[0, -1],
	[1, -1],
];

// Reconstruct a shortest path from the production labels instead of introducing
// a second search implementation. Every edge and the complete sum are checked.
function edge(cell: number, direction: number) {
	const x = cell % grid.width,
		y = Math.floor(cell / grid.width);
	const [dx, dy] = directions[direction];
	const xx = x + dx,
		yy = y + dy;
	if (xx < 0 || xx >= grid.width || yy < 0 || yy >= grid.height) return;
	const target = yy * grid.width + xx;
	if (!grid.traversable[target]) return;
	const key = direction < 4 ? cell * 4 + direction : target * 4 + direction - 4;
	const overland =
		!!((grid.shoreLinks?.[Math.floor(key / 4)] ?? 0) & (1 << (key % 4))) ||
		(grid.land[cell] &&
			grid.land[target] &&
			(!dx ||
				!dy ||
				(grid.land[y * grid.width + xx] && grid.land[yy * grid.width + x])));
	const km = distanceKm(gridPosition(grid, cell), gridPosition(grid, target));
	const roadMinutes = (grid.roadDeciseconds?.[key] || Infinity) / 600;
	const localMinutes = overland ? (km / grid.localSpeedKph) * 60 : Infinity;
	return {
		cell,
		target,
		minutes: Math.min(roadMinutes, localMinutes),
		kind: roadMinutes <= localMinutes ? "road" : "local",
		chordKm: km,
	};
}

const fields = new Map<string, ReturnType<typeof estimateGrid>>();
function trace(sample: Sample) {
	const originKey = JSON.stringify(sample.origin);
	let field = fields.get(originKey);
	if (!field) {
		field = estimateGrid(grid, sample.origin, 720);
		fields.set(originKey, field);
	}
	const labels = field.labels;
	const arrival = gridAttachments(grid, sample.destination)
		.map((a) => ({
			...a,
			minutes: labels[a.cell] + a.minutes,
		}))
		.sort((a, b) => a.minutes - b.minutes)[0];
	assert.ok(arrival && Number.isFinite(arrival.minutes));
	assert.ok(Math.abs(arrival.minutes - sample.candidate.pointMinutes) < 1e-8);
	const seeds = gridAttachments(grid, sample.origin);
	const reversePath = [];
	let cell = arrival.cell;
	let seed: (typeof seeds)[number] | undefined;
	while (reversePath.length < labels.length) {
		seed = seeds.find(
			(s) => s.cell === cell && Math.abs(labels[cell] - s.minutes) < 1e-8,
		);
		if (seed) break;
		// Edges are bidirectional; trace a lower-cost neighbor using the same key.
		const next = directions
			.map((_, d) => edge(cell, d))
			.find(
				(e) =>
					e &&
					labels[e.target] < labels[cell] &&
					Math.abs(labels[e.target] + e.minutes - labels[cell]) < 1e-8,
			);
		assert.ok(next, `No predecessor for ${sample.id}, cell ${cell}`);
		reversePath.push(next);
		cell = next.target;
	}
	assert.ok(seed, `No origin attachment for ${sample.id}`);
	const path = reversePath
		.reverse()
		.map((e) => ({ ...e, cell: e.target, target: e.cell }));
	const originAccessMinutes = seed.minutes;
	const destinationAccessMinutes = arrival.minutes - labels[arrival.cell];
	const roadMinutes = path
		.filter((e) => e.kind === "road")
		.reduce((sum, e) => sum + e.minutes, 0);
	const localMinutes = path
		.filter((e) => e.kind === "local")
		.reduce((sum, e) => sum + e.minutes, 0);
	assert.ok(
		Math.abs(
			originAccessMinutes +
				roadMinutes +
				localMinutes +
				destinationAccessMinutes -
				arrival.minutes,
		) < 1e-8,
	);
	return {
		id: sample.id,
		origin: sample.origin,
		destination: sample.destination,
		referenceMinutes: sample.referenceMinutes,
		pointMinutes: arrival.minutes,
		differenceMinutes: arrival.minutes - sample.referenceMinutes,
		originAccessMinutes,
		originAccessRoadKm: seed.roadKm ?? 0,
		originAccessLocalKm: seed.distanceKm - (seed.roadKm ?? 0),
		roadMinutes,
		intercellLocalMinutes: localMinutes,
		destinationAccessMinutes,
		destinationAccessRoadKm: arrival.roadKm ?? 0,
		destinationAccessLocalKm: arrival.distanceKm - (arrival.roadKm ?? 0),
		originAttachmentCell: seed.cell,
		destinationAttachmentCell: arrival.cell,
		path,
	};
}

const sourcePath = "data/coarse-sources/natural-earth-v5.1.2/roads.geojson";
const sourceBytes = await readFile(sourcePath);
const sourceSha256 = createHash("sha256").update(sourceBytes).digest("hex");
assert.equal(sourceSha256, data.sources.roads.sha256);
type Road = {
	properties: {
		type: string;
		sov_a3: string;
		name: string | null;
		uident: number;
	};
	geometry: { type: string; coordinates: number[][] | number[][][] };
};
const roads: Road[] = JSON.parse(sourceBytes.toString()).features;
function coverage(point: Origin) {
	const scale = Math.cos((point.lat * Math.PI) / 180);
	let any = null,
		eligible = null;
	for (const road of roads) {
		const paths =
			road.geometry.type === "LineString"
				? [road.geometry.coordinates as number[][]]
				: (road.geometry.coordinates as number[][][]);
		let nearestKm = Infinity;
		for (const path of paths)
			for (let i = 1; i < path.length; i++) {
				const a = path[i - 1],
					b = path[i];
				// A generous window for these saved regional endpoints, not a national
				// nearest-road service. Below we require a result inside 40 km.
				if (
					point.lon < Math.min(a[0], b[0]) - 0.75 ||
					point.lon > Math.max(a[0], b[0]) + 0.75 ||
					point.lat < Math.min(a[1], b[1]) - 0.75 ||
					point.lat > Math.max(a[1], b[1]) + 0.75
				)
					continue;
				const ax = (a[0] - point.lon) * scale,
					ay = a[1] - point.lat;
				const dx = (b[0] - a[0]) * scale,
					dy = b[1] - a[1];
				const length = dx * dx + dy * dy;
				const t = length
					? Math.max(0, Math.min(1, -(ax * dx + ay * dy) / length))
					: 0;
				nearestKm = Math.min(
					nearestKm,
					distanceKm(
						[point.lon, point.lat],
						[a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t],
					),
				);
			}
		const p = road.properties;
		const row = {
			approximateKm: nearestKm,
			name: p.name,
			type: p.type,
			country: p.sov_a3,
			sourceId: p.uident,
		};
		if (!any || nearestKm < any.approximateKm) any = row;
		if (
			p.sov_a3 === "USA" &&
			p.type in data.roadSpeedsKph &&
			(!eligible || nearestKm < eligible.approximateKm)
		)
			eligible = row;
	}
	assert.ok(any && eligible && eligible.approximateKm < 40);
	return { point, nearestSourceRoad: any, nearestEligibleSourceRoad: eligible };
}

const original = (report.original.samples as Sample[]).map(trace);
const regional = (report.regional.samples as Sample[]).map(trace);
const points = new Map(
	[...original, ...regional]
		.flatMap((s) => [s.origin, s.destination])
		.map((p) => [JSON.stringify(p), p]),
);
console.log(
	JSON.stringify(
		{
			artifact,
			artifactSha256: report.artifactSha256,
			sourcePath,
			sourceSha256,
			original,
			regional,
			endpointSourceCoverage: [...points.values()].map(coverage),
			publicRoutingApiCalls: 0,
			localServiceRequests: 0,
			scope:
				"Offline decomposition of one shortest path per saved candidate point comparison. All 35 point costs and reconstructed path sums match preserved results. Road time includes v2 anchor connectors and rounding; local time includes assumed 25 km/h travel without roads. Nearest source distances use a local planar projection followed by haversine distance, within a 0.75-degree segment window; they diagnose these regional endpoints only. References are static models, not real-world truth. No national accuracy or real-world ETA claim is made.",
		},
		null,
		2,
	),
);
