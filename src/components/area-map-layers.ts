import type { Map as MapLibreMap } from "maplibre-gl";
import {
	type AreaLayerKind,
	areaLayers,
	type ElevationRange,
	elevationMatches,
	gridHeight,
	gridPixel,
	gridWidth,
	pixelLocation,
} from "../lib/area-layers";
import { contourPolygons } from "../lib/contour-membership";
import type { ReachabilityResult } from "../lib/reachability";

type Contours = ReachabilityResult["contours"];

function canvasContext(width: number, height: number) {
	const canvas = document.createElement("canvas");
	canvas.width = width;
	canvas.height = height;
	return canvas.getContext("2d");
}

export function setAreaMapLayer(
	map: MapLibreMap,
	kind: AreaLayerKind,
	contours: Contours | undefined,
	grid: Uint16Array | null | undefined,
	elevationRange?: ElevationRange,
) {
	const id = `overlay-${kind}`;
	if (map.getLayer(id)) map.removeLayer(id);
	if (map.getSource(id)) map.removeSource(id);
	if (!contours || !grid) return;

	let left = gridWidth;
	let top = gridHeight;
	let right = 0;
	let bottom = 0;
	const polygons = contourPolygons(contours).map((polygon) =>
		polygon.map((ring) =>
			ring.map(([lon, lat]) => {
				const [x, y] = gridPixel(lon, lat);
				left = Math.min(left, x);
				right = Math.max(right, x);
				top = Math.min(top, y);
				bottom = Math.max(bottom, y);
				return [x, y];
			}),
		),
	);
	left = Math.max(0, Math.floor(left));
	right = Math.min(gridWidth, Math.ceil(right));
	top = Math.max(0, Math.floor(top));
	bottom = Math.min(gridHeight, Math.ceil(bottom));
	const width = right - left;
	const height = bottom - top;
	if (width <= 0 || height <= 0) return;

	const mask = canvasContext(width, height);
	const output = canvasContext(width, height);
	if (!mask || !output) return;

	for (const rings of polygons) {
		const path = new Path2D();
		for (const ring of rings) {
			ring.forEach(([x, y], i) => {
				if (i === 0) path.moveTo(x - left, y - top);
				else path.lineTo(x - left, y - top);
			});
			path.closePath();
		}
		mask.fill(path, "evenodd");
	}

	const pixels = output.createImageData(width, height);
	const [red, green, blue] = areaLayers[kind].color;
	for (let row = 0; row < height; row++) {
		for (let col = 0; col < width; col++) {
			const value = grid[(row + top) * gridWidth + col + left];
			const included =
				kind === "land"
					? value !== 0
					: elevationRange && elevationMatches(value, elevationRange);
			if (!included) continue;
			const dest = (row * width + col) * 4;
			pixels.data[dest] = red;
			pixels.data[dest + 1] = green;
			pixels.data[dest + 2] = blue;
			pixels.data[dest + 3] = 255;
		}
	}
	output.putImageData(pixels, 0, 0);
	output.globalCompositeOperation = "destination-in";
	output.drawImage(mask.canvas, 0, 0);

	map.addSource(id, {
		type: "canvas",
		canvas: output.canvas,
		coordinates: [
			pixelLocation(left, top),
			pixelLocation(right, top),
			pixelLocation(right, bottom),
			pixelLocation(left, bottom),
		],
		animate: false,
	});
	map.addLayer(
		{
			id,
			type: "raster",
			source: id,
			paint: {
				"raster-opacity": 0.57,
				"raster-resampling": "nearest",
				"raster-fade-duration": 0,
			},
		},
		kind === "land" && map.getLayer("overlay-elevation")
			? "overlay-elevation"
			: "reachability-line",
	);
}
