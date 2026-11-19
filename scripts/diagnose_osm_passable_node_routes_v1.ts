/** Fixed-attachment screen of a separately source-audited generic node policy. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { gunzipSync, gzipSync } from "node:zlib";
import { accessStarts } from "./coarse_osm_access_inputs_v1.ts";
import { loadTurnContexts } from "./coarse_osm_context_loader_v1.ts";
import {
	type RoadWitness,
	searchContextRoadWitness,
} from "./coarse_osm_context_witness_v1.ts";
import type { OriginConnection } from "./coarse_osm_origin_connections_v2.ts";
import { loadPackedCar } from "./coarse_osm_packed_loader_v1.ts";
import { loadPaidGeometry } from "./coarse_osm_paid_geometry_loader_v1.ts";
import type { RoadPosition } from "./coarse_osm_paid_positions_v1.ts";
import {
	assertPhaseReleased,
	settledPhaseMemory,
} from "./coarse_osm_phase_lifetime_v1.ts";
import { withSourceNodeOpenings } from "./coarse_osm_source_node_openings_v1.ts";

type Asset = {
	filename: string;
	rawBytes: number;
	rawSha256: string;
	compressedBytes: number;
	sha256: string;
};
type Point = { lon: number; lat: number };
type Record = {
	sample: { id: string; origin: Point };
	roadTarget: RoadPosition | null;
	road: RoadWitness | null;
};
const repo = path.resolve(import.meta.dirname, ".."),
	sha = (raw: Uint8Array) => createHash("sha256").update(raw).digest("hex");

async function main() {
	const began = performance.now(),
		[recipe, pin] = process.argv.slice(2);
	assert.ok(recipe && pin && global.gc);
	const raw = await readFile(path.resolve(repo, recipe));
	assert.equal(sha(raw), pin);
	const plan = JSON.parse(raw.toString("utf8"));
	assert.equal(
		plan.output,
		"data/coarse-quality/us-osm-passable-node-routes-v1",
	);
	assert.equal(plan.controlsPassed, 18);
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
	let written = raw.length,
		outbound = 0;
	await writeFile(path.join(root, "execution-plan.json"), raw, { flag: "wx" });
	globalThis.fetch = async () => {
		outbound++;
		throw new Error("Unexpected outbound request");
	};
	const check = () => {
		assert.ok(performance.now() - began < 300000, "Obstruction probe deadline");
		assert.ok(
			process.memoryUsage().rss < 4 * 1024 ** 3,
			"Obstruction probe RSS",
		);
		assert.ok(written <= plan.maxOwnedBytes, "Obstruction probe output cap");
	};
	async function decoded<T>(directory: string, asset: Asset): Promise<T> {
		assert.equal(path.basename(asset.filename), asset.filename);
		const packed = await readFile(path.join(repo, directory, asset.filename));
		assert.equal(packed.length, asset.compressedBytes);
		assert.equal(sha(packed), asset.sha256);
		const value = gunzipSync(packed, { maxOutputLength: 33554432 });
		assert.equal(value.length, asset.rawBytes);
		assert.equal(sha(value), asset.rawSha256);
		return JSON.parse(value.toString("utf8"));
	}
	async function put(name: string, value: Uint8Array) {
		written += value.length;
		check();
		await writeFile(path.join(root, name), value, { flag: "wx" });
	}
	try {
		const current = JSON.parse(
			await readFile(path.join(repo, plan.witnessReport), "utf8"),
		) as {
			paths: number;
			unavailable: number;
			rows: { id: string; asset: Asset }[];
		};
		assert.equal(current.paths, 83);
		assert.equal(current.unavailable, 0);
		assert.equal(current.rows.length, 83);
		const inputs = JSON.parse(
			await readFile(path.join(repo, plan.connections), "utf8"),
		) as { coordinate: number[]; connection: OriginConnection | null }[];
		const access = JSON.parse(
			await readFile(path.join(repo, plan.accessReport), "utf8"),
		) as { rows: { coordinate: number[]; output: Asset }[] };
		const byPoint = new Map(
			inputs.map((row) => [JSON.stringify(row.coordinate), row.connection]),
		);
		const assets = new Map(
			access.rows.map((row) => [JSON.stringify(row.coordinate), row.output]),
		);
		assert.equal(byPoint.size, 79);
		assert.equal(assets.size, 79);
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
		assert.equal(history.contexts.states, 34179);
		assert.equal(core.graph.arcs, 9826630);
		assert.equal(core.graph.vertices, 5731903);
		let blockedVertices = 0;
		for (let vertex = 0; vertex < core.graph.vertices; vertex++)
			if (core.graph.nodeFlags(vertex) & 1) blockedVertices++;

		// The complete flag overlay was independently source-audited before queries.
		const openings = await (async () => {
			const original = await readFile(path.join(repo, plan.originalNodeFlags));
			const proposed = await readFile(path.join(repo, plan.proposedNodeFlags));
			const encoded = await readFile(path.join(repo, plan.openedVertices));
			assert.equal(original.length, core.graph.vertices);
			assert.equal(proposed.length, original.length);
			assert.equal(encoded.length % 4, 0);
			const declared = new Set<number>();
			let previous = -1;
			for (let at = 0; at < encoded.length; at += 4) {
				const vertex = encoded.readUInt32LE(at);
				assert.ok(vertex > previous && vertex < core.graph.vertices);
				previous = vertex;
				declared.add(vertex);
			}
			let changed = 0;
			for (let vertex = 0; vertex < original.length; vertex++) {
				assert.equal(core.graph.nodeFlags(vertex), original[vertex]);
				const expected = declared.has(vertex)
					? original[vertex] & ~1
					: original[vertex];
				assert.equal(proposed[vertex], expected);
				if (original[vertex] !== proposed[vertex]) changed++;
			}
			assert.equal(changed, declared.size);
			assert.equal(changed, plan.expectedOpenings);
			return declared;
		})();

		const originalMethod = core.graph.nodeFlags,
			afterLoad = await settledPhaseMemory(),
			rows = [];
		let searches = 0;
		async function probe(item: (typeof current.rows)[number], i: number) {
			check();
			const record = await decoded<Record>(plan.witnessRoot, item.asset);
			assert.equal(record.sample.id, item.id);
			const key = JSON.stringify([
				record.sample.origin.lon,
				record.sample.origin.lat,
			]);
			const source = byPoint.get(key),
				asset = assets.get(key);
			assert.ok(source && asset);
			const choices = await decoded<OriginConnection[]>(
					plan.accessSource,
					asset,
				),
				starts = accessStarts(source, choices);
			let baseline: RoadWitness | null = null,
				trial: RoadWitness | null = null;
			if (record.roadTarget !== null) {
				const target = record.roadTarget;
				const run = () =>
					searchContextRoadWitness(
						core.graph,
						paid.geometry,
						history.contexts,
						starts,
						target,
						{ maxTicks: 432000, check },
					);
				baseline = run();
				searches++;
				assert.equal(baseline.ticks, record.road?.ticks);
				trial = withSourceNodeOpenings(core.graph, openings, run);
				searches++;
				assert.equal(core.graph.nodeFlags, originalMethod);
				assert.ok(
					baseline.ticks !== null &&
						trial.ticks !== null &&
						trial.ticks <= baseline.ticks,
				);
			} else assert.equal(record.road, null);
			const crossedBlockedVertices: number[] = [];
			for (let j = 1; j < (trial?.steps.length ?? 0); j++) {
				assert.ok(trial);
				const vertex = core.graph.arcTarget(trial.steps[j - 1].arc);
				assert.equal(vertex, core.graph.arcTail(trial.steps[j].arc));
				if (core.graph.nodeFlags(vertex) & 1) {
					assert.ok(
						openings.has(vertex),
						"Every newly crossed blocker is source-qualified",
					);
					crossedBlockedVertices.push(vertex);
				}
			}
			const savingsTicks =
				baseline?.ticks != null && trial?.ticks != null
					? baseline.ticks - trial.ticks
					: 0;
			if (savingsTicks > 0) assert.ok(crossedBlockedVertices.length > 0);
			const body = Buffer.from(
				JSON.stringify({
					id: item.id,
					roadTarget: record.roadTarget,
					baselineTicks: baseline?.ticks ?? null,
					trial,
					crossedBlockedVertices,
					permissionsVerified: false,
				}),
			);
			const packed = gzipSync(body, { level: 9 });
			assert.ok(body.length <= 33554432 && packed.length <= 2097152);
			const filename = `trial-${String(i + 1).padStart(2, "0")}.json.gz`;
			await put(filename, packed);
			return {
				id: item.id,
				baselineTicks: baseline?.ticks ?? null,
				trialTicks: trial?.ticks ?? null,
				savingsTicks,
				blockedVerticesCrossed: crossedBlockedVertices.length,
				asset: {
					filename,
					rawBytes: body.length,
					rawSha256: sha(body),
					compressedBytes: packed.length,
					sha256: sha(packed),
				},
			};
		}
		for (const [i, item] of current.rows.entries()) {
			rows.push(await probe(item, i));
			await assertPhaseReleased(
				afterLoad.arrayBuffers,
				"after counterfactual witness owners",
			);
		}

		assert.equal(new Set(rows.map((row) => row.id)).size, 83);
		assert.equal(outbound, 0);
		const report = {
			status:
				"all83_fixed_attachments_source_qualified_passable_node_screen_complete",
			recipeSha256: pin,
			rows,
			originalCases: 83,
			searches,
			improvedRoadLegs: rows.filter((row) => row.savingsTicks > 0).length,
			allStaticTurnBansRetained: 237741,
			blockedVerticesInGraph: blockedVertices,
			sourceQualifiedOpenings: openings.size,
			nodeOpeningPolicySourceAudited: true,
			onlyBlockedTraversalBitCleared: true,
			singleViaHistoryStatesRetained: history.contexts.states,
			allPhysicalCostsAndStartsUnchanged: true,
			allBaselineRoadLegTimesReproduced: true,
			nodeMethodRestored: core.graph.nodeFlags === originalMethod,
			providerRequests: outbound,
			newMaps: 0,
			candidateAdmitted: false,
			nodeAccessPermissionsVerified: false,
			afterLoad,
			afterQueries: await settledPhaseMemory(),
			hostTotalMs: performance.now() - began,
			scope:
				"All 83 frozen winning road attachments under one independently source-audited generic passable-feature node policy. Every original/proposed vertex flag and opened-vertex byte compared to the loaded physical graph before queries. Retain all static bans, single-via histories, physical costs, starts/endpoints/local suffix; open only qualified source-tag vertices, preserving every independent node-only restriction contributor. Every baseline optimum reproduces and each newly crossed blocker belongs to the complete source-derived set. Synchronous predicate and temporary buffers restore exactly. This is not a full point optimum, new map, accuracy score, current availability, lawful-trip guarantee or app admission. No PBF, source constructor, provider, application DB or app operation. Offline witness/RSS/whole-host timing is not production or cloud latency.",
		};
		await put(
			"report.json",
			Buffer.from(`${JSON.stringify(report, null, 2)}\n`),
		);
		process.stdout.write(
			`${JSON.stringify({ status: report.status, cases: rows.length, improvedRoadLegs: report.improvedRoadLegs, hostTotalMs: report.hostTotalMs })}\n`,
		);
	} catch (error) {
		await put(
			"failure.json",
			Buffer.from(
				`${JSON.stringify({ error: String(error), stack: error instanceof Error ? error.stack : null })}\n`,
			),
		);
		throw error;
	}
}
await main();
