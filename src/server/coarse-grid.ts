import type { Origin } from "../lib/reachability";
import { cellContours, containsPolygon } from "./coarse-contours";
import { landConnection } from "./coarse-geography";

export type RoadVisit = {
	speedKph: number;
	anchorIndex: number;
	points: number[][];
	cumulativeKm: number[];
};

export type GridAttachment = {
	cell: number;
	distanceKm: number;
	minutes: number;
	roadKm?: number;
};

export type GridData = {
	bounds: number[];
	width: number;
	height: number;
	step: number;
	localSpeedKph: number;
	land: Uint8Array;
	traversable: Uint8Array;
	links: Uint8Array;
	roadDeciseconds?: Uint16Array;
	displayLand?: Uint8Array;
	anchorOffsets?: Int16Array;
	shoreLinks?: Uint8Array;
	roadAccess?: number[][];
	roadVisits?: Map<number, RoadVisit>;
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

export function gridPosition(grid: GridData, cell: number) {
	return [
		grid.bounds[0] +
			((cell % grid.width) + 0.5) * grid.step +
			(grid.anchorOffsets?.[cell * 2] ?? 0) / 100000,
		grid.bounds[1] +
			(Math.floor(cell / grid.width) + 0.5) * grid.step +
			(grid.anchorOffsets?.[cell * 2 + 1] ?? 0) / 100000,
	];
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

export function gridAttachments(
	grid: GridData,
	origin: Origin,
): GridAttachment[] {
	const x = Math.floor((origin.lon - grid.bounds[0]) / grid.step);
	const y = Math.floor((origin.lat - grid.bounds[1]) / grid.step);
	if (x < 0 || x >= grid.width || y < 0 || y >= grid.height) return [];
	const cell = y * grid.width + x;
	const point = [origin.lon, origin.lat];
	const candidate = (target: number) => {
		const km = distanceKm(point, gridPosition(grid, target));
		return {
			cell: target,
			distanceKm: km,
			minutes: (km / grid.localSpeedKph) * 60,
		};
	};
	if (!grid.shoreLinks) return [candidate(cell)];
	const supported = (attachment: { cell: number; distanceKm: number }) =>
		grid.traversable[attachment.cell] &&
		landConnection(
			grid,
			point,
			gridPosition(grid, attachment.cell),
			1 / Math.max(attachment.distanceKm, 1),
		);
	const own = candidate(cell);
	const ownSupported = supported(own);
	if (ownSupported && !grid.roadVisits) return [own];
	// An adjacent representative is usable only with a continuous land connection.
	// A known island cannot attach across even a narrow channel to the mainland.
	const neighborCells = directions.flatMap(([dx, dy]) => {
		const xx = x + dx,
			yy = y + dy;
		return xx >= 0 && xx < grid.width && yy >= 0 && yy < grid.height
			? [yy * grid.width + xx]
			: [];
	});
	const nearby: GridAttachment[] = ownSupported
		? [own]
		: neighborCells.map(candidate).filter(supported);
	const cells = new Set([cell, ...neighborCells]);
	for (const [target, lon, lat, roadKm] of grid.roadAccess ?? []) {
		if (ownSupported || !cells.has(target)) continue;
		const localKm = distanceKm(point, [lon, lat]);
		if (landConnection(grid, point, [lon, lat], 1 / Math.max(localKm, 1)))
			nearby.push({
				cell: target,
				distanceKm: localKm + roadKm,
				minutes: ((localKm + roadKm) / grid.localSpeedKph) * 60,
			});
	}
	const visit = grid.roadVisits?.get(cell);
	if (visit) nearby.push(...roadAttachments(grid, point, cell, visit));
	const best = new Map<number, GridAttachment>();
	for (const attachment of nearby)
		if (attachment.minutes < (best.get(attachment.cell)?.minutes ?? Infinity))
			best.set(attachment.cell, attachment);
	return [...best.values()].sort((a, b) => a.minutes - b.minutes);
}

function roadAttachments(
	grid: GridData,
	point: number[],
	cell: number,
	visit: RoadVisit,
): GridAttachment[] {
	const result = [];
	const scale = Math.cos(point[1] * radians);
	for (let i = 1; i < visit.points.length; i++) {
		const a = visit.points[i - 1],
			b = visit.points[i];
		const dx = (b[0] - a[0]) * scale,
			dy = b[1] - a[1];
		const length = dx * dx + dy * dy;
		const t = length
			? Math.max(
					0,
					Math.min(
						1,
						((point[0] - a[0]) * scale * dx + (point[1] - a[1]) * dy) / length,
					),
				)
			: 0;
		// Endpoints remain candidates when the nearest projection is generalized
		// water or its local connector crosses a channel. Only the retained road
		// geometry may cross water between the access point and canonical anchor.
		for (const part of new Set([0, t, 1])) {
			const projected = [a[0] + (b[0] - a[0]) * part, a[1] + dy * part];
			const localKm = distanceKm(point, projected);
			if (!landConnection(grid, point, projected, 1 / Math.max(localKm, 1)))
				continue;
			const roadKm =
				i <= visit.anchorIndex
					? visit.cumulativeKm[visit.anchorIndex] -
						visit.cumulativeKm[i] +
						distanceKm(projected, b)
					: visit.cumulativeKm[i - 1] -
						visit.cumulativeKm[visit.anchorIndex] +
						distanceKm(a, projected);
			result.push({
				cell,
				distanceKm: localKm + roadKm,
				minutes:
					Math.ceil(
						(localKm / grid.localSpeedKph + roadKm / visit.speedKph) * 36000,
					) / 600,
				roadKm,
			});
		}
	}
	return result;
}

export function attachGrid(grid: GridData, origin: Origin) {
	return gridAttachments(grid, origin)[0];
}

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
	// Retain legacy seed activation for v1/v2 comparison. V3 uses checked input
	// access and keeps shared land/traversal masks unchanged.
	const land =
		grid.shoreLinks || grid.land[seed] ? grid.land : grid.land.slice();
	const traversable =
		grid.shoreLinks || grid.traversable[seed]
			? grid.traversable
			: grid.traversable.slice();
	if (!grid.shoreLinks) land[seed] = traversable[seed] = 1;
	const attachments = gridAttachments(grid, origin);
	const attachmentKm = attachments[0]?.distanceKm ?? 0;
	// Seed every supported fallback: the nearest land patch may be a dead end
	// while a slightly longer explicit bridge access reaches the road network.
	for (const attachment of attachments) {
		const initialCost = attachment.minutes;
		labels[attachment.cell] = initialCost;
		queue.push(attachment.cell, initialCost);
	}
	if (!attachments.length) labels[seed] = 0; // Display an isolated input cell without expanding it.
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
			const link = d < 4 ? cell * 4 + d : target * 4 + d - 4;
			const roadSpeed = links[link];
			const overland =
				!!(
					(grid.shoreLinks?.[Math.floor(link / 4)] ?? 0) &
					(1 << (link % 4))
				) ||
				(land[cell] &&
					land[target] &&
					(!dx || !dy || (land[cy * width + xx] && land[yy * width + cx])));
			const roadMinutes = grid.roadDeciseconds
				? (grid.roadDeciseconds[link] || Infinity) / 600
				: roadSpeed
					? (lengths[cy][d] / roadSpeed) * 60
					: Infinity;
			const localMinutes = overland
				? ((grid.anchorOffsets
						? distanceKm(gridPosition(grid, cell), gridPosition(grid, target))
						: lengths[cy][d]) /
						grid.localSpeedKph) *
					60
				: Infinity;
			const next = cost + Math.min(roadMinutes, localMinutes);
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
		if (
			(i === seed && grid.shoreLinks) ||
			((i === seed || (grid.displayLand ?? land)[i]) && labels[i] <= budget)
		) {
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
