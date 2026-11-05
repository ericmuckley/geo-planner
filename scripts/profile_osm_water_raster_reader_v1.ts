/** One fresh host packet load and arbitrary-coordinate observation/lifetime proof. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { setImmediate as nextTurn } from "node:timers/promises";
import { fileURLToPath } from "node:url";
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
	"data/coarse-quality/us-osm-water-raster-reader-profile-v1",
);
assert.equal(
	plan.source,
	"data/coarse-quality/us-osm-water-raster-source-run-v1",
);
assert.equal(plan.randomCellQueries, 512);
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

async function observe(basis: {
	queries: Array<{ coordinate: RasterCoordinate; [key: string]: unknown }>;
}) {
	const start = performance.now();
	const packet = await loadWaterRaster(
		path.join(repo, plan.source),
		plan.manifestSha256,
	);
	assert.equal(packet.backingBytes, 15340000);
	assert.equal(packet.compressedBytes, 1781499);
	assert.equal(packet.sourceIncompleteFeatures.length, 1);
	const first = packet.lookup(basis.queries[0].coordinate);
	const loadAndFirstObservationMs = performance.now() - start;
	assert.equal(first.kind, "cell");
	await settle();
	const retainedArrayBuffers = process.memoryUsage().arrayBuffers;
	const observations: Array<
		Extract<ReturnType<typeof packet.lookup>, { kind: "cell" }> & {
			phase: string;
			sourceIndex: number;
			coordinate: RasterCoordinate;
		}
	> = [];
	for (let index = 0; index < basis.queries.length; index++) {
		const source = basis.queries[index],
			cell = packet.lookup(source.coordinate);
		assert.equal(cell.kind, "cell");
		if (cell.kind !== "cell")
			throw new Error("Saved coordinate outside declared packet domain");
		observations.push({
			phase: "saved-point",
			sourceIndex: index,
			coordinate: source.coordinate,
			...cell,
		});
	}
	for (let index = 0; index < basis.queries.length; index++) {
		const prior = observations[index];
		const center: RasterCoordinate = [
			prior.centerE7[0] / 1e7,
			prior.centerE7[1] / 1e7,
		];
		const cell = packet.lookup(center);
		assert.equal(cell.kind, "cell");
		if (cell.kind !== "cell") throw new Error("Cell center outside packet");
		assert.deepEqual(
			[cell.column, cell.row, cell.waterAtCenter, cell.sourceUncertainty],
			[prior.column, prior.row, prior.waterAtCenter, prior.sourceUncertainty],
		);
		observations.push({
			phase: "saved-cell-center",
			sourceIndex: index,
			coordinate: center,
			...cell,
		});
	}
	let state = 4187321;
	const next = () => {
		state = (Math.imul(1664525, state) + 1013904223) >>> 0;
		return state;
	};
	for (let index = 0; index < plan.randomCellQueries; index++) {
		const column = next() % packet.grid.columns,
			row = next() % packet.grid.rows;
		const coordinate: RasterCoordinate = [
			(packet.grid.xE7 + (column + 0.5) * packet.grid.stepE7) / 1e7,
			(packet.grid.yE7 + (row + 0.5) * packet.grid.stepE7) / 1e7,
		];
		const cell = packet.lookup(coordinate);
		assert.equal(cell.kind, "cell");
		if (cell.kind !== "cell")
			throw new Error("Generated supported center outside packet");
		assert.equal(cell.column, column);
		assert.equal(cell.row, row);
		observations.push({
			phase: "generated-cell-center",
			sourceIndex: index,
			coordinate,
			...cell,
		});
	}
	assert.equal(observations.length, 1002);
	await settle();
	const afterQueriesArrayBuffers = process.memoryUsage().arrayBuffers;
	assert.ok(
		afterQueriesArrayBuffers <= retainedArrayBuffers + 1048576,
		"Unbounded packet query backing growth",
	);
	return {
		loadAndFirstObservationMs,
		loaderLoadMs: packet.loadMs,
		retainedArrayBuffers,
		afterQueriesArrayBuffers,
		packetBackingBytes: packet.backingBytes,
		compressedPlaneBytes: packet.compressedBytes,
		manifestBytes: packet.manifestBytes,
		planeFingerprints: packet.planeFingerprints,
		sourceIncompleteFeatures: packet.sourceIncompleteFeatures,
		observations,
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
	const result = await observe(basis);
	assert.ok(
		result.retainedArrayBuffers - baselineArrayBuffers <= 15340000 + 1048576,
		"Packet retained buffer allowance",
	);
	await settle();
	const releasedArrayBuffers = process.memoryUsage().arrayBuffers;
	assert.ok(
		releasedArrayBuffers <= baselineArrayBuffers + 1048576,
		"Packet buffers remain after owner release",
	);
	await save("report.json", {
		status: "host_compact_water_packet_and_arbitrary_observations_passed",
		...result,
		baselineArrayBuffers,
		releasedArrayBuffers,
		hostSecondsAfterBindingsThroughQueryAndReleaseChecks:
			(performance.now() - began) / 1000,
		sourcePbfReads: 0,
		modelQueries: 0,
		providerRequests: 0,
		maskOrModelChanged: false,
		appActivated: false,
		scope:
			"Fresh host data-packet hash/inflate/schema/popcount/copy and first observation,1002 arbitrary data lookups and buffer lifetime. Excludes process startup/graph/routing/render/complete app/cloud. No land/geographic coverage/mask policy admission.",
	});
} catch (error) {
	await save("failure.json", {
		status: "host_water_packet_profile_stopped",
		error: String(error),
		hostSeconds: (performance.now() - began) / 1000,
	});
	process.exitCode = 2;
} finally {
	clearTimeout(timer);
}
