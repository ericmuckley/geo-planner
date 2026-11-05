/** One in-process V8 profile of water-mask links; no road graph or network. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { Session } from "node:inspector/promises";
import path from "node:path";
import type { Frame } from "./coarse_osm_display_grid_v1.ts";
import { rasterLand, rasterLinks } from "./coarse_osm_display_grid_v2.ts";
import { loadOriginGeography } from "./coarse_osm_origin_geography_v1.ts";
import {
	assertPhaseReleased,
	settledPhaseMemory,
} from "./coarse_osm_phase_lifetime_v1.ts";
import { waterRoutingGeographyV4 } from "./coarse_osm_routing_geography_v4.ts";
import { loadWaterRasterV2 } from "./coarse_osm_water_raster_loader_v2.ts";

const repo = path.resolve(import.meta.dirname, ".."),
	sha = (b: Uint8Array) => createHash("sha256").update(b).digest("hex");
const [name, pin] = process.argv.slice(2);
assert.ok(name && pin && global.gc);
const raw = await readFile(path.resolve(repo, name));
assert.equal(sha(raw), pin);
const plan = JSON.parse(raw.toString("utf8"));
assert.equal(
	plan.output,
	"data/coarse-quality/us-osm-water-mask-cpu-profile-v1",
);
assert.equal(plan.hostSeconds, 300);
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
const began = performance.now(),
	check = () => {
		assert.ok(performance.now() - began < 300000, "CPU profile deadline");
		assert.ok(process.memoryUsage().rss < 4 * 1024 ** 3, "CPU profile RSS");
	};
async function observe() {
	const packet = await loadWaterRasterV2(
		path.join(repo, plan.waterSource),
		plan.waterManifestSha256,
	);
	const source = await loadOriginGeography(
		path.join(repo, plan.geographySource),
		plan.geographyManifestSha256,
	);
	const geography = waterRoutingGeographyV4(source.geography, packet),
		frame = plan.frame as Frame;
	assert.ok(
		frame.width * frame.height <= 2500000 &&
			frame.width > 0 &&
			frame.height > 0,
	);
	const cells = frame.width * frame.height,
		land = new Uint8Array(Math.ceil(cells / 8)),
		boundary = new Uint8Array(Math.ceil(cells / 8)),
		links = new Uint8Array(Math.ceil(cells / 2)),
		row = new Uint8Array(2 * frame.width);
	const start = performance.now();
	rasterLand(frame, geography, land, boundary, row, check);
	const landMs = performance.now() - start;
	const session = new Session();
	session.connect();
	try {
		await session.post("Profiler.enable");
		await session.post("Profiler.start");
		const linksBegan = performance.now();
		rasterLinks(frame, geography, land, boundary, links, check);
		const linksMs = performance.now() - linksBegan;
		const { profile } = await session.post("Profiler.stop");
		await session.post("Profiler.disable");
		const encoded = Buffer.from(JSON.stringify(profile));
		assert.ok(encoded.length <= 16777216);
		await writeFile(path.join(root, "links.cpuprofile"), encoded, {
			flag: "wx",
		});
		const counts = new Map<number, number>();
		for (const id of profile.samples ?? [])
			counts.set(id, (counts.get(id) ?? 0) + 1);
		const topSelf = profile.nodes
			.map((node) => ({
				function: node.callFrame.functionName,
				url: node.callFrame.url,
				line: node.callFrame.lineNumber + 1,
				exclusiveSamples: counts.get(node.id) ?? 0,
			}))
			.sort((a, b) => b.exclusiveSamples - a.exclusiveSamples)
			.slice(0, 40);
		return {
			frame,
			landMs,
			profiledLinksMs: linksMs,
			samples: profile.samples?.length ?? 0,
			topSelf,
			profile: { bytes: encoded.length, sha256: sha(encoded) },
			fingerprints: {
				land: sha(land),
				boundary: sha(boundary),
				links: sha(links),
			},
		};
	} finally {
		session.disconnect();
	}
}
try {
	const baseline = await settledPhaseMemory(),
		result = await observe();
	assert.ok(result.samples > 0);
	const released = await assertPhaseReleased(
		baseline.arrayBuffers,
		"CPU profile packet/raster/output owners",
	);
	const report = {
		status: "water_mask_links_cpu_profile_complete",
		recipeSha256: pin,
		...result,
		baselineArrayBuffers: baseline.arrayBuffers,
		releasedArrayBuffers: released.arrayBuffers,
		hostMs: performance.now() - began,
		roadQueries: 0,
		sourcePbfReads: 0,
		providerRequests: 0,
		scope:
			"One exact saved frame, unchanged V4 mask predicate. In-process inspector Session, no debug network listener. Sampling only rasterLinks; no road field/search/query, source PBF, app or provider. Profiled time includes profiler overhead/shared host and is not app/cloud latency or an isolated speed benchmark.",
	};
	await writeFile(
		path.join(root, "report.json"),
		`${JSON.stringify(report, null, 2)}\n`,
		{ flag: "wx" },
	);
	process.stdout.write(
		`${JSON.stringify({ status: report.status, samples: report.samples, topSelf: report.topSelf.slice(0, 8) })}\n`,
	);
} catch (error) {
	await writeFile(
		path.join(root, "failure.json"),
		`${JSON.stringify({ error: String(error), hostMs: performance.now() - began }, null, 2)}\n`,
		{ flag: "wx" },
	);
	throw error;
}
