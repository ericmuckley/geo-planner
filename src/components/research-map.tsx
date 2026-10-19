import type { GeoJSONSource, Map as MapLibreMap, Marker } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import type { ExperimentResult } from "../lib/experiment";
import type { Origin, ReachabilityResult } from "../lib/reachability";

type Props = {
	origin: Origin;
	result: ReachabilityResult | null;
	experiment?: ExperimentResult | null;
	showContour: boolean;
	onOriginChange: (origin: Origin) => void;
	onMapIdle: (id: string, milliseconds: number) => void;
};

export function ResearchMap(props: Props) {
	const container = useRef<HTMLDivElement>(null);
	const mapRef = useRef<MapLibreMap | null>(null);
	const markerRef = useRef<Marker | null>(null);
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
				const { map, marker } = createResearchMap(
					container.current,
					current.current.origin,
				);
				mapRef.current = map;
				markerRef.current = marker;
				map
					.getCanvas()
					.setAttribute(
						"aria-label",
						"Reachability map. Click to select an origin, or use the coordinate fields.",
					);
				map.on("click", ({ lngLat }) => {
					if (Math.abs(lngLat.lat) <= 85)
						current.current.onOriginChange({
							lat: lngLat.lat,
							lon: lngLat.wrap().lng,
						});
				});
				map.on("error", () =>
					setError(
						"Some map resources could not load. Check the basemap URL, network, and archive coverage. Coordinate controls still work.",
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
					setReady(true);
				});
				resize = new ResizeObserver(() => map.resize());
				resize.observe(container.current);
			})
			.catch(() => {
				if (!disposed)
					setError(
						"The map could not start. A WebGL-capable browser is required. You can still use coordinate controls.",
					);
			});
		return () => {
			disposed = true;
			resize?.disconnect();
			mapRef.current?.remove();
			mapRef.current = null;
			markerRef.current = null;
		};
	}, []);

	useEffect(() => {
		const map = mapRef.current;
		if (!map || !ready) return;
		markerRef.current?.setLngLat([props.origin.lon, props.origin.lat]);
		if (!map.getBounds().contains([props.origin.lon, props.origin.lat])) {
			map.easeTo({ center: [props.origin.lon, props.origin.lat] });
		}
	}, [props.origin, ready]);

	useEffect(() => {
		const map = mapRef.current;
		if (!map || !ready) return;
		const source = map.getSource<GeoJSONSource>("reachability");
		const started = performance.now();
		const data = props.experiment?.geometry ?? props.result?.contours;
		source?.setData(data ?? { type: "FeatureCollection", features: [] });
		const result = props.experiment ?? props.result;
		if (!result) return;
		let west = 180;
		let south = 90;
		let east = -180;
		let north = -90;
		for (const feature of data?.features ?? []) {
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
			{ padding: 48, maxZoom: 11, duration: 0 },
		);
		const onIdle = () =>
			current.current.onMapIdle(result.id, performance.now() - started);
		map.once("idle", onIdle);
		return () => {
			map.off("idle", onIdle);
		};
	}, [props.result, props.experiment, ready]);

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
		<div className="relative min-h-[440px] h-full overflow-hidden rounded-2xl border border-[var(--line)] bg-[var(--sand)]">
			{/* MapLibre's unlayered CSS overrides Tailwind's position utility. */}
			<div ref={container} style={{ position: "absolute", inset: 0 }} />
			{!ready && !error && (
				<output className="absolute left-4 top-4 rounded-lg bg-white/95 px-4 py-2 text-sm">
					Loading map…
				</output>
			)}
			{error && (
				<output className="absolute left-4 right-14 top-4 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">
					{error}
				</output>
			)}
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
		</div>
	);
}
