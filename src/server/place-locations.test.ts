import assert from "node:assert/strict";
import test from "node:test";
import { gridWidth, pixelLocation } from "../lib/area-layers";
import {
	type PlaceLocations,
	parsePlaceCatalog,
	placeLocationsInArea,
	placeTerrainFilter,
} from "../lib/place-locations";
import { contoursSchema } from "../lib/reachability";

const square = [
	[-120, 30],
	[-116, 30],
	[-116, 34],
	[-120, 34],
	[-120, 30],
];
const hole = [
	[-119, 31],
	[-118, 31],
	[-118, 32],
	[-119, 32],
	[-119, 31],
];
const metadata = {
	version: 1,
	sourceDate: "2026-10-25",
	sourceSha256: "0".repeat(64),
};
const stations = [
	[-119.5, 32, "A station", "n1"],
	[-118.5, 31.5, "In the hole", "w2"],
	[-108, 38, "Elsewhere", "n3"],
	[-113.5, 34.5, "", "w4"],
];

test("place locations match the displayed area across separate polygons and holes", () => {
	const contours = contoursSchema.parse({
		type: "FeatureCollection",
		features: [
			{
				type: "Feature",
				properties: null,
				geometry: {
					type: "MultiPolygon",
					coordinates: [
						[square, hole],
						[
							[
								[-114, 34],
								[-113, 34],
								[-113, 35],
								[-114, 35],
								[-114, 34],
							],
						],
					],
				},
			},
		],
	});
	const layers = [
		["fuel", { ...metadata, stations }, "Unnamed fuel stop"],
		["trailheads", { ...metadata, places: stations }, "Unnamed trailhead"],
		["campgrounds", { ...metadata, places: stations }, "Unnamed campground"],
	] as const;
	for (const [kind, data, unnamed] of layers) {
		const { features } = placeLocationsInArea(
			kind,
			parsePlaceCatalog(kind, data),
			contours,
		);
		assert.deepEqual(
			features.map((feature) => feature.id),
			["n1", "w4"],
		);
		assert.equal(features[1].properties.name, unnamed);
	}
});

test("place catalogs reject malformed source metadata and coordinates", () => {
	assert.throws(() =>
		parsePlaceCatalog("trailheads", {
			...metadata,
			places: [[32, -117, "Swapped longitude and latitude", "n1"]],
		}),
	);
	assert.throws(() =>
		parsePlaceCatalog("campgrounds", {
			...metadata,
			version: 2,
			places: stations,
		}),
	);
});

test("outdoor filters combine the same grid cell, preserve exact cutoff, and exclude missing data", () => {
	const land = Uint16Array.of(1, 1, 0, 1);
	const elevation = Uint16Array.of(32768 + 1524, 32768 + 1523, 32768 + 1820, 0);
	const locations: PlaceLocations = {
		type: "FeatureCollection",
		features: [0, 1, 2, 3, gridWidth].map((column) => ({
			type: "Feature",
			id: column,
			geometry: {
				type: "Point",
				coordinates: pixelLocation(column + 0.5, 0.5),
			},
			properties: { name: `Test point ${column}` },
		})),
	};
	const matches = (
		filter: NonNullable<ReturnType<typeof placeTerrainFilter>>,
	) => filter(locations).features.map(({ id }) => id);
	const cutoff = { grid: elevation, minimumFeet: 5000 };
	const landOnly = placeTerrainFilter(land);
	const elevationOnly = placeTerrainFilter(undefined, cutoff);
	const combined = placeTerrainFilter(land, cutoff);
	assert.ok(landOnly && elevationOnly && combined);
	assert.deepEqual(matches(landOnly), [0, 1, 3]);
	assert.deepEqual(matches(elevationOnly), [0, 2]);
	assert.deepEqual(matches(combined), [0]);
	assert.equal(placeTerrainFilter(undefined), undefined);
	assert.equal(placeTerrainFilter(null, cutoff), null);
	assert.equal(placeTerrainFilter(land, { ...cutoff, grid: null }), null);
	assert.equal(
		placeTerrainFilter(land, { ...cutoff, minimumFeet: null }),
		null,
	);
	assert.equal(locations.features.length, 5);
});
