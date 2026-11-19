import assert from "node:assert/strict";
import test from "node:test";
import {
	parsePlaceCatalog,
	placeLocationsInArea,
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
