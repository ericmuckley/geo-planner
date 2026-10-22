import type { GridData } from "./coarse-grid";

type EncodedGrid = Omit<
	GridData,
	| "land"
	| "traversable"
	| "links"
	| "roadDeciseconds"
	| "displayLand"
	| "anchorOffsets"
	| "shoreLinks"
> & {
	land: string;
	traversable: string;
	links: string;
	roadDeciseconds?: string;
	displayLand?: string;
	anchorOffsets?: string;
	shoreLinks?: string;
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
	return grid;
}
