/** Offline generic water-mask hypothesis:point/snap/continuous-mask/lifetime checks. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { setImmediate as nextTurn } from "node:timers/promises";
import { fileURLToPath } from "node:url";
import { landConnection } from "../src/server/coarse-geography.ts";

import { loadOriginGeography } from "./coarse_osm_origin_geography_v1.ts";
import { prepareWaterGeography } from "./coarse_osm_water_geography_v1.ts";
import {
	loadWaterRaster,
	type RasterCoordinate,
} from "./coarse_osm_water_raster_loader_v1.ts";

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const sha = (raw: Uint8Array) => createHash("sha256").update(raw).digest("hex");
const [recipeName, pin] = process.argv.slice(2);
assert.ok(recipeName && /^[a-f0-9]{64}$/.test(pin));
const recipe = path.resolve(recipeName),
	encoded = await readFile(recipe);
assert.equal(sha(encoded), pin);
assert.ok(recipe.startsWith(`${repo}/docs/evidence/`));
const plan = JSON.parse(encoded.toString("utf8"));
assert.equal(
	plan.output,
	"data/coarse-quality/us-osm-water-geography-profile-v1",
);
assert.equal(
	plan.source,
	"data/coarse-quality/us-osm-water-raster-source-run-v1",
);
assert.equal(plan.savedPointCount, 245);
assert.ok(typeof global.gc === "function", "Run with --expose-gc");
for (const [name, expected] of Object.entries(plan.bindings)) {
	assert.ok(!path.isAbsolute(name) && !name.split("/").includes(".."));
	const digest = createHash("sha256");
	for await (const raw of createReadStream(path.join(repo, name)))
		digest.update(raw);
	assert.equal(digest.digest("hex"), expected, name);
}
const root = path.join(repo, plan.output);
await mkdir(root);
await writeFile(path.join(root, "execution-plan.json"), encoded, {
	flag: "wx",
});
const began = performance.now();
const save = async (name: string, record: unknown) => {
	const raw = Buffer.from(`${JSON.stringify(record, null, 2)}\n`);
	assert.ok(raw.length <= 1048576);
	await writeFile(path.join(root, name), raw, { flag: "wx" });
};
const timer = setTimeout(() => {
	process.stderr.write("Water packet profile deadline\n");
	process.exit(2);
}, 120000);
const settle = async () => {
	for (let i = 0; i < 12; i++) {
		global.gc?.();
		await nextTurn();
	}
};

async function observe(
	basis: {
		queries: Array<{ coordinate: RasterCoordinate; [key: string]: unknown }>;
	},
	snaps: {
		references: Array<{
			id: string;
			requested: RasterCoordinate[];
			returned: RasterCoordinate[];
		}>;
	},
) {
	const start = performance.now();
	const packet = await loadWaterRaster(
		path.join(repo, plan.source),
		plan.manifestSha256,
	);
	const coarse = await loadOriginGeography(
		path.join(repo, plan.geography),
		plan.geographyManifestSha256,
	);
	await settle();
	const beforePolicyArrayBuffers = process.memoryUsage().arrayBuffers;
	const policy = prepareWaterGeography(coarse.geography, packet);
	policy.contains(basis.queries[0].coordinate);
	const loadAndFirstObservationMs = performance.now() - start;
	await settle();
	const retainedArrayBuffers = process.memoryUsage().arrayBuffers;
	const points = basis.queries.map((row, index) => ({
		sourceIndex: index,
		coordinate: row.coordinate,
		legacyMaskAllows: landConnection(
			coarse.geography,
			[...row.coordinate],
			[...row.coordinate],
		),
		newMaskAllows: policy.contains(row.coordinate),
		packetObservation: packet.lookup(row.coordinate),
	}));
	const segments = [];
	for (const reference of snaps.references)
		for (let endpoint = 0; endpoint < 2; endpoint++) {
			const a = reference.requested[endpoint],
				b = reference.returned[endpoint];
			segments.push({
				referenceId: reference.id,
				endpoint,
				from: a,
				to: b,
				legacyMaskAllows: landConnection(coarse.geography, [...a], [...b]),
				newMaskAllows: policy.landConnection(a, b),
			});
		}
	assert.equal(points.length, 245);
	assert.equal(segments.length, 166);
	const pointRegressions = points.filter(
		(row) => row.legacyMaskAllows && !row.newMaskAllows,
	);
	const segmentRegressions = segments.filter(
		(row) => row.legacyMaskAllows && !row.newMaskAllows,
	);
	await settle();
	const afterQueriesArrayBuffers = process.memoryUsage().arrayBuffers;
	assert.ok(
		afterQueriesArrayBuffers <= retainedArrayBuffers + 1048576,
		"Geography query backing grows",
	);
	return {
		loadAndFirstObservationMs,
		beforePolicyArrayBuffers,
		retainedArrayBuffers,
		afterQueriesArrayBuffers,
		additionalPolicyIndexBackingBytes:
			retainedArrayBuffers - beforePolicyArrayBuffers,
		packetBackingBytes: packet.backingBytes,
		compressedPlaneBytes: packet.compressedBytes,
		sourceIncompleteFeatureCount: policy.sourceIncompleteFeatureCount,
		points,
		segments,
		pointRegressions,
		segmentRegressions,
	};
}

try {
	const basis = JSON.parse(
		(await readFile(path.join(repo, plan.pointReport))).toString("utf8"),
	);
	assert.equal(
		basis.status,
		"all_saved_inputs_and_reference_endpoints_scanned_against_accepted_water_geometry",
	);
	assert.equal(basis.queries.length, 245);
	await settle();
	const baselineArrayBuffers = process.memoryUsage().arrayBuffers;
	const snaps = JSON.parse(
		(await readFile(path.join(repo, plan.snapReport))).toString("utf8"),
	);
	assert.equal(snaps.references.length, 83);
	const result = await observe(basis, snaps);
	await save("comparison.json", result);
	assert.equal(
		result.pointRegressions.length,
		0,
		"An old positive point mask regressed",
	);
	assert.equal(
		result.segmentRegressions.length,
		0,
		"An old positive provider-snap mask segment regressed",
	);
	assert.ok(
		result.retainedArrayBuffers - baselineArrayBuffers <= 15340000 + 5246029,
		"Packet retained buffer allowance",
	);
	await settle();
	const releasedArrayBuffers = process.memoryUsage().arrayBuffers;
	assert.ok(
		releasedArrayBuffers <= baselineArrayBuffers + 1048576,
		"Packet buffers remain after owner release",
	);
	await save("report.json", {
		status: "host_generic_water_geography_point_and_snap_checks_passed",
		...result,
		baselineArrayBuffers,
		releasedArrayBuffers,
		hostSecondsAfterBindingsThroughQueryAndReleaseChecks:
			(performance.now() - began) / 1000,
		sourcePbfReads: 0,
		routingQueries: 0,
		providerRequests: 0,
		productionMaskOrModelChanged: false,
		experimentalMaskHypothesisEvaluated: true,
		appActivated: false,
		scope:
			"Host offline geography hypothesis:unchanged country/coast,coarse water fallback in uncertain/uncovered cells,fine water elsewhere,all245 saved points/all166 provider-snap segments and buffer lifetime. No road permissions/cost/search/transfer/ETA/app integration. Observed development/source checks,not real land/geographic completeness or route recovery. Global incomplete source remains explicit.",
	});
} catch (error) {
	await save("failure.json", {
		status: "host_generic_water_geography_profile_stopped",
		error: String(error),
		hostSeconds: (performance.now() - began) / 1000,
	});
	process.exitCode = 2;
} finally {
	clearTimeout(timer);
}
