import type {
	GeoJSONSource,
	LngLat,
	Map as MapLibreMap,
	Marker,
} from "maplibre-gl";
import { type RefObject, useEffect, useRef, useState } from "react";
import type { ElevationRange } from "../lib/area-layers";
import type { ExperimentResult } from "../lib/experiment";
import type { MapPlaces, OutdoorPlaceSelection } from "../lib/place-locations";
import type { Origin, ReachabilityResult } from "../lib/reachability";
import { cn } from "../lib/utils";
import { setAreaMapLayer } from "./area-map-layers";
import type { createPlaceMapLayers } from "./place-map-layers";

type Props = {
	origin: Origin | null;
	result: ReachabilityResult | null;
	places?: MapPlaces;
	selectedOutdoorPlace?: OutdoorPlaceSelection | null;
	landGrid?: Uint16Array | null;
	elevationGrid?: Uint16Array | null;
	elevationRange?: ElevationRange;
	experiment?: ExperimentResult | null;
	showContour: boolean;
	fullscreen?: boolean;
	overlayRef?: RefObject<HTMLElement | null>;
	onOriginChange: (origin: Origin) => void;
	onMapIdle: (id: string, milliseconds: number) => void;
};

function fitResult(
	map: MapLibreMap,
	props: Pick<Props, "result" | "experiment" | "overlayRef">,
) {
	if (!props.experiment && !props.result) return;
	let west = 180;
	let south = 90;
	let east = -180;
	let north = -90;
	for (const feature of (props.experiment?.geometry ?? props.result?.contours)
		?.features ?? []) {
		const geometry = feature.geometry;
		const positions =
			geometry.type === "Point"
				? [geometry.coordinates]
				: geometry.type === "LineString" || geometry.type === "MultiPoint"
					? geometry.coordinates
					: geometry.type === "MultiPolygon"
						? geometry.coordinates.flat(2)
						: geometry.coordinates.flat();
		for (const [lon, lat] of positions) {
			west = Math.min(west, lon);
			south = Math.min(south, lat);
			east = Math.max(east, lon);
			north = Math.max(north, lat);
		}
	}
	map.fitBounds(
		[
			[west, south],
			[east, north],
		],
		{
			padding: props.overlayRef ? map.getPadding() : 48,
			absolutePadding: Boolean(props.overlayRef),
			maxZoom: 11,
			duration: 0,
		},
	);
}

