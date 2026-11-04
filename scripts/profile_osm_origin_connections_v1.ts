/** Fixed complete saved-endpoint connection profile, without route evaluation. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { landConnection } from "../src/server/coarse-geography.ts";
import { connectOrigin } from "./coarse_osm_origin_connections_v1.ts";
import { loadOriginGeography } from "./coarse_osm_origin_geography_v1.ts";
import { loadPackedCar } from "./coarse_osm_packed_loader_v1.ts";
import { loadPaidGeometry } from "./coarse_osm_paid_geometry_loader_v1.ts";

const repo = path.resolve(import.meta.dirname, "..");
const sha = (bytes: Uint8Array) =>
	createHash("sha256").update(bytes).digest("hex");
async function main() {
	const began = performance.now();
	const [recipeName, pin] = process.argv.slice(2);
	assert.ok(recipeName && pin && global.gc);
	const recipe = await readFile(path.resolve(repo, recipeName));
	assert.equal(sha(recipe), pin);
	const plan = JSON.parse(recipe.toString("utf8"));
	assert.equal(
		plan.output,
		"data/coarse-quality/us-osm-car-origin-connections-profile-v1",
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
	assert.equal(plan.controlsPassed, 6);
	for (const [name, expected] of Object.entries(plan.bindings))
		assert.equal(sha(await readFile(path.join(repo, name))), expected);
	const root = path.join(repo, plan.output);
	await mkdir(root);
	await writeFile(path.join(root, "execution-plan.json"), recipe, {
		flag: "wx",
	});
	const check = () =>
		assert.ok(
			performance.now() - began < 120000,
			"Origin connection host deadline",
		);
	try {
		const saved = JSON.parse(
			(await readFile(path.join(repo, plan.savedSnaps))).toString("utf8"),
		);
		assert.equal(saved.origins, 56);
		global.gc();
		global.gc();
		const baseline = process.memoryUsage();
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
		global.gc();
		global.gc();
		const retainedAfterLoad = process.memoryUsage();
		const rows = [];
		let firstLoadAndConnectionMs = 0;
		for (const value of saved.queries) {
			check();
			const started = performance.now();
			const origin: [number, number] = value.coordinate;
			const result = connectOrigin(
				core.graph,
				paid.geometry,
				core.keys,
				core.starts,
				geo.geography,
				origin,
				check,
			);
			assert.ok(result.connection);
			assert.ok(
				result.connection.connectorMeters + 0.001 >=
					result.connection.snap.distanceMeters &&
					result.connection.connectorTicks >= 0 &&
					result.connection.connectorTicks <= 345600,
			);
			if (result.connection.connectorMeters > 0)
				assert.ok(result.connection.connectorTicks > 0);
			const strictMaskConnection = landConnection(geo.geography, origin, [
				...result.connection.snap.coordinate,
			]);
			if (!strictMaskConnection) {
				assert.equal(result.connection.kind, "modeled-road");
				assert.ok(result.connection.snap.distanceMeters <= 1);
			}
			const connectionMs = performance.now() - started;
			global.gc();
			if (!rows.length)
				firstLoadAndConnectionMs = performance.now() - firstBegan;
			rows.push({
				origin,
				...result,
				strictMaskConnection,
				connectionMs,
				hostQueryMsIncludingGc: performance.now() - started,
			});
		}
		global.gc();
		global.gc();
		const afterQueries = process.memoryUsage();
		const report = {
			status: "host_all_saved_origin_connections_passed",
			recipeSha256: pin,
			origins: 56,
			rows,
			strictMaskConnections: rows.filter((row) => row.strictMaskConnection)
				.length,
			modeledRoadMaskAllowances: rows.filter((row) => !row.strictMaskConnection)
				.length,
			combinedCompressedDataBytes:
				core.compressedBytes + paid.compressedBytes + geo.compressedBytes,
			coreAndGeometryBackingBufferBytes:
				core.retainedDataBackingBufferBytes +
				paid.retainedDataBackingBufferBytes,
			geography: {
				points: geo.points,
				rings: geo.rings,
				rawBytes: geo.rawBytes,
				compressedBytes: geo.compressedBytes,
			},
			hostFirstLoadAndConnectionMsIncludingGc: firstLoadAndConnectionMs,
			baseline,
			retainedAfterLoad,
			afterQueries,
			prototypeProcessManagedBytes:
				afterQueries.heapUsed + afterQueries.arrayBuffers,
			hostTotalMs: performance.now() - began,
			modelChanged: false,
			scope:
				"Fresh host load after modules/config and all saved coarse input-to-road connections. One-meter modeled-road position allowance and ordinary continuous-mask land pricing are explicit. No route/ETA evaluation, field/display/app/packaged estimate, protected Linux or Vercel admission.",
		};
		await writeFile(
			path.join(root, "report.json"),
			`${JSON.stringify(report, null, 2)}\n`,
			{ flag: "wx" },
		);
		process.stdout.write(
			`${JSON.stringify({ status: report.status, origins: 56, strictMaskConnections: report.strictMaskConnections, modeledRoadMaskAllowances: report.modeledRoadMaskAllowances, prototypeProcessManagedBytes: report.prototypeProcessManagedBytes, hostFirstLoadAndConnectionMsIncludingGc: firstLoadAndConnectionMs, hostTotalMs: report.hostTotalMs })}\n`,
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
