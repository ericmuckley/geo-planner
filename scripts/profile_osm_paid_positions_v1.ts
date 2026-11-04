/** Fixed host software qualification; no provider-accuracy evaluation. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { loadPackedCar } from "./coarse_osm_packed_loader_v1.ts";
import { searchPackedCar } from "./coarse_osm_packed_search_v1.ts";
import { loadPaidGeometry } from "./coarse_osm_paid_geometry_loader_v1.ts";
import {
	type RoadPosition,
	resolveRoadPosition,
	searchRoadPositions,
} from "./coarse_osm_paid_positions_v1.ts";

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
		"data/coarse-quality/us-osm-car-paid-positions-profile-v1",
	);
	assert.equal(plan.coreSource, "data/coarse-quality/us-osm-car-wire-codec-v1");
	assert.equal(
		plan.geometrySource,
		"data/coarse-quality/us-osm-car-paid-geometry-codec-v1",
	);
	assert.equal(plan.seed, 20261104);
	assert.equal(plan.draws, 32);
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
			"Paid-position host deadline",
		);
	try {
		global.gc();
		const baseline = process.memoryUsage();
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
		let state = plan.seed;
		const rows = [];
		for (let draw = 0; draw < plan.draws; draw++) {
			check();
			state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
			const selectedArc = Math.floor((state / 2 ** 32) * core.graph.arcs);
			const arc = paid.geometry.canonicalArc(selectedArc);
			let points = 0;
			paid.geometry.visitPoints(arc, () => {
				points++;
			});
			const position = (fraction: number): RoadPosition => {
				const rank = fraction * (points - 1);
				const segment = Math.min(points - 2, Math.floor(rank));
				return { canonicalArc: arc, segment, segmentFraction: rank - segment };
			};
			const tail = core.graph.arcTail(arc);
			const head = core.graph.arcTarget(arc);
			const checks = [];
			for (const forward of [true, false]) {
				const start = performance.now();
				const endpointReference = searchPackedCar(
					core.graph,
					{ vertex: forward ? tail : head },
					{ vertex: forward ? head : tail },
					{ check },
				);
				const endpoint = searchRoadPositions(
					core.graph,
					paid.geometry,
					position(forward ? 0 : 1),
					position(forward ? 1 : 0),
					{ check },
				);
				assert.equal(endpoint.ticks, endpointReference.ticks);
				const from = position(forward ? 0.25 : 0.75);
				const to = position(forward ? 0.75 : 0.25);
				const locatedFrom = resolveRoadPosition(
					core.graph,
					paid.geometry,
					from,
				);
				const locatedTo = resolveRoadPosition(core.graph, paid.geometry, to);
				assert.ok(
					"partials" in locatedFrom.source && "partials" in locatedTo.target,
				);
				assert.ok(locatedFrom.source.partials.every((part) => part.ticks > 0));
				assert.ok(locatedTo.target.partials.every((part) => part.ticks > 0));
				const interior = searchRoadPositions(
					core.graph,
					paid.geometry,
					from,
					to,
					{ check },
				);
				if (forward)
					assert.ok(
						interior.ticks !== null &&
							interior.ticks > 0 &&
							interior.ticks <= core.graph.arcCostTicks(arc),
					);
				if (interior.ticks !== null) assert.ok(interior.ticks > 0);
				global.gc();
				checks.push({
					forward,
					from,
					to,
					endpointReference,
					endpoint,
					interior,
					hostMsIncludingGc: performance.now() - start,
				});
			}
			rows.push({
				draw,
				selectedArc,
				canonicalArc: arc,
				tail,
				head,
				points,
				checks,
			});
		}
		const original = JSON.parse(
			(await readFile(path.join(repo, plan.queryReference))).toString("utf8"),
		);
		const originalQueries = [];
		for (const value of original.queries) {
			const result = searchPackedCar(
				core.graph,
				{ vertex: value.sourceVertex },
				{ vertex: value.targetVertex },
				{ check },
			);
			assert.equal(result.ticks, value.ticks);
			originalQueries.push({ ...value, ...result });
			global.gc();
		}
		assert.equal(originalQueries.length, 4);
		global.gc();
		const report = {
			status: "host_national_paid_position_software_checks_passed",
			recipeSha256: pin,
			draws: 32,
			endpointComparisons: 64,
			interiorQueries: 64,
			rows,
			originalQueries,
			retainedDataBackingBufferBytes:
				core.retainedDataBackingBufferBytes +
				paid.retainedDataBackingBufferBytes,
			baseline,
			retainedAfterLoad,
			afterQueries: process.memoryUsage(),
			hostTotalMs: performance.now() - began,
			scope:
				"Host software checks on fixed unfiltered seeded physical arcs, both directions; exact original full endpoint/core query preservation and paid internal states. No connectors/shore, provider accuracy, full reachability/display/app/packaged estimate, protected Linux or Vercel admission.",
			modelChanged: false,
		};
		await writeFile(
			path.join(root, "report.json"),
			`${JSON.stringify(report, null, 2)}\n`,
			{ flag: "wx" },
		);
		process.stdout.write(
			`${JSON.stringify({ status: report.status, draws: 32, endpointComparisons: 64, interiorQueries: 64, hostTotalMs: report.hostTotalMs })}\n`,
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
