/** Read-only national frame masks: equality and component timing, no road queries. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import type { Frame } from "./coarse_osm_display_grid_v1.ts";
import { rasterLand, rasterLinks } from "./coarse_osm_display_grid_v2.ts";
import { loadOriginGeography } from "./coarse_osm_origin_geography_v1.ts";
import {
	assertPhaseReleased,
	settledPhaseMemory,
} from "./coarse_osm_phase_lifetime_v1.ts";
import type { RoutingGeography } from "./coarse_osm_routing_geography_v1.ts";
import { waterRoutingGeographyV4 } from "./coarse_osm_routing_geography_v4.ts";
import { waterRoutingGeographyV5 } from "./coarse_osm_routing_geography_v5.ts";
import { loadWaterRasterV2 } from "./coarse_osm_water_raster_loader_v2.ts";

const repo = path.resolve(import.meta.dirname, ".."),
	sha = (bytes: Uint8Array) => createHash("sha256").update(bytes).digest("hex");
const [name, pin] = process.argv.slice(2);
assert.ok(name && pin && global.gc);
const raw = await readFile(path.resolve(repo, name));
assert.equal(sha(raw), pin);
const plan = JSON.parse(raw.toString("utf8"));
assert.equal(
	plan.output,
	"data/coarse-quality/us-osm-water-mask-index-profile-v1",
);
assert.equal(plan.controlsPassed, 20);
assert.equal(plan.hostSeconds, 600);
assert.ok(
	plan.priorReserveBytes +
		plan.newClosedAllocationBytes +
		plan.metadataScratchReserveBytes +
		plan.activeCandidateReserveBytes +
		plan.maxOwnedBytes <
		72 * 1024 ** 3,
);
for (const [file, expected] of Object.entries(plan.bindings))
	assert.equal(sha(await readFile(path.join(repo, file))), expected, file);
const root = path.join(repo, plan.output);
await mkdir(root);
await writeFile(path.join(root, "execution-plan.json"), raw, { flag: "wx" });
const began = performance.now();
const check = () => {
	assert.ok(performance.now() - began < 600000, "Mask profile deadline");
	assert.ok(process.memoryUsage().rss < 4 * 1024 ** 3, "Mask profile host RSS");
};
const mask = (geography: RoutingGeography, frame: Frame) => {
	assert.ok(
		Number.isSafeInteger(frame.width) &&
			Number.isSafeInteger(frame.height) &&
			frame.width > 0 &&
			frame.height > 0 &&
			frame.width * frame.height <= 2500000,
	);
	const cells = frame.width * frame.height,
		land = new Uint8Array(Math.ceil(cells / 8)),
		boundary = new Uint8Array(Math.ceil(cells / 8)),
		links = new Uint8Array(Math.ceil(cells / 2)),
		row = new Uint8Array(2 * frame.width);
	const start = performance.now();
	rasterLand(frame, geography, land, boundary, row, check);
	const landMs = performance.now() - start;
	const linksBegan = performance.now();
	rasterLinks(frame, geography, land, boundary, links, check);
	const linksMs = performance.now() - linksBegan;
	return {
		landMs,
		linksMs,
		maskMs: landMs + linksMs,
		backingBytes:
			land.byteLength + boundary.byteLength + links.byteLength + row.byteLength,
		fingerprints: {
			land: sha(land),
			boundary: sha(boundary),
			links: sha(links),
		},
	};
};
async function observe() {
	const packet = await loadWaterRasterV2(
		path.join(repo, plan.waterSource),
		plan.waterManifestSha256,
	);
	const coarse = await loadOriginGeography(
		path.join(repo, plan.geographySource),
		plan.geographyManifestSha256,
	);
	const old = waterRoutingGeographyV4(coarse.geography, packet),
		indexed = waterRoutingGeographyV5(coarse.geography, packet);
	const retained = await settledPhaseMemory(),
		rows = [];
	for (const frame of plan.frames as Frame[]) {
		check();
		const before = mask(old, frame);
		await assertPhaseReleased(retained.arrayBuffers, "old mask buffers");
		const after = mask(indexed, frame);
		await assertPhaseReleased(retained.arrayBuffers, "indexed mask buffers");
		assert.deepEqual(after.fingerprints, before.fingerprints);
		assert.equal(after.backingBytes, before.backingBytes);
		rows.push({ frame, before, after });
		process.stdout.write(
			`${JSON.stringify({ frames: rows.length, beforeMaskMs: before.maskMs, afterMaskMs: after.maskMs, identical: true })}\n`,
		);
	}
	return {
		rows,
		retainedArrayBuffers: retained.arrayBuffers,
		afterQueriesArrayBuffers: (
			await assertPhaseReleased(retained.arrayBuffers, "all mask buffers")
		).arrayBuffers,
		packetBackingBytes: packet.backingBytes,
	};
}
try {
	const baseline = await settledPhaseMemory(),
		result = await observe();
	const released = await assertPhaseReleased(
		baseline.arrayBuffers,
		"packet/geography owners",
	);
	const report = {
		status: "national_frame_mask_ring_index_equal",
		recipeSha256: pin,
		...result,
		baselineArrayBuffers: baseline.arrayBuffers,
		releasedArrayBuffers: released.arrayBuffers,
		hostMs: performance.now() - began,
		roadQueries: 0,
		sourcePbfReads: 0,
		providerRequests: 0,
		modelOrProductionChanged: false,
		scope:
			"Two frozen national900min display frames; exact land/boundary/link backing SHA equality, same query buffer sizes and owner release. Timers cover rasterLand/rasterLinks only, excluding packet/geo load, road field, seeding/fill/contours/render/JSON/GC/app/cloud. Shared host with separate fixed candidate; not an isolated speed benchmark or packaged5s/runtime/accuracy admission.",
	};
	await writeFile(
		path.join(root, "report.json"),
		`${JSON.stringify(report, null, 2)}\n`,
		{ flag: "wx" },
	);
} catch (error) {
	await writeFile(
		path.join(root, "failure.json"),
		`${JSON.stringify({ error: String(error), hostMs: performance.now() - began }, null, 2)}\n`,
		{ flag: "wx" },
	);
	throw error;
}
