import { layers, namedFlavor } from "@protomaps/basemaps";
import {
	addProtocol,
	Map as MapLibreMap,
	Marker,
	NavigationControl,
	ScaleControl,
	type StyleSpecification,
	setWorkerUrl,
} from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { Protocol } from "pmtiles";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Origin } from "../lib/reachability";

setWorkerUrl(workerUrl);
addProtocol("pmtiles", new Protocol().tile);

export function createResearchMap(container: HTMLDivElement, origin: Origin) {
	const archive = import.meta.env.VITE_PMTILES_URL;
	const style: string | StyleSpecification = archive
		? {
				version: 8,
				glyphs:
					import.meta.env.VITE_MAP_GLYPHS_URL ||
					"https://protomaps.github.io/basemaps-assets/fonts/{fontstack}/{range}.pbf",
				sprite:
					import.meta.env.VITE_MAP_SPRITE_URL ||
					"https://protomaps.github.io/basemaps-assets/sprites/v4/light",
				sources: {
					protomaps: {
						type: "vector",
						url: `pmtiles://${new URL(archive, window.location.href).href}`,
						attribution:
							'<a href="https://protomaps.com">Protomaps</a> © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
					},
				},
				layers: layers("protomaps", namedFlavor("light"), { lang: "en" }),
			}
		: import.meta.env.VITE_MAP_STYLE_URL ||
			"https://tiles.openfreemap.org/styles/liberty";
	const map = new MapLibreMap({
		container,
		style,
		center: [origin.lon, origin.lat],
		zoom: 8.5,
		maxPitch: 0,
		renderWorldCopies: false,
	});
	map.addControl(new NavigationControl({ showCompass: false }), "top-right");
	map.addControl(new ScaleControl({ unit: "imperial" }));
	const marker = new Marker({ color: "#328f97" })
		.setLngLat([origin.lon, origin.lat])
		.addTo(map);
	return { map, marker };
}
