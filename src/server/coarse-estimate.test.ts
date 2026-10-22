import assert from "node:assert/strict";
import { mock, test } from "node:test";
import { defaultQuery, resultSchema } from "../lib/reachability";
import { cellContours, containsPolygon } from "./coarse-contours";
import { decodeGrid } from "./coarse-data.server";
import { getEstimateConfig, runEstimate } from "./coarse-estimate.server";
import { landConnection } from "./coarse-geography";
import {
	attachGrid,
	distanceKm,
	estimateGrid,
	type GridData,
	gridAttachments,
	gridPosition,
} from "./coarse-grid";
import v2 from "./data/coarse-grid-v2.json";
import data from "./data/coarse-grid-v4.json";

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

test("geometry times and consistent road positions charge origin access and road transfers", () => {
	const grid = fixture([1, 0, 1]);
	grid.traversable[1] = 1;
	grid.links[0] = grid.links[4] = 105;
	grid.roadDeciseconds = new Uint16Array(12);
	grid.roadDeciseconds[0] = 6000;
	grid.roadDeciseconds[4] = 7200;
	grid.anchorOffsets = new Int16Array([1000, 0, 0, 0, -1000, 0]);
	const origin = { lon: 0.05, lat: 0.05 };
	const initial =
		(distanceKm([origin.lon, origin.lat], gridPosition(grid, 0)) / 25) * 60;
	const field = estimateGrid(grid, origin, 60);
	assert.ok(Math.abs(field.labels[2] - initial - 22) < 1e-9);
	assert.equal(estimateGrid(grid, origin, 20).labels[2], Infinity);
	const reverse = estimateGrid(grid, { lon: 0.24, lat: 0.05 }, 60);
	assert.ok(Math.abs(reverse.labels[0] - 22) < 1e-9);
});

test("road-supported shore shading grants no general travel across water", () => {
	const grid = fixture([1, 0, 0, 1]);
	grid.displayLand = Uint8Array.from([1, 1, 0, 1]);
	grid.traversable[1] = 1;
	grid.links[0] = 90;
	const result = estimateGrid(grid, { lon: 0.05, lat: 0.05 }, 60);
	assert.equal(result.reachedCells, 2);
	assert.equal(result.labels[3], Infinity);
	assert.deepEqual([...grid.land], [1, 0, 0, 1]);
});

