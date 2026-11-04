/** Saved-snap shoreline diagnostic; no route search or ETA evaluation. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import {
	landConnection,
	prepareGeography,
} from "../src/server/coarse-geography.ts";

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
		"data/coarse-quality/us-osm-car-origin-shore-screen-v1",
	);
	assert.equal(plan.geographySource, "src/server/data/coarse-grid-v9.json");
	assert.equal(
		plan.geographySourceSha256,
		"28271c809a04cdfab41ad735ad66b29e3875179b617198b7b1d4490533439bf6",
	);
	for (const [name, expected] of Object.entries(plan.bindings))
		assert.equal(sha(await readFile(path.join(repo, name))), expected);
	const root = path.join(repo, plan.output);
	await mkdir(root);
	await writeFile(path.join(root, "execution-plan.json"), recipe, {
		flag: "wx",
	});
	try {
		const saved = JSON.parse(
			(await readFile(path.join(repo, plan.savedSnaps))).toString("utf8"),
		);
		assert.equal(saved.origins, 56);
		async function geography() {
			const bytes = await readFile(path.join(repo, plan.geographySource));
			assert.ok(bytes.length < 70000000);
			assert.equal(sha(bytes), plan.geographySourceSha256);
			const data = JSON.parse(bytes.toString("utf8"));
			return {
				boundary: data.boundary as number[][][][],
				lakes: data.lakes as number[][][][],
			};
		}
		global.gc();
		const baseline = process.memoryUsage();
		const geo = await geography();
		prepareGeography(geo);
		global.gc();
		const retainedGeographyOnly = process.memoryUsage();
		const queries: {
			coordinate: number[];
			snap: { coordinate: number[]; distanceMeters: number };
		}[] = saved.queries;
		const rows = queries.map(
			(query: {
				coordinate: number[];
				snap: { coordinate: number[]; distanceMeters: number };
			}) => ({
				origin: query.coordinate,
				geometricFoot: query.snap.coordinate,
				distanceMeters: query.snap.distanceMeters,
				originOnMask: landConnection(geo, query.coordinate, query.coordinate),
				footOnMask: landConnection(
					geo,
					query.snap.coordinate,
					query.snap.coordinate,
				),
				continuousMaskLand: landConnection(
					geo,
					query.coordinate,
					query.snap.coordinate,
				),
			}),
		);
		assert.ok(performance.now() - began < 30000);
		const report = {
			status: "saved_geometric_foot_continuous_shore_screen_complete",
			origins: 56,
			originOnMask: rows.filter((row) => row.originOnMask).length,
			footOnMask: rows.filter((row) => row.footOnMask).length,
			continuousMaskLand: rows.filter((row) => row.continuousMaskLand).length,
			rows,
			geography: {
				boundaryPolygons: geo.boundary.length,
				lakePolygons: geo.lakes.length,
				rings: [...geo.boundary, ...geo.lakes].reduce(
					(n, p) => n + p.length,
					0,
				),
				points: [...geo.boundary, ...geo.lakes].reduce(
					(n, p) => n + p.reduce((sum, ring) => sum + ring.length, 0),
					0,
				),
			},
			baseline,
			retainedGeographyOnly,
			hostTotalMs: performance.now() - began,
			scope:
				"Host read-only saved-snap/old coarse geography diagnostic. Zero routing queries, provider calls, source PBF, new geography artifact or connector/ETA/app admission. Mask generalization is distinct from actual road/shore truth.",
			modelChanged: false,
		};
		await writeFile(
			path.join(root, "report.json"),
			`${JSON.stringify(report, null, 2)}\n`,
			{ flag: "wx" },
		);
		process.stdout.write(
			`${JSON.stringify({ status: report.status, originOnMask: report.originOnMask, footOnMask: report.footOnMask, continuousMaskLand: report.continuousMaskLand, hostTotalMs: report.hostTotalMs })}\n`,
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
