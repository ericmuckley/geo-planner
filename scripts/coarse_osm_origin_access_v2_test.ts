import assert from "node:assert/strict";
import test from "node:test";
import { landConnection } from "../src/server/coarse-geography.ts";
import {
	geography,
	prepared,
	rectangle,
} from "./coarse_osm_access_fixture_v2.ts";
import { connectOriginAccess } from "./coarse_osm_origin_access_v2.ts";
import {
	connectOrigin,
	connectorPrice,
	type OriginConnection,
} from "./coarse_osm_origin_connections_v1.ts";
import { resolveRoadPosition } from "./coarse_osm_paid_positions_v1.ts";
import {
	type Coordinate,
	nearestOnSegment,
	sphericalDistance,
} from "./coarse_osm_spherical_v1.ts";

type Prepared = ReturnType<typeof prepared>;
const identity = (p: Prepared, c: OriginConnection) => {
	const point = resolveRoadPosition(p.graph, p.geometry, c.snap);
	return "vertex" in point.source
		? `v${point.source.vertex}`
		: `a${point.canonicalArc}/${point.rank}`;
};

test("initial alternatives retain the primary and independently pay nearby roads", () => {
	const p = prepared(
			[
				[-0.0005, 0],
				[0.0005, 0],
				[0.004, -0.01],
				[0.004, 0.01],
			],
			[
				[0, 1],
				[2, 3],
			],
		),
		geo = geography(),
		origin = [0, 0.0001] as const;
	const result = connectOriginAccess(
		p.graph,
		p.geometry,
		p.keys,
		p.starts,
		geo,
		origin,
	);
	assert.deepEqual(
		result.primary,
		connectOrigin(p.graph, p.geometry, p.keys, p.starts, geo, origin)
			.connection,
	);
	assert.ok(result.connections.length > 1);
	assert.ok(result.connections.some((c) => c.snap.coordinate[0] > 0.003));
	assert.equal(
		new Set(result.connections.map((c) => identity(p, c))).size,
		result.connections.length,
	);
	for (const c of result.connections) {
		assert.deepEqual(c.origin, origin);
		assert.equal(
			c.connectorTicks,
			connectorPrice(origin, c.snap.coordinate).ticks,
		);
		assert.ok(c.connectorMeters <= (result.radiusMeters ?? 0) + 1e-6);
	}
});
test("on-mask sources retain strict water crossings even within the uncertainty radius", () => {
	const p = prepared(
		[
			[0.0004, -0.001],
			[0.0004, 0.001],
			[-0.004, -0.001],
			[-0.004, 0.001],
		],
		[
			[0, 1],
			[2, 3],
		],
	);
	const geo = geography([[rectangle(0.0001, -0.01, 0.0003, 0.01)]]);
	const result = connectOriginAccess(
		p.graph,
		p.geometry,
		p.keys,
		p.starts,
		geo,
		[0, 0],
	);
	assert.ok(result.primary);
	assert.equal(result.maskOmissionAllowance, false);
	assert.ok(result.connections.every((c) => c.snap.coordinate[0] < 0));
	for (const c of result.connections)
		assert.ok(landConnection(geo, [0, 0], [...c.snap.coordinate]));
});
test("unmasked inputs use only the explicit paid100m initial uncertainty branch", () => {
	const geo = geography();
	geo.boundary = [[rectangle(0.01, -0.01, 0.02, 0.01)]];
	for (const [x, accepted] of [
		[0.0004, true],
		[0.002, false],
	] as const) {
		const p = prepared(
				[
					[x, -0.001],
					[x, 0.001],
				],
				[[0, 1]],
			),
			result = connectOriginAccess(
				p.graph,
				p.geometry,
				p.keys,
				p.starts,
				geo,
				[0, 0],
			);
		assert.equal(result.maskOmissionAllowance, accepted);
		assert.equal(result.primary !== null, accepted);
		for (const c of result.connections) {
			assert.ok(c.connectorMeters <= 100);
			assert.ok(c.connectorTicks > 0);
		}
		if (!accepted) assert.equal(result.reason, "outside-geography-mask");
	}
});
test("graph vertices deduplicate by identity; crossing roads never acquire a junction", () => {
	let p = prepared(
		[
			[0, 0],
			[0.004, 0],
			[0, 0.004],
		],
		[
			[0, 1],
			[0, 2],
		],
	);
	let result = connectOriginAccess(
		p.graph,
		p.geometry,
		p.keys,
		p.starts,
		geography(),
		[-0.0001, -0.0001],
	);
	assert.equal(
		result.connections.filter(
			(c) => c.snap.coordinate[0] === 0 && c.snap.coordinate[1] === 0,
		).length,
		1,
	);
	p = prepared(
		[
			[-0.003, -0.003],
			[0.003, 0.003],
			[-0.003, 0.003],
			[0.003, -0.003],
		],
		[
			[0, 1],
			[2, 3],
		],
	);
	result = connectOriginAccess(
		p.graph,
		p.geometry,
		p.keys,
		p.starts,
		geography(),
		[0, 0],
	);
	assert.equal(
		result.connections.filter((c) => c.snap.distanceMeters < 0.001).length,
		2,
	);
});
test("connection/geometry/cancellation and unsupported inputs fail explicitly", () => {
	const p = prepared(
			[
				[-0.001, 0],
				[0.001, 0],
				[0.004, -0.001],
				[0.004, 0.001],
			],
			[
				[0, 1],
				[2, 3],
			],
		),
		geo = geography();
	assert.throws(
		() =>
			connectOriginAccess(
				p.graph,
				p.geometry,
				p.keys,
				p.starts,
				geo,
				[0, 0],
				() => {},
				1,
			),
		/cap exceeded/,
	);
	assert.throws(
		() =>
			connectOriginAccess(
				p.graph,
				p.geometry,
				p.keys,
				p.starts,
				geo,
				[0, 0],
				() => {
					throw new Error("cancel");
				},
			),
		/cancel/,
	);
	assert.throws(
		() =>
			connectOriginAccess(
				p.graph,
				p.geometry,
				p.keys,
				p.starts,
				geo,
				[0, 0],
				() => {},
				1025,
			),
		/domain/,
	);
	assert.equal(
		connectOriginAccess(p.graph, p.geometry, p.keys, p.starts, geo, [1, 0])
			.reason,
		"outside-coverage-bounds",
	);
});
test("collector equals exhaustive segment feet/endpoints on100 unfiltered generated inputs", () => {
	let state = 79349;
	const random = () => {
		state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
		return state / 2 ** 32;
	};
	const points: Coordinate[] = Array.from({ length: 80 }, () => [
		(random() - 0.5) * 0.04,
		(random() - 0.5) * 0.04,
	]);
	const p = prepared(
			points,
			Array.from({ length: 40 }, (_, i) => [2 * i, 2 * i + 1]),
		),
		geo = geography();
	for (let run = 0; run < 100; run++) {
		const origin: Coordinate = [
			(random() - 0.5) * 0.02,
			(random() - 0.5) * 0.02,
		];
		const actual = connectOriginAccess(
			p.graph,
			p.geometry,
			p.keys,
			p.starts,
			geo,
			origin,
		);
		assert.ok(actual.primary);
		assert.ok(actual.radiusMeters !== null);
		const expected = new Map<string, number>();
		for (let arc = 0; arc < p.graph.arcs; arc++) {
			const a = p.graph.coordinate(p.graph.arcTail(arc)),
				b = p.graph.coordinate(p.graph.arcTarget(arc)),
				foot = nearestOnSegment(origin, a, b);
			for (const candidate of [
				foot,
				{ coordinate: a, fraction: 0, distance: sphericalDistance(origin, a) },
				{ coordinate: b, fraction: 1, distance: sphericalDistance(origin, b) },
			]) {
				const price = connectorPrice(origin, candidate.coordinate);
				if (price.meters > actual.radiusMeters + 1e-6) continue;
				const c: OriginConnection = {
					origin,
					snap: {
						canonicalArc: arc,
						segment: 0,
						segmentFraction: candidate.fraction,
						coordinate: candidate.coordinate,
						distanceMeters: candidate.distance,
						forwardProgress: candidate.fraction,
						backwardProgress: 0,
					},
					connectorMeters: price.meters,
					connectorTicks: price.ticks,
					kind: "land-connector",
				};
				const key = identity(p, c);
				expected.set(
					key,
					Math.min(expected.get(key) ?? Infinity, c.connectorTicks),
				);
			}
		}
		assert.deepEqual(
			new Map(
				actual.connections.map((c) => [identity(p, c), c.connectorTicks]),
			),
			expected,
		);
	}
});