test("bundled geometry steps cannot teleport, and Calexico's reachable road cell is shaded", () => {
	const grid = decodeGrid(data);
	const times = grid.roadDeciseconds;
	assert.ok(times);
	let checked = 0;
	for (let cell = 0; cell < grid.land.length; cell++) {
		for (const [direction, delta] of [
			1,
			grid.width + 1,
			grid.width,
			grid.width - 1,
		].entries()) {
			const key = cell * 4 + direction;
			if (!grid.links[key]) continue;
			assert.ok(times[key] > 0);
			const minimum =
				(distanceKm(
					gridPosition(grid, cell),
					gridPosition(grid, cell + delta),
				) /
					grid.links[key]) *
				60;
			assert.ok(
				times[key] / 600 + 1e-7 >= minimum,
				`Impossible road step ${key}`,
			);
			checked++;
		}
	}
	assert.equal(checked, data.roadLinks);
	const calexico =
		Math.floor((32.6789 - grid.bounds[1]) / grid.step) * grid.width +
		Math.floor((-115.4989 - grid.bounds[0]) / grid.step);
	const field = estimateGrid(grid, defaultQuery.origin, 360);
	assert.equal(grid.land[calexico], 0);
	assert.equal(grid.displayLand?.[calexico], 1);
	assert.ok(field.labels[calexico] < 360);
	assert.ok(
		field.coordinates.some((polygon) =>
			containsPolygon([-115.4989, 32.6789], polygon),
		),
	);
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

test("shore links allow bidirectional land-supported travel without enabling open-water neighbors", () => {
	const grid = fixture([1, 0, 0, 1]);
	grid.shoreLinks = Uint8Array.from([1, 0, 0, 0]);
	grid.displayLand = Uint8Array.from([1, 1, 0, 1]);
	grid.traversable[1] = 1;
	const before = grid.land.slice();
	const forward = estimateGrid(grid, { lon: 0.05, lat: 0.05 }, 720);
	const reverse = estimateGrid(grid, { lon: 0.15, lat: 0.05 }, 720);
	assert.ok(forward.labels[1] > 26 && forward.labels[1] < 27);
	assert.ok(Math.abs(forward.labels[1] - reverse.labels[0]) < 1e-8);
	assert.equal(forward.labels[3], Infinity);
	assert.deepEqual(grid.land, before);
});

test("land connections reject narrow channels, diagonal island contact and water after initial shore tolerance", () => {
	const grid = fixture([1, 1, 1]);
	const rectangle = (west: number, east: number, south = 0, north = 0.1) => [
		[
			[west, south],
			[east, south],
			[east, north],
			[west, north],
			[west, south],
		],
	];
	grid.lakes = [rectangle(0.1499, 0.1501)];
	assert.equal(landConnection(grid, [0.05, 0.05], [0.25, 0.05]), false);
	assert.equal(landConnection(grid, [0.15, 0.05], [0.25, 0.05], 0.1), true);
	grid.lakes.push(rectangle(0.2, 0.201));
	assert.equal(landConnection(grid, [0.15, 0.05], [0.25, 0.05], 0.1), false);
	grid.boundary = [rectangle(0, 0.1, 0, 0.1), rectangle(0.1, 0.2, 0.1, 0.2)];
	grid.lakes = [];
	assert.equal(landConnection(grid, [0.05, 0.05], [0.15, 0.15]), false);
});

test("an island sharing a grid cell with mainland cannot attach across its channel", () => {
	const grid = fixture([1, 0, 0]);
	grid.boundary = [
		[
			[
				[0, 0],
				[0.11, 0],
				[0.11, 0.1],
				[0, 0.1],
				[0, 0],
			],
		],
		[
			[
				[0.13, 0.04],
				[0.14, 0.04],
				[0.14, 0.06],
				[0.13, 0.06],
				[0.13, 0.04],
			],
		],
	];
	grid.shoreLinks = new Uint8Array(3);
	grid.traversable[1] = 1;
	grid.displayLand = Uint8Array.from([1, 1, 0]);
	grid.anchorOffsets = new Int16Array([0, 0, -4500, 0, 0, 0]);
	const origin = { lon: 0.135, lat: 0.05 };
	assert.equal(attachGrid(grid, origin), undefined);
	const field = estimateGrid(grid, origin, 720);
	assert.equal(field.reachedCells, 1);
	assert.equal(field.labels[0], Infinity);
	// An explicit retained-road access path can connect this island; an unrelated
	// island still cannot reach that road port across open water.
	grid.roadAccess = [[1, 0.135, 0.05, 3]];
	assert.deepEqual(attachGrid(grid, origin), {
		cell: 1,
		distanceKm: 3,
		minutes: (3 / 25) * 60,
	});
	grid.boundary.push([
		[
			[0.17, 0.04],
			[0.18, 0.04],
			[0.18, 0.06],
			[0.17, 0.06],
			[0.17, 0.04],
		],
	]);
	assert.equal(attachGrid(grid, { lon: 0.175, lat: 0.05 }), undefined);
});

test("nationwide shore links stay on continuous land, preserve road costs and restore shore arrival", () => {
	const grid = decodeGrid(data);
	assert.equal(data.land, v2.land);
	assert.equal(data.links, v2.links);
	assert.equal(data.roadDeciseconds, v2.roadDeciseconds);
	assert.deepEqual(data.roadSpeedsKph, v2.roadSpeedsKph);
	let count = 0;
	for (let cell = 0; cell < grid.land.length; cell++)
		for (const [d, delta] of [
			1,
			grid.width + 1,
			grid.width,
			grid.width - 1,
		].entries()) {
			if (!((grid.shoreLinks?.[cell] ?? 0) & (1 << d))) continue;
			assert.ok(
				landConnection(
					grid,
					gridPosition(grid, cell),
					gridPosition(grid, cell + delta),
				),
				`Water-crossing shore link ${cell}/${d}`,
			);
			count++;
		}
	assert.equal(count, data.shoreLocalLinks);
	for (const [cell, lon, lat, km] of data.roadAccess) {
		assert.ok(landConnection(grid, [lon, lat], [lon, lat]));
		assert.ok(km + 1e-6 >= distanceKm([lon, lat], gridPosition(grid, cell)));
	}
	const origin = { lat: 33.2986, lon: -115.9561 },
		destination = { lat: 33.3503, lon: -115.7297 };
	const targets = gridAttachments(grid, destination),
		starts = gridAttachments(grid, origin);
	assert.ok(targets.length && starts.length);
	assert.equal(
		landConnection(
			grid,
			[origin.lon, origin.lat],
			[destination.lon, destination.lat],
		),
		false,
	);
	const destinationCell =
		Math.floor((destination.lat - grid.bounds[1]) / grid.step) * grid.width +
		Math.floor((destination.lon - grid.bounds[0]) / grid.step);
	for (const budget of [360, 720]) {
		const forward = estimateGrid(grid, origin, budget),
			reverse = estimateGrid(grid, destination, budget);
		const outbound = Math.min(
			...targets.map((target) => forward.labels[target.cell] + target.minutes),
		);
		const inbound = Math.min(
			...starts.map((start) => reverse.labels[start.cell] + start.minutes),
		);
		assert.ok(outbound < budget && outbound > 0);
		assert.ok(Math.abs(outbound - inbound) < 1e-8);
		assert.ok(forward.labels[destinationCell] < budget);
		assert.ok(
			forward.coordinates.some((poly) =>
				containsPolygon([destination.lon, destination.lat], poly),
			),
		);
	}
});

test("fallback seeds retain a road connection when the nearest land representative is isolated", () => {
	const grid = fixture([1, 0, 0]);
	grid.boundary = [
		[
			[
				[0, 0],
				[0.11, 0],
				[0.11, 0.1],
				[0, 0.1],
				[0, 0],
			],
		],
		[
			[
				[0.13, 0],
				[0.3, 0],
				[0.3, 0.1],
				[0.13, 0.1],
				[0.13, 0],
			],
		],
	];
	grid.shoreLinks = new Uint8Array(3);
	grid.traversable.fill(1);
	grid.displayLand = Uint8Array.from([1, 1, 1]);
	grid.anchorOffsets = new Int16Array([0, 0, -4500, 0, 0, 0]);
	grid.roadAccess = [[1, 0.135, 0.05, 15]];
	grid.links[0] = 90;
	const origin = { lon: 0.135, lat: 0.05 };
	const attachments = gridAttachments(grid, origin);
	assert.equal(attachments[0].cell, 2);
	assert.ok(attachments.some((a) => a.cell === 1));
	assert.ok(estimateGrid(grid, origin, 60).labels[0] < 60);
});

test("geography-checked attachment preserves road-connected island origins", () => {
	const grid = decodeGrid(data);
	for (const origin of [
		{ lat: 40.7128, lon: -74.006 },
		{ lat: 24.5551, lon: -81.78 },
	]) {
		assert.ok(attachGrid(grid, origin));
		assert.ok(estimateGrid(grid, origin, 360).reachedCells > 100);
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
