/** Fixed national field/software profile; provider reference times are not read. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import {
	connectOrigin,
	type OriginConnection,
} from "./coarse_osm_origin_connections_v1.ts";
import { loadOriginGeography } from "./coarse_osm_origin_geography_v1.ts";
import type { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import { loadPackedCar } from "./coarse_osm_packed_loader_v1.ts";
import { loadPaidGeometry } from "./coarse_osm_paid_geometry_loader_v1.ts";
import type { PaidRoadGeometry } from "./coarse_osm_paid_geometry_v1.ts";
import { searchRoadPositions } from "./coarse_osm_paid_positions_v1.ts";
import {
	assertPhaseReleased,
	settledPhaseMemory,
} from "./coarse_osm_phase_lifetime_v1.ts";
import {
	arrivalAtRoadPosition,
	computeRoadField,
	UNREACHED_SECONDS,
} from "./coarse_osm_road_field_v1.ts";

type Case = {
	id: string;
	originId: string;
	budgetMinutes: number;
	request: { coordinates: [[number, number], [number, number]] };
};
const repo = path.resolve(import.meta.dirname, "..");
const sha = (bytes: Uint8Array) =>
	createHash("sha256").update(bytes).digest("hex");
function summarizeField(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	access: OriginConnection,
	sourceId: string,
	minutes: number,
	cases: Case[],
	connections: Map<string, OriginConnection>,
	check: () => void,
) {
	const horizon = minutes * 480;
	const started = performance.now();
	const field = computeRoadField(
		graph,
		geometry,
		access.snap,
		access.connectorTicks,
		{ maxTicks: horizon, check },
	);
	const fieldMsIncludingAllocationAndSearch = performance.now() - started;
	assert.equal(field.stats.maximumBackingBufferBytes, 57946526);
	assert.equal(
		arrivalAtRoadPosition(graph, geometry, field, access.snap),
		access.connectorTicks,
	);
	let fullHeadArcs = 0;
	let frontierEntries = 0;
	let reachedVertices = 0;
	const vertexBounds = [Infinity, Infinity, -Infinity, -Infinity];
	for (const label of field.labels) {
		if (label < 0x80000000) fullHeadArcs++;
		else if (label !== 0xffffffff) frontierEntries++;
	}
	for (let vertex = 0; vertex < graph.vertices; vertex++)
		if (field.vertexArrivalSeconds[vertex] !== UNREACHED_SECONDS) {
			reachedVertices++;
			const [x, y] = graph.coordinate(vertex);
			vertexBounds[0] = Math.min(vertexBounds[0], x);
			vertexBounds[1] = Math.min(vertexBounds[1], y);
			vertexBounds[2] = Math.max(vertexBounds[2], x);
			vertexBounds[3] = Math.max(vertexBounds[3], y);
		}
	const samples = [];
	for (const value of cases)
		if (value.originId === sourceId && value.budgetMinutes === minutes) {
			const target = connections.get(
				JSON.stringify(value.request.coordinates[1]),
			);
			assert.ok(target);
			const fieldRoadUpper = arrivalAtRoadPosition(
				graph,
				geometry,
				field,
				target.snap,
			);
			samples.push({
				id: value.id,
				target,
				fieldRoadUpper,
				fieldTotalUpper:
					fieldRoadUpper === null
						? null
						: fieldRoadUpper + target.connectorTicks,
			});
		}
	const fieldStats = { ...field.stats };
	const partials = field.partials.map((value) => ({ ...value }));
	return {
		fieldMsIncludingAllocationAndSearch,
		fullHeadArcs,
		frontierEntries,
		reachedVertices,
		vertexBounds,
		samples,
		fieldStats,
		partials,
	};
}

function summarizePairComparisons(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	access: OriginConnection,
	horizon: number,
	samples: ReturnType<typeof summarizeField>["samples"],
	check: () => void,
) {
	const results = [];
	for (const sample of samples) {
		const roadBudget =
			horizon - access.connectorTicks - sample.target.connectorTicks;
		const reference =
			roadBudget < 0
				? { ticks: null, settles: 0, searchBufferBytes: 0 }
				: searchRoadPositions(
						graph,
						geometry,
						access.snap,
						sample.target.snap,
						{ maxTicks: roadBudget, check },
					);
		const total =
			reference.ticks === null
				? null
				: access.connectorTicks +
					reference.ticks +
					sample.target.connectorTicks;
		if (total === null)
			assert.ok(
				sample.fieldTotalUpper === null || sample.fieldTotalUpper > horizon,
			);
		else
			assert.ok(
				sample.fieldTotalUpper !== null &&
					sample.fieldTotalUpper >= total &&
					sample.fieldTotalUpper <= total + 7,
				`${sample.id}: field/pair mismatch`,
			);
		results.push({
			id: sample.id,
			fieldTotalUpper: sample.fieldTotalUpper,
			pairTotalTicks: total,
			...reference,
		});
	}
	return results;
}

async function main() {
	const began = performance.now();
	const [recipeName, pin] = process.argv.slice(2);
	assert.ok(recipeName && pin && global.gc);
	const recipe = await readFile(path.resolve(repo, recipeName));
	assert.equal(sha(recipe), pin);
	const plan = JSON.parse(recipe.toString("utf8"));
	assert.equal(
		plan.output,
		"data/coarse-quality/us-osm-car-road-field-profile-v3",
	);
	assert.equal(plan.coreSource, "data/coarse-quality/us-osm-car-wire-codec-v1");
	assert.equal(
		plan.geometrySource,
		"data/coarse-quality/us-osm-car-paid-geometry-codec-v1",
	);
	assert.equal(
		plan.geographySource,
		"data/coarse-quality/us-osm-car-geography-v1",
	);
	assert.equal(plan.controlsPassed, 11);
	assert.equal(plan.lifetimeControlsPassed, 4);
	assert.deepEqual(plan.horizonsMinutes, [120, 360, 600, 720]);
	assert.equal(plan.sources.length, 8);
	assert.equal(plan.cases.length, 48);
	for (const [name, expected] of Object.entries(plan.bindings))
		assert.equal(sha(await readFile(path.join(repo, name))), expected);
	const root = path.join(repo, plan.output);
	await mkdir(root);
	await writeFile(path.join(root, "execution-plan.json"), recipe, {
		flag: "wx",
	});
	const check = () =>
		assert.ok(performance.now() - began < 120000, "Road field host deadline");
	try {
		const saved = JSON.parse(
			(await readFile(path.join(repo, plan.savedConnections))).toString("utf8"),
		);
		assert.equal(saved.origins, 56);
		const connections = new Map<string, OriginConnection>();
		for (const row of saved.rows) {
			assert.ok(row.connection);
			connections.set(JSON.stringify(row.origin), row.connection);
		}
		const baseline = await settledPhaseMemory();
		const firstBegan = performance.now();
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
		const geo = await loadOriginGeography(
			path.join(repo, plan.geographySource),
			plan.geographyManifestSha256,
		);
		const retainedAfterLoad = await settledPhaseMemory();
		const baselineArrayBuffers = retainedAfterLoad.arrayBuffers;
		const rows = [];
		let comparisons = 0;
		let maxScratch = 0;
		let firstLoadConnectionFieldMs = 0;
		for (const source of plan.sources) {
			const connected = connectOrigin(
				core.graph,
				paid.geometry,
				core.keys,
				core.starts,
				geo.geography,
				source.coordinate,
				check,
			);
			assert.ok(connected.connection);
			const access = connected.connection;
			assert.deepEqual(
				access,
				connections.get(JSON.stringify(source.coordinate)),
			);
			for (const minutes of plan.horizonsMinutes as number[]) {
				check();
				const horizon = minutes * 480;
				const phase = summarizeField(
					core.graph,
					paid.geometry,
					access,
					source.id,
					minutes,
					plan.cases,
					connections,
					check,
				);
				const {
					fieldMsIncludingAllocationAndSearch,
					fullHeadArcs,
					frontierEntries,
					reachedVertices,
					vertexBounds,
					samples,
					fieldStats,
					partials,
				} = phase;
				maxScratch = Math.max(maxScratch, fieldStats.maximumBackingBufferBytes);
				const afterFieldRelease = await assertPhaseReleased(
					baselineArrayBuffers,
					"after field summary function",
				);

				if (!rows.length)
					firstLoadConnectionFieldMs = performance.now() - firstBegan;
				const results = summarizePairComparisons(
					core.graph,
					paid.geometry,
					access,
					horizon,
					samples,
					check,
				);
				comparisons += results.length;
				const afterPairRelease = await assertPhaseReleased(
					baselineArrayBuffers,
					"after reference summary function",
				);

				rows.push({
					sourceId: source.id,
					coordinate: source.coordinate,
					minutes,
					initialConnectorTicks: access.connectorTicks,
					fieldMsIncludingAllocationAndSearch,
					fullHeadArcs,
					frontierEntries,
					reachedVertices,
					fullVertexBoundsOnly: vertexBounds,
					stats: fieldStats,
					sourcePartialShadows: partials,
					comparisons: results,
					afterFieldRelease,
					afterPairRelease,
				});
			}
		}
		assert.equal(rows.length, 32);
		assert.equal(comparisons, 48);
		const afterQueries = await assertPhaseReleased(
			baselineArrayBuffers,
			"after all fields and references",
		);
		const report = {
			status: "host_national_fields_and_qualified_pair_comparisons_passed",
			recipeSha256: pin,
			fields: 32,
			originalRequestPairSoftwareComparisons: 48,
			rows,
			maximumFieldBackingBufferBytes: maxScratch,
			hostFirstLoadConnectionAndFieldMsIncludingGc: firstLoadConnectionFieldMs,
			baseline,
			retainedAfterLoad,
			afterQueries,
			hostTotalMs: performance.now() - began,
			modelChanged: false,
			scope:
				"Host field software profile at 2/6/10/12h for all eight saved source sites; all 48 request pairs compare with qualified pair search, without reading provider reference times. Source connection computed once per site. Field timing includes array allocation and search; first load adds source connection, summaries, field release/GC. Field and reference summaries return only small values; explicit event-loop/GC boundaries pass the unchanged one-MiB extra-buffer guard. Independent pair buffers do not overlap field buffers. Bounds contain full reached vertices only, not a display envelope. No filled display/full app/packaged estimate, protected Linux or Vercel/ETA admission.",
		};
		await writeFile(
			path.join(root, "report.json"),
			`${JSON.stringify(report, null, 2)}\n`,
			{ flag: "wx" },
		);
		process.stdout.write(
			`${JSON.stringify({ status: report.status, fields: 32, pairComparisons: 48, maximumFieldBackingBufferBytes: maxScratch, hostFirstLoadConnectionAndFieldMsIncludingGc: firstLoadConnectionFieldMs, hostTotalMs: report.hostTotalMs })}\n`,
		);
	} catch (error) {
		await writeFile(
			path.join(root, "failure.json"),
			`${JSON.stringify({ error: String(error), hostMs: performance.now() - began })}\n`,
			{ flag: "wx" },
		);
		throw error;
	}
}
await main();
