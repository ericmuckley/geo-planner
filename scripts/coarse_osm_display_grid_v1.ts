/** Bounded local-display grid; coordinates are integer microdegrees at edges. */
import { landConnection } from "../src/server/coarse-geography.ts";
import type { OriginGeography } from "./coarse_osm_origin_connections_v1.ts";
import { connectorPrice } from "./coarse_osm_origin_connections_v1.ts";
import type { Coordinate } from "./coarse_osm_spherical_v1.ts";

export type Frame = {
	west: number;
	south: number;
	step: number;
	width: number;
	height: number;
};
export class DisplayLimit extends Error {}
export const DIRECTIONS = [
	[1, 0],
	[1, 1],
	[0, 1],
	[-1, 1],
	[-1, 0],
	[-1, -1],
	[0, -1],
	[1, -1],
] as const;
export const bit = (bytes: Uint8Array, i: number) =>
	(bytes[i >>> 3] >>> (i & 7)) & 1;
export const setBit = (bytes: Uint8Array, i: number) => {
	bytes[i >>> 3] |= 1 << (i & 7);
};
export const nibble = (bytes: Uint8Array, i: number) =>
	(bytes[i >>> 1] >>> (4 * (i & 1))) & 15;
export function setNibble(bytes: Uint8Array, i: number, value: number) {
	const shift = 4 * (i & 1);
	bytes[i >>> 1] = (bytes[i >>> 1] & ~(15 << shift)) | (value << shift);
}
export function center(frame: Frame, i: number): [number, number] {
	return [
		(frame.west + ((i % frame.width) + 0.5) * frame.step) / 1e6,
		(frame.south + (Math.floor(i / frame.width) + 0.5) * frame.step) / 1e6,
	];
}
export function cellAt(frame: Frame, point: Coordinate) {
	const gx = (point[0] * 1e6 - frame.west) / frame.step;
	const gy = (point[1] * 1e6 - frame.south) / frame.step;
	const x = gx === frame.width ? frame.width - 1 : Math.floor(gx);
	const y = gy === frame.height ? frame.height - 1 : Math.floor(gy);
	return x >= 0 && x < frame.width && y >= 0 && y < frame.height
		? y * frame.width + x
		: -1;
}
export function makeFrame(bounds: readonly number[], step: number): Frame {
	const west = Math.floor((bounds[0] * 1e6) / step) * step;
	const south = Math.floor((bounds[1] * 1e6) / step) * step;
	return {
		west,
		south,
		step,
		width: Math.max(1, Math.ceil((Math.ceil(bounds[2] * 1e6) - west) / step)),
		height: Math.max(1, Math.ceil((Math.ceil(bounds[3] * 1e6) - south) / step)),
	};
}

/** Mark every closed cell touched by a straight polygon edge, including corner ties. */
export function markBoundary(
	frame: Frame,
	bytes: Uint8Array,
	a: number[],
	b: number[],
) {
	const ax = (a[0] * 1e6 - frame.west) / frame.step;
	const ay = (a[1] * 1e6 - frame.south) / frame.step;
	const bx = (b[0] * 1e6 - frame.west) / frame.step;
	const by = (b[1] * 1e6 - frame.south) / frame.step;
	if (Math.max(ax, bx) < 0 || Math.min(ax, bx) > frame.width) return;
	const first = Math.max(0, Math.floor(Math.min(ay, by) - 1e-8));
	const last = Math.min(frame.height - 1, Math.floor(Math.max(ay, by) + 1e-8));
	for (let y = first; y <= last; y++) {
		let lo = 0,
			hi = 1;
		if (ay !== by) {
			const u = (y - ay) / (by - ay),
				v = (y + 1 - ay) / (by - ay);
			lo = Math.max(0, Math.min(u, v));
			hi = Math.min(1, Math.max(u, v));
		}
		if (lo > hi) continue;
		const x1 = ax + (bx - ax) * lo,
			x2 = ax + (bx - ax) * hi;
		for (
			let x = Math.max(0, Math.floor(Math.min(x1, x2) - 1e-8));
			x <= Math.min(frame.width - 1, Math.floor(Math.max(x1, x2) + 1e-8));
			x++
		)
			setBit(bytes, y * frame.width + x);
	}
}

/** Scanline polygon union/holes, with original center membership semantics. */
export function rasterLand(
	frame: Frame,
	geography: OriginGeography,
	land: Uint8Array,
	boundary: Uint8Array,
	row: Uint8Array,
	check: () => void,
) {
	land.fill(0);
	boundary.fill(0);
	const fillRing = (ring: number[][], latitude: number, value: number) => {
		const crosses: number[] = [];
		for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
			const [xi, yi] = ring[i],
				[xj, yj] = ring[j];
			if (yi > latitude !== yj > latitude)
				crosses.push(((xj - xi) * (latitude - yi)) / (yj - yi) + xi);
		}
		crosses.sort((a, b) => a - b);
		for (let i = 0; i + 1 < crosses.length; i += 2) {
			const lo = Math.max(
				0,
				Math.ceil((crosses[i] * 1e6 - frame.west) / frame.step - 0.5),
			);
			const hi = Math.min(
				frame.width,
				Math.ceil((crosses[i + 1] * 1e6 - frame.west) / frame.step - 0.5),
			);
			row.fill(value, lo, Math.max(lo, hi));
		}
	};
	for (const [polygons, lake] of [
		[geography.boundary, false],
		[geography.lakes, true],
	] as const) {
		for (const polygon of polygons) {
			check();
			let south = Infinity,
				north = -Infinity;
			for (const ring of polygon)
				for (let i = 1; i < ring.length; i++) {
					south = Math.min(south, ring[i][1]);
					north = Math.max(north, ring[i][1]);
					markBoundary(frame, boundary, ring[i - 1], ring[i]);
				}
			const lo = Math.max(
				0,
				Math.ceil((south * 1e6 - frame.south) / frame.step - 0.5),
			);
			const hi = Math.min(
				frame.height,
				Math.ceil((north * 1e6 - frame.south) / frame.step - 0.5),
			);
			for (let y = lo; y < hi; y++) {
				row.fill(0, 0, frame.width);
				const lat = (frame.south + (y + 0.5) * frame.step) / 1e6;
				polygon.forEach((ring, i) => {
					fillRing(ring, lat, i === 0 ? 1 : 0);
				});
				for (let x = 0; x < frame.width; x++)
					if (row[x]) {
						const i = y * frame.width + x;
						if (lake) land[i >>> 3] &= ~(1 << (i & 7));
						else setBit(land, i);
					}
			}
		}
	}
}

