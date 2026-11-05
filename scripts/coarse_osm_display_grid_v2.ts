/** Policy-aware raster paths; pure frame/queue/cost helpers remain sealed V1. */
import { landConnection as legacyConnection } from "../src/server/coarse-geography.ts";
import {
	bit,
	center,
	DIRECTIONS,
	type Frame,
	rasterLand as legacyRasterLand,
	setBit,
	setNibble,
} from "./coarse_osm_display_grid_v1.ts";
import {
	landConnection,
	type RoutingGeography,
} from "./coarse_osm_routing_geography_v1.ts";

export * from "./coarse_osm_display_grid_v1.ts";

export function rasterLand(
	frame: Frame,
	geography: RoutingGeography,
	land: Uint8Array,
	boundary: Uint8Array,
	row: Uint8Array,
	check: () => void,
) {
	const packet = geography.rasterMask;
	if (packet === null) {
		legacyRasterLand(frame, geography, land, boundary, row, check);
		return;
	}
	legacyRasterLand(
		frame,
		{ ...geography, lakes: [] },
		land,
		boundary,
		row,
		check,
	);
	const { grid } = packet;
	for (let y = 0; y < frame.height; y++) {
		if ((y & 31) === 0) check();
		const bottom = (frame.south + y * frame.step) * 10;
		const cy = bottom + frame.step * 5;
		const maskY = Math.floor((cy - grid.yE7) / grid.stepE7);
		for (let x = 0; x < frame.width; x++) {
			const i = y * frame.width + x,
				left = (frame.west + x * frame.step) * 10;
			const cx = left + frame.step * 5;
			const flags = packet.cellFlags(
				Math.floor((cx - grid.xE7) / grid.stepE7),
				maskY,
			);
			let allowed = Boolean(bit(land, i));
			if (bit(boundary, i))
				allowed = landConnection(
					geography,
					[cx / 1e7, cy / 1e7],
					[cx / 1e7, cy / 1e7],
				);
			else if (allowed) {
				if (flags === null || flags & 2)
					allowed = legacyConnection(
						geography,
						[cx / 1e7, cy / 1e7],
						[cx / 1e7, cy / 1e7],
					);
				else allowed = !(flags & 1);
			}
			if (allowed) setBit(land, i);
			else land[i >>> 3] &= ~(1 << (i & 7));
			// A full-cell shortcut is valid only when no source/fallback transition
			// or original country edge can occur anywhere in its closed footprint.
			if (
				packet.uncertaintyTouchesE7Box(
					left,
					bottom,
					left + frame.step * 10,
					bottom + frame.step * 10,
				)
			)
				setBit(boundary, i);
		}
	}
}

export function rasterLinks(
	frame: Frame,
	geography: RoutingGeography,
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
