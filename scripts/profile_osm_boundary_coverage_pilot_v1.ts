/** Paid boundary coverage at the highest saved finer-grid queue pressure; no score. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { gunzipSync } from "node:zlib";
import { accessStarts } from "./coarse_osm_access_inputs_v1.ts";
import type { PointTiming } from "./coarse_osm_access_timing_v2.ts";
import {
	finishAccessPointTiming,
	type PreparedPointTiming,
	prepareAccessPointTiming,
} from "./coarse_osm_access_timing_v3.ts";
import { boundaryContextDisplay } from "./coarse_osm_boundary_display_v1.ts";
import { loadTurnContexts } from "./coarse_osm_context_loader_v1.ts";
import { bit, center } from "./coarse_osm_display_grid_v3.ts";
import type { DisplayProbe } from "./coarse_osm_filled_display_v1.ts";
import type { OriginConnection } from "./coarse_osm_origin_connections_v2.ts";
import { connectorPrice } from "./coarse_osm_origin_connections_v2.ts";
import { loadOriginGeography } from "./coarse_osm_origin_geography_v1.ts";
import { loadPackedCar } from "./coarse_osm_packed_loader_v1.ts";
import { loadPaidGeometry } from "./coarse_osm_paid_geometry_loader_v1.ts";
import { settledPhaseMemory } from "./coarse_osm_phase_lifetime_v1.ts";
import { landConnection } from "./coarse_osm_routing_geography_v1.ts";
import { waterRoutingGeographyV6 } from "./coarse_osm_routing_geography_v6.ts";
import type { Coordinate } from "./coarse_osm_spherical_v1.ts";
import { loadWaterRasterV2 } from "./coarse_osm_water_raster_loader_v2.ts";

const began = performance.now();
const repo = path.resolve(import.meta.dirname, "..");
const sha = (bytes: Uint8Array | string) =>
	createHash("sha256").update(bytes).digest("hex");
const xy = (place: { lon: number; lat: number }): Coordinate => [
	place.lon,
	place.lat,
];
const key = (point: Coordinate) => JSON.stringify(point);
const loadJson = async (name: string) =>
	JSON.parse(await readFile(path.join(repo, name), "utf8"));
const [recipe, pin] = process.argv.slice(2);
assert.ok(recipe && pin && global.gc);
const encoded = await readFile(path.resolve(repo, recipe));
assert.equal(sha(encoded), pin);
const plan = JSON.parse(encoded.toString("utf8"));
assert.equal(
	plan.output,
	"data/coarse-quality/us-osm-boundary-coverage-pilot-v1",
);
assert.deepEqual(plan.originIndices, [2]);
assert.ok(
	plan.priorReserveBytes +
		plan.newClosedAllocationBytes +
		plan.metadataScratchReserveBytes +
		plan.maxOwnedBytes <
		72 * 1024 ** 3,
);
for (const [name, pin] of Object.entries(plan.bindings))
	assert.equal(sha(await readFile(path.join(repo, name))), pin, name);
const root = path.join(repo, plan.output);
await mkdir(root);
await writeFile(path.join(root, "execution-plan.json"), encoded, {
	flag: "wx",
});

let requests = 0;
globalThis.fetch = async () => {
	requests++;
	throw new Error("Unexpected outbound request");
};
const check = () => {
	assert.ok(
		performance.now() - began < 1800000,
		"Boundary coverage pilot deadline",
	);
	assert.ok(
		process.memoryUsage().rss < 4 * 1024 ** 3,
		"Boundary coverage pilot RSS",
	);
};
let activeMinutes: number | null = null;
let lastObservedQueryArrayBuffers = 0;
let immutableSeedingChecked = false;
let heldArrayBuffers: number | null = null;
const queryBuffers: WeakRef<ArrayBufferLike>[] = [];
try {
	const parity = await loadJson(plan.parityReport);
	assert.equal(
		parity.status,
		"all_saved_origins_reused_display_same_resolution_parity_complete",
	);
	assert.equal(parity.displays, 58);
	assert.equal(parity.diagnosticPointCases, 83);
	const candidate = await loadJson(plan.candidate);
	const peaks = candidate.phases.map(
		(phase: {
			diagnostic: { stats: { maximumHeapEntries: number } };
			productions: { stats: { maximumHeapEntries: number } }[];
		}) =>
			Math.max(
				...[phase.diagnostic, ...phase.productions].map(
					(p) => p.stats.maximumHeapEntries,
				),
			),
	);
	const originIndex = peaks.indexOf(Math.max(...peaks));
	assert.equal(originIndex, 2);
	const phase = candidate.phases[originIndex];
	const samples = candidate.rows.filter(
		(row: { origin: { lon: number; lat: number } }) =>
			key(xy(row.origin)) === key(phase.origin),
	);
	const records = (await loadJson(plan.connections)) as {
		coordinate: Coordinate;
		connection: OriginConnection | null;
	}[];
	const connections = new Map(
		records.map((row) => [key(row.coordinate), row.connection]),
	);
	const source = connections.get(key(phase.origin));
	assert.ok(source);
	const access = await loadJson(plan.accessReport);
	const asset = access.rows.find(
		(row: { coordinate: Coordinate }) =>
			key(row.coordinate) === key(phase.origin),
	).output;
	const compressed = readFileSync(
		path.join(repo, plan.accessSource, asset.filename),
	);
	assert.equal(sha(compressed), asset.sha256);
	assert.equal(compressed.length, asset.compressedBytes);
	const raw = gunzipSync(compressed);
	assert.equal(sha(raw), asset.rawSha256);
	assert.equal(raw.length, asset.rawBytes);
	const choices = JSON.parse(raw.toString("utf8")) as OriginConnection[];
	const starts = accessStarts(source, choices);
	const baseline = await settledPhaseMemory();
	const core = await loadPackedCar(
		path.join(repo, plan.coreSource),
		plan.coreManifestSha256,
		check,
	);
	const paid = await loadPaidGeometry(
		path.join(repo, plan.geometrySource),
		plan.geometryManifestSha256,
		core.graph,
		check,
	);
	const history = await loadTurnContexts(
		path.join(repo, plan.contextSource),
		plan.contextManifestSha256,
		path.join(repo, plan.coreSource),
		plan.coreManifestSha256,
		core.graph,
		check,
	);
	const coarse = await loadOriginGeography(
		path.join(repo, plan.geographySource),
		plan.geographyManifestSha256,
	);
	const packet = await loadWaterRasterV2(
		path.join(repo, plan.waterSource),
		plan.waterManifestSha256,
	);
	const geography = waterRoutingGeographyV6(coarse.geography, packet);
	const afterLoad = await settledPhaseMemory();
	heldArrayBuffers = afterLoad.arrayBuffers;
	const held = afterLoad.arrayBuffers - baseline.arrayBuffers;
	assert.ok(held <= 162238546);
	const specs = [
		{ minutes: 900, expected: phase.diagnostic, diagnostic: true },
		...phase.productions.map((p: { minutes: number }) => ({
			minutes: p.minutes,
			expected: p,
			diagnostic: false,
		})),
	];
	assert.equal(specs.length, 4);
	const results = [];
	for (const spec of specs) {
		activeMinutes = spec.minutes;
		immutableSeedingChecked = false;
		check();
		let prepared: PreparedPointTiming[] = [];
		const timings: Record<string, PointTiming> = {};
		let fingerprints: string[] = [];
		let observations = 0,
			maxObservedQueryArrayBuffers = 0;
		const runBegan = performance.now();
		let loan: DisplayProbe | undefined;
		let gridHashes: string[] = [];
		let oldCoverageCount = 0;
		let witnessed = 0,
			lastCell = -1,
			waterCenterCells = 0,
			uncertainCenterCells = 0,
			outsideWaterRasterCells = 0;
		const certificateHash = createHash("sha256");
		const gridBuffers = (g: DisplayProbe) =>
			[
				g.times,
				g.parents,
				g.links,
				g.land,
				g.boundary,
				g.horizontal,
				g.diagonal,
			].map((v) => sha(new Uint8Array(v.buffer, v.byteOffset, v.byteLength)));
		const coverageCount = (g: DisplayProbe) => {
			let sum = 0;
			for (const byte of g.coverage) {
				let b = byte;
				while (b) {
					b &= b - 1;
					sum++;
				}
			}
			return sum;
		};
		const result = boundaryContextDisplay(
			core.graph,
			paid.geometry,
			history.contexts,
			geography,
			source,
			starts,
			{
				maxTicks: spec.minutes * 60 * 8,
				maxCells: 33554432,
				check,
				beforeSeed: (field) => {
					fingerprints = [
						sha(new Uint8Array(field.labels.buffer)),
						sha(new Uint8Array(field.vertexArrivalSeconds.buffer)),
						sha(new Uint8Array(field.seeds.buffer)),
					];
					if (spec.diagnostic)
						prepared = samples.map(
							(sample: { destination: { lon: number; lat: number } }) =>
								prepareAccessPointTiming(
									core.graph,
									paid.geometry,
									field,
									source.origin,
									xy(sample.destination),
									connections.get(key(xy(sample.destination))) ?? null,
								),
						);
				},
				observeBacking: (buffers) => {
					queryBuffers.push(...buffers.map((b) => new WeakRef(b)));
					const extra =
						process.memoryUsage().arrayBuffers - afterLoad.arrayBuffers;
					lastObservedQueryArrayBuffers = extra;
					maxObservedQueryArrayBuffers = Math.max(
						maxObservedQueryArrayBuffers,
						extra,
					);
					assert.ok(extra <= 67108864, "Observed query backing cap");
					if (observations++ === 0) {
						assert.deepEqual(
							[buffers[0], buffers[1], buffers[5]].map((b) =>
								sha(new Uint8Array(b)),
							),
							fingerprints,
							"Road seeding changed query labels",
						);
						immutableSeedingChecked = true;
					}
				},
				beforeBoundary: (grid) => {
					const extra =
						process.memoryUsage().arrayBuffers - afterLoad.arrayBuffers;
					maxObservedQueryArrayBuffers = Math.max(
						maxObservedQueryArrayBuffers,
						extra,
					);
					assert.ok(extra <= 67108864, "Boundary pre-probe backing cap");
					loan = grid;
					gridHashes = gridBuffers(grid);
					oldCoverageCount = coverageCount(grid);
				},
				boundaryWitness: (w) => {
					assert.ok(loan);
					assert.ok(w.cell > lastCell && w.cell < loan.times.length);
					lastCell = w.cell;
					assert.equal(bit(loan.land, w.cell), 0);
					assert.equal(bit(loan.coverage, w.cell), 0);
					assert.equal(loan.times[w.cell], 65535);
					assert.equal(bit(loan.land, w.fromCell), 1);
					assert.equal(loan.times[w.fromCell], w.fromSeconds);
					assert.deepEqual(center(loan.frame, w.fromCell), w.from);
					const x = w.cell % loan.frame.width,
						y = Math.floor(w.cell / loan.frame.width);
					const sx = w.fromCell % loan.frame.width,
						sy = Math.floor(w.fromCell / loan.frame.width);
					assert.ok(
						Math.abs(x - sx) <= 1 &&
							Math.abs(y - sy) <= 1 &&
							w.cell !== w.fromCell,
					);
					assert.ok(
						Number.isInteger(w.sample) && w.sample >= 0 && w.sample < 4,
					);
					const ox = w.sample % 2 === 0 ? 0.25 : 0.75,
						oy = w.sample < 2 ? 0.25 : 0.75;
					assert.deepEqual(w.to, [
						(loan.frame.west + (x + ox) * loan.frame.step) / 1e6,
						(loan.frame.south + (y + oy) * loan.frame.step) / 1e6,
					]);
					assert.equal(
						w.connectorSeconds,
						Math.ceil(connectorPrice(w.from, w.to).ticks / 8),
					);
					assert.ok(w.fromSeconds + w.connectorSeconds <= spec.minutes * 60);
					assert.ok(landConnection(geography, [...w.to], [...w.to]));
					assert.ok(landConnection(geography, [...w.from], [...w.to]));
					const c = center(loan.frame, w.cell),
						rg = packet.grid;
					const flags = packet.cellFlags(
						Math.floor((c[0] * 1e7 - rg.xE7) / rg.stepE7),
						Math.floor((c[1] * 1e7 - rg.yE7) / rg.stepE7),
					);
					if (flags === null) outsideWaterRasterCells++;
					else if (flags & 2) uncertainCenterCells++;
					else if (flags & 1) waterCenterCells++;
					certificateHash.update(JSON.stringify(w));
					witnessed++;
					if ((witnessed & 255) === 0) check();
				},
				probe: (grid) => {
					const extra =
						process.memoryUsage().arrayBuffers - afterLoad.arrayBuffers;
					maxObservedQueryArrayBuffers = Math.max(
						maxObservedQueryArrayBuffers,
						extra,
					);
					assert.ok(extra <= 67108864, "Boundary post-probe backing cap");
					assert.deepEqual(
						gridBuffers(grid),
						gridHashes,
						"Boundary coverage changed local fields",
					);
					assert.equal(coverageCount(grid) - oldCoverageCount, witnessed);
					if (spec.diagnostic)
						for (let i = 0; i < samples.length; i++)
							timings[samples[i].id] = finishAccessPointTiming(
								geography,
								grid,
								prepared[i],
							);
				},
			},
			spec.diagnostic,
		);
		loan = undefined;
		assert.equal(result.boundary.addedCells, witnessed);
		assert.equal(observations, 2);
		assert.deepEqual(result.frame, spec.expected.frame);
		assert.equal(result.stats.localCells, spec.expected.stats.localCells);
		assert.equal(result.stats.roadOnlyCells, spec.expected.stats.roadOnlyCells);
		assert.equal(
			result.stats.selectedCells,
			spec.expected.stats.selectedCells + witnessed,
		);
		assert.ok(result.frame.step >= 5000 && result.frame.step <= 25000);
		assert.deepEqual(result.fieldStats, spec.expected.fieldStats);
		if (spec.diagnostic)
			for (const sample of samples)
				assert.deepEqual(timings[sample.id], spec.expected.timings[sample.id]);
		const json = JSON.stringify(result.output);
		await settledPhaseMemory();
		const released = await settledPhaseMemory();
		assert.equal(
			released.arrayBuffers,
			afterLoad.arrayBuffers,
			"Query owner backing restored",
		);
		const filename = spec.expected.output.filename;
		assert.equal(
			filename,
			`origin-${String(originIndex + 1).padStart(2, "0")}-${spec.minutes}.geojson`,
		);
		await writeFile(path.join(root, filename), json, { flag: "wx" });
		const row = {
			minutes: spec.minutes,
			diagnostic: spec.diagnostic,
			fieldStats: result.fieldStats,
			stats: result.stats,
			boundary: result.boundary,
			witnessAudit: {
				witnessed,
				certificateSha256: certificateHash.digest("hex"),
				waterCenterCells,
				uncertainCenterCells,
				outsideWaterRasterCells,
				allNoncoverageGridHashesExact: true,
			},
			timings,
			frame: result.frame,
			maxObservedQueryArrayBuffers,
			afterReleaseArrayBuffers: released.arrayBuffers,
			output: { filename, bytes: Buffer.byteLength(json), sha256: sha(json) },
			hostPhaseMsIncludingQueryChecks: performance.now() - runBegan,
		};
		results.push(row);
		process.stdout.write(
			`${JSON.stringify({ minutes: spec.minutes, step: result.frame.step, cells: result.frame.width * result.frame.height, maxObservedQueryArrayBuffers })}\n`,
		);
	}
	const report = {
		status: "highest_saved_finer_queue_pressure_paid_boundary_pilot_complete",
		recipeSha256: pin,
		origins: 1,
		originIndex,
		selection:
			"Highest maximumHeapEntries across every saved finer display; first index breaks ties",
		displays: results.length,
		diagnosticPointCases: samples.length,
		results,
		heldBackingBytes: held,
		baseline,
		afterLoad,
		afterQueries: await settledPhaseMemory(),
		providerRequests: requests,
		hostTotalMsIncludingBindingsFieldsChecksMapsIOAndGC:
			performance.now() - began,
		isAccuracyCandidate: false,
		higherResolutionEvaluated: true,
		allFramesAndPointComponentsExactVsFinerCandidate: true,
		wholeCellWaterPaintUnresolved: true,
		scope: plan.scope,
	};
	assert.equal(report.afterQueries.arrayBuffers, afterLoad.arrayBuffers);
	assert.equal(requests, 0);
	await writeFile(
		path.join(root, "report.json"),
		`${JSON.stringify(report, null, 2)}\n`,
		{ flag: "wx" },
	);
	process.stdout.write(
		`${JSON.stringify({ status: report.status, displays: report.displays, hostTotalMs: report.hostTotalMsIncludingBindingsFieldsChecksMapsIOAndGC })}\n`,
	);
} catch (error) {
	await settledPhaseMemory();
	const afterFailure = await settledPhaseMemory();
	await writeFile(
		path.join(root, "failure.json"),
		`${JSON.stringify({ error: String(error), activeMinutes, lastObservedQueryArrayBuffers, immutableSeedingChecked, providerRequests: requests, heldArrayBuffers, afterFailure, observedQueryBuffers: queryBuffers.length, queryBuffersReleased: queryBuffers.length === 0 ? null : queryBuffers.every((b) => b.deref() === undefined), afterFailureMayAlsoCollectRuntimeInputs: true, stack: error instanceof Error ? error.stack : null, hostTotalMs: performance.now() - began }, null, 2)}\n`,
		{ flag: "wx" },
	);
	throw error;
}
