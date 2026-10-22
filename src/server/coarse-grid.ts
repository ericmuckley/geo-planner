import type { Origin } from "../lib/reachability";
import { cellContours, containsPolygon } from "./coarse-contours";

export type GridData = {
	bounds: number[];
	width: number;
	height: number;
	step: number;
	localSpeedKph: number;
	land: Uint8Array;
	traversable: Uint8Array;
	links: Uint8Array;
	boundary: number[][][][];
	lakes: number[][][][];
};

const radians = Math.PI / 180;
export function distanceKm(a: number[], b: number[]) {
	const lat = (b[1] - a[1]) * radians;
	const lon = (b[0] - a[0]) * radians;
	const h =
		Math.sin(lat / 2) ** 2 +
		Math.cos(a[1] * radians) *
			Math.cos(b[1] * radians) *
			Math.sin(lon / 2) ** 2;
	return 12_742 * Math.asin(Math.min(1, Math.sqrt(h)));
}

function nearBoundary(point: [number, number], polygon: number[][][]) {
	const scale = Math.cos(point[1] * radians);
	for (const ring of polygon) {
		for (let i = 1; i < ring.length; i++) {
			const a = ring[i - 1];
			const b = ring[i];
			if (
				point[1] < Math.min(a[1], b[1]) - 0.01 ||
				point[1] > Math.max(a[1], b[1]) + 0.01 ||
				point[0] < Math.min(a[0], b[0]) - 0.02 ||
				point[0] > Math.max(a[0], b[0]) + 0.02
			)
				continue;
			const dx = (b[0] - a[0]) * scale;
			const dy = b[1] - a[1];
			const length = dx * dx + dy * dy;
			const t = length
				? Math.max(
						0,
						Math.min(
							1,
							((point[0] - a[0]) * scale * dx + (point[1] - a[1]) * dy) /
								length,
						),
					)
				: 0;
			if (distanceKm(point, [a[0] + (b[0] - a[0]) * t, a[1] + dy * t]) <= 1)
				return true;
		}
	}
	return false;
}

class Queue {
	private cells: number[] = [];
	private costs: number[] = [];
	get length() {
		return this.cells.length;
	}
	push(cell: number, cost: number) {
		let index = this.cells.length;
		this.cells.push(cell);
		this.costs.push(cost);
		while (index > 0) {
			const parent = (index - 1) >> 1;
			if (this.costs[parent] <= cost) break;
			this.cells[index] = this.cells[parent];
			this.costs[index] = this.costs[parent];
			index = parent;
		}
		this.cells[index] = cell;
		this.costs[index] = cost;
	}
	pop(): [number, number] {
		const result: [number, number] = [this.cells[0], this.costs[0]];
		const lastCell = this.cells.pop();
		const lastCost = this.costs.pop();
		if (this.cells.length && lastCell !== undefined && lastCost !== undefined) {
			let index = 0;
			while (index * 2 + 1 < this.cells.length) {
				let child = index * 2 + 1;
				if (
					child + 1 < this.cells.length &&
					this.costs[child + 1] < this.costs[child]
				)
					child++;
				if (this.costs[child] >= lastCost) break;
				this.cells[index] = this.cells[child];
				this.costs[index] = this.costs[child];
				index = child;
			}
			this.cells[index] = lastCell;
			this.costs[index] = lastCost;
		}
		return result;
	}
}

const directions = [
	[1, 0],
	[1, 1],
	[0, 1],
	[-1, 1],
	[-1, 0],
	[-1, -1],
	[0, -1],
	[1, -1],
];

export function estimateGrid(grid: GridData, origin: Origin, budget: number) {
	const started = performance.now();
	const point: [number, number] = [origin.lon, origin.lat];
	if (
		!grid.boundary.some(
			(polygon) =>
				containsPolygon(point, polygon) || nearBoundary(point, polygon),
		) ||
		grid.lakes.some(
			(polygon) =>
				containsPolygon(point, polygon) && !nearBoundary(point, polygon),
		)
	)
		throw new RangeError(
			"Choose a land location in the contiguous United States.",
		);
	const [west, south] = grid.bounds;
	const { width, height, step, links } = grid;
	const center = (x: number, y: number) => [
		west + (x + 0.5) * step,
		south + (y + 0.5) * step,
	];
	const x = Math.floor((origin.lon - west) / step);
	const y = Math.floor((origin.lat - south) / step);
	const labels = new Float64Array(width * height).fill(Infinity);
	const queue = new Queue();
	if (x < 0 || x >= width || y < 0 || y >= height)
		throw new RangeError("Choose a location within the contiguous US grid.");
	const seed = y * width + x;
	// A verified coastal/island origin makes its own cell land for this query.
	// Never move an island origin to the mainland or mutate the shared dataset.
	const land = grid.land[seed] ? grid.land : grid.land.slice();
	const traversable = grid.traversable[seed]
		? grid.traversable
		: grid.traversable.slice();
	land[seed] = traversable[seed] = 1;
	const attachmentKm = distanceKm(point, center(x, y));
	const initialCost = (attachmentKm / grid.localSpeedKph) * 60;
	labels[seed] = initialCost;
	queue.push(seed, initialCost);
	// Distances depend on latitude and direction, not longitude. Compute once per row.
	const lengths = Array.from({ length: height }, (_, row) =>
		directions.map(([dx, dy]) =>
			distanceKm(center(0, row), center(dx, row + dy)),
		),
	);
	let settled = 0;
	while (queue.length) {
		const [cell, cost] = queue.pop();
		if (cost !== labels[cell]) continue;
		if (cost > budget) break;
		settled++;
		const cx = cell % width;
		const cy = Math.floor(cell / width);
		for (let d = 0; d < directions.length; d++) {
			const [dx, dy] = directions[d];
			const xx = cx + dx;
			const yy = cy + dy;
			if (xx < 0 || xx >= width || yy < 0 || yy >= height) continue;
			const target = yy * width + xx;
			if (!traversable[target]) continue;
			const roadSpeed = d < 4 ? links[cell * 4 + d] : links[target * 4 + d - 4];
			const overland =
				land[cell] &&
				land[target] &&
				(!dx || !dy || (land[cy * width + xx] && land[yy * width + cx]));
			const speed = Math.max(roadSpeed, overland ? grid.localSpeedKph : 0);
			if (!speed) continue;
			const next = cost + (lengths[cy][d] / speed) * 60;
			if (next <= budget && next < labels[target]) {
				labels[target] = next;
				queue.push(target, next);
			}
		}
	}
	const searchMs = performance.now() - started;
	const mask = new Uint8Array(width * height);
	let reachedCells = 0;
	for (let i = 0; i < labels.length; i++) {
		if (land[i] && labels[i] <= budget) {
			mask[i] = 1;
			reachedCells++;
		}
	}
	const coordinates = cellContours(mask, width, height, west, south, step);
	if (!coordinates.length)
		throw new RangeError("Choose a longer budget for this coarse-grid origin.");
	return {
		coordinates,
		labels,
		reachedCells,
		settled,
		attachmentKm,
		searchMs,
		contourMs: performance.now() - started - searchMs,
	};
}
