/** Same cell union as the deployed contour tracer, with caller-owned scratch/caps. */
import { containsRing } from "../src/server/coarse-contours.ts";
import { DisplayLimit, type Frame } from "./coarse_osm_display_grid_v1.ts";

type Position = [number, number];
export type DisplayPolygon = Position[][];
export type ContourLimits = { edges: number; rings: number; vertices: number };
const area = (ring: Position[]) => {
	let value = 0;
	for (let i = 1; i < ring.length; i++)
		value += ring[i - 1][0] * ring[i][1] - ring[i][0] * ring[i - 1][1];
	return value / 2;
};
const straight = (a: Position, b: Position, c: Position) =>
	(a[0] === b[0] && b[0] === c[0]) || (a[1] === b[1] && b[1] === c[1]);

export function boundedContours(
	mask: Uint8Array,
	edges: Uint8Array,
	frame: Frame,
	limits: ContourLimits,
	check: () => void,
	bounds?: readonly number[],
) {
	const { width, height, west, south, step } = frame;
	const stride = width + 1,
		size = stride * (height + 1);
	if (edges.length < size || mask.length < width * height)
		throw new Error("Contour workspace shape");
	edges.fill(0, 0, size);
	let edgeCount = 0;
	const add = (vertex: number, direction: number) => {
		if (++edgeCount > limits.edges)
			throw new DisplayLimit("contour edge capacity");
		edges[vertex] |= 1 << direction;
	};
	for (let y = 0; y < height; y++) {
		if ((y & 63) === 0) check();
		for (let x = 0; x < width; x++) {
			const cell = y * width + x;
			if (!mask[cell]) continue;
			if (!y || !mask[cell - width]) add(y * stride + x, 0);
			if (x === width - 1 || !mask[cell + 1]) add(y * stride + x + 1, 1);
			if (y === height - 1 || !mask[cell + width])
				add((y + 1) * stride + x + 1, 2);
			if (!x || !mask[cell - 1]) add((y + 1) * stride + x, 3);
		}
	}
	const rings: Position[][] = [],
		moves = [1, stride, -1, -stride];
	let vertices = 0;
	for (let start = 0; start < size; start++)
		while (edges[start]) {
			check();
			if (rings.length >= limits.rings)
				throw new DisplayLimit("contour ring capacity");
			const ring: Position[] = [];
			let vertex = start,
				direction = Math.floor(Math.log2(edges[start] & -edges[start]));
			do {
				let x = (west + (vertex % stride) * step) / 1e6;
				let y = (south + Math.floor(vertex / stride) * step) / 1e6;
				if (bounds) {
					x = Math.max(bounds[0], Math.min(bounds[2], x));
					y = Math.max(bounds[1], Math.min(bounds[3], y));
				}
				const point: Position = [x, y];
				if (
					ring.length > 1 &&
					straight(ring[ring.length - 2], ring[ring.length - 1], point)
				)
					ring.pop();
				ring.push(point);
				if (vertices + ring.length + 1 > limits.vertices)
					throw new DisplayLimit("contour vertex capacity");
				edges[vertex] &= ~(1 << direction);
				vertex += moves[direction];
				if (vertex === start) break;
				let next = -1;
				for (const turn of [1, 0, 3, 2])
					if (edges[vertex] & (1 << ((direction + turn) % 4))) {
						next = (direction + turn) % 4;
						break;
					}
				if (next < 0) throw new Error("Open display contour");
				direction = next;
			} while (vertex !== start);
			if (
				ring.length > 1 &&
				straight(ring[ring.length - 2], ring[ring.length - 1], ring[0])
			)
				ring.pop();
			ring.push(ring[0]);
			vertices += ring.length;
			rings.push(ring);
		}
	const polygons: DisplayPolygon[] = rings
		.filter((ring) => area(ring) > 0)
		.map((ring) => [ring]);
	for (const hole of rings.filter((ring) => area(ring) < 0)) {
		let parent: DisplayPolygon | undefined,
			smallest = Infinity;
		for (const polygon of polygons)
			if (containsRing(hole[0], polygon[0])) {
				const size = area(polygon[0]);
				if (size < smallest) {
					smallest = size;
					parent = polygon;
				}
			}
		if (!parent) throw new Error("Display hole has no exterior");
		parent.push(hole);
	}
	return { polygons, edgeCount, rings: rings.length, vertices };
}
