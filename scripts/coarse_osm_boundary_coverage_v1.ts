/** Visual partial-cell coverage only; a closed center never becomes traversable. */
import {
	bit,
	center,
	DIRECTIONS,
	setBit,
} from "./coarse_osm_display_grid_v3.ts";
import type { DisplayProbe } from "./coarse_osm_filled_display_v1.ts";
import {
	connectorPrice,
	type OriginGeography,
} from "./coarse_osm_origin_connections_v2.ts";
import { landConnection } from "./coarse_osm_routing_geography_v1.ts";
import type { Coordinate } from "./coarse_osm_spherical_v1.ts";

const OFFSETS = [
	[0.25, 0.25],
	[0.75, 0.25],
	[0.25, 0.75],
	[0.75, 0.75],
] as const;

export type BoundaryCoverageWitness = {
	cell: number;
	fromCell: number;
	sample: number;
	from: Coordinate;
	to: Coordinate;
	fromSeconds: number;
	connectorSeconds: number;
};

export function addPaidBoundaryCoverage(
	geography: OriginGeography,
	grid: DisplayProbe,
	horizonSeconds: number,
	check: () => void = () => {},
	witness?: (value: BoundaryCoverageWitness) => void,
) {
	const { frame, times, land, coverage } = grid;
	const count = frame.width * frame.height;
	if (
		!Number.isSafeInteger(count) ||
		count < 1 ||
		frame.step <= 0 ||
		times.length !== count ||
		land.length < Math.ceil(count / 8) ||
		coverage.length < Math.ceil(count / 8) ||
		!Number.isInteger(horizonSeconds) ||
		horizonSeconds < 0 ||
		horizonSeconds > 54000
	)
		throw new Error("Boundary coverage domain");
	const stats = {
		closedUncoveredCells: 0,
		adjacentToFiniteCenter: 0,
		samplesTested: 0,
		landSamples: 0,
		paidConnectionsTested: 0,
		addedCells: 0,
	};
	for (let cell = 0; cell < count; cell++) {
		if ((cell & 65535) === 0) check();
		if (bit(land, cell) || bit(coverage, cell)) continue;
		if (times[cell] !== 65535)
			throw new Error("Closed display center has a local arrival");
		stats.closedUncoveredCells++;
		const x = cell % frame.width;
		const y = Math.floor(cell / frame.width);
		let adjacent = false;
		for (const [dx, dy] of DIRECTIONS) {
			const nx = x + dx;
			const ny = y + dy;
			if (nx < 0 || ny < 0 || nx >= frame.width || ny >= frame.height) continue;
			const fromCell = ny * frame.width + nx;
			if (bit(land, fromCell) && times[fromCell] <= horizonSeconds) {
				adjacent = true;
				break;
			}
		}
		if (!adjacent) continue;
		stats.adjacentToFiniteCenter++;
		let added = false;
		for (const [sample, [ox, oy]] of OFFSETS.entries()) {
			const to: [number, number] = [
				(frame.west + (x + ox) * frame.step) / 1e6,
				(frame.south + (y + oy) * frame.step) / 1e6,
			];
			stats.samplesTested++;
			if (!landConnection(geography, to, to)) continue;
			stats.landSamples++;
			for (const [dx, dy] of DIRECTIONS) {
				const nx = x + dx;
				const ny = y + dy;
				if (nx < 0 || ny < 0 || nx >= frame.width || ny >= frame.height)
					continue;
				const fromCell = ny * frame.width + nx;
				if (!bit(land, fromCell) || times[fromCell] > horizonSeconds) continue;
				const from = center(frame, fromCell);
				const seconds = Math.ceil(connectorPrice(from, to).ticks / 8);
				if (times[fromCell] + seconds > horizonSeconds) continue;
				stats.paidConnectionsTested++;
				if (!landConnection(geography, from, to)) continue;
				witness?.({
					cell,
					fromCell,
					sample,
					from,
					to,
					fromSeconds: times[fromCell],
					connectorSeconds: seconds,
				});
				setBit(coverage, cell);
				stats.addedCells++;
				added = true;
				break;
			}
			if (added) break;
		}
	}
	return stats;
}
