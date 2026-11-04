/** Single-use host profile of frozen geometric snapping, with one full scan. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { nearestModeledRoad } from "./coarse_osm_geometric_snap_v1.ts";
import { loadPackedCar } from "./coarse_osm_packed_loader_v1.ts";
import { loadPaidGeometry } from "./coarse_osm_paid_geometry_loader_v1.ts";
import type { PaidShapePoint } from "./coarse_osm_paid_geometry_v1.ts";
import {
	type Coordinate,
	nearestOnSegment,
} from "./coarse_osm_spherical_v1.ts";

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
		"data/coarse-quality/us-osm-car-geometric-snap-profile-v1",
	);
	assert.equal(plan.coreSource, "data/coarse-quality/us-osm-car-wire-codec-v1");
	assert.equal(
		plan.geometrySource,
		"data/coarse-quality/us-osm-car-paid-geometry-codec-v1",
	);
	assert.equal(plan.controlsPassed, 8);
	for (const [name, expected] of Object.entries(plan.bindings)) {
		assert.ok(name.startsWith("scripts/") || name.startsWith("docs/evidence/"));
		assert.equal(sha(await readFile(path.join(repo, name))), expected);
	}
	const root = path.join(repo, plan.output);
	await mkdir(root);
	await writeFile(path.join(root, "execution-plan.json"), recipe, {
		flag: "wx",
	});
	const check = () =>
		assert.ok(
			performance.now() - began < 120000,
			"Geometric profile host deadline",
		);
	try {
		assert.ok(plan.origins.length > 0 && plan.origins.length <= 200);
		global.gc();
		const baseline = process.memoryUsage();
		const loadBegan = performance.now();
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
		global.gc();
		const retainedAfterLoad = process.memoryUsage();
		const queries = [];
		let firstLoadAndSnapMs = 0;
		for (const value of plan.origins) {
			check();
			const started = performance.now();
			const result = nearestModeledRoad(
				core.graph,
				paid.geometry,
				core.keys,
				core.starts,
				value.coordinate,
				check,
			);
			assert.ok(result.snap && Number.isFinite(result.snap.distanceMeters));
			assert.ok(
				result.snap.forwardProgress >= 0 &&
					result.snap.forwardProgress <= 1 &&
					result.snap.backwardProgress >= 0 &&
					result.snap.backwardProgress <= 1,
			);
			assert.equal(result.stats.longSpansExamined, 529205);
			const snapMs = performance.now() - started;
			global.gc();
			if (!queries.length) firstLoadAndSnapMs = performance.now() - loadBegan;
			queries.push({
				...value,
				...result,
				snapMs,
				hostQueryMsIncludingGc: performance.now() - started,
			});
		}
		const exhaustiveBegan = performance.now();
		const origin = plan.origins[0].coordinate as Coordinate;
		let physicalSpans = 0;
		let segments = 0;
		let best: {
			canonicalArc: number;
			segment: number;
			distanceMeters: number;
			segmentFraction: number;
		} | null = null;
		// Independent candidate enumeration: every physical span, no cell or
		// length pruning. Projection is separately checked against a 3D oracle.
		for (let vertex = 0; vertex < core.graph.vertices; vertex++) {
			if (vertex % 16384 === 0) check();
			for (
				let arc = core.graph.outgoingStart(vertex);
				arc < core.graph.outgoingEnd(vertex);
				arc++
			) {
				const reverse = core.graph.reverseArc(arc);
				if (reverse !== null && reverse < arc) continue;
				physicalSpans++;
				let previous: PaidShapePoint | null = null;
				let segment = -1;
				paid.geometry.visitPoints(arc, (point) => {
					if (previous !== null) {
						segment++;
						segments++;
						const candidate = nearestOnSegment(
							origin,
							[previous.xE7 / 1e7, previous.yE7 / 1e7],
							[point.xE7 / 1e7, point.yE7 / 1e7],
						);
						if (
							best === null ||
							candidate.distance < best.distanceMeters - 1e-6 ||
							(Math.abs(candidate.distance - best.distanceMeters) <= 1e-6 &&
								(arc < best.canonicalArc ||
									(arc === best.canonicalArc && segment < best.segment)))
						)
							best = {
								canonicalArc: arc,
								segment,
								distanceMeters: candidate.distance,
								segmentFraction: candidate.fraction,
							};
					}
					previous = point;
				});
			}
		}
		assert.equal(physicalSpans, 6408084);
		assert.ok(best);
		const expected = best as {
			canonicalArc: number;
			segment: number;
			distanceMeters: number;
			segmentFraction: number;
		};
		assert.equal(queries[0].snap.canonicalArc, expected.canonicalArc);
		assert.equal(queries[0].snap.segment, expected.segment);
		assert.equal(queries[0].snap.distanceMeters, expected.distanceMeters);
		assert.equal(queries[0].snap.segmentFraction, expected.segmentFraction);
		global.gc();
		const report = {
			status:
				"host_national_geometric_snap_profile_and_complete_first_origin_scan_passed",
			recipeSha256: pin,
			origins: queries.length,
			sourceRequests: 48,
			queries,
			hostFirstLoadAndSnapMsIncludingGc: firstLoadAndSnapMs,
			retainedDataBackingBufferBytes:
				core.retainedDataBackingBufferBytes +
				paid.retainedDataBackingBufferBytes,
			combinedCompressedBytes: core.compressedBytes + paid.compressedBytes,
			completeEnumeration: {
				origin,
				physicalSpans,
				segments,
				result: expected,
				hostMs: performance.now() - exhaustiveBegan,
			},
			baseline,
			retainedAfterLoad,
			afterQueries: process.memoryUsage(),
			hostTotalMs: performance.now() - began,
			scope:
				"Host geometric nearest simplified modeled road only; one complete physical-span enumeration shares a separately oracle-tested projection. No origin connector/access/shore, real source-curve/ETA, full field/display/app/packaged estimate, Linux or Vercel admission.",
			modelChanged: false,
		};
		await writeFile(
			path.join(root, "report.json"),
			JSON.stringify(report, null, 2) + "\n",
			{ flag: "wx" },
		);
		process.stdout.write(
			JSON.stringify({
				status: report.status,
				origins: report.origins,
				hostFirstLoadAndSnapMsIncludingGc: firstLoadAndSnapMs,
				physicalSpansEnumerated: physicalSpans,
				hostTotalMs: report.hostTotalMs,
			}) + "\n",
		);
	} catch (error) {
		await writeFile(
			path.join(root, "failure.json"),
			JSON.stringify({
				error: String(error),
				hostMs: performance.now() - began,
			}) + "\n",
			{ flag: "wx" },
		);
		throw error;
	}
}

await main();
