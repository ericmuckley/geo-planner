/** V2: explicitly sever closure-held work buffers on every return/exception. */

import type { AccessStart } from "./coarse_osm_access_road_field_v1.ts";
import { MinQueue } from "./coarse_osm_min_queue_v1.ts";
import type { PackedCarGraph } from "./coarse_osm_packed_car_v1.ts";
import type { SearchOptions } from "./coarse_osm_packed_search_v1.ts";
import type { PaidRoadGeometry } from "./coarse_osm_paid_geometry_v1.ts";
import {
	type RoadPosition,
	resolveRoadPosition,
} from "./coarse_osm_paid_positions_v1.ts";

const NONE = 0xffffffff,
	ROOT = 0x80000000;
type Located = ReturnType<typeof resolveRoadPosition>;
export type RoadStep = {
	arc: number;
	portion: "full" | "source-suffix" | "target-prefix" | "direct";
	ticks: number;
	signalBeforeTicks: number;
	reversalBeforeTicks: number;
};
export type RoadWitness = {
	ticks: number | null;
	startIndex: number | null;
	steps: RoadStep[];
	stats: {
		settles: number;
		maximumHeapEntries: number;
		offlineSearchBackingBytes: number;
	};
};
type Finish =
	| { kind: "vertex"; ticks: number; parent: number }
	| { kind: "prefix"; ticks: number; parent: number; arc: number }
	| { kind: "direct"; ticks: number; start: number; arc: number | null };
const portion = (full: number, units: number, empty: boolean) =>
	empty ? 0 : Math.max(1, Math.min(full, Math.ceil((full * units) / 65535)));
function integer(value: number, maximum: number, label: string) {
	if (!Number.isInteger(value) || value < 0 || value > maximum)
		throw new Error(`Road witness ${label} domain`);
}

function direct(
	graph: PackedCarGraph,
	from: Located,
	to: Located,
): { arc: number | null; ticks: number } | null {
	if (
		"vertex" in from.source &&
		"vertex" in to.target &&
		from.source.vertex === to.target.vertex
	)
		return { arc: null, ticks: 0 };
	if (from.canonicalArc !== to.canonicalArc) return null;
	if (from.rank <= to.rank)
		return {
			arc: from.canonicalArc,
			ticks: portion(
				graph.arcCostTicks(from.canonicalArc),
				to.forwardUnits - from.forwardUnits,
				from.rank === to.rank,
			),
		};
	const reverse = graph.reverseArc(from.canonicalArc);
	return reverse === null
		? null
		: {
				arc: reverse,
				ticks: portion(
					graph.arcCostTicks(reverse),
					from.backwardUnits - to.backwardUnits,
					false,
				),
			};
}
function turn(graph: PackedCarGraph, previous: number, following: number) {
	const vertex = graph.arcTarget(previous),
		flags = graph.nodeFlags(vertex);
	if (
		graph.arcTail(following) !== vertex ||
		flags & 1 ||
		graph.forbidsTurn(previous, following)
	)
		throw new Error("Road witness forbidden transition");
	const reversal = graph.reverseArc(previous) === following;
	if (reversal && !(flags & 4))
		throw new Error("Road witness forbidden physical reversal");
	return {
		signalBeforeTicks: flags & 2 ? 40 : 0,
		reversalBeforeTicks: reversal ? 160 : 0,
	};
}

