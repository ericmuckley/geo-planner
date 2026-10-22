import assert from "node:assert/strict";
import { mock, test } from "node:test";
import { defaultQuery, resultSchema } from "../lib/reachability";
import { cellContours } from "./coarse-contours";
import { getEstimateConfig, runEstimate } from "./coarse-estimate.server";
import { estimateGrid, type GridData } from "./coarse-grid";

function request(origin = defaultQuery.origin, minutes = 360) {
	return new Request("http://localhost/api/estimate", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ ...defaultQuery, origin, budgetMinutes: minutes }),
	});
}

function fixture(land: number[], width = land.length): GridData {
	const height = land.length / width;
	return {
		bounds: [0, 0, width / 10, height / 10],
		width,
		height,
		step: 0.1,
		localSpeedKph: 25,
		land: Uint8Array.from(land),
		traversable: Uint8Array.from(land),
		links: new Uint8Array(land.length * 4),
		boundary: [
			[
				[
					[0, 0],
					[width / 10, 0],
					[width / 10, height / 10],
					[0, height / 10],
					[0, 0],
				],
			],
		],
		lakes: [],
	};
}

test("coarse search respects water barriers, with crossings only on explicit road links", () => {
	const grid = fixture([1, 0, 1]);
	const origin = { lon: 0.05, lat: 0.05 };
	assert.equal(estimateGrid(grid, origin, 720).labels[2], Infinity);
	grid.traversable[1] = 1;
	grid.links[0] = grid.links[4] = 90;
	const crossed = estimateGrid(grid, origin, 60);
	assert.ok(crossed.labels[2] > 14 && crossed.labels[2] < 15);
	assert.equal(crossed.reachedCells, 2);
	assert.equal(crossed.coordinates.length, 2);
	assert.ok(estimateGrid(grid, { lon: 0.25, lat: 0.05 }, 60).labels[0] < 15);
});

test("higher road speeds reduce costs, longer budgets preserve every reached cell", () => {
	const grid = fixture([1, 1, 1, 1, 1]);
	const origin = { lon: 0.05, lat: 0.05 };
	const local = estimateGrid(grid, origin, 60);
	assert.equal(local.reachedCells, 3);
	for (let i = 0; i < 4; i++) grid.links[i * 4] = 90;
	const fast = estimateGrid(grid, origin, 60);
	assert.equal(fast.reachedCells, 5);
	assert.ok(fast.labels[2] < local.labels[2]);
	const extended = estimateGrid(grid, origin, 120);
	for (let i = 0; i < local.labels.length; i++)
		if (local.labels[i] <= 60) assert.ok(extended.labels[i] <= 60);
});

test("small-island origins stay in their own cell without changing shared data", () => {
	const grid = fixture([0, 0, 0, 1]);
	const original = grid.land.slice();
	const result = estimateGrid(grid, { lon: 0.05, lat: 0.05 }, 720);
	assert.equal(result.reachedCells, 1);
	assert.equal(result.labels[3], Infinity);
	assert.deepEqual(grid.land, original);
	assert.deepEqual(grid.traversable, original);
});

test("cell contours preserve holes and separate diagonally touching islands", () => {
	const donut = cellContours(
		Uint8Array.from([1, 1, 1, 1, 0, 1, 1, 1, 1]),
		3,
		3,
		0,
		0,
		1,
	);
	assert.equal(donut.length, 1);
	assert.equal(donut[0].length, 2);
	const islands = cellContours(Uint8Array.from([1, 0, 0, 1]), 2, 2, 0, 0, 1);
	assert.equal(islands.length, 2);
	for (const polygon of [...donut, ...islands])
		for (const ring of polygon) {
			assert.ok(ring.length >= 4);
			assert.deepEqual(ring[0], ring.at(-1));
		}
});

test("coarse estimates need no network, credential or local worker, including the Vercel environment", async () => {
	const previous = process.env.VERCEL;
	process.env.VERCEL = "1";
	const fetchMock = mock.method(globalThis, "fetch", () => {
		throw new Error("Coarse estimates must not fetch");
	});
	try {
		const config = await (await getEstimateConfig()).json();
		assert.equal(config.provider, "coarse");
		assert.equal(config.health, "ready");
		assert.equal(config.maxMinutes, 720);
		for (const [lat, lon] of [
			[32.7157, -117.1611],
			[47.6062, -122.3321],
			[39.7392, -104.9903],
			[25.7617, -80.1918],
			[40.7128, -74.006],
			[42.3314, -83.0458],
			[24.5551, -81.78],
			[41.2835, -70.0995],
		]) {
			const response = await runEstimate(request({ lat, lon }));
			assert.equal(
				response.status,
				200,
				JSON.stringify(await response.clone().json()),
			);
			const result = resultSchema.parse(await response.json());
			assert.equal(result.metadata.engine, "coarse");
			assert.equal(result.metadata.coverageVerified, false);
			assert.ok(result.metadata.approximation?.reachedCells);
			assert.equal(result.metadata.upstreamBytes, 0);
			assert.ok(result.contours.warnings?.length);
		}
		assert.equal(fetchMock.mock.callCount(), 0);
	} finally {
		fetchMock.mock.restore();
		if (previous === undefined) delete process.env.VERCEL;
		else process.env.VERCEL = previous;
	}
});

test("unsupported origins, horizons and malformed queries produce useful errors", async () => {
	for (const origin of [
		{ lat: 51, lon: 0 },
		{ lat: 21.3, lon: -157.8 },
		{ lat: 44, lon: -87 },
		{ lat: 32, lon: -130 },
	])
		assert.equal((await runEstimate(request(origin))).status, 422);
	for (const minutes of [0, 59, 720.5, 721])
		assert.equal(
			(await runEstimate(request(defaultQuery.origin, minutes))).status,
			422,
		);
	assert.equal(
		(
			await runEstimate(
				new Request("http://localhost", { method: "POST", body: "{" }),
			)
		).status,
		400,
	);
	assert.equal(
		(
			await runEstimate(
				new Request("http://localhost", {
					method: "POST",
					body: "x".repeat(2049),
				}),
			)
		).status,
		400,
	);
});
