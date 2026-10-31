// Isolated candidate: no production route imports this module.
import type { Origin } from "../lib/reachability";
import {
	type Backbone,
	cellArcs,
	interpolate,
	nodeArcs,
	nodePoint,
	type Point,
	pointCell,
	pointCells,
	project,
	sourceMinutes,
	sourceSegments,
} from "./backbone-geometry";
import { cellContours, containsPolygon } from "./coarse-contours";
import { landConnection } from "./coarse-geography";
import {
	distanceKm,
	gridAttachments,
	gridPosition,
	gridTransitions,
} from "./coarse-grid";

const rounded = (minutes: number) => Math.ceil(minutes * 600) / 600;
const size = (model: Backbone) => model.base.width * model.base.height;
type Kind = "road" | "local" | "transfer";
export type BackboneEdge = {
	from: number;
	target: number;
	minutes: number;
	kind: Kind;
	arc?: number;
};
type Access = {
	arc: number;
	point: Point;
	km: number;
	localMinutes: number;
	localKm: number;
};
type Seed = { node: number; minutes: number };

function validateOrigin(model: Backbone, origin: Origin) {
	const { base } = model,
		point: Point = [origin.lon, origin.lat];
	if (!point.every(Number.isFinite) || pointCell(base, point) < 0)
		throw new RangeError("Choose a location within the contiguous US grid.");
	const near = (polygon: number[][][]) =>
		polygon.some((ring) =>
			ring.some((a, i) => {
				if (!i) return false;
				const b = ring[i - 1];
				if (
					point[1] < Math.min(a[1], b[1]) - 0.01 ||
					point[1] > Math.max(a[1], b[1]) + 0.01 ||
					point[0] < Math.min(a[0], b[0]) - 0.02 ||
					point[0] > Math.max(a[0], b[0]) + 0.02
				)
					return false;
				return distanceKm(point, interpolate(a, b, project(point, a, b))) <= 1;
			}),
		);
	if (
		!base.boundary.some((p) => containsPolygon(point, p) || near(p)) ||
		base.lakes.some((p) => containsPolygon(point, p) && !near(p))
	)
		throw new RangeError(
			"Choose a land location in the contiguous United States.",
		);
	if (
		base.roadLayer ||
		base.supplementalRoadVisits ||
		base.localSpeedKph !== 25
	)
		throw new RangeError(
			"The candidate requires the kept-v9 base and local25 costs.",
		);
	return point;
}

export function transferMinutes(model: Backbone, node: number, cell: number) {
	const { base, graph } = model;
	const point = nodePoint(graph, node);
	if (!base.traversable[cell] || !pointCells(base, point).includes(cell))
		return Infinity;
	const representative = gridPosition(base, cell);
	if (!landConnection(base, representative, point)) return Infinity;
	return Math.max(
		1 / 600,
		rounded((distanceKm(representative, point) / 25) * 60),
	);
}

export function* backboneTransitions(
	model: Backbone,
	state: number,
): Generator<BackboneEdge> {
	const count = size(model),
		{ base, graph } = model;
	if (state < count) {
		for (const edge of gridTransitions(base, state))
			yield { from: state, ...edge };
		const nodes = new Set<number>();
		// Closed upper/right boundaries can be indexed in the neighboring floor cell.
		const x = state % base.width,
			y = Math.floor(state / base.width);
		for (let dy = 0; dy <= 1; dy++)
			for (let dx = 0; dx <= 1; dx++) {
				if (x + dx >= base.width || y + dy >= base.height) continue;
				for (const arc of cellArcs(graph, state + dy * base.width + dx)) {
					nodes.add(graph.arcFrom[arc]);
					nodes.add(graph.arcTo[arc]);
				}
			}
		for (const node of [...nodes].sort((a, b) => a - b)) {
			const minutes = transferMinutes(model, node, state);
			if (Number.isFinite(minutes))
				yield { from: state, target: count + node, minutes, kind: "transfer" };
		}
	} else {
		const node = state - count;
		for (const arc of nodeArcs(model, node))
			yield {
				from: state,
				target:
					count +
					(graph.arcFrom[arc] === node ? graph.arcTo[arc] : graph.arcFrom[arc]),
				minutes: graph.arcMinutes[arc],
				kind: "road",
				arc,
			};
		for (const cell of pointCells(base, nodePoint(graph, node))) {
			const minutes = transferMinutes(model, node, cell);
			if (Number.isFinite(minutes))
				yield { from: state, target: cell, minutes, kind: "transfer" };
		}
	}
}

