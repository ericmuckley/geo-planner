import assert from "node:assert/strict";
import test from "node:test";
import { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import { fixture, words } from "./coarse_osm_packed_fixture_v1.ts";
import {
	PAID_GEOMETRY_FILES,
	type PaidGeometryFiles,
	PaidRoadGeometry,
} from "./coarse_osm_paid_geometry_v1.ts";
import { searchRoadPositions } from "./coarse_osm_paid_positions_v1.ts";
import {
	assertPhaseReleased,
	settledPhaseMemory,
} from "./coarse_osm_phase_lifetime_v1.ts";

test("reference pair phase returns primitive summaries and releases its full queue", async () => {
	const graph = new PackedCarGraph(
		fixture(3, [
			[0, 1, 1000],
			[1, 2, 10],
			[2, 0, 10],
		]),
	);
	const files = Object.fromEntries(
		PAID_GEOMETRY_FILES.map((name) => [name, new Uint8Array()]),
	) as PaidGeometryFiles;
	files["geometry/curve-offsets.u32"] = words([0], 4);
	const geometry = new PaidRoadGeometry(graph, files);
	const baseline = await settledPhaseMemory();
	function pairPhase() {
		const result = searchRoadPositions(
			graph,
			geometry,
			{ canonicalArc: 0, segment: 0, segmentFraction: 0.75 },
			{ canonicalArc: 0, segment: 0, segmentFraction: 0.25 },
		);
		return {
			ticks: result.ticks,
			settles: result.settles,
			searchBufferBytes: result.searchBufferBytes,
		};
	}
	const first = pairPhase();
	assert.equal(first.ticks, 520);
	assert.equal(first.searchBufferBytes, 8000012);
	await assertPhaseReleased(
		baseline.arrayBuffers,
		"first actual reference phase",
	);
	const second = pairPhase();
	assert.deepEqual(second, first);
	await assertPhaseReleased(
		baseline.arrayBuffers,
		"second actual reference phase",
	);
});
