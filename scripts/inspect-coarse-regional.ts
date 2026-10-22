import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { containsPolygon } from "../src/server/coarse-contours";
import { decodeGrid } from "../src/server/coarse-data.server";
import { distanceKm, gridPosition } from "../src/server/coarse-grid";

const report = JSON.parse(
	await readFile(
		"docs/evidence/coarse-regional-2026-10-22/comparison.json",
		"utf8",
	),
);
const raw = JSON.parse(
	await readFile("src/server/data/coarse-grid-v2.json", "utf8"),
);
const grid = decodeGrid(raw);
type Sample = {
	id: string;
	origin: { lat: number; lon: number };
	destination: { lat: number; lon: number };
	referenceMinutes: number;
	baseline: {
		cellMinutes: number | null;
		originAccessMinutes: number;
		destinationAccessMinutes: number;
		pointMinutes: number | null;
	};
	candidate: {
		cellMinutes: number | null;
		originAccessMinutes: number;
		destinationAccessMinutes: number;
		pointMinutes: number | null;
	};
};
const samples = report.samples as Sample[];

function inspect(point: { lat: number; lon: number }) {
	const x = Math.floor((point.lon - grid.bounds[0]) / grid.step),
		y = Math.floor((point.lat - grid.bounds[1]) / grid.step);
	const cell = y * grid.width + x,
		neighbors = [];
	for (let dy = -1; dy <= 1; dy++)
		for (let dx = -1; dx <= 1; dx++) {
			const i = cell + dy * grid.width + dx;
			const links = [];
			for (const [direction, delta] of [
				1,
				grid.width + 1,
				grid.width,
				grid.width - 1,
				-1,
				-grid.width - 1,
				-grid.width,
				-grid.width + 1,
			].entries()) {
				const key =
					direction < 4 ? i * 4 + direction : (i + delta) * 4 + direction - 4;
				if (grid.links[key])
					links.push({ direction, speedKph: grid.links[key] });
			}
			neighbors.push({
				dx,
				dy,
				cell: i,
				land: !!grid.land[i],
				traversable: !!grid.traversable[i],
				display: !!grid.displayLand?.[i],
				roadLinks: links,
			});
		}
	return {
		point,
		cell,
		node: gridPosition(grid, cell),
		nodeAccessKm: distanceKm([point.lon, point.lat], gridPosition(grid, cell)),
		inputInGeneralizedLake: grid.lakes.some((p) =>
			containsPolygon([point.lon, point.lat], p),
		),
		land: !!grid.land[cell],
		traversable: !!grid.traversable[cell],
		display: !!grid.displayLand?.[cell],
		neighbors,
	};
}

const missing = samples.find((s) => s.id === "salton-city--bombay-beach");
const mountain = samples.find((s) => s.id === "palm-springs--idyllwild");
const bigBear = samples.find((s) => s.id === "bakersfield--big-bear-lake");
assert.ok(missing && mountain && bigBear);
assert.equal(missing.candidate.cellMinutes, null);
const missingCell = inspect(missing.destination);
assert.equal(missingCell.traversable, false);
assert.ok(
	missingCell.neighbors
		.filter((n) => n.dx === 0 && n.dy === 0)
		.every((n) => n.roadLinks.length === 0),
);

function decomposition(sample: Sample) {
	const model = (value: typeof sample.candidate) => ({
		originAccessMinutes: value.originAccessMinutes,
		intercellMinutes:
			value.cellMinutes === null
				? null
				: value.cellMinutes - value.originAccessMinutes,
		destinationAccessMinutes: value.destinationAccessMinutes,
		pointMinutes: value.pointMinutes,
	});
	return {
		route: sample.id,
		referenceMinutes: sample.referenceMinutes,
		baseline: model(sample.baseline),
		candidate: model(sample.candidate),
	};
}

console.log(
	JSON.stringify(
		{
			missingDestination: {
				route: missing.id,
				referenceMinutes: missing.referenceMinutes,
				cell: missingCell,
				interpretation:
					"The destination's center is lake, with no retained road link and no display eligibility. The input lies in the generalized lake but is accepted as an origin within the existing shore tolerance. Query-local seed activation explains why the reverse direction can leave this cell while arrival from another origin is blocked. The local reference snaps to a road within 9 m; generalized lake membership is not actual water truth.",
			},
			mountainRegression: {
				...decomposition(mountain),
				origin: inspect(mountain.origin),
				destination: inspect(mountain.destination),
				interpretation:
					"V2 representatives add endpoint access and change the intercell distance. This decomposition does not isolate all geometry/transfer effects or prove the overland path is realistic. Do not fix it with a global speed increase.",
			},
			largestMountainDifference: {
				...decomposition(bigBear),
				destination: inspect(bigBear.destination),
				interpretation:
					"No retained road reaches the destination cell or its eight neighbors. Local overland fallback therefore substitutes for real road access near Big Bear. This supports a missing-road/access investigation, not an assertion that the reference route is ground truth.",
			},
			nextCorrection:
				"Represent land-supported shore cells symmetrically for arrival and departure, with access connections that cannot bridge open water or move isolated islands to the mainland. Preserve v2 and both comparison sets, version a candidate separately, and keep the current class speeds while isolating this correction.",
			remainingQueue: [
				"Investigate representative-position access detours in the four regressed mountain cases.",
				"Investigate missing generalized road coverage near Big Bear and the east Salton Sea shore before further speed fitting.",
			],
			publicRoutingApiCalls: 0,
			localServiceRequests: 0,
		},
		null,
		2,
	),
);
