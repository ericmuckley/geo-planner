/** Reopen saved public maps and inspect all endpoint cells; no graph or rerender. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { containsPolygon } from "../src/server/coarse-contours.ts";
import { cellAt, center, type Frame } from "./coarse_osm_display_grid_v1.ts";
import { loadOriginGeography } from "./coarse_osm_origin_geography_v1.ts";
import {
	assertPhaseReleased,
	settledPhaseMemory,
} from "./coarse_osm_phase_lifetime_v1.ts";
import { waterRoutingGeographyV6 } from "./coarse_osm_routing_geography_v6.ts";
import type { Coordinate } from "./coarse_osm_spherical_v1.ts";
import { loadWaterRasterV2 } from "./coarse_osm_water_raster_loader_v2.ts";

type Place = { lon: number; lat: number };
type Row = {
	id: string;
	set: string;
	origin: Place;
	destination: Place;
	budgetMinutes: number;
	referenceMinutes: number;
	candidate: {
		pointMinutes: number | null;
		predictedReachable: boolean;
		classification: string;
	};
};
type Output = { filename: string; bytes: number; sha256: string };
type Phase = {
	origin: Coordinate;
	productions: { minutes: number; frame: Frame; output: Output }[];
};
const repo = path.resolve(import.meta.dirname, ".."),
	sha = (b: Uint8Array) => createHash("sha256").update(b).digest("hex"),
	xy = (p: Place): Coordinate => [p.lon, p.lat];
const [name, pin] = process.argv.slice(2);
assert.ok(name && pin && global.gc);
const raw = await readFile(path.resolve(repo, name));
assert.equal(sha(raw), pin);
const plan = JSON.parse(raw.toString("utf8"));
assert.equal(
	plan.output,
	"data/coarse-quality/us-osm-water-shading-diagnostic-v1",
);
assert.ok(
	plan.priorReserveBytes +
		plan.newClosedAllocationBytes +
		plan.metadataScratchReserveBytes +
		plan.activePathReserveBytes +
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
		assert.ok(performance.now() - began < 120000, "Shading audit deadline");
		assert.ok(process.memoryUsage().rss < 4 * 1024 ** 3, "Shading audit RSS");
	};
async function observe() {
	const packet = await loadWaterRasterV2(
		path.join(repo, plan.waterSource),
		plan.waterManifestSha256,
	);
	const coarse = await loadOriginGeography(
			path.join(repo, plan.geographySource),
			plan.geographyManifestSha256,
		),
		geo = waterRoutingGeographyV6(coarse.geography, packet);
	const candidate = JSON.parse(
		await readFile(path.join(repo, plan.candidate), "utf8"),
	) as { rows: Row[]; phases: Phase[] };
	const connections = JSON.parse(
		await readFile(path.join(repo, plan.connections), "utf8"),
	) as {
		coordinate: Coordinate;
		connection: {
			snap: { coordinate: Coordinate };
			connectorTicks: number;
		} | null;
	}[];
	assert.equal(candidate.rows.length, 83);
	assert.equal(connections.length, 79);
	const feet = new Map(
		connections.map((row) => [JSON.stringify(row.coordinate), row.connection]),
	);
	const rows = [],
		maps = [];
	for (const phase of candidate.phases)
		for (const production of phase.productions) {
			check();
			const selected = candidate.rows.filter(
				(row) =>
					JSON.stringify(xy(row.origin)) === JSON.stringify(phase.origin) &&
					row.budgetMinutes === production.minutes,
			);
			assert.ok(selected.length);
			assert.match(production.output.filename, /^origin-\d{2}-\d+\.geojson$/);
			const encoded = await readFile(
				path.join(repo, plan.candidateRoot, production.output.filename),
			);
			assert.equal(encoded.length, production.output.bytes);
			assert.equal(sha(encoded), production.output.sha256);
			const shape = JSON.parse(encoded.toString("utf8")) as {
				type: string;
				coordinates: number[][][][];
			};
			assert.equal(shape.type, "MultiPolygon");
			for (const row of selected) {
				const point = xy(row.destination),
					cell = cellAt(production.frame, point),
					mid = cell < 0 ? null : center(production.frame, cell),
					connection = feet.get(JSON.stringify(point));
				assert.ok(connection);
				const pointOnMask = geo.connectionPolicy([...point], [...point]);
				const centerOnMask =
					mid === null ? null : geo.connectionPolicy(mid, mid);
				const shaded = shape.coordinates.some((polygon) =>
					containsPolygon([...point], polygon),
				);
				assert.equal(shaded, row.candidate.predictedReachable, row.id);
				rows.push({
					id: row.id,
					set: row.set,
					budgetMinutes: row.budgetMinutes,
					referenceMinutes: row.referenceMinutes,
					pointMinutes: row.candidate.pointMinutes,
					classification: row.candidate.classification,
					shaded,
					point,
					frame: production.frame,
					cell,
					cellCenter: mid,
					pointOnMask,
					centerOnMask,
					pointObservation: packet.lookup(point),
					centerObservation: mid === null ? null : packet.lookup(mid),
					primaryFoot: connection.snap.coordinate,
					primaryFootCell: cellAt(production.frame, connection.snap.coordinate),
					primaryConnectorTicks: connection.connectorTicks,
					primaryPaidSegmentAllowed: geo.connectionPolicy(
						[...point],
						[...connection.snap.coordinate],
					),
				});
			}
			maps.push(production.output);
		}
	assert.equal(rows.length, 83);
	assert.equal(new Set(rows.map((row) => row.id)).size, 83);
	assert.equal(maps.length, 37);
	return { rows, maps };
}
try {
	const baseline = await settledPhaseMemory(),
		result = await observe();
	const released = await assertPhaseReleased(
		baseline.arrayBuffers,
		"shading packet/map owners",
	);
	const report = {
		status: "all83_saved_public_shading_and_mask_cells_audited",
		recipeSha256: pin,
		...result,
		pointsOnMask: result.rows.filter((row) => row.pointOnMask).length,
		pointDryButCellCenterWet: result.rows
			.filter((row) => row.pointOnMask && row.centerOnMask === false)
			.map((row) => row.id),
		missedReachable: result.rows
			.filter((row) => row.classification === "missedReachable")
			.map((row) => row.id),
		baselineArrayBuffers: baseline.arrayBuffers,
		releasedArrayBuffers: released.arrayBuffers,
		hostMs: performance.now() - began,
		roadQueries: 0,
		newDisplays: 0,
		sourcePbfReads: 0,
		providerRequests: 0,
		scope:
			"Reopen all37 frozen original-budget GeoJSON files/SHA and all83 selected point classifications; inspect original full geography on actual endpoint, display-cell center and primary paid segment. No graph/field/search/rerender/source/provider/DB/app operation. Diagnostic cell differences are observed development evidence, not a routing exception, causal national claim, policy or gate change.",
	};
	await writeFile(
		path.join(root, "report.json"),
		`${JSON.stringify(report, null, 2)}\n`,
		{ flag: "wx" },
	);
	process.stdout.write(
		`${JSON.stringify({ status: report.status, points: report.rows.length, maps: report.maps.length, pointDryButCellCenterWet: report.pointDryButCellCenterWet, missedReachable: report.missedReachable })}\n`,
	);
} catch (error) {
	await writeFile(
		path.join(root, "failure.json"),
		`${JSON.stringify({ error: String(error), hostMs: performance.now() - began }, null, 2)}\n`,
		{ flag: "wx" },
	);
	throw error;
}
