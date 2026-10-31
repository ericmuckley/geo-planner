// Experimental runtime version; checksum-bound source producers stay unchanged.
import { distanceKm, type GridData } from "./coarse-grid";

export type Point = [number, number];
export type BackboneGraph = {
	nodeCoordinates: Float64Array;
	arcFrom: Uint32Array;
	arcTo: Uint32Array;
	arcRoadKm: Float64Array;
	arcMinutes: Float64Array;
	arcSpeedKph: Uint8Array;
	arcByteOffsets: Uint32Array;
	arcInteriorOffsets: Uint32Array;
	interiorSourceKm: Float64Array;
	geometryBytes: Uint8Array;
	partArcOffsets: Uint32Array;
	crossingFirstArc: Uint32Array;
	endpointAdjOffsets: Uint32Array;
	endpointAdjArcs: Uint32Array;
	cellIds: Uint32Array;
	cellArcOffsets: Uint32Array;
	cellArcs: Uint32Array;
};
export type Backbone = {
	base: GridData;
	graph: BackboneGraph;
	originalNodes: number;
};

export function nodePoint(graph: BackboneGraph, node: number): Point {
	return [graph.nodeCoordinates[node * 2], graph.nodeCoordinates[node * 2 + 1]];
}

export function pointCell(grid: GridData, point: number[]) {
	const x = Math.floor((point[0] - grid.bounds[0]) / grid.step);
	const y = Math.floor((point[1] - grid.bounds[1]) / grid.step);
	return x >= 0 && x < grid.width && y >= 0 && y < grid.height
		? y * grid.width + x
		: -1;
}

// A protected crossing belongs to both closed cells, without merging road IDs.
export function pointCells(grid: GridData, point: number[]) {
	const x = (point[0] - grid.bounds[0]) / grid.step;
	const y = (point[1] - grid.bounds[1]) / grid.step;
	const axis = (value: number) =>
		Math.abs(value - Math.round(value)) <= 1e-8
			? [Math.round(value) - 1, Math.round(value)]
			: [Math.floor(value)];
	return axis(y).flatMap((yy) =>
		axis(x).flatMap((xx) =>
			xx >= 0 && xx < grid.width && yy >= 0 && yy < grid.height
				? [yy * grid.width + xx]
				: [],
		),
	);
}

export function* cellArcs(graph: BackboneGraph, cell: number) {
	let low = 0,
		high = graph.cellIds.length;
	while (low < high) {
		const middle = (low + high) >>> 1;
		if (graph.cellIds[middle] < cell) low = middle + 1;
		else high = middle;
	}
	if (graph.cellIds[low] !== cell) return;
	for (
		let i = graph.cellArcOffsets[low];
		i < graph.cellArcOffsets[low + 1];
		i++
	)
		yield graph.cellArcs[i];
}

export function* nodeArcs(model: Backbone, node: number) {
	const graph = model.graph;
	if (node < model.originalNodes) {
		for (
			let i = graph.endpointAdjOffsets[node];
			i < graph.endpointAdjOffsets[node + 1];
			i++
		)
			yield graph.endpointAdjArcs[i];
	} else {
		const first = graph.crossingFirstArc[node - model.originalNodes];
		yield first;
		yield first + 1;
	}
}

function roundEven(value: number) {
	const lower = Math.floor(value),
		fraction = value - lower;
	return fraction === 0.5
		? lower % 2 === 0
			? lower
			: lower + 1
		: Math.round(value);
}

export type SourceSegment = {
	a: Point;
	b: Point;
	startKm: number;
	endKm: number;
};

export function* sourceSegments(
	graph: BackboneGraph,
	arc: number,
): Generator<SourceSegment> {
	if (!Number.isInteger(arc) || arc < 0 || arc >= graph.arcFrom.length)
		throw new RangeError("Invalid source arc");
	let a = nodePoint(graph, graph.arcFrom[arc]);
	let x = roundEven(a[0] * 100000),
		y = roundEven(a[1] * 100000);
	let offset = graph.arcByteOffsets[arc];
	const end = graph.arcByteOffsets[arc + 1];
	const signed = () => {
		let value = 0,
			shift = 0;
		while (offset < end) {
			const byte = graph.geometryBytes[offset++];
			if (shift > 28 || (shift === 28 && byte > 15))
				throw new RangeError("Geometry varint overflow");
			value += (byte & 127) * 2 ** shift;
			if (!(byte & 128)) {
				if (shift && byte === 0)
					throw new RangeError("Noncanonical geometry varint");
				return value % 2 ? -(value + 1) / 2 : value / 2;
			}
			shift += 7;
		}
		throw new RangeError("Truncated geometry varint");
	};
	let startKm = 0;
	for (
		let i = graph.arcInteriorOffsets[arc];
		i < graph.arcInteriorOffsets[arc + 1];
		i++
	) {
		x += signed();
		y += signed();
		const b: Point = [x / 100000, y / 100000];
		const endKm = graph.interiorSourceKm[i];
		if (
			!Number.isFinite(endKm) ||
			endKm < startKm ||
			endKm > graph.arcRoadKm[arc]
		)
			throw new RangeError("Invalid cumulative source distance");
		yield { a, b, startKm, endKm };
		a = b;
		startKm = endKm;
	}
	if (offset !== end)
		throw new RangeError("Geometry coordinate count mismatch");
	yield {
		a,
		b: nodePoint(graph, graph.arcTo[arc]),
		startKm,
		endKm: graph.arcRoadKm[arc],
	};
}

export function project(point: number[], a: number[], b: number[]) {
	const scale = Math.cos((point[1] * Math.PI) / 180);
	const dx = (b[0] - a[0]) * scale,
		dy = b[1] - a[1];
	const squared = dx * dx + dy * dy;
	return squared
		? Math.max(
				0,
				Math.min(
					1,
					((point[0] - a[0]) * scale * dx + (point[1] - a[1]) * dy) / squared,
				),
			)
		: 0;
}

export function interpolate(a: number[], b: number[], t: number): Point {
	return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
}

export function sourceMinutes(
	graph: BackboneGraph,
	arc: number,
	km: number,
	a: Point,
	b: Point,
) {
	return Math.max(
		graph.arcMinutes[arc] * (km / graph.arcRoadKm[arc]),
		(distanceKm(a, b) / graph.arcSpeedKph[arc]) * 60,
	);
}