export function searchRoadWitness(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	starts: AccessStart[],
	target: RoadPosition,
	options: SearchOptions = {},
): RoadWitness {
	const horizon = options.maxTicks ?? 432000,
		capacity = options.maxHeapEntries ?? 1000000,
		maxSettles = options.maxSettles ?? 40000000;
	integer(horizon, 432000, "horizon");
	integer(capacity, 1000000, "heap");
	integer(maxSettles, 40000000, "settles");
	if (starts.length < 1 || starts.length > 4096)
		throw new Error("Road witness source count domain");
	const offlineSearchBackingBytes = 8 * graph.arcs + 8 * capacity;
	if (offlineSearchBackingBytes > 96 * 1024 ** 2)
		throw new Error("Road witness offline backing cap exceeded");
	for (const start of starts)
		integer(start.initialTicks, 345600, "initial cost");
	const located = starts.map((s) =>
			resolveRoadPosition(graph, geometry, s.position),
		),
		end = resolveRoadPosition(graph, geometry, target);
	let distances = new Uint32Array(graph.arcs).fill(NONE),
		parents = new Uint32Array(graph.arcs).fill(NONE),
		heap = new MinQueue(capacity);
	try {
		const targetVertex = "vertex" in end.target ? end.target.vertex : null;
		const prefixes = new Map(
			"partials" in end.target
				? end.target.partials.map((p) => [p.arc, p.ticks])
				: [],
		);
		let best: Finish | null = null,
			settles = 0;
		const offerFinish = (finish: Finish) => {
			if (
				finish.ticks <= horizon &&
				(best === null || finish.ticks < best.ticks)
			)
				best = finish;
		};
		const offerHead = (arc: number, ticks: number, parent: number) => {
			if (ticks > horizon || ticks >= distances[arc]) return;
			distances[arc] = ticks;
			parents[arc] = parent;
			heap.push(arc, ticks);
			if (graph.arcTarget(arc) === targetVertex)
				offerFinish({ kind: "vertex", ticks, parent: arc });
		};
		const offerEntry = (arc: number, ticks: number, parent: number) => {
			if (ticks > horizon) return;
			const prefix = prefixes.get(arc);
			if (prefix !== undefined)
				offerFinish({ kind: "prefix", ticks: ticks + prefix, parent, arc });
			offerHead(arc, ticks + graph.arcCostTicks(arc), parent);
		};
		for (const [i, point] of located.entries()) {
			const initial = starts[i].initialTicks;
			if (initial > horizon) continue;
			const same = direct(graph, point, end);
			if (same)
				offerFinish({
					kind: "direct",
					ticks: initial + same.ticks,
					start: i,
					arc: same.arc,
				});
			if ("vertex" in point.source) {
				for (
					let arc = graph.outgoingStart(point.source.vertex);
					arc < graph.outgoingEnd(point.source.vertex);
					arc++
				)
					offerEntry(arc, initial, ROOT + i);
			} else
				for (const partial of point.source.partials)
					offerHead(partial.arc, initial + partial.ticks, ROOT + i);
		}
		while (heap.length) {
			const [arc, ticks] = heap.pop();
			if (distances[arc] !== ticks) continue;
			const knownBest = best as Finish | null;
			if (knownBest !== null && ticks >= knownBest.ticks) break;
			if (++settles > maxSettles)
				throw new Error("Road witness settle cap exceeded");
			if ((settles & 1023) === 0) options.check?.();
			const vertex = graph.arcTarget(arc),
				flags = graph.nodeFlags(vertex);
			if (flags & 1) continue;
			const reverse = graph.reverseArc(arc);
			for (
				let next = graph.outgoingStart(vertex);
				next < graph.outgoingEnd(vertex);
				next++
			) {
				const reversal = next === reverse;
				if ((reversal && !(flags & 4)) || graph.forbidsTurn(arc, next))
					continue;
				offerEntry(
					next,
					ticks + (flags & 2 ? 40 : 0) + (reversal ? 160 : 0),
					arc,
				);
			}
		}
		options.check?.();
		const stats = {
			settles,
			maximumHeapEntries: heap.peak,
			offlineSearchBackingBytes,
		};
		// Callbacks above assign the winner; TS does not track those side effects.
		const finish = best as Finish | null;
		if (finish === null)
			return { ticks: null, startIndex: null, steps: [], stats };
		let startIndex: number;
		const steps: RoadStep[] = [];
		if (finish.kind === "direct") {
			startIndex = finish.start;
			const ticks = finish.ticks - starts[startIndex].initialTicks;
			if (finish.arc !== null && ticks)
				steps.push({
					arc: finish.arc,
					portion: "direct",
					ticks,
					signalBeforeTicks: 0,
					reversalBeforeTicks: 0,
				});
		} else {
			let parent = finish.parent;
			const reversePath: number[] = [];
			while (parent < ROOT) {
				if (reversePath.length >= graph.arcs)
					throw new Error("Road witness parent cycle");
				reversePath.push(parent);
				parent = parents[parent];
			}
			if (parent === NONE || parent - ROOT >= starts.length)
				throw new Error("Road witness missing source root");
			startIndex = parent - ROOT;
			const source = located[startIndex].source;
			for (const arc of reversePath.reverse()) {
				const before = steps.length
					? turn(graph, steps[steps.length - 1].arc, arc)
					: { signalBeforeTicks: 0, reversalBeforeTicks: 0 };
				const firstPartial =
					!steps.length && "partials" in source
						? source.partials.find((p) => p.arc === arc)
						: null;
				if (!steps.length && "partials" in source && !firstPartial)
					throw new Error("Road witness invalid initial suffix");
				steps.push({
					arc,
					portion: firstPartial ? "source-suffix" : "full",
					ticks: firstPartial?.ticks ?? graph.arcCostTicks(arc),
					...before,
				});
			}
			if (finish.kind === "prefix")
				steps.push({
					arc: finish.arc,
					portion: "target-prefix",
					ticks: prefixes.get(finish.arc) as number,
					...(steps.length
						? turn(graph, steps[steps.length - 1].arc, finish.arc)
						: { signalBeforeTicks: 0, reversalBeforeTicks: 0 }),
				});
		}
		const result = { ticks: finish.ticks, startIndex, steps, stats };
		validateRoadWitness(graph, geometry, starts, target, result);
		return result;
	} finally {
		// A surviving optimized callback context must not retain country work arrays.
		distances = new Uint32Array(0);
		parents = new Uint32Array(0);
		heap = new MinQueue(0);
	}
}

