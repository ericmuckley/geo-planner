import assert from "node:assert/strict";
import test from "node:test";
import { areaMembership, isInEstimatedArea } from "../lib/contour-membership";
import { contoursSchema } from "../lib/reachability";

const contours = contoursSchema.parse({
	type: "FeatureCollection",
	features: [
		{
			type: "Feature",
			properties: null,
			geometry: {
				type: "Polygon",
				coordinates: [
					[
						[-120, 30],
						[-116, 30],
						[-116, 34],
						[-120, 34],
						[-120, 30],
					],
					[
						[-119, 31],
						[-118, 31],
						[-118, 32],
						[-119, 32],
						[-119, 31],
					],
				],
			},
		},
		{
			type: "Feature",
			properties: null,
			geometry: {
				type: "MultiPolygon",
				coordinates: [
					[
						[
							[-115, 34],
							[-114, 34],
							[-114, 35],
							[-115, 35],
							[-115, 34],
						],
					],
					[
						[
							[-113, 33],
							[-112, 33],
							[-112, 34],
							[-113, 34],
							[-113, 33],
						],
					],
				],
			},
		},
		{
			type: "Feature",
			properties: { type: "snapped" },
			geometry: { type: "Point", coordinates: [-111, 33] },
		},
	],
});

test("the destination check respects polygon holes and disconnected areas", () => {
	assert.equal(isInEstimatedArea({ lon: -119.5, lat: 32.5 }, contours), true);
	assert.equal(isInEstimatedArea({ lon: -118.5, lat: 31.5 }, contours), false);
	assert.equal(isInEstimatedArea({ lon: -114.5, lat: 34.5 }, contours), true);
	assert.equal(isInEstimatedArea({ lon: -112.5, lat: 33.5 }, contours), true);
	assert.equal(isInEstimatedArea({ lon: -111, lat: 33 }, contours), false);
});

test("indexed membership agrees with the direct test near vertices and holes", () => {
	const outline = [
		[0, 0],
		[4, 0],
		[4, 4],
		[2, 4],
		[2, 2],
		[0, 2],
		[0, 0],
	];
	const ring = outline.slice(0, -1).flatMap(([x, y], index) => {
		const [nextX, nextY] = outline[index + 1];
		return Array.from({ length: 16 }, (_, i) => [
			x + ((nextX - x) * i) / 16,
			y + ((nextY - y) * i) / 16,
		]);
	});
	const complex = contoursSchema.parse({
		type: "FeatureCollection",
		features: [
			{
				type: "Feature",
				properties: null,
				geometry: {
					type: "Polygon",
					coordinates: [
						[...ring, ring[0]],
						[
							[0.5, 0.5],
							[1, 0.5],
							[1, 1],
							[0.5, 1],
							[0.5, 0.5],
						],
					],
				},
			},
		],
	});
	const contains = areaMembership(complex);
	for (let lon = -0.25; lon <= 4.25; lon += 0.125) {
		for (let lat = -0.25; lat <= 4.25; lat += 0.125) {
			assert.equal(
				contains(lon, lat),
				isInEstimatedArea({ lon, lat }, complex),
			);
		}
	}
});