function roadAccesses(model: Backbone, point: Point): Access[] {
	const { base, graph } = model;
	const own = pointCell(base, point),
		x = own % base.width,
		y = Math.floor(own / base.width);
	const cells = new Set<number>();
	for (let dy = -1; dy <= 1; dy++)
		for (let dx = -1; dx <= 1; dx++)
			if (
				x + dx >= 0 &&
				x + dx < base.width &&
				y + dy >= 0 &&
				y + dy < base.height
			)
				cells.add((y + dy) * base.width + x + dx);
	const arcs = new Set<number>();
	for (const cell of cells)
		for (const arc of cellArcs(graph, cell)) arcs.add(arc);
	const result: Access[] = [];
	for (const arc of [...arcs].sort((a, b) => a - b)) {
		const seen = new Set<string>();
		for (const segment of sourceSegments(graph, arc)) {
			for (const t of new Set([0, project(point, segment.a, segment.b), 1])) {
				const projected = interpolate(segment.a, segment.b, t);
				const km = segment.startKm + (segment.endKm - segment.startKm) * t;
				const key = `${km}/${projected[0]}/${projected[1]}`;
				if (
					seen.has(key) ||
					!pointCells(base, projected).some((cell) => cells.has(cell))
				)
					continue;
				seen.add(key);
				const localKm = distanceKm(point, projected);
				if (landConnection(base, point, projected, 1 / Math.max(localKm, 1)))
					result.push({
						arc,
						point: projected,
						km,
						localKm,
						localMinutes: (localKm / 25) * 60,
					});
			}
		}
	}
	return result;
}

function attachments(model: Backbone, origin: Origin) {
	const point = validateOrigin(model, origin),
		{ base, graph } = model;
	const best = new Map<number, Seed>();
	const add = (seed: Seed) => {
		if (seed.minutes < (best.get(seed.node)?.minutes ?? Infinity))
			best.set(seed.node, seed);
	};
	for (const seed of gridAttachments(base, origin))
		add({ node: seed.cell, minutes: seed.minutes });
	const accesses = roadAccesses(model, point);
	for (const access of accesses)
		for (const [node, km] of [
			[graph.arcFrom[access.arc], access.km],
			[graph.arcTo[access.arc], graph.arcRoadKm[access.arc] - access.km],
		])
			add({
				node: size(model) + node,
				minutes: rounded(
					access.localMinutes +
						sourceMinutes(
							graph,
							access.arc,
							km,
							access.point,
							nodePoint(graph, node),
						),
				),
			});
	return {
		point,
		seeds: [...best.values()].sort(
			(a, b) => a.minutes - b.minutes || a.node - b.node,
		),
		accesses,
	};
}

// Kept separate from the sealed grid implementation so its prior recipes stay valid.
class Queue {
	private entries: [number, number][] = [];
	get length() {
		return this.entries.length;
	}
	private before(a: [number, number], b: [number, number]) {
		return a[1] < b[1] || (a[1] === b[1] && a[0] < b[0]);
	}
	push(node: number, cost: number) {
		const entry: [number, number] = [node, cost];
		let i = this.entries.length;
		this.entries.push(entry);
		while (i) {
			const parent = (i - 1) >>> 1;
			if (!this.before(entry, this.entries[parent])) break;
			this.entries[i] = this.entries[parent];
			i = parent;
		}
		this.entries[i] = entry;
	}
	pop() {
		const first = this.entries[0],
			last = this.entries.pop();
		if (this.entries.length && last) {
			let i = 0;
			while (i * 2 + 1 < this.entries.length) {
				let child = i * 2 + 1;
				if (
					child + 1 < this.entries.length &&
					this.before(this.entries[child + 1], this.entries[child])
				)
					child++;
				if (!this.before(this.entries[child], last)) break;
				this.entries[i] = this.entries[child];
				i = child;
			}
			this.entries[i] = last;
		}
		return first;
	}
}

