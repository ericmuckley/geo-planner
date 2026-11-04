/** Retained modeled-road geometry for independently replayed path steps. */
import type { AccessStart } from "./coarse_osm_access_road_field_v1.ts";
import { roadCoordinate } from "./coarse_osm_filled_display_v1.ts";
import type { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import type { PaidRoadGeometry } from "./coarse_osm_paid_geometry_v1.ts";
import type { RoadPosition } from "./coarse_osm_paid_positions_v1.ts";
import {
	type RoadWitness,
	validateRoadWitness,
} from "./coarse_osm_road_witness_v1.ts";
import {
	type Coordinate,
	sphericalDistance,
} from "./coarse_osm_spherical_v1.ts";

function shape(geometry: PaidRoadGeometry, arc: number) {
	const points: Coordinate[] = [];
	geometry.visitPoints(arc, (p) => {
		if (points.length === 4096) throw new Error("Witness curve point cap");
		points.push([p.xE7 / 1e7, p.yE7 / 1e7]);
	});
	return points;
}
function at(points: Coordinate[], position: RoadPosition) {
	if (position.segment < 0 || position.segment + 1 >= points.length)
		throw new Error("Witness geometry position segment");
	return roadCoordinate(
		points[position.segment],
		points[position.segment + 1],
		position.segmentFraction,
	);
}
export function witnessPositionCoordinate(
	geometry: PaidRoadGeometry,
	position: RoadPosition,
) {
	return at(shape(geometry, position.canonicalArc), position);
}
export function roadWitnessGeometry(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	starts: AccessStart[],
	target: RoadPosition,
	witness: RoadWitness,
) {
	validateRoadWitness(graph, geometry, starts, target, witness);
	if (witness.ticks === null || witness.startIndex === null) return null;
	const source = starts[witness.startIndex].position,
		coordinates: Coordinate[] = [],
		steps = [];
	let retainedRoadMeters = 0,
		conservativeWholeSpanSourceUpperMeters = 0;
	const append = (point: Coordinate) => {
		const previous = coordinates.at(-1);
		if (previous && previous[0] === point[0] && previous[1] === point[1])
			return;
		if (coordinates.length === 1000000)
			throw new Error("Witness output coordinate cap");
		coordinates.push(point);
	};
	if (!witness.steps.length)
		append(witnessPositionCoordinate(geometry, source));
	for (const step of witness.steps) {
		const canonical = geometry.canonicalArc(step.arc),
			points = shape(geometry, step.arc),
			forward = step.arc === canonical;
		const from =
				step.portion === "source-suffix" || step.portion === "direct"
					? source
					: null,
			to =
				step.portion === "target-prefix" || step.portion === "direct"
					? target
					: null;
		if (
			(from && from.canonicalArc !== canonical) ||
			(to && to.canonicalArc !== canonical)
		)
			throw new Error("Witness geometry physical identity mismatch");
		const first = from
				? from.segment + from.segmentFraction
				: forward
					? 0
					: points.length - 1,
			last = to
				? to.segment + to.segmentFraction
				: forward
					? points.length - 1
					: 0;
		if ((forward && first > last) || (!forward && first < last))
			throw new Error("Witness geometry direction mismatch");
		const selected: Coordinate[] = [from ? at(points, from) : points[first]];
		if (forward)
			for (let i = Math.floor(first) + 1; i < last; i++)
				selected.push(points[i]);
		else
			for (let i = Math.ceil(first) - 1; i > last; i--)
				selected.push(points[i]);
		selected.push(to ? at(points, to) : points[last]);
		const previous = coordinates.at(-1);
		if (previous && sphericalDistance(previous, selected[0]) > 0.001)
			throw new Error("Witness road geometry discontinuity");
		let meters = 0;
		for (let i = 1; i < selected.length; i++)
			meters += sphericalDistance(selected[i - 1], selected[i]);
		selected.forEach(append);
		retainedRoadMeters += meters;
		const sourceSpanUpperMeters = geometry.lengthUpperMeters(step.arc);
		conservativeWholeSpanSourceUpperMeters += sourceSpanUpperMeters;
		steps.push({
			arc: step.arc,
			portion: step.portion,
			modeledMeters: meters,
			sourceSpanUpperMeters,
			ticks: step.ticks,
			fullArcTicks: graph.arcCostTicks(step.arc),
		});
	}
	const finish = witnessPositionCoordinate(geometry, target);
	if (sphericalDistance(coordinates.at(-1) as Coordinate, finish) > 0.001)
		throw new Error("Witness road geometry endpoint mismatch");
	return {
		coordinates,
		retainedRoadMeters,
		conservativeWholeSpanSourceUpperMeters,
		steps,
	};
}