/** Replay original graph/state/cost rules, independently of search labels/parents. */
export function validateRoadWitness(
	graph: PackedCarGraph,
	geometry: PaidRoadGeometry,
	starts: AccessStart[],
	target: RoadPosition,
	result: RoadWitness,
) {
	if (result.ticks === null) {
		if (result.startIndex !== null || result.steps.length)
			throw new Error("Unreached witness has a path");
		return null;
	}
	if (
		result.startIndex === null ||
		!Number.isInteger(result.startIndex) ||
		result.startIndex < 0 ||
		result.startIndex >= starts.length
	)
		throw new Error("Road witness invalid root");
	const initial = starts[result.startIndex],
		from = resolveRoadPosition(graph, geometry, initial.position),
		to = resolveRoadPosition(graph, geometry, target);
	integer(initial.initialTicks, 345600, "initial cost");
	let roadTicks = 0,
		signalTicks = 0,
		reversalTicks = 0;
	if (!result.steps.length) {
		const same = direct(graph, from, to);
		if (!same || same.ticks !== 0)
			throw new Error("Road witness missing travel");
	}
	for (const [i, step] of result.steps.entries()) {
		if (
			!["full", "source-suffix", "target-prefix", "direct"].includes(
				step.portion,
			)
		)
			throw new Error("Road witness portion domain");
		let expected: number;
		const last = i === result.steps.length - 1;
		const before = i
			? turn(graph, result.steps[i - 1].arc, step.arc)
			: { signalBeforeTicks: 0, reversalBeforeTicks: 0 };
		if (
			step.signalBeforeTicks !== before.signalBeforeTicks ||
			step.reversalBeforeTicks !== before.reversalBeforeTicks
		)
			throw new Error("Road witness unpaid turn");
		if (step.portion === "direct") {
			const same = direct(graph, from, to);
			if (i !== 0 || !last || !same || same.arc !== step.arc)
				throw new Error("Road witness illegal direct portion");
			expected = same.ticks;
		} else if (step.portion === "source-suffix") {
			const part =
				"partials" in from.source
					? from.source.partials.find((p) => p.arc === step.arc)
					: null;
			if (i !== 0 || !part)
				throw new Error("Road witness wrong initial suffix");
			expected = part.ticks;
		} else {
			if (
				!i &&
				(!("vertex" in from.source) ||
					graph.arcTail(step.arc) !== from.source.vertex)
			)
				throw new Error("Road witness initial vertex mismatch");
			if (step.portion === "target-prefix") {
				const part =
					"partials" in to.target
						? to.target.partials.find((p) => p.arc === step.arc)
						: null;
				if (!last || !part) throw new Error("Road witness wrong final prefix");
				expected = part.ticks;
			} else expected = graph.arcCostTicks(step.arc);
		}
		if (
			step.ticks !== expected ||
			!Number.isInteger(step.ticks) ||
			step.ticks <= 0
		)
			throw new Error("Road witness unpaid road portion");
		roadTicks += step.ticks;
		signalTicks += step.signalBeforeTicks;
		reversalTicks += step.reversalBeforeTicks;
		if (
			last &&
			step.portion !== "target-prefix" &&
			step.portion !== "direct" &&
			(!("vertex" in to.target) ||
				graph.arcTarget(step.arc) !== to.target.vertex)
		)
			throw new Error("Road witness final vertex mismatch");
	}
	const total = initial.initialTicks + roadTicks + signalTicks + reversalTicks;
	if (total !== result.ticks) throw new Error("Road witness path sum mismatch");
	return {
		initialTicks: initial.initialTicks,
		roadTicks,
		signalTicks,
		reversalTicks,
		totalTicks: total,
	};
}