export function searchBackbone(
	model: Backbone,
	origin: Origin,
	budget: number,
) {
	if (!Number.isFinite(budget) || budget < 0)
		throw new RangeError("Invalid time budget");
	const started = performance.now();
	const input = attachments(model, origin),
		count = size(model),
		graph = model.graph;
	const labels = new Float64Array(
		count + graph.nodeCoordinates.length / 2,
	).fill(Infinity);
	const parents = new Int32Array(labels.length).fill(-1),
		queue = new Queue();
	for (const seed of input.seeds) {
		labels[seed.node] = seed.minutes;
		queue.push(seed.node, seed.minutes);
	}
	let settled = 0;
	while (queue.length) {
		const [node, cost] = queue.pop();
		if (cost !== labels[node]) continue;
		if (cost > budget) break;
		settled++;
		for (const edge of backboneTransitions(model, node)) {
			if (!(edge.minutes > 0 && Number.isFinite(edge.minutes)))
				throw new RangeError("Invalid candidate edge cost");
			const next = cost + edge.minutes;
			if (next <= budget && next < labels[edge.target]) {
				labels[edge.target] = next;
				parents[edge.target] = node;
				queue.push(edge.target, next);
			}
		}
	}
	const searchMs = performance.now() - started;
	const cellMinutes = labels.slice(0, count);
	const mark = (point: Point, time: number) => {
		const cell = pointCell(model.base, point);
		if (cell >= 0 && time < cellMinutes[cell]) cellMinutes[cell] = time;
	};
	for (let arc = 0; arc < graph.arcFrom.length; arc++) {
		const a = labels[count + graph.arcFrom[arc]],
			b = labels[count + graph.arcTo[arc]];
		if (Math.min(a, b) > budget) continue;
		const at = (km: number) =>
			Math.min(
				a + (graph.arcMinutes[arc] * km) / graph.arcRoadKm[arc],
				b + graph.arcMinutes[arc] * (1 - km / graph.arcRoadKm[arc]),
			);
		for (const segment of sourceSegments(graph, arc)) {
			const start = at(segment.startKm),
				end = at(segment.endKm);
			mark(segment.a, start);
			mark(segment.b, end);
			mark(interpolate(segment.a, segment.b, 0.5), Math.min(start, end));
		}
	}
	cellMinutes[pointCell(model.base, input.point)] = 0;
	return {
		labels,
		parents,
		cellMinutes,
		input,
		origin,
		budget,
		settled,
		searchMs,
		displayMs: performance.now() - started - searchMs,
	};
}
export type BackboneField = ReturnType<typeof searchBackbone>;

export function backboneContour(
	model: Backbone,
	field: BackboneField,
	budget: number,
) {
	if (budget > field.budget || budget < 0 || !Number.isFinite(budget))
		throw new RangeError("Budget exceeds the computed field");
	const { base } = model,
		mask = new Uint8Array(size(model));
	let reachedCells = 0;
	const own = pointCell(base, field.input.point);
	for (let i = 0; i < mask.length; i++)
		if (
			(i === own || (base.displayLand ?? base.land)[i]) &&
			field.cellMinutes[i] <= budget
		) {
			mask[i] = 1;
			reachedCells++;
		}
	return {
		mask,
		reachedCells,
		coordinates: cellContours(
			mask,
			base.width,
			base.height,
			base.bounds[0],
			base.bounds[1],
			base.step,
		),
	};
}

export function pointTiming(
	model: Backbone,
	field: BackboneField,
	destination: Origin,
) {
	const output = attachments(model, destination);
	let minutes = Infinity,
		terminal: Seed | undefined,
		direct: { from: Access; to: Access; road: number } | undefined;
	for (const seed of output.seeds) {
		const total = field.labels[seed.node] + seed.minutes;
		if (total < minutes) {
			minutes = total;
			terminal = seed;
		}
	}
	for (const from of field.input.accesses)
		for (const to of output.accesses) {
			if (from.arc !== to.arc) continue;
			const road = sourceMinutes(
				model.graph,
				from.arc,
				Math.abs(from.km - to.km),
				from.point,
				to.point,
			);
			const total = rounded(from.localMinutes + road + to.localMinutes);
			if (total < minutes) {
				minutes = total;
				direct = { from, to, road };
				terminal = undefined;
			}
		}
	if (!Number.isFinite(minutes)) return null;
	const components = {
		origin: 0,
		road: 0,
		local: 0,
		transfer: 0,
		destination: 0,
	};
	const edges: BackboneEdge[] = [];
	if (direct) {
		components.origin = direct.from.localMinutes;
		components.road = direct.road;
		components.destination = minutes - components.origin - components.road;
	} else if (terminal) {
		components.destination = terminal.minutes;
		let node = terminal.node;
		while (field.parents[node] >= 0) {
			const parent = field.parents[node];
			const edge = [...backboneTransitions(model, parent)].find(
				(e) =>
					e.target === node &&
					Math.abs(field.labels[parent] + e.minutes - field.labels[node]) <
						1e-8,
			);
			if (
				!edge ||
				!(field.labels[parent] < field.labels[node]) ||
				edges.length >= field.labels.length
			)
				throw new Error("Candidate path does not reconstruct");
			edges.push(edge);
			components[edge.kind] += edge.minutes;
			node = parent;
		}
		const seed = field.input.seeds.find(
			(s) => s.node === node && Math.abs(s.minutes - field.labels[node]) < 1e-8,
		);
		if (!seed) throw new Error("Candidate path has no origin attachment");
		components.origin = seed.minutes;
		edges.reverse();
	}
	if (
		Math.abs(Object.values(components).reduce((a, b) => a + b, 0) - minutes) >
		1e-8
	)
		throw new Error("Candidate path sum mismatch");
	return {
		minutes,
		components,
		edges,
		direct: direct
			? { arc: direct.from.arc, from: direct.from.point, to: direct.to.point }
			: null,
	};
}
