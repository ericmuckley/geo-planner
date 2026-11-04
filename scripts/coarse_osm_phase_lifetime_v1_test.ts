import assert from "node:assert/strict";
import test from "node:test";
import { MinQueue } from "./coarse_osm_min_queue_v1.ts";
import { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import { fixture, words } from "./coarse_osm_packed_fixture_v1.ts";
import {
	PAID_GEOMETRY_FILES,
	type PaidGeometryFiles,
	PaidRoadGeometry,
} from "./coarse_osm_paid_geometry_v1.ts";
import {
	assertPhaseReleased,
	settledPhaseMemory,
} from "./coarse_osm_phase_lifetime_v1.ts";
import { computeRoadField } from "./coarse_osm_road_field_v1.ts";

test("country-sized synthetic field/queue buffers release across a function boundary", async () => {
	const baseline = await settledPhaseMemory();
	function phase() {
		const labels = new Uint32Array(9620680).fill(0xffffffff);
		const vertices = new Uint16Array(5731903).fill(65535);
		const queue = new MinQueue(1000000);
		queue.push(1, 2);
		queue.pop();
		let count = 0;
		for (const label of labels) if (label < 0x80000000) count++;
		for (const vertex of vertices) if (vertex !== 65535) count++;
		return {
			count,
			peak: queue.peak,
			viewBytes: labels.byteLength + vertices.byteLength,
		};
	}
	assert.deepEqual(phase(), { count: 0, peak: 1, viewBytes: 49946526 });
	await assertPhaseReleased(baseline.arrayBuffers, "synthetic field");
});

test("same strict release guard rejects deliberately retained backing buffers", async () => {
	const baseline = await settledPhaseMemory();
	const holder: { current: Uint32Array | null } = {
		current: new Uint32Array(2000000),
	};
	await assert.rejects(
		assertPhaseReleased(baseline.arrayBuffers, "retained negative control"),
		/retained backing buffers/,
	);
	assert.equal(holder.current?.byteLength, 8000000);
	holder.current = null;
	await assertPhaseReleased(baseline.arrayBuffers, "negative control released");
});

test("actual tiny field returns only summary values before reference work", async () => {
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
	function phase() {
		const field = computeRoadField(
			graph,
			geometry,
			{ canonicalArc: 0, segment: 0, segmentFraction: 0.75 },
			0,
			{ maxTicks: 500 },
		);
		return {
			stats: { ...field.stats },
			shadows: field.partials.map((seed) => ({ ...seed })),
		};
	}
	const summary = phase();
	assert.equal(summary.stats.settles, 3);
	assert.equal(summary.shadows[0].regularEntryTicks, 270);
	await assertPhaseReleased(baseline.arrayBuffers, "actual tiny field");
});
