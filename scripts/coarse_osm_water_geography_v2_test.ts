import assert from "node:assert/strict";
import test from "node:test";
import { landConnection } from "../src/server/coarse-geography.ts";
import { prepareWaterGeographyV2 } from "./coarse_osm_water_geography_v2.ts";
import type {
	loadWaterRaster,
	RasterCoordinate,
} from "./coarse_osm_water_raster_loader_v1.ts";

const rectangle = (x1: number, y1: number, x2: number, y2: number) => [
	[x1, y1],
	[x2, y1],
	[x2, y2],
	[x1, y2],
	[x1, y1],
];
const source = () => ({
	boundary: [[rectangle(-3, -3, 3, 3)]],
	lakes: [[rectangle(-0.5, -0.5, 0.5, 0.5)]],
});
type Packet = Pick<
	Awaited<ReturnType<typeof loadWaterRaster>>,
	"grid" | "lookup" | "sourceIncompleteFeatures"
>;
function packet(
	wet: (x: number, y: number) => boolean,
	uncertain: (x: number, y: number) => boolean = () => false,
): Packet {
	const grid = {
		xE7: -20000000,
		yE7: -20000000,
		stepE7: 10000000,
		columns: 4,
		rows: 4,
		cells: 16,
		bitOrder: "row-major-lsb-first" as const,
	};
	return {
		grid,
		sourceIncompleteFeatures: [],
		lookup: (xy: RasterCoordinate) => {
			const column = Math.floor(xy[0] + 2),
				row = Math.floor(xy[1] + 2),
				status = {
					sourceGeometryCompletelyBounded: true,
					sourceIncompleteFeatureCount: 0,
				};
			if (column < 0 || row < 0 || column >= 4 || row >= 4)
				return { kind: "outside-grid", ...status };
			return {
				kind: "cell",
				column,
				row,
				waterAtCenter: wet(column, row),
				sourceUncertainty: uncertain(column, row),
				centerE7: [
					-20000000 + (column + 0.5) * 10000000,
					-20000000 + (row + 0.5) * 10000000,
				],
				...status,
			};
		},
	};
}

test("unflagged finer data replaces coarse lake assumptions, uncertainty retains fallback", () => {
	const geo = source(),
		fine = prepareWaterGeographyV2(
			geo,
			packet(() => false),
		),
		fallback = prepareWaterGeographyV2(
			geo,
			packet(
				() => false,
				() => true,
			),
		);
	assert.equal(landConnection(geo, [0, 0], [0, 0]), false);
	assert.equal(fine.contains([0, 0]), true);
	assert.equal(fallback.contains([0, 0]), false);
	assert.equal(fine.contains([4, 0]), false);
	assert.equal(fine.contains([2.5, 0]), true);
});

test("every raster crossing checked when dry endpoints span interior water", () => {
	const policy = prepareWaterGeographyV2(
		source(),
		packet((column) => column === 2),
	);
	assert.equal(policy.contains([-1.5, 1.5]), true);
	assert.equal(policy.contains([1.5, 1.5]), true);
	assert.equal(policy.landConnection([-1.5, 1.5], [1.5, 1.5]), false);
	assert.equal(policy.landConnection([-1.5, 1.5], [-0.5, 1.5]), true);
});

test("diagonal/reverse/vertical paths preserve blocking and free paths", () => {
	const policy = prepareWaterGeographyV2(
		source(),
		packet((x, y) => x === 2 && y === 2),
	);
	assert.equal(policy.landConnection([-1.5, -1.5], [1.5, 1.5]), false);
	assert.equal(policy.landConnection([1.5, 1.5], [-1.5, -1.5]), false);
	assert.equal(policy.landConnection([0.5, -1.5], [0.5, 1.5]), false);
	assert.equal(policy.landConnection([-1.5, -1.5], [-1.5, 1.5]), true);
});

test("water prefix may be tolerated only before reaching land", () => {
	const policy = prepareWaterGeographyV2(
		source(),
		packet((x) => x === 2),
	);
	assert.equal(policy.landConnection([0.1, 1.5], [1.5, 1.5]), false);
	assert.equal(policy.landConnection([0.1, 1.5], [1.5, 1.5], 0.65), true);
	assert.equal(policy.landConnection([0.1, 1.5], [1.5, 1.5], 0.6), false);
	assert.equal(policy.landConnection([-1.5, 1.5], [1.5, 1.5], 1), false);
	assert.equal(policy.landConnection([-1.5, 1.5], [0.5, 1.5], 1), false);
});

test("uncertain cells retain narrow coarse-lake cuts and original results", () => {
	const geo = source(),
		policy = prepareWaterGeographyV2(
			geo,
			packet(
				() => false,
				() => true,
			),
		);
	for (let y = -1; y <= 1; y += 0.25) {
		for (const [a, b] of [
			[
				[-2, y],
				[2, y],
			],
			[
				[2, y],
				[-2, y],
			],
			[
				[-1, y],
				[-0.75, y],
			],
		] as const)
			assert.equal(
				policy.landConnection(a, b),
				landConnection(geo, [...a], [...b]),
			);
	}
});

test("country holes and disconnected land remain barriers with fine dry data", () => {
	const geo = {
		boundary: [
			[rectangle(-2, -2, 2, 2), rectangle(-0.2, -0.2, 0.2, 0.2)],
			[rectangle(2.2, -1, 2.8, 1)],
		],
		lakes: [],
	};
	const policy = prepareWaterGeographyV2(
		geo,
		packet(() => false),
	);
	assert.equal(policy.contains([0, 0]), false);
	assert.equal(policy.landConnection([-1, 0], [1, 0]), false);
	assert.equal(policy.landConnection([1.5, 0.5], [2.5, 0.5]), false);
});

test("zero-length and invalid coordinate/prefix domains are explicit", () => {
	const policy = prepareWaterGeographyV2(
		source(),
		packet(() => false),
	);
	assert.equal(policy.landConnection([0.1, 0.1], [0.1, 0.1]), true);
	assert.throws(() => policy.contains([NaN, 0]));
	assert.throws(() => policy.contains([181, 0]));
	for (const prefix of [-1, 2, Infinity])
		assert.throws(() => policy.landConnection([0, 0], [1, 1], prefix));
});
