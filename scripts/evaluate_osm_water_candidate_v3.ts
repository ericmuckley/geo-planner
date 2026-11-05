/** Fixed refined-water candidate; every original case and accuracy gate retained. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { gunzipSync } from "node:zlib";
import { containsPolygon } from "../src/server/coarse-contours.ts";
import {
	accessFilledDisplay,
	diagnosticAccessFilledDisplay,
} from "./coarse_osm_access_display_v2.ts";
import { accessStarts } from "./coarse_osm_access_inputs_v1.ts";
import type {
	AccessRoadField,
	AccessStart,
} from "./coarse_osm_access_road_field_v2.ts";
import {
	computeAccessRoadField,
	computeDiagnosticAccessRoadField,
} from "./coarse_osm_access_road_field_v2.ts";
import {
	accessDisplayPointTiming,
	type PointTiming,
} from "./coarse_osm_access_timing_v2.ts";
import { numericalGates } from "./coarse_osm_display_gates_v1.ts";
import {
	connectorPrice,
	type OriginConnection,
	type OriginGeography,
} from "./coarse_osm_origin_connections_v2.ts";
import { loadOriginGeography } from "./coarse_osm_origin_geography_v1.ts";
import type { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import { loadPackedCar } from "./coarse_osm_packed_loader_v1.ts";
import { loadPaidGeometry } from "./coarse_osm_paid_geometry_loader_v1.ts";
import type { PaidRoadGeometry } from "./coarse_osm_paid_geometry_v1.ts";
import {
	assertPhaseReleased,
	settledPhaseMemory,
} from "./coarse_osm_phase_lifetime_v1.ts";
import { landConnection } from "./coarse_osm_routing_geography_v1.ts";
import { waterRoutingGeographyV3 as waterRoutingGeography } from "./coarse_osm_routing_geography_v3.ts";
import type { Coordinate } from "./coarse_osm_spherical_v1.ts";
import { timingRow } from "./coarse_osm_timing_rows_v2.ts";
import { loadWaterRasterV2 } from "./coarse_osm_water_raster_loader_v2.ts";
import type { TimingRow } from "./coarse-damped-gates.ts";
import { timingSummary } from "./coarse-damped-gates.ts";

type Place = { lon: number; lat: number };
type Sample = TimingRow & {
	id: string;
	origin: Place;
	destination: Place;
	valhallaMinutes: number | null;
};
const repo = path.resolve(import.meta.dirname, ".."),
	coordinate = (p: Place): Coordinate => [p.lon, p.lat],
	key = (p: Place) => JSON.stringify(coordinate(p));
const sha = (bytes: Uint8Array) =>
	createHash("sha256").update(bytes).digest("hex");

function diagnosticPhase(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	geography: OriginGeography,
	source: OriginConnection,
	starts: AccessStart[],
	samples: Sample[],
	connections: Map<string, OriginConnection | null>,
	root: string,
	filename: string,
	check: () => void,
) {
	const began = performance.now(),
		field = computeDiagnosticAccessRoadField(graph, geometry, starts, {
			maxTicks: 432000,
			check,
		});
	const fingerprints = fieldFingerprints(field);
	const timings: Record<string, PointTiming> = {};
	const display = diagnosticAccessFilledDisplay(
		graph,
		geometry,
		geography,
		source,
		field,
		{
			check,
			probe: (grid) => {
				for (const sample of samples)
					timings[sample.id] = accessDisplayPointTiming(
						graph,
						geometry,
						geography,
						field,
						grid,
						source.origin,
						coordinate(sample.destination),
						connections.get(key(sample.destination)) ?? null,
					);
			},
		},
	);
	assert.deepEqual(fieldFingerprints(field), fingerprints);
	const json = JSON.stringify(display.output);
	writeFileSync(path.join(root, filename), json, { flag: "wx" });
	assert.equal(Object.keys(timings).length, samples.length);
	return {
		timings,
		fieldStats: field.stats,
		restorationChecked: true,
		frame: display.frame,
		stats: display.stats,
		phaseMs: performance.now() - began,
		output: {
			filename,
			bytes: Buffer.byteLength(json),
			sha256: sha(Buffer.from(json)),
		},
	};
}
function productionPhase(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	geography: OriginGeography,
	source: OriginConnection,
	starts: AccessStart[],
	samples: Sample[],
	minutes: number,
	root: string,
	filename: string,
	check: () => void,
) {
	const field = computeAccessRoadField(graph, geometry, starts, {
		maxTicks: minutes * 480,
		check,
	});
	const fingerprints = fieldFingerprints(field);
	const display = accessFilledDisplay(
		graph,
		geometry,
		geography,
		source,
		field,
		{
			check,
		},
	);
	const classified = Object.fromEntries(
		samples.map((sample) => [
			sample.id,
			display.output.coordinates.some((poly) =>
				containsPolygon([sample.destination.lon, sample.destination.lat], poly),
			),
		]),
	);
	assert.deepEqual(fieldFingerprints(field), fingerprints);
	const json = JSON.stringify(display.output);
	writeFileSync(path.join(root, filename), json, { flag: "wx" });
	return {
		classified,
		fieldStats: field.stats,
		restorationChecked: true,
		frame: display.frame,
		stats: display.stats,
		output: {
			filename,
			bytes: Buffer.byteLength(json),
			sha256: sha(Buffer.from(json)),
		},
	};
}

function fieldFingerprints(field: AccessRoadField) {
	return [
		sha(new Uint8Array(field.labels.buffer)),
		sha(new Uint8Array(field.vertexArrivalSeconds.buffer)),
		sha(new Uint8Array(field.seeds.buffer)),
	];
}
function choicesFor(
	root: string,
	output: {
		filename: string;
		sha256: string;
		rawSha256: string;
		compressedBytes: number;
		rawBytes: number;
	},
) {
	assert.match(output.filename, /^endpoint-\d{2}\.json\.gz$/);
	assert.ok(output.rawBytes <= 4194304);
	const compressed = readFileSync(path.join(root, output.filename));
	assert.equal(compressed.length, output.compressedBytes);
	assert.equal(sha(compressed), output.sha256);
	const raw = gunzipSync(compressed, { maxOutputLength: 4194304 });
	assert.equal(raw.length, output.rawBytes);
	assert.equal(sha(raw), output.rawSha256);
	return JSON.parse(raw.toString("utf8")) as OriginConnection[];
}
async function main() {
	const began = performance.now(),
		[recipeName, pin] = process.argv.slice(2);
	assert.ok(recipeName && pin && global.gc);
	const raw = await readFile(path.resolve(repo, recipeName));
	assert.equal(sha(raw), pin);
	const plan = JSON.parse(raw.toString("utf8"));
	assert.equal(plan.output, "data/coarse-quality/us-osm-water-evaluation-v3");
	assert.equal(plan.controlsPassed, 18);
	assert.equal(plan.hostSeconds, 1200);
	assert.equal(plan.maxOwnedBytes, 268435456);
	assert.ok(
		plan.priorReserveBytes +
			plan.newClosedAllocationBytes +
			plan.metadataScratchReserveBytes +
			plan.maxOwnedBytes <
			72 * 1024 ** 3,
	);
	for (const [name, expected] of Object.entries(plan.bindings))
		assert.equal(sha(await readFile(path.join(repo, name))), expected, name);
	const root = path.join(repo, plan.output);
	await mkdir(root);
	await writeFile(path.join(root, "execution-plan.json"), raw, { flag: "wx" });
	let outboundCalls = 0;
	globalThis.fetch = async () => {
		outboundCalls++;
		throw new Error("Unexpected outbound request");
	};
	const check = () => {
		assert.ok(
			performance.now() - began < 1200000,
			"Access candidate host deadline",
		);
		assert.ok(
			process.memoryUsage().rss < 4 * 1024 ** 3,
			"Access candidate host RSS bound",
		);
	};
	try {
		const baseline = JSON.parse(
				(await readFile(path.join(repo, plan.baseline))).toString("utf8"),
			),
			samples = baseline.rows as Sample[];
		assert.equal(samples.length, 83);
		assert.equal(samples.filter((s) => s.valhallaMinutes !== null).length, 35);
		const accessRows = JSON.parse(
			(await readFile(path.join(repo, plan.originalConnections))).toString(
				"utf8",
			),
		) as {
			coordinate: Coordinate;
			connection: OriginConnection | null;
			reason: string | null;
		}[];
		const connections = new Map(
			accessRows.map((row) => [JSON.stringify(row.coordinate), row.connection]),
		);
		assert.equal(connections.size, 79);
		const access = JSON.parse(
			(await readFile(path.join(repo, plan.accessReport))).toString("utf8"),
		);
		assert.equal(access.inputs, 79);
		assert.ok(access.supported >= 78 && access.supported <= 79);
		assert.equal(access.originalSupportedInputsRetained, 78);
		const accessByCoordinate = new Map<
			string,
			{ supported: boolean; output: Parameters<typeof choicesFor>[1] }
		>(
			access.rows.map((row: { coordinate: Coordinate }) => [
				JSON.stringify(row.coordinate),
				row,
			]),
		);
		const previous = JSON.parse(
			(await readFile(path.join(repo, plan.previousCandidate))).toString(
				"utf8",
			),
		);
		const oldRoadTicks = new Map<string, number | null>();
		for (const phase of previous.phases)
			if (phase.diagnostic)
				for (const [id, timing] of Object.entries(
					phase.diagnostic.timings as Record<string, PointTiming>,
				))
					oldRoadTicks.set(id, timing.roadTicks);
		const baselineMemory = await settledPhaseMemory();
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
		const coarse = await loadOriginGeography(
			path.join(repo, plan.geographySource),
			plan.geographyManifestSha256,
		);
		const packet = await loadWaterRasterV2(
			path.join(repo, plan.waterSource),
			plan.waterManifestSha256,
		);
		const geography = waterRoutingGeography(coarse.geography, packet);
		const accessAuditStarted = performance.now();
		let validatedInitialChoices = 0;
		for (const row of access.rows) {
			check();
			const onMask = landConnection(geography, row.coordinate, row.coordinate);
			assert.ok(onMask && row.supported && !row.offMask);
			for (const choice of choicesFor(
				path.join(repo, plan.accessSource),
				row.output,
			)) {
				const price = connectorPrice(choice.origin, choice.snap.coordinate);
				assert.equal(price.ticks, choice.connectorTicks);
				assert.equal(price.meters, choice.connectorMeters);
				if (choice.snap.distanceMeters > 1)
					assert.ok(
						landConnection(
							geography,
							[...choice.origin],
							[...choice.snap.coordinate],
						),
					);
				validatedInitialChoices++;
			}
		}
		assert.equal(validatedInitialChoices, access.totalConnections);
		const accessAuditMs = performance.now() - accessAuditStarted;
		process.stdout.write(
			`${JSON.stringify({ validatedInitialChoices, accessAuditMs })}\n`,
		);
		const roadArrivalRegressions: {
			id: string;
			previous: number;
			current: number | null;
		}[] = [];
		const afterLoad = await settledPhaseMemory(),
			origins = new Map(samples.map((s) => [key(s.origin), s.origin])),
			rows: Sample[] = [],
			phases = [];
		let index = 0,
			productionDisplays = 0,
			diagnosticDisplays = 0,
			unsupportedSourceCases = 0,
			roadMonotonicComparisons = 0;
		for (const [originKey, origin] of origins) {
			check();
			const source = connections.get(originKey),
				selected = samples.filter((s) => key(s.origin) === originKey),
				stem = `origin-${String(++index).padStart(2, "0")}`;
			const record = accessByCoordinate.get(originKey);
			assert.ok(record);
			assert.equal(record.supported, source !== null);
			if (!source) {
				const failure = accessRows.find(
					(row) => JSON.stringify(row.coordinate) === originKey,
				)?.reason;
				assert.ok(failure);
				for (const sample of selected)
					rows.push(timingRow(sample, null, false, failure));
				unsupportedSourceCases += selected.length;
				const phase = {
					origin: coordinate(origin),
					sourceConnectionFailure: failure,
					cases: selected.map((s) => s.id),
					estimateProduced: false,
				};
				phases.push(phase);
				await writeFile(
					path.join(root, `${stem}.json`),
					`${JSON.stringify(phase, null, 2)}\n`,
					{ flag: "wx" },
				);
				continue;
			}
			const alternatives = choicesFor(
					path.join(repo, plan.accessSource),
					record.output,
				),
				starts = accessStarts(source, alternatives);
			const diagnostic = diagnosticPhase(
				core.graph,
				paid.geometry,
				geography,
				source,
				starts,
				selected,
				connections,
				root,
				`${stem}-900.geojson`,
				check,
			);
			diagnosticDisplays++;
			const afterDiagnosticRelease = await assertPhaseReleased(
				afterLoad.arrayBuffers,
				"after multi-source diagnostic summary",
			);
			for (const sample of selected) {
				const old = oldRoadTicks.get(sample.id),
					now = diagnostic.timings[sample.id].roadTicks;
				if (old !== null && old !== undefined) {
					if (now === null || now > old)
						roadArrivalRegressions.push({
							id: sample.id,
							previous: old,
							current: now,
						});
					roadMonotonicComparisons++;
				}
			}
			const classified: Record<string, boolean> = {},
				productions = [];
			for (const minutes of new Set(selected.map((s) => s.budgetMinutes))) {
				const subset = selected.filter((s) => s.budgetMinutes === minutes),
					display = productionPhase(
						core.graph,
						paid.geometry,
						geography,
						source,
						starts,
						subset,
						minutes,
						root,
						`${stem}-${minutes}.geojson`,
						check,
					);
				Object.assign(classified, display.classified);
				productionDisplays++;
				productions.push({ minutes, ...display });
				await assertPhaseReleased(
					afterLoad.arrayBuffers,
					"after multi-source production display summary",
				);
			}
			for (const sample of selected) {
				assert.equal(typeof classified[sample.id], "boolean");
				rows.push(
					timingRow(
						sample,
						diagnostic.timings[sample.id].ticks,
						classified[sample.id],
					),
				);
			}
			const phase = {
				origin: coordinate(origin),
				initialChoices: starts.length,
				accessInput: record.output,
				diagnostic,
				productions,
				afterDiagnosticRelease,
			};
			phases.push(phase);
			await writeFile(
				path.join(root, `${stem}.json`),
				`${JSON.stringify(phase, null, 2)}\n`,
				{ flag: "wx" },
			);
			process.stdout.write(
				`${JSON.stringify({ origin: index, origins: origins.size, choices: starts.length, cases: selected.length, finite: selected.filter((s) => diagnostic.timings[s.id].ticks !== null).length, diagnosticMs: diagnostic.phaseMs })}\n`,
			);
		}
		assert.equal(rows.length, 83);
		assert.deepEqual(
			rows.map((r) => r.id).sort(),
			samples.map((s) => s.id).sort(),
		);
		assert.equal(outboundCalls, 0);
		const common = rows.filter((row) => row.candidate.pointMinutes !== null),
			report = {
				status: "completed_fixed_water_mask_candidate_screen",
				recipeSha256: pin,
				candidateModel: "osm-car-refined-water-v1",
				...numericalGates(rows),
				rows,
				phases,
				commonFiniteComparison: {
					cases: common.length,
					baseline: timingSummary(common, "baseline"),
					candidate: timingSummary(common, "candidate"),
				},
				originalCases: 83,
				valhallaCases: 35,
				origins: 21,
				productionDisplays,
				diagnosticDisplays,
				unsupportedSourceCases,
				roadMonotonicComparisons,
				roadArrivalRegressions,
				validatedInitialChoices,
				accessAuditMs,
				waterPacketBackingBytes: packet.backingBytes,
				waterCompressedBytes: packet.compressedBytes,
				retainedBackingBytes:
					afterLoad.arrayBuffers - baselineMemory.arrayBuffers,
				retainedBackingGatePassed:
					afterLoad.arrayBuffers - baselineMemory.arrayBuffers <= 162238546,
				providerRequests: outboundCalls,
				baselineMemory,
				afterLoad,
				afterQueries: await assertPhaseReleased(
					afterLoad.arrayBuffers,
					"after all initial access fields/displays",
				),
				hostTotalMs: performance.now() - began,
				candidateAdmitted: false,
				pending: [
					"All166 complete road/local path witnesses and physical/source/shore checks",
					"Full app/package/retained/startup/API/shared-camera gates",
				],
				scope:
					"One fixed refined-water-mask candidate on all83ORS/35Valhalla observed development cases vs v9. Same corrected graph/geometry/permissions/source speeds/road prices/grid/allowances; all79 initial collections independently recomputed. One shared frozen approximate water policy used in access, raster, local field, display and terminal timing. Original country/coast and uncertain-cell coarse fallback retained. Every original numerical/physical/path/app/resource gate remains. Mask changes may remove a prior invalid connector; road-arrival losses are recorded, never hidden or used to skip cases. No provider/DB/env/source/download/deployment operation. Host functional timing, not cgroup/CPU/swap/packaged/cloud admission.",
			};
		await writeFile(
			path.join(root, "report.json"),
			`${JSON.stringify(report, null, 2)}\n`,
			{ flag: "wx" },
		);
		process.stdout.write(
			`${JSON.stringify({ status: report.status, numericalGatesPassed: report.numericalGatesPassed, overall: report.overall, commonFiniteComparison: report.commonFiniteComparison, gates: report.gates, hostTotalMs: report.hostTotalMs })}\n`,
		);
	} catch (error) {
		await writeFile(
			path.join(root, "failure.json"),
			`${JSON.stringify({ error: String(error), stack: error instanceof Error ? error.stack : null, hostMs: performance.now() - began }, null, 2)}\n`,
			{ flag: "wx" },
		);
		throw error;
	}
}
await main();
