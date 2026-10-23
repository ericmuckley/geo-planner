import assert from "node:assert/strict";
import test from "node:test";
import { landConnection, prepareGeography } from "./coarse-geography";
import data from "./data/coarse-grid-v4.json";

const rectangle = (
	west: number,
	south: number,
	east: number,
	north: number,
) => [
	[west, south],
	[east, south],
	[east, north],
	[west, north],
	[west, south],
];

test("indexed crossings match the full scan at band boundaries, holes and open rings", () => {
	const geography = {
		boundary: [
			[rectangle(-0.4, -0.4, 0.4, 0.4), rectangle(-0.2, -0.2, -0.1, 0.2)],
			[rectangle(0.4, 0.4, 0.8, 0.8).slice(0, -1)],
		],
		lakes: [[rectangle(0.09999, -0.3, 0.10001, 0.3)]],
	};
	const indexed = structuredClone(geography);
	prepareGeography(indexed);
	const values = [
		-0.5, -0.4, -0.3, -0.2, -0.1, -0.025, 0, 0.00999, 0.01, 0.01001, 0.02499,
		0.025, 0.02501, 0.04999, 0.05, 0.05001, 0.09999, 0.1, 0.10001, 0.2, 0.3,
		0.4, 0.5,
	];
	for (const x of values)
		for (const y of values) {
			const a = [x, y];
			for (const b of [[-x, -y], [x, -y], [-x, y], a, [0.5, 0.5]])
				for (const tolerance of [0, 0.1, 1])
					assert.equal(
						landConnection(indexed, a, b, tolerance),
						landConnection(geography, a, b, tolerance),
						JSON.stringify({ a, b, tolerance }),
					);
		}
	assert.throws(() => indexed.lakes[0][0].push([0, 0]), TypeError);
	// Replacing geometry cannot accidentally use the old index.
	indexed.lakes = [];
	assert.equal(landConnection(indexed, [0, 0], [0.3, 0]), true);
});

test("indexed national geography matches unindexed checks for arbitrary segments and exact vertices", () => {
	const geography = { boundary: data.boundary, lakes: data.lakes };
	const indexed = structuredClone(geography);
	prepareGeography(indexed);
	let seed = 1717;
	const random = () => {
		seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
		return seed / 2 ** 32;
	};
	for (let i = 0; i < 2048; i++) {
		const a = [-125 + random() * 59, 24 + random() * 26];
		const b = [a[0] + (random() - 0.5) * 2, a[1] + (random() - 0.5) * 2];
		const tolerance = i % 3 ? 0 : 0.1;
		assert.equal(
			landConnection(indexed, a, b, tolerance),
			landConnection(geography, a, b, tolerance),
			JSON.stringify({ a, b, tolerance }),
		);
	}
	for (const polygon of [...geography.boundary, ...geography.lakes])
		for (const ring of polygon)
			for (const a of [ring[0], ring[Math.floor(ring.length / 2)]])
				for (const delta of [0, 1e-10, -1e-10]) {
					const b = [a[0] + delta, a[1] + 0.1];
					assert.equal(
						landConnection(indexed, a, b),
						landConnection(geography, a, b),
					);
				}
});
