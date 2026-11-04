/** Paid locations on modeled roads; origin connectors remain a separate policy. */
import type { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import {
	type PackedPoint,
	type SearchOptions,
	searchPackedCar,
	TWELVE_HOURS_TICKS,
} from "./coarse_osm_packed_search_v1.ts";
import type {
	PaidRoadGeometry,
	PaidShapePoint,
} from "./coarse_osm_paid_geometry_v1.ts";

export type RoadPosition = {
	canonicalArc: number;
	segment: number;
	segmentFraction: number;
};

function paidTicks(full: number, units: number): number {
	return Math.max(1, Math.min(full, Math.ceil((full * units) / 65535)));
}

export function resolveRoadPosition(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	position: RoadPosition,
) {
	const { canonicalArc: arc, segment, segmentFraction: fraction } = position;
	if (
		geometry.canonicalArc(arc) !== arc ||
		!Number.isInteger(segment) ||
		segment < 0 ||
		!Number.isFinite(fraction) ||
		fraction < 0 ||
		fraction > 1
	)
		throw new Error("Invalid modeled road position");
	let previous: PaidShapePoint | null = null;
	let count = 0;
	let forwardUnits = -1;
	let backwardUnits = -1;
	geometry.visitPoints(arc, (point) => {
		if (previous !== null && count - 1 === segment) {
			forwardUnits =
				previous.forward + fraction * (point.forward - previous.forward);
			backwardUnits =
				previous.backward + fraction * (point.backward - previous.backward);
		}
		previous = point;
		count++;
	});
	if (forwardUnits < 0) throw new Error("Modeled road segment outside packet");
	const rank = segment + fraction;
	const endpoint =
		rank === 0
			? graph.arcTail(arc)
			: rank === count - 1
				? graph.arcTarget(arc)
				: null;
	let source: PackedPoint;
	let target: PackedPoint;
	const reverse = graph.reverseArc(arc);
	if (endpoint !== null) {
		source = { vertex: endpoint };
		target = { vertex: endpoint };
	} else {
		const from = [
			{ arc, ticks: paidTicks(graph.arcCostTicks(arc), 65535 - forwardUnits) },
		];
		const to = [
			{ arc, ticks: paidTicks(graph.arcCostTicks(arc), forwardUnits) },
		];
		if (reverse !== null) {
			from.push({
				arc: reverse,
				ticks: paidTicks(graph.arcCostTicks(reverse), backwardUnits),
			});
			to.push({
				arc: reverse,
				ticks: paidTicks(graph.arcCostTicks(reverse), 65535 - backwardUnits),
			});
		}
		source = { partials: from };
		target = { partials: to };
	}
	return {
		canonicalArc: arc,
		rank,
		forwardUnits,
		backwardUnits,
		source,
		target,
	};
}

export function searchRoadPositions(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	from: RoadPosition,
	to: RoadPosition,
	options: SearchOptions = {},
) {
	const horizon = options.maxTicks ?? TWELVE_HOURS_TICKS;
	if (!Number.isInteger(horizon) || horizon < 0 || horizon > TWELVE_HOURS_TICKS)
		throw new Error("Invalid road-position horizon");
	const a = resolveRoadPosition(graph, geometry, from);
	const b = resolveRoadPosition(graph, geometry, to);
	let direct: number | null = null;
	if (a.canonicalArc === b.canonicalArc) {
		if (a.rank === b.rank) direct = 0;
		else if (a.rank < b.rank)
			direct = paidTicks(
				graph.arcCostTicks(a.canonicalArc),
				b.forwardUnits - a.forwardUnits,
			);
		else {
			const reverse = graph.reverseArc(a.canonicalArc);
			if (reverse !== null)
				direct = paidTicks(
					graph.arcCostTicks(reverse),
					a.backwardUnits - b.backwardUnits,
				);
		}
	}
	if (direct !== null && direct > horizon) direct = null;
	const result = searchPackedCar(graph, a.source, b.target, {
		...options,
		maxTicks: direct === null ? horizon : Math.min(horizon, direct),
	});
	const ticks =
		direct === null
			? result.ticks
			: result.ticks === null
				? direct
				: Math.min(direct, result.ticks);
	return { ...result, ticks, directCandidateTicks: direct };
}
