import assert from "node:assert/strict";
import test from "node:test";
import { fuelCatalogSchema, fuelLocationsInArea } from "../lib/fuel-locations";
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
const catalog = fuelCatalogSchema.parse({
	version: 1,
	sourceDate: "2026-10-25",
	sourceSha256: "0".repeat(64),
	stations: [
		[-119.5, 32, "A station", "n1"],
		[-118.5, 31.5, "In the hole", "w2"],
		[-108, 38, "Elsewhere", "n3"],
		[-113.5, 34.5, "", "w4"],
	],
});

test("fuel locations match the displayed area across separate polygons and holes", () => {
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
	const { features } = fuelLocationsInArea(catalog, contours);
	assert.deepEqual(
		features.map((feature) => feature.id),
		["n1", "w4"],
	);
	assert.equal(features[1].properties.name, "Unnamed fuel stop");
});

test("fuel catalog rejects coordinate and source format errors", () => {
	assert.equal(
		fuelCatalogSchema.safeParse({
			...catalog,
			stations: [[32, -117, "Swapped longitude and latitude", "n1"]],
		}).success,
		false,
	);
	assert.equal(
		fuelCatalogSchema.safeParse({ ...catalog, version: 2 }).success,
		false,
	);
});