/** Four undirected link bits per cell; boundary cells get continuous land checks. */
export function rasterLinks(
	frame: Frame,
	geography: OriginGeography,
	land: Uint8Array,
	boundary: Uint8Array,
	links: Uint8Array,
	check: () => void,
) {
	links.fill(0);
	for (let y = 0; y < frame.height; y++) {
		if ((y & 31) === 0) check();
		for (let x = 0; x < frame.width; x++) {
			const i = y * frame.width + x;
			if (!bit(land, i)) continue;
			let flags = 0;
			for (let d = 0; d < 4; d++) {
				const [dx, dy] = DIRECTIONS[d],
					nx = x + dx,
					ny = y + dy;
				if (nx < 0 || nx >= frame.width || ny >= frame.height) continue;
				const j = ny * frame.width + nx;
				if (
					bit(land, j) &&
					(!(bit(boundary, i) || bit(boundary, j)) ||
						landConnection(geography, center(frame, i), center(frame, j)))
				)
					flags |= 1 << d;
			}
			setNibble(links, i, flags);
		}
	}
}
export function hasLink(links: Uint8Array, i: number, j: number, d: number) {
	return (nibble(links, d < 4 ? i : j) & (1 << (d % 4))) !== 0;
}
export function localCosts(
	frame: Frame,
	horizontal: Uint16Array,
	diagonal: Uint16Array,
) {
	for (let y = 0; y < frame.height; y++) {
		const a = center(frame, y * frame.width);
		const b: Coordinate = [a[0] + frame.step / 1e6, a[1]];
		horizontal[y] = Math.ceil(connectorPrice(a, b).ticks / 8);
		diagonal[y] = Math.ceil(
			connectorPrice(a, [b[0], a[1] + frame.step / 1e6]).ticks / 8,
		);
	}
	const a = center(frame, 0);
	return Math.ceil(
		connectorPrice(a, [a[0], a[1] + frame.step / 1e6]).ticks / 8,
	);
}

/** Fixed backing buffers, including a caller-owned queue view when available. */
export class DisplayQueue {
	length = 0;
	peak = 0;
	constructor(
		readonly keys: Uint32Array,
		readonly costs: Uint32Array,
	) {}
	push(key: number, cost: number) {
		if (this.length === this.keys.length)
			throw new DisplayLimit("local heap capacity");
		let p = this.length++;
		this.peak = Math.max(this.peak, this.length);
		while (p > 0) {
			const parent = (p - 1) >>> 1;
			if (this.costs[parent] <= cost) break;
			this.keys[p] = this.keys[parent];
			this.costs[p] = this.costs[parent];
			p = parent;
		}
		this.keys[p] = key;
		this.costs[p] = cost;
	}
	pop(): [number, number] {
		if (!this.length) throw new Error("Empty display queue");
		const key = this.keys[0],
			cost = this.costs[0],
			last = --this.length;
		const k = this.keys[last],
			c = this.costs[last];
		let p = 0;
		while (2 * p + 1 < last) {
			let child = 2 * p + 1;
			if (child + 1 < last && this.costs[child + 1] < this.costs[child])
				child++;
			if (this.costs[child] >= c) break;
			this.keys[p] = this.keys[child];
			this.costs[p] = this.costs[child];
			p = child;
		}
		this.keys[p] = k;
		this.costs[p] = c;
		return [key, cost];
	}
}
export function fillLocal(
	frame: Frame,
	times: Uint16Array,
	parents: Uint8Array,
	links: Uint8Array,
	horizontal: Uint16Array,
	diagonal: Uint16Array,
	vertical: number,
	horizon: number,
	heap: DisplayQueue,
	check: () => void,
) {
	const count = frame.width * frame.height;
	for (let i = 0; i < count; i++)
		if (times[i] <= horizon) heap.push(i, times[i]);
	check();
	let settles = 0;
	while (heap.length) {
		const [i, time] = heap.pop();
		if (times[i] !== time) continue;
		if ((++settles & 4095) === 0) check();
		const x = i % frame.width,
			y = Math.floor(i / frame.width);
		for (let d = 0; d < 8; d++) {
			const [dx, dy] = DIRECTIONS[d],
				nx = x + dx,
				ny = y + dy;
			if (nx < 0 || nx >= frame.width || ny < 0 || ny >= frame.height) continue;
			const j = ny * frame.width + nx;
			if (!hasLink(links, i, j, d)) continue;
			const price =
				dy === 0
					? horizontal[y]
					: dx === 0
						? vertical
						: diagonal[Math.min(y, ny)];
			const candidate = time + price;
			if (candidate <= horizon && candidate < times[j]) {
				times[j] = candidate;
				setNibble(parents, j, (d + 4) % 8);
				heap.push(j, candidate);
			}
		}
	}
	return settles;
}
