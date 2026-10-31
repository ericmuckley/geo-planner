// Saved-path accounting only. No distance-field or route-search execution.
import type { Origin } from "../lib/reachability";
import { replayCostAttachments } from "./backbone-cost";
import { type Backbone, nodePoint } from "./backbone-geometry";
import { type BackboneEdge, backboneTransitions } from "./backbone-routing";
import { gridPosition } from "./coarse-grid";

export type CapturedPath = {
	id: string;
	origin: Origin;
	destination: Origin;
	pointMinutes: number;
	components: {
		origin: number;
		road: number;
		local: number;
		transfer: number;
		destination: number;
	};
	direct: unknown;
	edges: (BackboneEdge & { fromPoint: number[]; toPoint: number[] })[];
};
const tolerance = 1e-8;
const total = (values: Record<string, number>) =>
	Object.values(values).reduce((a, b) => a + b, 0);

export function priceCapturedPath(
	model: Backbone,
	path: CapturedPath,
	verifyRecordedCosts = false,
) {
	if (path.direct || !path.edges.length)
		throw new RangeError("Captured path needs explicit graph transitions");
	const states =
		model.base.width * model.base.height +
		model.graph.nodeCoordinates.length / 2;
	const position = (state: number) =>
		state < model.base.width * model.base.height
			? gridPosition(model.base, state)
			: nodePoint(model.graph, state - model.base.width * model.base.height);
	const endpoint = (origin: Origin, state: number) => {
		const seed = replayCostAttachments(model, origin).seeds.find(
			(s) => s.node === state,
		);
		if (!seed) throw new Error("Captured endpoint state is no longer eligible");
		return seed.minutes;
	};
	const first = path.edges[0].from,
		last = path.edges[path.edges.length - 1].target;
	const components = {
		origin: endpoint(path.origin, first),
		road: 0,
		local: 0,
		transfer: 0,
		destination: 0,
	};
	let stateMinutes = components.origin,
		maximumStateMinutes = stateMinutes,
		kindChanges = 0;
	const edges: BackboneEdge[] = [];
	for (let index = 0; index < path.edges.length; index++) {
		const captured = path.edges[index];
		if (
			![captured.from, captured.target].every(
				(n) => Number.isSafeInteger(n) && n >= 0 && n < states,
			) ||
			(index && path.edges[index - 1].target !== captured.from)
		)
			throw new RangeError("Captured path chain is invalid");
		if (
			![captured.fromPoint, captured.toPoint].every(
				(point, i) =>
					point.length === 2 &&
					point.every(
						(v, k) => v === position(i ? captured.target : captured.from)[k],
					),
			)
		)
			throw new Error("Captured state position differs from bound geometry");
		let matched: BackboneEdge | undefined;
		for (const edge of backboneTransitions(model, captured.from)) {
			if (edge.target === captured.target && edge.arc === captured.arc) {
				matched = edge;
				break;
			}
		}
		if (!matched || !(matched.minutes > 0 && Number.isFinite(matched.minutes)))
			throw new Error("Captured transition/source arc is no longer eligible");
		if (
			verifyRecordedCosts &&
			(matched.kind !== captured.kind ||
				Math.abs(matched.minutes - captured.minutes) > tolerance)
		)
			throw new Error("Captured transition price/kind does not reproduce");
		if (matched.kind !== captured.kind) kindChanges++;
		components[matched.kind] += matched.minutes;
		stateMinutes += matched.minutes;
		maximumStateMinutes = Math.max(maximumStateMinutes, stateMinutes);
		edges.push(matched);
	}
	components.destination = endpoint(path.destination, last);
	const minutes = total(components);
	if (!Number.isFinite(minutes))
		throw new Error("Nonfinite captured path cost");
	if (verifyRecordedCosts) {
		if (
			Math.abs(minutes - path.pointMinutes) > tolerance ||
			Object.keys(components).some(
				(name) =>
					Math.abs(
						components[name as keyof typeof components] -
							path.components[name as keyof typeof components],
					) > tolerance,
			)
		)
			throw new Error("Captured path components do not reproduce");
	}
	return { minutes, components, maximumStateMinutes, kindChanges, edges };
}

export function controlledCostChange(
	oldMinutes: number,
	heldMinutes: number,
	actualMinutes: number,
	maximumStateMinutes: number,
	capMinutes: number,
) {
	if (
		![
			oldMinutes,
			heldMinutes,
			actualMinutes,
			maximumStateMinutes,
			capMinutes,
		].every((v) => Number.isFinite(v) && v >= 0)
	)
		throw new RangeError("Invalid path-control cost");
	const boundApplied = maximumStateMinutes <= capMinutes + tolerance;
	const directCostShift = heldMinutes - oldMinutes;
	const pathChoiceBenefit = heldMinutes - actualMinutes;
	if (directCostShift < -tolerance)
		throw new Error("Fixed allowance decreased held-path cost");
	if (boundApplied && pathChoiceBenefit < -tolerance)
		throw new Error("Stored prediction exceeds eligible held-state path bound");
	return {
		directCostShift,
		pathChoiceBenefit,
		actualCostShift: actualMinutes - oldMinutes,
		boundApplied,
		capLimited: !boundApplied,
		heldStatePrefixMaximum: maximumStateMinutes,
	};
}

export function sameStateSequence(a: CapturedPath, b: CapturedPath) {
	return (
		a.edges.length === b.edges.length &&
		a.edges.every(
			(edge, i) =>
				edge.from === b.edges[i].from &&
				edge.target === b.edges[i].target &&
				edge.arc === b.edges[i].arc,
		)
	);
}
