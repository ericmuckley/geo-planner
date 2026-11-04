/** Offline path diagnosis: preserve the frozen candidate, reconstruct its winners. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { gunzipSync, gzipSync } from "node:zlib";
import { landConnection } from "../src/server/coarse-geography.ts";
import { accessStarts } from "./coarse_osm_access_inputs_v1.ts";
import { computeDiagnosticAccessRoadField } from "./coarse_osm_access_road_field_v1.ts";
import type { PointTiming } from "./coarse_osm_access_timing_v1.ts";
import { displayPointWitness } from "./coarse_osm_local_witness_v1.ts";
import {
	connectorPrice,
	type OriginConnection,
	type OriginGeography,
} from "./coarse_osm_origin_connections_v1.ts";
import { loadOriginGeography } from "./coarse_osm_origin_geography_v1.ts";
import type { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import { loadPackedCar } from "./coarse_osm_packed_loader_v1.ts";
import { loadPaidGeometry } from "./coarse_osm_paid_geometry_loader_v1.ts";
import type { PaidRoadGeometry } from "./coarse_osm_paid_geometry_v1.ts";
import {
	assertPhaseReleased,
	settledPhaseMemory,
} from "./coarse_osm_phase_lifetime_v1.ts";
import { searchRoadWitness } from "./coarse_osm_road_witness_v2.ts";
import {
	type Coordinate,
	sphericalDistance,
} from "./coarse_osm_spherical_v1.ts";
import {
	createSeedTrace,
	offlineTraceAccessDisplay,
} from "./coarse_osm_trace_display_v1.ts";
import {
	roadWitnessGeometry,
	witnessPositionCoordinate,
} from "./coarse_osm_witness_geometry_v1.ts";

type Place = { lon: number; lat: number };
type Sample = {
	id: string;
	set: string;
	origin: Place;
	destination: Place;
	budgetMinutes: number;
	referenceMinutes: number;
	valhallaMinutes: number | null;
};
type Asset = {
	filename: string;
	rawBytes: number;
	rawSha256: string;
	compressedBytes: number;
	sha256: string;
};
type Phase = {
	origin: Coordinate;
	sourceConnectionFailure?: string;
	diagnostic?: {
		timings: Record<string, PointTiming>;
		output: { bytes: number; sha256: string };
	};
};
const repo = path.resolve(import.meta.dirname, ".."),
	coordinate = (p: Place): Coordinate => [p.lon, p.lat],
	key = (p: Coordinate) => JSON.stringify(p),
	sha = (bytes: Uint8Array | string) =>
		createHash("sha256").update(bytes).digest("hex");

function alternatives(root: string, asset: Asset): OriginConnection[] {
	assert.match(asset.filename, /^endpoint-\d{2}\.json\.gz$/);
	const compressed = readFileSync(path.join(root, asset.filename));
	assert.equal(compressed.length, asset.compressedBytes);
	assert.equal(sha(compressed), asset.sha256);
	const raw = gunzipSync(compressed, { maxOutputLength: 4194304 });
	assert.equal(raw.length, asset.rawBytes);
	assert.equal(sha(raw), asset.rawSha256);
	return JSON.parse(raw.toString("utf8"));
}

function tracePhase(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	geography: OriginGeography,
	source: OriginConnection,
	choices: OriginConnection[],
	samples: Sample[],
	connections: Map<string, OriginConnection | null>,
	expected: NonNullable<Phase["diagnostic"]>,
	check: () => void,
) {
	const starts = accessStarts(source, choices),
		field = computeDiagnosticAccessRoadField(graph, geometry, starts, {
			maxTicks: 432000,
			check,
		}),
		seedTrace = createSeedTrace(),
		traces: Record<string, ReturnType<typeof displayPointWitness>> = {};
	const before = [
		sha(new Uint8Array(field.labels.buffer)),
		sha(new Uint8Array(field.vertexArrivalSeconds.buffer)),
	];
	const display = offlineTraceAccessDisplay(
		graph,
		geometry,
		geography,
		source,
		field,
		{
			check,
			seedTrace,
			probe: (grid) => {
				for (const sample of samples) {
					const target = coordinate(sample.destination),
						trace = displayPointWitness(
							graph,
							geometry,
							geography,
							field,
							grid,
							seedTrace,
							source.origin,
							target,
							connections.get(key(target)) ?? null,
						);
					assert.deepEqual(
						trace.measured,
						expected.timings[sample.id],
						sample.id,
					);
					traces[sample.id] = trace;
				}
			},
		},
	);
	assert.deepEqual(
		[
			sha(new Uint8Array(field.labels.buffer)),
			sha(new Uint8Array(field.vertexArrivalSeconds.buffer)),
		],
		before,
	);
	const json = JSON.stringify(display.output);
	assert.equal(Buffer.byteLength(json), expected.output.bytes);
	assert.equal(sha(json), expected.output.sha256);
	return {
		traces,
		stats: display.stats,
		fieldStats: field.stats,
		outputSha256: sha(json),
	};
}

function pathPhase(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	geography: OriginGeography,
	source: OriginConnection,
	choices: OriginConnection[],
	trace: ReturnType<typeof displayPointWitness>,
	sample: Sample,
	filename: string,
	check: () => void,
	reused?: ReturnType<typeof searchRoadWitness>,
) {
	const starts = accessStarts(source, choices),
		road =
			trace.roadTarget === null
				? null
				: (reused ??
					searchRoadWitness(graph, geometry, starts, trace.roadTarget, {
						maxTicks: 432000,
						check,
					})),
		geometryWitness =
			road === null || trace.roadTarget === null
				? null
				: roadWitnessGeometry(graph, geometry, starts, trace.roadTarget, road);
	let initialTicks = 0,
		roadTravelTicks = 0,
		signalTicks = 0,
		reversalTicks = 0,
		endpointRoundingTicks = 0;
	let initialConnection: OriginConnection | null = null;
	if (road !== null) {
		assert.ok(
			road.ticks !== null &&
				road.startIndex !== null &&
				geometryWitness !== null &&
				trace.fieldRoadTicks !== null,
		);
		// Map the encoded root back to exactly the primary-first ordering used by the field.
		const chosen = starts[road.startIndex];
		initialConnection =
			road.startIndex === 0
				? source
				: (choices.find(
						(c) =>
							c.snap.canonicalArc === chosen.position.canonicalArc &&
							c.snap.segment === chosen.position.segment &&
							c.snap.segmentFraction === chosen.position.segmentFraction &&
							c.connectorTicks === chosen.initialTicks,
					) ?? null);
		assert.ok(initialConnection);
		assert.deepEqual(initialConnection.origin, source.origin);
		const foot = witnessPositionCoordinate(geometry, chosen.position);
		assert.ok(
			sphericalDistance(foot, initialConnection.snap.coordinate) <= 0.001,
		);
		assert.equal(
			connectorPrice(source.origin, initialConnection.snap.coordinate).ticks,
			chosen.initialTicks,
		);
		const onMask = landConnection(
			geography,
			[...source.origin],
			[...source.origin],
		);
		if (initialConnection.snap.distanceMeters > 1) {
			if (onMask)
				assert.ok(
					landConnection(
						geography,
						[...source.origin],
						[...initialConnection.snap.coordinate],
					),
				);
			else
				assert.ok(
					initialConnection.snap.distanceMeters <= 100,
					"Original explicit off-mask allowance",
				);
		}
		initialTicks = chosen.initialTicks;
		roadTravelTicks = road.steps.reduce((n, s) => n + s.ticks, 0);
		signalTicks = road.steps.reduce((n, s) => n + s.signalBeforeTicks, 0);
		reversalTicks = road.steps.reduce((n, s) => n + s.reversalBeforeTicks, 0);
		assert.equal(
			initialTicks + roadTravelTicks + signalTicks + reversalTicks,
			road.ticks,
		);
		endpointRoundingTicks = trace.fieldRoadTicks - road.ticks;
		assert.ok(
			endpointRoundingTicks >= 0 && endpointRoundingTicks <= 7,
			"Explicit upward endpoint-summary rounding only",
		);
	}
	const components = {
			initialTicks,
			roadTravelTicks,
			signalTicks,
			reversalTicks,
			endpointRoundingTicks,
			...trace.components,
		},
		sumTicks = Object.values(components).reduce((n, ticks) => n + ticks, 0);
	assert.equal(sumTicks, trace.measured.ticks, sample.id);
	const record = {
		sample,
		measured: trace.measured,
		components,
		sumTicks,
		initialConnection,
		roadTarget: trace.roadTarget,
		road,
		roadGeometry: geometryWitness,
		localCoordinates: trace.coordinates,
	};
	const raw = Buffer.from(JSON.stringify(record)),
		compressed = gzipSync(raw, { level: 9 });
	assert.ok(
		raw.length <= 33554432 && compressed.length <= 2097152,
		"Whole path output cap; never truncate",
	);
	writeFileSync(filename, compressed, { flag: "wx" });
	const retainedRoadMeters = geometryWitness?.retainedRoadMeters ?? 0;
	return {
		id: sample.id,
		kind: trace.measured.kind,
		sumTicks,
		components,
		retainedRoadMeters,
		sourceConnectorMeters: initialConnection?.connectorMeters ?? 0,
		roadSteps: road?.steps.length ?? 0,
		searchStats: road?.stats ?? null,
		asset: {
			filename: path.basename(filename),
			rawBytes: raw.length,
			rawSha256: sha(raw),
			compressedBytes: compressed.length,
			sha256: sha(compressed),
		},
	};
}

async function main() {
	const began = performance.now(),
		[recipe, pin] = process.argv.slice(2);
	assert.ok(recipe && pin && global.gc);
	const bytes = await readFile(path.resolve(repo, recipe));
	assert.equal(sha(bytes), pin);
	const plan = JSON.parse(bytes.toString("utf8"));
	assert.equal(
		plan.output,
		"data/coarse-quality/us-osm-car-access-path-diagnostic-v2",
	);
	assert.equal(plan.controlsPassed, 23);
	assert.equal(plan.maxOwnedBytes, 268435456);
	assert.equal(plan.hostSeconds, 1800);
	assert.ok(
		plan.priorReserveBytes +
			plan.newClosedAllocationBytes +
			plan.metadataScratchReserveBytes +
			plan.maxOwnedBytes <
			64 * 1024 ** 3,
	);
	for (const [name, expected] of Object.entries(plan.bindings))
		assert.equal(sha(await readFile(path.join(repo, name))), expected, name);
	const root = path.join(repo, plan.output);
	await mkdir(root);
	await writeFile(path.join(root, "execution-plan.json"), bytes, {
		flag: "wx",
	});
	let providerRequests = 0;
	globalThis.fetch = async () => {
		providerRequests++;
		throw new Error("Unexpected outbound request");
	};
	const check = () => {
		assert.ok(performance.now() - began < 1800000, "Path diagnostic deadline");
		assert.ok(
			process.memoryUsage().rss < 4 * 1024 ** 3,
			"Path diagnostic RSS bound",
		);
	};
	try {
		const candidate = JSON.parse(
				await readFile(path.join(repo, plan.candidate), "utf8"),
			) as { rows: Sample[]; phases: Phase[] },
			inputs = JSON.parse(
				await readFile(path.join(repo, plan.originalConnections), "utf8"),
			) as { coordinate: Coordinate; connection: OriginConnection | null }[],
			access = JSON.parse(
				await readFile(path.join(repo, plan.accessReport), "utf8"),
			) as {
				rows: { coordinate: Coordinate; supported: boolean; output?: Asset }[];
			};
		assert.equal(candidate.rows.length, 83);
		assert.equal(
			candidate.rows.filter((s) => s.valhallaMinutes !== null).length,
			35,
		);
		const connections = new Map(
				inputs.map((r) => [key(r.coordinate), r.connection]),
			),
			accessByKey = new Map(access.rows.map((r) => [key(r.coordinate), r]));
		assert.equal(connections.size, 79);
		const core = await loadPackedCar(
				path.join(repo, plan.coreSource),
				plan.coreManifestSha256,
				check,
			),
			paid = await loadPaidGeometry(
				path.join(repo, plan.geometrySource),
				plan.geometryManifestSha256,
				core.graph,
				check,
			),
			geo = await loadOriginGeography(
				path.join(repo, plan.geographySource),
				plan.geographyManifestSha256,
			),
			afterLoad = await settledPhaseMemory(),
			rows = [],
			phases = [];
		const reusedPaths = new Map<
			string,
			{ filename: string; sha256: string; bytes: number }
		>(
			plan.reusedPaths.map(
				(r: {
					id: string;
					filename: string;
					sha256: string;
					bytes: number;
				}) => [r.id, r],
			),
		);
		let reusedRoadPaths = 0;
		let paths = 0,
			unavailable = 0,
			index = 0;
		for (const phase of candidate.phases) {
			check();
			const selected = candidate.rows.filter(
					(s) => key(coordinate(s.origin)) === key(phase.origin),
				),
				source = connections.get(key(phase.origin)),
				accessInput = accessByKey.get(key(phase.origin));
			assert.ok(selected.length && accessInput);
			if (!source) {
				assert.ok(
					!phase.diagnostic &&
						phase.sourceConnectionFailure &&
						!accessInput.supported,
				);
				for (const sample of selected) {
					rows.push({
						id: sample.id,
						unavailable: phase.sourceConnectionFailure,
					});
					unavailable++;
				}
				continue;
			}
			assert.ok(phase.diagnostic && accessInput.output);
			const choices = alternatives(
					path.join(repo, plan.accessSource),
					accessInput.output,
				),
				traced = tracePhase(
					core.graph,
					paid.geometry,
					geo.geography,
					source,
					choices,
					selected,
					connections,
					phase.diagnostic,
					check,
				),
				afterTraceRelease = await assertPhaseReleased(
					afterLoad.arrayBuffers,
					"after trace raster/field release",
				);
			for (const sample of selected) {
				const trace = traced.traces[sample.id];
				if (trace.measured.ticks === null) {
					rows.push({ id: sample.id, unavailable: trace.measured.kind });
					unavailable++;
					continue;
				}
				const previous = reusedPaths.get(sample.id);
				let reused: ReturnType<typeof searchRoadWitness> | undefined;
				if (previous) {
					const packed = readFileSync(
						path.join(repo, plan.reusedSource, previous.filename),
					);
					assert.equal(packed.length, previous.bytes);
					assert.equal(sha(packed), previous.sha256);
					const record = JSON.parse(
						gunzipSync(packed, { maxOutputLength: 33554432 }).toString("utf8"),
					);
					assert.deepEqual(record.sample, sample);
					assert.deepEqual(record.measured, trace.measured);
					assert.deepEqual(record.roadTarget, trace.roadTarget);
					assert.deepEqual(record.localCoordinates, trace.coordinates);
					reused = record.road;
					assert.ok(reused);
					reusedRoadPaths++;
				}
				const row = pathPhase(
					core.graph,
					paid.geometry,
					geo.geography,
					source,
					choices,
					trace,
					sample,
					path.join(root, `path-${String(++index).padStart(2, "0")}.json.gz`),
					check,
					reused,
				);
				const released = await assertPhaseReleased(
					afterLoad.arrayBuffers,
					"after independent path search/output release",
				);
				rows.push({ ...row, afterReleaseArrayBuffers: released.arrayBuffers });
				paths++;
				console.log(
					JSON.stringify({
						path: paths,
						id: sample.id,
						kind: row.kind,
						steps: row.roadSteps,
					}),
				);
			}
			const summary = {
				origin: phase.origin,
				outputSha256: traced.outputSha256,
				fieldStats: traced.fieldStats,
				traceStats: traced.stats,
				afterTraceReleaseArrayBuffers: afterTraceRelease.arrayBuffers,
			};
			phases.push(summary);
			writeFileSync(
				path.join(
					root,
					`origin-${String(phases.length).padStart(2, "0")}.json`,
				),
				`${JSON.stringify(summary, null, 2)}\n`,
				{ flag: "wx" },
			);
		}
		assert.equal(reusedRoadPaths, 14);
		assert.equal(paths, 80);
		assert.equal(unavailable, 3);
		assert.equal(rows.length, 83);
		assert.equal(phases.length, 20);
		assert.equal(new Set(rows.map((r) => r.id)).size, 83);
		assert.equal(providerRequests, 0);
		const report = {
			status: "frozen_candidate_path_diagnostic_complete",
			recipeSha256: pin,
			paths,
			reusedRoadPaths,
			newRoadSearches: paths - reusedRoadPaths,
			unavailable,
			originalCases: 83,
			valhallaCases: 35,
			phases,
			rows,
			providerRequests,
			afterLoad,
			afterQueries: await settledPhaseMemory(),
			hostTotalMs: performance.now() - began,
			candidateAdmitted: false,
			scope:
				"Independent road/root/turn and actual local suffix witnesses with byte-identical frozen diagnostic outputs/timings. Larger offline buffers are not app scratch. Three unavailable rows persist; no accuracy/policy change or all166 admission.",
		};
		await writeFile(
			path.join(root, "report.json"),
			`${JSON.stringify(report, null, 2)}\n`,
			{ flag: "wx" },
		);
		console.log(
			JSON.stringify({
				status: report.status,
				paths,
				unavailable,
				hostTotalMs: report.hostTotalMs,
			}),
		);
	} catch (error) {
		await writeFile(
			path.join(root, "failure.json"),
			`${JSON.stringify({ status: "path_diagnostic_stopped", error: String(error), stack: error instanceof Error ? error.stack : null, providerRequests, hostTotalMs: performance.now() - began }, null, 2)}\n`,
			{ flag: "wx" },
		);
		throw error;
	}
}
await main();
