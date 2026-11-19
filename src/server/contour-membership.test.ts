import assert from "node:assert/strict";
import test from "node:test";
import { areaMembership, contourPolygons } from "../lib/contour-membership";
import { contoursSchema } from "../lib/reachability";
import { containsPolygon } from "./coarse-contours";

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

test("area membership respects polygon holes and disconnected areas", () => {
	const contains = areaMembership(contours);
	assert.equal(contains(-119.5, 32.5), true);
	assert.equal(contains(-118.5, 31.5), false);
	assert.equal(contains(-114.5, 34.5), true);
	assert.equal(contains(-112.5, 33.5), true);
	assert.equal(contains(-111, 33), false);
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
	const polygons = contourPolygons(complex);
	for (let lon = -0.25; lon <= 4.25; lon += 0.125) {
		for (let lat = -0.25; lat <= 4.25; lat += 0.125) {
			assert.equal(
				contains(lon, lat),
				polygons.some((polygon) => containsPolygon([lon, lat], polygon)),
			);
		}
	}
});