export function ResearchMap(props: Props) {
	const container = useRef<HTMLDivElement>(null);
	const mapRef = useRef<MapLibreMap | null>(null);
	const markerRef = useRef<Marker | null>(null);
	const placesRef = useRef<ReturnType<typeof createPlaceMapLayers> | null>(
		null,
	);
	const current = useRef(props);
	const [ready, setReady] = useState(false);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		current.current = props;
	}, [props]);

	useEffect(() => {
		let disposed = false;
		let resize: ResizeObserver | undefined;
		import("./map-client")
			.then(({ createResearchMap }) => {
				if (disposed || !container.current) return;
				const { map, marker, places } = createResearchMap(
					container.current,
					current.current.origin,
				);
				mapRef.current = map;
				markerRef.current = marker;
				placesRef.current = places;
				const canvas = map.getCanvas();
				const fullscreen = current.current.fullscreen;
				canvas.setAttribute(
					"aria-label",
					fullscreen
						? "Reachability map. Click or tap to set the starting point. Use the arrow keys to pan and Enter to select the map center."
						: "Reachability map. Click to select an origin, or use the coordinate fields.",
				);
				function selectMapPoint(lngLat: LngLat) {
					if (Math.abs(lngLat.lat) <= 85)
						current.current.onOriginChange({
							lat: lngLat.lat,
							lon: lngLat.wrap().lng,
						});
				}
				if (fullscreen) {
					canvas.addEventListener("keydown", (event) => {
						if (event.key !== "Enter" || event.repeat) return;
						event.preventDefault();
						places.closePopup();
						selectMapPoint(map.getCenter());
					});
				}
				map.on("click", (event) => {
					places.closePopup();
					if (places.select(event)) return;
					selectMapPoint(event.lngLat);
				});
				map.on("error", () =>
					setError(
						"Some map resources could not load. Check the basemap URL, network, and archive coverage.",
					),
				);
				map.on("load", () => {
					map.addSource("reachability", {
						type: "geojson",
						// Preserve short sampled road segments at regional zoom levels.
						...(current.current.experiment !== undefined
							? { tolerance: 0 }
							: {}),
						data: { type: "FeatureCollection", features: [] },
					});
					map.addLayer({
						id: "reachability-fill",
						type: "fill",
						source: "reachability",
						filter: ["==", ["geometry-type"], "Polygon"],
						paint: { "fill-color": "#328f97", "fill-opacity": 0.22 },
					});
					map.addLayer({
						id: "reachability-line",
						type: "line",
						source: "reachability",
						filter: ["==", ["geometry-type"], "Polygon"],
						paint: { "line-color": "#246f76", "line-width": 2 },
					});
					map.addLayer({
						id: "experiment-roads",
						type: "line",
						source: "reachability",
						filter: ["==", ["get", "kind"], "road"],
						layout: { "line-cap": "round", "line-join": "round" },
						paint: {
							"line-color": "#08757e",
							"line-width": 2.5,
							"line-opacity": 0.9,
						},
					});
					map.addLayer({
						id: "experiment-coverage",
						type: "line",
						source: "reachability",
						filter: ["==", ["get", "kind"], "coverage"],
						paint: {
							"line-color": "#b76b23",
							"line-width": 2,
							"line-dasharray": [4, 3],
						},
					});
					map.addLayer({
						id: "experiment-cuts",
						type: "circle",
						source: "reachability",
						filter: ["==", ["get", "kind"], "cut"],
						paint: {
							"circle-color": [
								"case",
								["==", ["get", "reached"], true],
								"#c43232",
								"#89969a",
							],
							"circle-radius": [
								"case",
								["==", ["get", "reached"], true],
								5,
								2.5,
							],
							"circle-stroke-width": 1,
							"circle-stroke-color": "#fff",
						},
					});
					map.addLayer({
						id: "snapped-origin",
						type: "circle",
						source: "reachability",
						filter: [
							"all",
							["==", ["geometry-type"], "Point"],
							["==", ["get", "type"], "snapped"],
						],
						paint: {
							"circle-color": "#e68a35",
							"circle-radius": 5,
							"circle-stroke-width": 2,
							"circle-stroke-color": "#fff",
						},
					});
					if (current.current.places) places.add();
					setReady(true);
				});
				resize = new ResizeObserver(() => {
					map.resize();
					const overlay = current.current.overlayRef?.current;
					if (!overlay || !container.current) return;
					const bounds = container.current.getBoundingClientRect();
					const panel = overlay.getBoundingClientRect();
					// Keep the map's focus and fitted contours clear of the floating panel.
					map.setPadding({
						top:
							panel.width > bounds.width / 2
								? panel.bottom - bounds.top + 24
								: 32,
						left:
							panel.width > bounds.width / 2
								? 24
								: panel.right - bounds.left + 24,
						right: 48,
						bottom: 48,
					});
					if (!places.hasFocusedPlace()) fitResult(map, current.current);
				});
				resize.observe(container.current);
				if (current.current.overlayRef?.current)
					resize.observe(current.current.overlayRef.current);
			})
			.catch(() => {
				if (!disposed)
					setError(
						"The map could not start. A WebGL-capable browser is required.",
					);
			});
		return () => {
			disposed = true;
			resize?.disconnect();
			mapRef.current?.remove();
			mapRef.current = null;
			markerRef.current = null;
			placesRef.current = null;
		};
	}, []);

	useEffect(() => {
		const map = mapRef.current;
		const marker = markerRef.current;
		if (!map || !marker || !props.origin) return;
		const coordinates: [number, number] = [props.origin.lon, props.origin.lat];
		marker.setLngLat(coordinates);
		if (!marker.getElement().isConnected) marker.addTo(map);
		if (!map.getBounds().contains(coordinates))
			map.easeTo({ center: coordinates });
	}, [props.origin]);

	useEffect(() => {
		if (ready) placesRef.current?.setLocations(props.places);
	}, [props.places, ready]);

	useEffect(() => {
		if (ready && props.selectedOutdoorPlace) {
			placesRef.current?.focusPlace(props.selectedOutdoorPlace);
		}
	}, [props.selectedOutdoorPlace, ready]);

	const contours = props.result?.contours;

	useEffect(() => {
		if (ready && mapRef.current)
			setAreaMapLayer(mapRef.current, "land", contours, props.landGrid);
	}, [ready, contours, props.landGrid]);

	useEffect(() => {
		if (ready && mapRef.current)
			setAreaMapLayer(
				mapRef.current,
				"elevation",
				contours,
				props.elevationGrid,
				props.elevationRange,
			);
	}, [ready, contours, props.elevationGrid, props.elevationRange]);

	useEffect(() => {
		const map = mapRef.current;
		if (!map || !ready) return;
		const source = map.getSource<GeoJSONSource>("reachability");
		const started = performance.now();
		const data = props.experiment?.geometry ?? props.result?.contours;
		source?.setData(data ?? { type: "FeatureCollection", features: [] });
		const result = props.experiment ?? props.result;
		if (!result) return;
		fitResult(map, {
			result: props.result,
			experiment: props.experiment,
			overlayRef: props.overlayRef,
		});
		const onIdle = () =>
			current.current.onMapIdle(result.id, performance.now() - started);
		map.once("idle", onIdle);
		return () => {
			map.off("idle", onIdle);
		};
	}, [props.result, props.experiment, props.overlayRef, ready]);

	useEffect(() => {
		if (!ready) return;
		for (const layer of [
			"reachability-fill",
			"reachability-line",
			"snapped-origin",
			"experiment-roads",
			"experiment-coverage",
			"experiment-cuts",
		]) {
			mapRef.current?.setLayoutProperty(
				layer,
				"visibility",
				props.showContour ? "visible" : "none",
			);
		}
	}, [props.showContour, ready]);

	return (
		<div
			className={cn(
				"relative h-full overflow-hidden bg-[var(--sand)]",
				props.fullscreen &&
					"[&_.maplibregl-canvas:focus-visible]:outline-2 [&_.maplibregl-canvas:focus-visible]:-outline-offset-4 [&_.maplibregl-canvas:focus-visible]:outline-neutral-900",
				props.fullscreen && !props.origin && "maplibregl-crosshair",
				!props.fullscreen &&
					"min-h-[440px] rounded-2xl border border-[var(--line)]",
			)}
		>
			{/* MapLibre's unlayered CSS overrides Tailwind's position utility. */}
			<div ref={container} style={{ position: "absolute", inset: 0 }} />
			{!ready && !error && (
				<output
					className={cn(
						"absolute rounded-lg bg-white/95 px-4 py-2 text-sm",
						props.fullscreen ? "bottom-14 right-4" : "left-4 top-4",
					)}
				>
					Loading map…
				</output>
			)}
			{error && (
				<output
					className={cn(
						"absolute rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950",
						props.fullscreen
							? "bottom-14 right-4 left-4 sm:left-auto sm:max-w-sm"
							: "left-4 right-14 top-4",
					)}
				>
					{error}
				</output>
			)}
			{!props.fullscreen && (
				<div className="pointer-events-none absolute bottom-10 left-3 max-w-[260px] rounded-lg bg-white/95 p-3 text-xs text-[var(--sea-ink)] shadow-sm">
					<p className="font-bold">Click the map to set your origin</p>
					<p className="mt-1">
						{import.meta.env.VITE_PMTILES_URL
							? "Regional PMTiles basemap"
							: "OpenFreeMap basemap · online"}
					</p>
					{props.experiment && (
						<p className="mt-1">
							Teal: sampled reachable roads · red: reached data edges · gray:
							other audited edges · dashed: dataset bounds · orange: snapped
							origin
						</p>
					)}
					{props.result && !props.experiment && (
						<p className="mt-1">
							Teal: displayed contour
							{props.result.contours.features.some(
								(feature) => feature.properties?.type === "snapped",
							) && " · orange: snapped origin"}
						</p>
					)}
				</div>
			)}
		</div>
	);
}
