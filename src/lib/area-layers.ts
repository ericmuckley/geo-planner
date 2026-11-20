export const areaLayers = {
	land: {
		label: "Public lands",
		url: "/overlays/public-lands-us-v1.png",
		attribution: "USGS PAD-US 4.1",
		attributionUrl: "https://doi.org/10.5066/P96WBCHS",
		color: [36, 110, 72],
	},
	elevation: {
		label: "Elevation",
		url: "/overlays/elevation-us-v1.png",
		attribution: "USGS 3DEP",
		attributionUrl:
			"https://www.usgs.gov/3d-elevation-program/about-3dep-products-services",
		color: [149, 72, 151],
	},
} as const;

export type AreaLayerKind = keyof typeof areaLayers;
export type ElevationRange = [minimumFeet: number, maximumFeet: number];
export const maximumElevationFeet = 10_000;
export const gridWidth = 3350;
export const gridHeight = 1900;
const west = -14_000_000;
const north = 6_500_000;
const resolution = 2000;
const earthRadius = 6_378_137;
const radians = Math.PI / 180;

export function gridPixel(lon: number, lat: number): [number, number] {
	const latitude = Math.max(-85, Math.min(85, lat)) * radians;
	const x = earthRadius * lon * radians;
	const y = earthRadius * Math.asinh(Math.tan(latitude));
	return [(x - west) / resolution, (north - y) / resolution];
}

export function pixelLocation(column: number, row: number): [number, number] {
	const x = west + column * resolution;
	const y = north - row * resolution;
	return [
		x / earthRadius / radians,
		Math.atan(Math.sinh(y / earthRadius)) / radians,
	];
}

export function gridCellIndex(lon: number, lat: number) {
	const [x, y] = gridPixel(lon, lat);
	const column = Math.floor(x);
	const row = Math.floor(y);
	if (column < 0 || column >= gridWidth || row < 0 || row >= gridHeight) {
		return undefined;
	}
	return row * gridWidth + column;
}

export function elevationMatches(
	encoded: number,
	[minimumFeet, maximumFeet]: ElevationRange,
) {
	const meters = encoded - 32768;
	return (
		encoded !== 0 &&
		meters >= minimumFeet * 0.3048 &&
		meters <= maximumFeet * 0.3048
	);
}

export async function loadAreaGrid(kind: AreaLayerKind, signal: AbortSignal) {
	const response = await fetch(areaLayers[kind].url, { signal });
	if (!response.ok) throw new Error("Area layer could not load");
	const bitmap = await createImageBitmap(await response.blob(), {
		colorSpaceConversion: "none",
	});
	try {
		if (bitmap.width !== gridWidth || bitmap.height !== gridHeight) {
			throw new Error("Unexpected area layer size");
		}
		const canvas = document.createElement("canvas");
		canvas.width = gridWidth;
		canvas.height = gridHeight;
		const context = canvas.getContext("2d");
		if (!context) throw new Error("Area layer canvas could not start");
		context.drawImage(bitmap, 0, 0);
		signal.throwIfAborted();
		const { data } = context.getImageData(0, 0, gridWidth, gridHeight);
		const values = new Uint16Array(gridWidth * gridHeight);
		for (let i = 0; i < values.length; i++) {
			values[i] = data[i * 4] * 256 + data[i * 4 + 1];
		}
		return values;
	} finally {
		bitmap.close();
	}
}
