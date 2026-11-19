/** Trace every saved primary road finish; no local-grid or map reconstruction. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { gunzipSync, gzipSync } from "node:zlib";
import { accessStarts } from "./coarse_osm_access_inputs_v1.ts";
import { loadTurnContexts } from "./coarse_osm_context_loader_v1.ts";
import { searchContextRoadWitness } from "./coarse_osm_context_witness_v1.ts";
import {
	connectorPrice,
	type OriginConnection,
} from "./coarse_osm_origin_connections_v2.ts";
import { loadPackedCar } from "./coarse_osm_packed_loader_v1.ts";
import { loadPaidGeometry } from "./coarse_osm_paid_geometry_loader_v1.ts";
import {
	assertPhaseReleased,
	settledPhaseMemory,
} from "./coarse_osm_phase_lifetime_v1.ts";
import {
	type Coordinate,
	sphericalDistance,
} from "./coarse_osm_spherical_v1.ts";
import {
	roadWitnessGeometry,
	witnessPositionCoordinate,
} from "./coarse_osm_witness_geometry_v1.ts";

type Sample = {
	id: string;
	set: string;
	origin: { lon: number; lat: number };
	destination: { lon: number; lat: number };
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
const repo = path.resolve(import.meta.dirname, ".."),
	sha = (bytes: Uint8Array) => createHash("sha256").update(bytes).digest("hex"),
	key = (p: Coordinate) => JSON.stringify(p);

async function main() {
	const began = performance.now(),
		[recipe, pin] = process.argv.slice(2);
	assert.ok(recipe && pin && global.gc);
	const rawRecipe = await readFile(path.resolve(repo, recipe));
	assert.equal(sha(rawRecipe), pin);
	const plan = JSON.parse(rawRecipe.toString("utf8"));
	assert.equal(plan.output, "data/coarse-quality/us-osm-lane-road-paths-v1");
	assert.equal(plan.controlsPassed, 12);
	assert.equal(plan.hostSeconds, 300);
	assert.equal(plan.maxOwnedBytes, 134217728);
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
	await writeFile(path.join(root, "execution-plan.json"), rawRecipe, {
		flag: "wx",
	});
	let written = rawRecipe.length,
		outbound = 0;
	globalThis.fetch = async () => {
		outbound++;
		throw new Error("Unexpected outbound request");
	};
	const check = () => {
		assert.ok(performance.now() - began < 300000);
		assert.ok(process.memoryUsage().rss < 4 * 1024 ** 3);
		assert.ok(written < plan.maxOwnedBytes);
	};
	const put = async (name: string, bytes: Uint8Array) => {
		written += bytes.length;
		check();
		await writeFile(path.join(root, name), bytes, { flag: "wx" });
	};
	try {
		const point = JSON.parse(
			await readFile(path.join(repo, plan.pointReport), "utf8"),
		) as {
			rows: Sample[];
			comparisons: { id: string; bestRoadTicks: number | null }[];
		};
		const inputs = JSON.parse(
			await readFile(path.join(repo, plan.connections), "utf8"),
		) as { coordinate: Coordinate; connection: OriginConnection | null }[];
		const access = JSON.parse(
			await readFile(path.join(repo, plan.accessReport), "utf8"),
		) as {
			rows: { coordinate: Coordinate; supported: boolean; output: Asset }[];
		};
		assert.equal(point.rows.length, 83);
		assert.equal(
			point.rows.filter((r) => r.valhallaMinutes !== null).length,
			35,
		);
		assert.equal(inputs.length, 79);
		assert.equal(access.rows.length, 79);
		const byPoint = new Map(
				inputs.map((r) => [key(r.coordinate), r.connection]),
			),
			assets = new Map(access.rows.map((r) => [key(r.coordinate), r]));
		const expected = new Map(
			point.comparisons.map((r) => [r.id, r.bestRoadTicks]),
		);
		assert.equal(expected.size, 83);
		const before = await settledPhaseMemory();
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
		const afterLoad = await settledPhaseMemory();
		function alternatives(coordinate: Coordinate) {
			const row = assets.get(key(coordinate));
			assert.ok(row?.supported);
			assert.match(row.output.filename, /^endpoint-\d{2}\.json\.gz$/);
			const packed = readFileSync(
				path.join(repo, plan.accessSource, row.output.filename),
			);
			assert.equal(packed.length, row.output.compressedBytes);
			assert.equal(sha(packed), row.output.sha256);
			const raw = gunzipSync(packed, { maxOutputLength: 4194304 });
			assert.equal(raw.length, row.output.rawBytes);
			assert.equal(sha(raw), row.output.rawSha256);
			return JSON.parse(raw.toString("utf8")) as OriginConnection[];
		}
		function trace(sample: Sample, index: number) {
			check();
			const source = byPoint.get(key([sample.origin.lon, sample.origin.lat])),
				terminal = byPoint.get(
					key([sample.destination.lon, sample.destination.lat]),
				);
			assert.ok(source && terminal);
			const choices = alternatives(source.origin),
				starts = accessStarts(source, choices);
			const terminalPrice = connectorPrice(
				terminal.origin,
				terminal.snap.coordinate,
			);
			assert.equal(terminalPrice.ticks, terminal.connectorTicks);
			assert.equal(terminalPrice.meters, terminal.connectorMeters);
			assert.ok(
				terminal.connectorTicks <= 345600 && terminal.connectorMeters <= 300000,
			);
			const road = searchContextRoadWitness(
				core.graph,
				paid.geometry,
				history.contexts,
				starts,
				terminal.snap,
				{ maxTicks: 432000 - terminal.connectorTicks, check },
			);
			const frozen = expected.get(sample.id);
			assert.notEqual(frozen, undefined);
			if (frozen === null) {
				assert.equal(road.ticks, null);
				return {
					row: {
						id: sample.id,
						set: sample.set,
						unavailable: true,
						primaryRoadTicks: null,
					},
					record: null,
				};
			}
			assert.ok(
				road.ticks !== null && road.startIndex !== null && frozen !== undefined,
			);
			const chosen = starts[road.startIndex];
			const initialConnection =
				road.startIndex === 0
					? source
					: choices.find(
							(c) =>
								c.snap.canonicalArc === chosen.position.canonicalArc &&
								c.snap.segment === chosen.position.segment &&
								c.snap.segmentFraction === chosen.position.segmentFraction &&
								c.connectorTicks === chosen.initialTicks,
						);
			assert.ok(initialConnection);
			assert.deepEqual(initialConnection.origin, source.origin);
			assert.equal(
				connectorPrice(source.origin, initialConnection.snap.coordinate).ticks,
				chosen.initialTicks,
			);
			assert.ok(
				sphericalDistance(
					witnessPositionCoordinate(paid.geometry, chosen.position),
					initialConnection.snap.coordinate,
				) <= 0.001,
			);
			const roadGeometry = roadWitnessGeometry(
				core.graph,
				paid.geometry,
				starts,
				terminal.snap,
				road,
			);
			assert.ok(roadGeometry);
			const endpointRoundingTicks =
				frozen - road.ticks - terminal.connectorTicks;
			assert.ok(endpointRoundingTicks >= 0 && endpointRoundingTicks <= 7);
			const components = {
				initialTicks: chosen.initialTicks,
				roadTravelTicks: road.steps.reduce((n, s) => n + s.ticks, 0),
				signalTicks: road.steps.reduce((n, s) => n + s.signalBeforeTicks, 0),
				reversalTicks: road.steps.reduce(
					(n, s) => n + s.reversalBeforeTicks,
					0,
				),
				endpointRoundingTicks,
				terminalTicks: terminal.connectorTicks,
			};
			const sumTicks = Object.values(components).reduce((n, v) => n + v, 0);
			assert.equal(sumTicks, frozen);
			const record = {
				sample,
				primaryRoadTicks: frozen,
				components,
				sumTicks,
				initialConnection,
				terminalConnection: terminal,
				roadTarget: terminal.snap,
				road,
				roadGeometry,
			};
			const raw = Buffer.from(JSON.stringify(record)),
				packed = gzipSync(raw, { level: 9 });
			assert.ok(raw.length <= 33554432 && packed.length <= 2097152);
			const filename = `path-${String(index).padStart(2, "0")}.json.gz`;
			check();
			return {
				row: {
					id: sample.id,
					set: sample.set,
					primaryRoadTicks: frozen,
					sumTicks,
					components,
					retainedRoadMeters: roadGeometry.retainedRoadMeters,
					offlineSearchBackingBytes: road.stats.offlineSearchBackingBytes,
					asset: {
						filename,
						rawBytes: raw.length,
						rawSha256: sha(raw),
						compressedBytes: packed.length,
						sha256: sha(packed),
					},
				},
				record: packed,
			};
		}
		const rows = [];
		for (const [index, sample] of point.rows.entries()) {
			const result = trace(sample, index);
			if (result.record !== null) {
				assert.ok(result.row.asset);
				await put(result.row.asset.filename, result.record);
			}
			result.record = null;
			rows.push(result.row);
			const released = await assertPhaseReleased(
				afterLoad.arrayBuffers,
				"after context primary-road witness",
			);
			await put(
				`case-${String(index).padStart(2, "0")}.json`,
				Buffer.from(
					`${JSON.stringify({ ...result.row, afterReleaseArrayBuffers: released.arrayBuffers }, null, 2)}\n`,
				),
			);
		}
		assert.equal(rows.length, 83);
		assert.equal(outbound, 0);
		const report = {
			status: "all83_context_primary_road_witnesses_reproduced",
			recipeSha256: pin,
			paths: rows.filter((r) => r.asset !== undefined).length,
			unavailable: rows.filter((r) => r.unavailable).length,
			originalCases: 83,
			valhallaCases: 35,
			rows,
			heldCoreGeometryContextBackingBytes:
				afterLoad.arrayBuffers - before.arrayBuffers,
			afterLoad,
			afterQueries: await assertPhaseReleased(
				afterLoad.arrayBuffers,
				"after all context witnesses",
			),
			maximumOfflineSearchBackingBytes: Math.max(
				...rows.map((r) => r.offlineSearchBackingBytes ?? 0),
			),
			providerRequests: outbound,
			hostTotalMsIncludingBindingsLoadSearchGeometryWritesAndGc:
				performance.now() - began,
			mapsRebuilt: false,
			localGridWinnerPathsClaimed: false,
			accuracyOrAppAdmitted: false,
			scope:
				"All83 primary-road fields reproduced,including nulls,with physical source cost/node/static-turn and history replay. Full source/terminal connector prices and explicit0..7tick endpoint summary rounding. Every emitted paid-road coordinate/partial direction/continuity checked. No local-grid winner or map rerender/166sum/accuracy/app admission. Offline search96MiB,not production64MiB;core+geometry+context retained excludes water/geography/display/app. HostRSS/deadline only,no cgroup/CPU/swap/cloud timing.",
		};
		await put(
			"report.json",
			Buffer.from(`${JSON.stringify(report, null, 2)}\n`),
		);
		process.stdout.write(
			`${JSON.stringify({ status: report.status, paths: report.paths, unavailable: report.unavailable, maximumOfflineSearchBackingBytes: report.maximumOfflineSearchBackingBytes, hostTotalMs: report.hostTotalMsIncludingBindingsLoadSearchGeometryWritesAndGc })}\n`,
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
