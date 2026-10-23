// Offline diagnostic: named public fixtures never enter application routing.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { gzipSync } from "node:zlib";
import { decodeGrid } from "../src/server/coarse-data.server";
import {
	distanceKm,
	estimateGrid,
	gridAttachments,
	gridCellMinutes,
	gridPosition,
	gridTransitions,
} from "../src/server/coarse-grid";
import { planSha256, readFrozenPlan } from "./coarse-holdout";

const [reportPath, output] = process.argv.slice(2);
assert.ok(
	reportPath && output,
	"Pass the saved replay report and a fresh output directory",
);
assert.ok(resolve(output).startsWith(`${resolve("data/coarse-quality")}/`));
const hash = (bytes: Buffer | string) =>
	createHash("sha256").update(bytes).digest("hex");
const artifact = "src/server/data/coarse-grid-v8.json";
const bytes = await readFile(artifact);
const artifactSha256 = hash(bytes);
assert.equal(
	artifactSha256,
	"2beb2fb6d9af6e07f37c5ba53acdeca2da1334c31a5fadd1371efd5453134910",
);
const plan = await readFrozenPlan();
const frozen = JSON.parse(plan.raw) as {
	sites: Array<{ id: string; lat: number; lon: number }>;
	queries: Array<{ id: string; modelCellMinutes: number }>;
};
const reportBytes = await readFile(reportPath);
const report = JSON.parse(reportBytes.toString()) as {
	planSha256: string;
	cases: Array<{
		id: string;
		outcome: string;
		reference: {
			minutes: number;
			distanceKm: number;
			snapOver100m: boolean;
		} | null;
	}>;
};
assert.equal(report.planSha256, planSha256);
assert.equal(report.cases.length, 48);
await mkdir(output); // Reserve a fresh run before doing diagnostic searches.
const grid = decodeGrid(JSON.parse(bytes.toString()));
const size = grid.width * grid.height;
const samples = [];
const paths = [];
// Recover a shortest path through production transitions, as in the older
// sealed access inspector. Do not change those checksum-bound producers.
for (const site of frozen.sites) {
	const origin = { lat: site.lat, lon: site.lon };
	const field = estimateGrid(grid, origin, 750);
	const labels = field.labels;
	const seeds = gridAttachments(grid, origin);
	for (const query of plan.queries.filter((q) => q.originId === site.id)) {
		const referenceCase = report.cases.find((row) => row.id === query.id);
		assert.ok(referenceCase);
		const [lon, lat] = query.request.coordinates[1];
		const arrival = gridAttachments(grid, { lat, lon })
			.map((a) => ({ ...a, totalMinutes: labels[a.cell] + a.minutes }))
			.sort((a, b) => a.totalMinutes - b.totalMinutes)[0];
		assert.ok(arrival && Number.isFinite(arrival.totalMinutes));
		assert.ok(Math.abs(arrival.totalMinutes - query.modelPointMinutes) < 1e-8);
		const displayCell =
			Math.floor((lat - grid.bounds[1]) / grid.step) * grid.width +
			Math.floor((lon - grid.bounds[0]) / grid.step);
		const frozenQuery = frozen.queries.find((q) => q.id === query.id);
		assert.ok(frozenQuery);
		assert.ok(
			Math.abs(
				gridCellMinutes(grid, labels, displayCell) -
					frozenQuery.modelCellMinutes,
			) < 1e-8,
		);
		let node = arrival.cell;
		let seed: (typeof seeds)[number] | undefined;
		const edges = [];
		while (edges.length < labels.length) {
			seed = seeds.find(
				(s) => s.cell === node && Math.abs(labels[node] - s.minutes) < 1e-8,
			);
			if (seed) break;
			const predecessor = [...gridTransitions(grid, node)].find(
				(e) =>
					e &&
					labels[e.target] < labels[node] &&
					Math.abs(labels[e.target] + e.minutes - labels[node]) < 1e-8,
			);
			assert.ok(predecessor, `No predecessor for ${query.id}/${node}`);
			edges.push(predecessor);
			node = predecessor.target;
		}
		assert.ok(seed);
		const path = edges.reverse().map((edge) => ({
			from: edge.target,
			to: edge.cell,
			fromPosition: gridPosition(grid, edge.target),
			toPosition: gridPosition(grid, edge.cell),
			minutes: edge.minutes,
			kind: edge.kind,
			censusLayer: edge.kind === "road" && edge.cell >= size,
		}));
		const sum = (kind: "road" | "local" | "transfer") =>
			path
				.filter((e) => e.kind === kind)
				.reduce((total, e) => total + e.minutes, 0);
		const chord = (kind: "road" | "local" | "transfer") =>
			path
				.filter((e) => e.kind === kind)
				.reduce(
					(total, e) => total + distanceKm(e.fromPosition, e.toPosition),
					0,
				);
		const components = {
			originAttachmentMinutes: seed.minutes,
			roadMinutes: sum("road"),
			localMinutes: sum("local"),
			transferMinutes: sum("transfer"),
			destinationAttachmentMinutes: arrival.minutes,
		};
		assert.ok(
			Math.abs(
				Object.values(components).reduce((a, b) => a + b, 0) -
					arrival.totalMinutes,
			) < 1e-8,
		);
		const reference = referenceCase.reference;
		samples.push({
			id: query.id,
			originId: query.originId,
			budgetMinutes: query.budgetMinutes,
			modelMinutes: arrival.totalMinutes,
			reference,
			differenceMinutes: reference
				? arrival.totalMinutes - reference.minutes
				: null,
			components,
			roadChordKm: chord("road"),
			localChordKm: chord("local"),
			transferChordKm: chord("transfer"),
			roadEdges: path.filter((e) => e.kind === "road").length,
			localEdges: path.filter((e) => e.kind === "local").length,
			transferEdges: path.filter((e) => e.kind === "transfer").length,
			censusRoadMinutes: path
				.filter((e) => e.censusLayer)
				.reduce((sum, e) => sum + e.minutes, 0),
			censusRoadEdges: path.filter((e) => e.censusLayer).length,
			originAttachment: seed,
			destinationAttachment: arrival,
			outcome: referenceCase.outcome,
		});
		paths.push({ id: query.id, path });
	}
}
assert.equal(samples.length, 48);
const pathBytes = gzipSync(`${JSON.stringify(paths)}\n`);
await writeFile(join(output, "paths.json.gz"), pathBytes, { flag: "wx" });
await writeFile(
	join(output, "diagnostic.json"),
	`${JSON.stringify(
		{
			artifact,
			artifactSha256,
			planSha256,
			reportSha256: hash(reportBytes),
			pathSha256: hash(pathBytes),
			pathBytes: pathBytes.length,
			samples,
			providerRequests: 0,
			scope:
				"One reconstructed v8 shortest path per frozen frontier probe. All 48 point/cell costs match the frozen plan and path components sum to each point cost. Road chord distance connects model state positions and is not source-polyline distance; road time also includes source-arc/connector costs. Local/transfer components and endpoint attachments are separated; reference geometry is a different route, not a timing ground truth. Diagnostic search extends to750min only to include outside720 probes. No runtime/model/weight changes or provider calls.",
		},
		null,
		2,
	)}\n`,
	{ flag: "wx" },
);
console.log(
	JSON.stringify({ output, samples: samples.length, providerRequests: 0 }),
);
