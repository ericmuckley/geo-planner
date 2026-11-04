/** Fixed all-endpoint access qualification, without ETA/reference scoring. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { gzipSync } from "node:zlib";
import { landConnection } from "../src/server/coarse-geography.ts";
import { connectOriginAccessV3 } from "./coarse_osm_origin_access_v3.ts";
import {
	connectorPrice,
	type OriginConnection,
} from "./coarse_osm_origin_connections_v1.ts";
import { loadOriginGeography } from "./coarse_osm_origin_geography_v1.ts";
import { loadPackedCar } from "./coarse_osm_packed_loader_v1.ts";
import { loadPaidGeometry } from "./coarse_osm_paid_geometry_loader_v1.ts";
import { resolveRoadPosition } from "./coarse_osm_paid_positions_v1.ts";
import { settledPhaseMemory } from "./coarse_osm_phase_lifetime_v1.ts";
import type { Coordinate } from "./coarse_osm_spherical_v1.ts";

const repo = path.resolve(import.meta.dirname, ".."),
	sha = (bytes: Uint8Array) => createHash("sha256").update(bytes).digest("hex");
async function main() {
	const began = performance.now(),
		[recipeName, pin] = process.argv.slice(2);
	assert.ok(recipeName && pin && global.gc);
	const bytes = await readFile(path.resolve(repo, recipeName));
	assert.equal(sha(bytes), pin);
	const plan = JSON.parse(bytes.toString("utf8"));
	assert.equal(
		plan.output,
		"data/coarse-quality/us-osm-car-entry-access-profile-v1",
	);
	assert.equal(plan.controlsPassed, 7);
	assert.equal(plan.hostSeconds, 180);
	assert.equal(plan.maxOwnedBytes, 67108864);
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
	const check = () => {
		assert.ok(performance.now() - began < 180000, "Access host deadline");
		assert.ok(
			process.memoryUsage().rss < 4 * 1024 ** 3,
			"Access host RSS bound",
		);
	};
	try {
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
		const prior = JSON.parse(
			(await readFile(path.join(repo, plan.originalConnections))).toString(
				"utf8",
			),
		) as { coordinate: Coordinate; connection: OriginConnection | null }[];
		assert.equal(prior.length, 79);
		const rows = [];
		const connectionRows = [];
		let firstLoadAndAccessMs = 0,
			totalConnections = 0;
		for (const [index, old] of prior.entries()) {
			check();
			const started = performance.now();
			const result = connectOriginAccessV3(
				core.graph,
				paid.geometry,
				core.keys,
				core.starts,
				geo.geography,
				old.coordinate,
				check,
			);
			const accessMs = performance.now() - started;
			// Source ranks/arc IDs changed. Recompute every choice from the new graph;
			// retain old support without pretending the old numeric arc IDs still apply.
			if (old.connection !== null) assert.ok(result.primary);
			if (result.primary !== null)
				assert.ok(
					result.connections.some(
						(c) => JSON.stringify(c) === JSON.stringify(result.primary),
					),
				);
			connectionRows.push({
				coordinate: old.coordinate,
				connection: result.primary,
				reason: result.reason,
			});

			const onMask = landConnection(
					geo.geography,
					[...old.coordinate],
					[...old.coordinate],
				),
				identities = new Set<string>();
			for (const c of result.connections) {
				const price = connectorPrice(c.origin, c.snap.coordinate);
				assert.equal(price.ticks, c.connectorTicks);
				assert.equal(price.meters, c.connectorMeters);
				assert.ok(
					c.connectorTicks <= 345600 &&
						c.connectorMeters <= 300000 &&
						c.connectorMeters <= (result.radiusMeters ?? 0) + 1e-6,
				);
				if (onMask && c.snap.distanceMeters > 1)
					assert.ok(
						landConnection(
							geo.geography,
							[...c.origin],
							[...c.snap.coordinate],
						),
					);
				if (!onMask) assert.ok(c.snap.distanceMeters <= 100);
				const point = resolveRoadPosition(core.graph, paid.geometry, c.snap),
					identity =
						"vertex" in point.source
							? `v${point.source.vertex}`
							: `a${point.canonicalArc}/${point.rank}`;
				assert.ok(!identities.has(identity));
				identities.add(identity);
			}
			assert.ok(result.connections.length <= 4096);
			const raw = Buffer.from(JSON.stringify(result.connections)),
				compressed = gzipSync(raw),
				filename = `endpoint-${String(index + 1).padStart(2, "0")}.json.gz`;
			await writeFile(path.join(root, filename), compressed, { flag: "wx" });
			const row = {
				coordinate: old.coordinate,
				reusedPriorEndpoint: null,
				offMask: !onMask,
				originalSupported: old.connection !== null,
				supported: result.primary !== null,
				originalSupportedInputRetained:
					old.connection === null ? null : result.primary !== null,
				connections: result.connections.length,
				maskOmissionAllowance: result.maskOmissionAllowance,
				radiusMeters: result.radiusMeters,
				reason: result.reason,
				work: result.work,
				accessMs,
				minimumConnectorTicks: result.connections[0]?.connectorTicks ?? null,
				maximumConnectorTicks:
					result.connections.at(-1)?.connectorTicks ?? null,
				output: {
					filename,
					rawBytes: raw.length,
					rawSha256: sha(raw),
					compressedBytes: compressed.length,
					sha256: sha(compressed),
				},
			};
			rows.push(row);
			totalConnections += row.connections;
			if (!index) firstLoadAndAccessMs = performance.now() - firstBegan;
		}
		const report = {
			status: "completed_all_endpoint_initial_access_profile",
			recipeSha256: pin,
			inputs: 79,
			reusedEndpointCollections: 0,
			newEndpointCollections: 79,
			rows,
			totalConnections,
			supported: rows.filter((r) => r.supported).length,
			unsupported: rows.filter((r) => !r.supported).length,
			originalSupportedInputsRetained: rows.filter(
				(r) => r.originalSupportedInputRetained,
			).length,
			maskOmissionAllowanceInputs: rows.filter((r) => r.maskOmissionAllowance)
				.length,
			maximumConnections: Math.max(...rows.map((r) => r.connections)),
			hostLoadAndFirstNewAccessMs: firstLoadAndAccessMs,
			hostTotalMs: performance.now() - began,
			afterQueries: await settledPhaseMemory(),
			scope:
				"All79 original endpoint inputs recomputed on entry-corrected graph IDs, with unchanged generic access rules. Full price/source identity/dedup/caps/strict land checks and original positive support audited; original numeric arc IDs are never reused. Off-mask100m uncertainty remains explicit. No ETA/provider-reference score, case selection, graph transfers, actual local-road/shore or app truth. Host RSS/deadline excludes cgroup/CPU/swap/cloud admission.",
		};
		await writeFile(
			path.join(root, "connections.json"),
			`${JSON.stringify(connectionRows, null, 2)}\n`,
			{ flag: "wx" },
		);
		await writeFile(
			path.join(root, "report.json"),
			`${JSON.stringify(report, null, 2)}\n`,
			{ flag: "wx" },
		);
		process.stdout.write(
			`${JSON.stringify({ status: report.status, inputs: 79, supported: report.supported, totalConnections, maximumConnections: report.maximumConnections, maskOmissionAllowanceInputs: report.maskOmissionAllowanceInputs, hostTotalMs: report.hostTotalMs })}\n`,
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
