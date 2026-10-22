import {
	distanceKm,
	type GridData,
	gridPosition,
	type RoadVisit,
} from "./coarse-grid";

type EncodedGrid = Omit<
	GridData,
	| "land"
	| "traversable"
	| "links"
	| "roadDeciseconds"
	| "displayLand"
	| "anchorOffsets"
	| "shoreLinks"
	| "roadVisits"
> & {
	land: string;
	traversable: string;
	links: string;
	roadDeciseconds?: string;
	displayLand?: string;
	anchorOffsets?: string;
	shoreLinks?: string;
	roadVisits?: Array<{
		cell: number;
		speedKph: number;
		anchorIndex: number;
		offsets: number[][];
	}>;
};

export function decodeGrid(data: EncodedGrid): GridData {
	const bytes = (value: string) => new Uint8Array(Buffer.from(value, "base64"));
	const grid = {
		...data,
		land: bytes(data.land),
		traversable: bytes(data.traversable),
		links: bytes(data.links),
		displayLand: data.displayLand ? bytes(data.displayLand) : undefined,
		shoreLinks: data.shoreLinks ? bytes(data.shoreLinks) : undefined,
		roadDeciseconds: undefined as Uint16Array | undefined,
		anchorOffsets: undefined as Int16Array | undefined,
		roadVisits: undefined as Map<number, RoadVisit> | undefined,
	};
	const size = data.width * data.height;
	if (
		grid.land.length !== size ||
		grid.traversable.length !== size ||
		grid.links.length !== size * 4 ||
		(grid.displayLand && grid.displayLand.length !== size) ||
		(grid.shoreLinks && grid.shoreLinks.length !== size)
	)
		throw new Error("Invalid bundled coarse-grid data");
	if (data.roadDeciseconds) {
		const encoded = bytes(data.roadDeciseconds);
		if (encoded.length !== size * 8)
			throw new Error("Invalid bundled road times");
		const view = new DataView(
			encoded.buffer,
			encoded.byteOffset,
			encoded.byteLength,
		);
		grid.roadDeciseconds = Uint16Array.from({ length: size * 4 }, (_, i) =>
			view.getUint16(i * 2, true),
		);
	}
	if (data.anchorOffsets) {
		const encoded = bytes(data.anchorOffsets);
		if (encoded.length !== size * 4)
			throw new Error("Invalid bundled road anchors");
		const view = new DataView(
			encoded.buffer,
			encoded.byteOffset,
			encoded.byteLength,
		);
		grid.anchorOffsets = Int16Array.from({ length: size * 2 }, (_, i) =>
			view.getInt16(i * 2, true),
		);
	}
	if (data.roadVisits) {
		grid.roadVisits = new Map();
		for (const { cell, speedKph, anchorIndex, offsets } of data.roadVisits) {
			if (
				!Number.isInteger(cell) ||
				cell < 0 ||
				cell >= size ||
				!grid.traversable[cell] ||
				grid.roadVisits.has(cell) ||
				!Number.isFinite(speedKph) ||
				speedKph < grid.localSpeedKph ||
				speedKph > 105 ||
				!Number.isInteger(anchorIndex) ||
				anchorIndex < 0 ||
				anchorIndex >= offsets.length ||
				offsets.length < 2 ||
				offsets.some(
					(p) =>
						p.length !== 2 ||
						p.some(
							(v) =>
								!Number.isInteger(v) || Math.abs(v) > data.step * 50000 + 1,
						),
				)
			)
				throw new Error("Invalid bundled road visit");
			const center = [
				data.bounds[0] + ((cell % data.width) + 0.5) * data.step,
				data.bounds[1] + (Math.floor(cell / data.width) + 0.5) * data.step,
			];
			const points = offsets.map((p) =>
				p.map((v, k) => center[k] + v / 100000),
			);
			if (distanceKm(points[anchorIndex], gridPosition(grid, cell)) > 1e-7)
				throw new Error("Road visit does not own its anchor");
			const cumulativeKm = [0];
			for (let i = 1; i < points.length; i++) {
				const km = distanceKm(points[i - 1], points[i]);
				if (!km) throw new Error("Duplicate road visit points");
				cumulativeKm.push(cumulativeKm[i - 1] + km);
			}
			grid.roadVisits.set(cell, {
				speedKph,
				anchorIndex,
				points,
				cumulativeKm,
			});
		}
	}
	return grid;
}
