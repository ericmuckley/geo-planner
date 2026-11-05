/** Approximate geography hypothesis, offline only; no road permissions or costs. */
import assert from "node:assert/strict";
import {
	landConnection,
	prepareGeography,
} from "../src/server/coarse-geography.ts";
import { waterCellFlags } from "./coarse_osm_water_lookup_v1.ts";
import type {
	loadWaterRasterV2,
	RasterCoordinate,
} from "./coarse_osm_water_raster_loader_v2.ts";

type Geography = Parameters<typeof landConnection>[0];
type Packet = Pick<
	Awaited<ReturnType<typeof loadWaterRasterV2>>,
	"grid" | "lookup" | "sourceIncompleteFeatures"
> &
	Partial<Pick<Awaited<ReturnType<typeof loadWaterRasterV2>>, "cellFlags">>;

export function prepareWaterGeographyV3(source: Geography, packet: Packet) {
	const country = { boundary: source.boundary, lakes: [] };
	prepareGeography(source);
	prepareGeography(country);
	const rings = [...source.boundary, ...source.lakes].flatMap((polygon) =>
		polygon.map((points) => {
			let x1 = Infinity,
				y1 = Infinity,
				x2 = -Infinity,
				y2 = -Infinity;
			for (const [x, y] of points) {
				x1 = Math.min(x1, x);
				y1 = Math.min(y1, y);
				x2 = Math.max(x2, x);
				y2 = Math.max(y2, y);
			}
			const firstBand = Math.floor(y1 * 100),
				lastBand = Math.floor(y2 * 100);
			const pending = Array.from(
				{ length: lastBand - firstBand + 1 },
				() => [] as number[],
			);
			for (let index = 1; index < points.length; index++) {
				const low = Math.floor(
					Math.min(points[index - 1][1], points[index][1]) * 100,
				);
				const high = Math.floor(
					Math.max(points[index - 1][1], points[index][1]) * 100,
				);
				for (let row = low; row <= high; row++)
					pending[row - firstBand].push(index);
			}
			const bands = pending.map((values) => Uint32Array.from(values));
			return { points, x1, y1, x2, y2, firstBand, bands };
		}),
	);
	const coordinate = (point: readonly number[]) => {
		assert.ok(
			point.length === 2 &&
				point.every(Number.isFinite) &&
				Math.abs(point[0]) <= 180 &&
				Math.abs(point[1]) <= 90,
		);
		return [point[0], point[1]] as [number, number];
	};
	const contains = (point: RasterCoordinate) => {
		const xy = coordinate(point);
		if (!landConnection(country, xy, xy)) return false;
		const flags = waterCellFlags(packet, point);
		if (flags === null || flags & 2) return landConnection(source, xy, xy);
		return !(flags & 1);
	};
	const connection = (
		from: RasterCoordinate,
		to: RasterCoordinate,
		maxWaterPrefix = 0,
	) => {
		const a = coordinate(from),
			b = coordinate(to);
		assert.ok(
			Number.isFinite(maxWaterPrefix) &&
				maxWaterPrefix >= 0 &&
				maxWaterPrefix <= 1,
		);
		if (!landConnection(country, a, b, maxWaterPrefix) || !contains(to))
			return false;
		const dx = b[0] - a[0],
			dy = b[1] - a[1];
		if (!dx && !dy) return true;
		const cuts = [0, 1],
			{ grid } = packet;
		for (const [axis, origin, count] of [
			[0, grid.xE7, grid.columns],
			[1, grid.yE7, grid.rows],
		] as const) {
			const delta = b[axis] - a[axis];
			if (!delta) continue;
			const low = Math.min(a[axis], b[axis]) * 1e7,
				high = Math.max(a[axis], b[axis]) * 1e7;
			const first = Math.max(0, Math.ceil((low - origin) / grid.stepE7)),
				last = Math.min(count, Math.floor((high - origin) / grid.stepE7));
			for (let index = first; index <= last; index++) {
				const fraction =
					((origin + index * grid.stepE7) / 1e7 - a[axis]) / delta;
				if (fraction > 0 && fraction < 1) cuts.push(fraction);
			}
		}
		// Preserve the original coarse polygon intersection arithmetic/tolerances.
		// Their crossings are needed inside fallback cells, even for narrow water.
		for (const ring of rings) {
			if (
				ring.x2 < Math.min(a[0], b[0]) ||
				ring.x1 > Math.max(a[0], b[0]) ||
				ring.y2 < Math.min(a[1], b[1]) ||
				ring.y1 > Math.max(a[1], b[1])
			)
				continue;
			const first = Math.max(
				ring.firstBand,
				Math.floor(Math.min(a[1], b[1]) * 100),
			);
			const last = Math.min(
				ring.firstBand + ring.bands.length - 1,
				Math.floor(Math.max(a[1], b[1]) * 100),
			);
			for (let row = first; row <= last; row++)
				for (const index of ring.bands[row - ring.firstBand]) {
					// Same closed latitude bands and once-only rule as coarse crossingEdges.
					if (
						row !== first &&
						row !==
							Math.floor(
								Math.min(ring.points[index - 1][1], ring.points[index][1]) *
									100,
							)
					)
						continue;
					const c = ring.points[index - 1],
						d = ring.points[index],
						ex = d[0] - c[0],
						ey = d[1] - c[1];
					const denominator = dx * ey - dy * ex;
					if (Math.abs(denominator) < 1e-15) continue;
					const cx = c[0] - a[0],
						cy = c[1] - a[1],
						t = (cx * ey - cy * ex) / denominator,
						u = (cx * dy - cy * dx) / denominator;
					if (t >= 0 && t <= 1 && u >= 0 && u <= 1) cuts.push(t);
				}
		}
		assert.ok(cuts.length <= 250000, "Water geography partition cap");
		cuts.sort((x, y) => x - y);
		let reachedLand = false;
		for (let index = 1; index < cuts.length; index++) {
			const start = cuts[index - 1],
				end = cuts[index];
			if (end - start < 1e-10) continue;
			const middle = (start + end) / 2;
			if (contains([a[0] + dx * middle, a[1] + dy * middle]))
				reachedLand = true;
			else if (reachedLand || end > maxWaterPrefix + 1e-10) return false;
		}
		return reachedLand;
	};
	return {
		contains,
		indexBackingBytes: rings.reduce(
			(sum, ring) =>
				sum +
				ring.bands.reduce((bytes, values) => bytes + values.byteLength, 0),
			0,
		),
		landConnection: connection,
		sourceIncompleteFeatureCount: packet.sourceIncompleteFeatures.length,
		scope:
			"Approximate source-water hypothesis with unchanged country/coast and coarse fallback in uncertain/uncovered cells. Global missing-source data remains unqualified. No real-land/access/road/ETA/app admission.",
	};
}
