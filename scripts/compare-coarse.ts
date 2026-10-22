import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { defaultQuery } from "../src/lib/reachability";
import { estimateGrid } from "../src/server/coarse-grid";

const data = JSON.parse(
	await readFile("src/server/data/coarse-grid-v1.json", "utf8"),
);
const grid = {
	...data,
	land: new Uint8Array(Buffer.from(data.land, "base64")),
	traversable: new Uint8Array(Buffer.from(data.traversable, "base64")),
	links: new Uint8Array(Buffer.from(data.links, "base64")),
};
const origin = defaultQuery.origin;
const estimate = estimateGrid(grid, origin, 720);
// Fixed loopback reference only: never consume a hosted routing service's quota.
const referenceUrl = "http://127.0.0.1:8002";
const statusResponse = await fetch(`${referenceUrl}/status`, {
	signal: AbortSignal.timeout(5_000),
});
assert.ok(statusResponse.ok, "Local Valhalla reference must be running");
const referenceStatus = await statusResponse.json();
const samples = [];
for (const [name, lat, lon] of [
	["Los Angeles", 34.0522, -118.2437],
	["Riverside", 33.9533, -117.3962],
	["Palm Springs", 33.8303, -116.5453],
	["Santa Barbara", 34.4208, -119.6982],
	["Bakersfield", 35.3733, -119.0187],
	["Big Bear Lake", 34.2439, -116.9114],
	["Idyllwild", 33.74, -116.7189],
	["Borrego Springs", 33.2559, -116.375],
	["Temecula", 33.4936, -117.1484],
	["Calexico", 32.6789, -115.4989],
	["Julian", 33.0787, -116.602],
] as const) {
	const request = {
		locations: [origin, { lat, lon }],
		costing: "auto",
		costing_options: { auto: { speed_types: ["freeflow", "constrained"] } },
		directions_options: { units: "kilometers" },
	};
	const response = await fetch(`${referenceUrl}/route`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(request),
		signal: AbortSignal.timeout(20_000),
	});
	assert.ok(
		response.ok,
		`Local reference failed for ${name}: HTTP ${response.status}`,
	);
	const reference = await response.json();
	const cell =
		Math.floor((lat - grid.bounds[1]) / grid.step) * grid.width +
		Math.floor((lon - grid.bounds[0]) / grid.step);
	const coarseCellMinutes = Number.isFinite(estimate.labels[cell])
		? estimate.labels[cell]
		: null;
	const referenceMinutes = reference.trip?.summary?.time / 60;
	assert.ok(
		Number.isFinite(referenceMinutes) && referenceMinutes > 0,
		`Missing reference time for ${name}`,
	);
	samples.push({
		name,
		destination: { lat, lon },
		coarseCellMinutes,
		coarseLandCell: !!grid.land[cell],
		referenceMinutes,
		referenceKm: reference.trip.summary.length,
		deltaMinutes:
			coarseCellMinutes === null ? null : coarseCellMinutes - referenceMinutes,
		ratio:
			coarseCellMinutes === null ? null : coarseCellMinutes / referenceMinutes,
		request,
		reference,
	});
}
const deltas = samples.flatMap((sample) =>
	sample.deltaMinutes === null ? [] : [sample.deltaMinutes],
);
console.log(
	JSON.stringify(
		{
			model: data.version,
			origin,
			referenceStatus,
			samples,
			summary: {
				routeCases: samples.length,
				finiteCellCosts: deltas.length,
				unshadedDestinationCells: samples.filter(
					(sample) => !sample.coarseLandCell,
				).length,
				meanAbsoluteDifferenceMinutes:
					deltas.reduce((sum, value) => sum + Math.abs(value), 0) /
					deltas.length,
				minimumDeltaMinutes: Math.min(...deltas),
				maximumDeltaMinutes: Math.max(...deltas),
			},
			publicRoutingApiCalls: 0,
			scope:
				"Regional static Valhalla route-model comparison, not real-world ETA ground truth or national accuracy validation. Coarse cost is arrival at a destination cell center, with origin attachment and no exact destination access. A successful command proves the comparison ran; it is not an accuracy pass.",
		},
		null,
		2,
	),
);
