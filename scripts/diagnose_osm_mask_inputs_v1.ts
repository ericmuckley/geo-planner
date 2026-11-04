/** Read-only all-input mask/snap semantics diagnostic; no routing or policy change. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { containsPolygon } from "../src/server/coarse-contours.ts";
import { landConnection } from "../src/server/coarse-geography.ts";
import { nearestModeledRoad } from "./coarse_osm_geometric_snap_v1.ts";
import { connectorPrice } from "./coarse_osm_origin_connections_v1.ts";
import { loadOriginGeography } from "./coarse_osm_origin_geography_v1.ts";
import { loadPackedCar } from "./coarse_osm_packed_loader_v1.ts";
import { loadPaidGeometry } from "./coarse_osm_paid_geometry_loader_v1.ts";
import type { Coordinate } from "./coarse_osm_spherical_v1.ts";

const repo = path.resolve(import.meta.dirname, ".."),
	sha = (bytes: Uint8Array) => createHash("sha256").update(bytes).digest("hex");
const began = performance.now(),
	[recipeName, pin] = process.argv.slice(2);
assert.ok(recipeName && pin);
const bytes = await readFile(path.resolve(repo, recipeName));
assert.equal(sha(bytes), pin);
const plan = JSON.parse(bytes.toString("utf8"));
assert.equal(plan.output, "data/coarse-quality/us-osm-car-mask-diagnostic-v1");
for (const [name, expected] of Object.entries(plan.bindings))
	assert.equal(sha(await readFile(path.join(repo, name))), expected, name);
const root = path.join(repo, plan.output);
await mkdir(root);
await writeFile(path.join(root, "execution-plan.json"), bytes, { flag: "wx" });
const check = () => {
	assert.ok(performance.now() - began < 120000, "Mask diagnostic deadline");
	assert.ok(
		process.memoryUsage().rss < 4 * 1024 ** 3,
		"Mask diagnostic host RSS bound",
	);
};
try {
	const inputs = JSON.parse(
		(await readFile(path.join(repo, plan.inputs))).toString("utf8"),
	) as { coordinate: Coordinate; connection: unknown }[];
	assert.equal(inputs.length, 79);
	const references = [];
	for (const name of plan.referencePlans as string[]) {
		const saved = JSON.parse(
			(await readFile(path.join(repo, name))).toString("utf8"),
		);
		for (const query of saved.queries) {
			assert.deepEqual(query.request.radiuses, [350, 350]);
			references.push(query.id.slice(query.id.indexOf("/") + 1));
		}
	}
	const baseline = JSON.parse(
		(await readFile(path.join(repo, plan.baseline))).toString("utf8"),
	);
	assert.equal(references.length, 83);
	assert.deepEqual(
		references.sort(),
		baseline.rows.map((row: { id: string }) => row.id).sort(),
	);
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
		),
		rows = [];
	for (const input of inputs) {
		check();
		const result = nearestModeledRoad(
			core.graph,
			paid.geometry,
			core.keys,
			core.starts,
			input.coordinate,
			check,
		);
		assert.ok(result.snap);
		const snap = result.snap,
			source = [...input.coordinate],
			foot = [...snap.coordinate];
		rows.push({
			coordinate: input.coordinate,
			originalSupported: input.connection !== null,
			sourceOnMask: landConnection(geo.geography, source, source),
			sourceInCountryBoundary: geo.geography.boundary.some((poly) =>
				containsPolygon(source as [number, number], poly),
			),
			containingLakePolygons: geo.geography.lakes
				.map((polygon, index) =>
					containsPolygon(source as [number, number], polygon) ? index : -1,
				)
				.filter((index) => index >= 0),
			nearestModeledRoad: snap,
			nearestFootOnMask: landConnection(geo.geography, foot, foot),
			strictContinuousLink: landConnection(geo.geography, source, foot),
			connector: connectorPrice(input.coordinate, snap.coordinate),
			withinExisting100mAssumption: snap.distanceMeters <= 100,
			withinSavedReference350mRadius: snap.distanceMeters <= 350,
		});
	}
	const report = {
		status: "all_input_mask_and_saved_snap_semantics_diagnostic_complete",
		recipeSha256: pin,
		inputs: 79,
		savedReferenceRequestsChecked: 83,
		savedReferenceRadiusMeters: 350,
		rows,
		outsideMask: rows.filter((row) => !row.sourceOnMask),
		modelFeetWithinReferenceRadius: rows.filter(
			(row) => row.withinSavedReference350mRadius,
		).length,
		hostTotalMs: performance.now() - began,
		modelChanged: false,
		providerRequests: 0,
		scope:
			"All79 original input points and all83 saved request radiuses, with no route search/new ETA score. Distances refer to the retained major-road model, not the provider's fuller road network. Being inside a saved snap radius does not prove actual land, local access or eligibility. Country/lake coordinates and100m policy are unchanged; this is diagnosis only, not a proposed relaxation or data truth.",
	};
	await writeFile(
		path.join(root, "report.json"),
		`${JSON.stringify(report, null, 2)}\n`,
		{ flag: "wx" },
	);
	process.stdout.write(
		`${JSON.stringify({ status: report.status, outsideMask: report.outsideMask, modelFeetWithinReferenceRadius: report.modelFeetWithinReferenceRadius, hostTotalMs: report.hostTotalMs })}\n`,
	);
} catch (error) {
	await writeFile(
		path.join(root, "failure.json"),
		`${JSON.stringify({ error: String(error) }, null, 2)}\n`,
		{ flag: "wx" },
	);
	throw error;
}
