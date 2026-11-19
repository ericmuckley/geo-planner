import assert from "node:assert/strict";
import test from "node:test";
import { prepared } from "./coarse_osm_access_fixture_v2.ts";
import { computeAccessRoadField } from "./coarse_osm_access_road_field_v2.ts";
import {
	connectorPrice,
	type OriginConnection,
} from "./coarse_osm_origin_connections_v2.ts";
import {
	sphericalDistance,
	type Coordinate,
} from "./coarse_osm_spherical_v1.ts";
import { paidTerminalArrival } from "./coarse_osm_terminal_access_v1.ts";

const position = (arc: number, fraction: number) => ({
	canonicalArc: arc,
	segment: 0,
	segmentFraction: fraction,
});
function connection(
	target: Coordinate,
	coordinate: Coordinate,
	arc: number,
	fraction: number,
): OriginConnection {
	const price = connectorPrice(target, coordinate);
	return {
		origin: target,
		...{ connectorTicks: price.ticks, connectorMeters: price.meters },
		kind: "land-connector",
		snap: {
			...position(arc, fraction),
			coordinate,
			distanceMeters: sphericalDistance(target, coordinate),
			forwardProgress: fraction,
			backwardProgress: 1 - fraction,
		},
	};
}
const field = (
	p: ReturnType<typeof prepared>,
	arc: number,
	fraction = 0,
	horizon = 2000,
) =>
	computeAccessRoadField(
		p.graph,
		p.geometry,
		[{ position: position(arc, fraction), initialTicks: 23 }],
		{ maxTicks: horizon, maxHeapEntries: 256 },
	);

test("an unreachable nearest road does not hide a farther independently paid finish", () => {
	const p = prepared(
		[
			[0, 0],
			[0.001, 0],
			[0, 0.0001],
			[0.001, 0.0001],
		],
		[
			[0, 1],
			[2, 3],
		],
	);
	const target: Coordinate = [0.0005, 0.00002];
	const choices = [
		connection(target, [0.0005, 0], 0, 0.5),
		connection(target, [0.0005, 0.0001], 1, 0.5),
	];
	const f = field(p, 1);
	assert.equal(
		paidTerminalArrival(p.graph, p.geometry, f, choices.slice(0, 1)),
		null,
	);
	assert.deepEqual(paidTerminalArrival(p.graph, p.geometry, f, choices), {
		ticks: 523 + choices[1].connectorTicks,
		index: 1,
	});
	assert.ok(choices[1].connectorTicks > choices[0].connectorTicks);
});

test("one-way partial travel and the full terminal price stay paid within the horizon", () => {
	const p = prepared(
		[
			[0, 0],
			[0.001, 0],
		],
		[[0, 1]],
	);
	const target: Coordinate = [0.0001, 0.0001];
	const choices = [
		connection(target, [0.0001, 0], 0, 0.1),
		connection(target, [0.0009, 0], 0, 0.9),
	];
	const f = field(p, 0, 0.75);
	assert.equal(
		paidTerminalArrival(p.graph, p.geometry, f, choices.slice(0, 1)),
		null,
	);
	const result = paidTerminalArrival(p.graph, p.geometry, f, choices);
	assert.equal(result?.index, 1);
	assert.equal(result?.ticks, 173 + choices[1].connectorTicks);
	assert.equal(
		paidTerminalArrival(p.graph, p.geometry, field(p, 0, 0.75, 174), choices),
		null,
	);
});

test("terminal choices reject mixed destinations, forged prices and oversized collections", () => {
	const p = prepared(
			[
				[0, 0],
				[0.001, 0],
			],
			[[0, 1]],
		),
		f = field(p, 0);
	const c = connection([0, 0.0001], [0, 0], 0, 0);
	assert.throws(() => paidTerminalArrival(p.graph, p.geometry, f, []), /count/);
	assert.throws(
		() => paidTerminalArrival(p.graph, p.geometry, f, Array(4097).fill(c)),
		/count/,
	);
	assert.throws(
		() =>
			paidTerminalArrival(p.graph, p.geometry, f, [
				c,
				{ ...c, origin: [0, 0.0002] },
			]),
		/mismatch/,
	);
	assert.throws(
		() =>
			paidTerminalArrival(p.graph, p.geometry, f, [
				{ ...c, connectorTicks: 0 },
			]),
		/Unpaid/,
	);
	assert.throws(
		() =>
			paidTerminalArrival(p.graph, p.geometry, f, [
				connection([4, 0], [0, 0], 0, 0),
			]),
		/price cap/,
	);
});
