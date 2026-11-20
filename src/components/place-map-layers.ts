import {
	type GeoJSONSource,
	type Map as MapLibreMap,
	type MapMouseEvent,
	Marker,
	Popup,
} from "maplibre-gl";
import {
	type MapPlaces,
	type OutdoorPlaceKind,
	type OutdoorPlaceSelection,
	type PlaceKind,
	type PlaceLocations,
	placeAttribution,
	placeAttributionUrl,
	placeKinds,
	placeLayers,
} from "../lib/place-locations";

const empty: PlaceLocations = { type: "FeatureCollection", features: [] };
const pointLayers = placeKinds.flatMap((kind) => [
	`${kind}-points`,
	`${kind}-clusters`,
]);
const placeSymbols = {
	fuel: "M3 21V4h11v17M2 21h13M3 10h11m0 3h2a2 2 0 0 1 2 2v3a2 2 0 0 0 4 0v-7l-4-4",
	trailheads: "M12 3v3m0 8v7M3 6h15l4 4-4 4H3z",
	campgrounds: "M2 21h20L12 4 2 21m6 0 4-7 4 7",
};

function addPlaceIcon(map: MapLibreMap, kind: PlaceKind) {
	const size = 22;
	const pixelRatio = 2;
	const canvas = document.createElement("canvas");
	canvas.width = canvas.height = size * pixelRatio;
	const context = canvas.getContext("2d");
	if (!context) return;
	context.scale(pixelRatio, pixelRatio);
	context.beginPath();
	context.arc(size / 2, size / 2, 10, 0, 2 * Math.PI);
	context.fillStyle = placeLayers[kind].color;
	context.fill();
	context.strokeStyle = "#fff";
	context.lineWidth = 1.5;
	context.stroke();
	context.translate(5, 5);
	context.scale(0.5, 0.5);
	context.lineCap = "round";
	context.lineJoin = "round";
	context.lineWidth = 2.5;
	context.stroke(new Path2D(placeSymbols[kind]));
	map.addImage(
		`place-${kind}`,
		context.getImageData(0, 0, canvas.width, canvas.height),
		{ pixelRatio },
	);
}

export function createPlaceMapLayers(map: MapLibreMap) {
	const popup = new Popup({
		closeOnClick: false,
		maxWidth: "220px",
		className:
			"[&_.maplibregl-popup-close-button]:right-2! [&_.maplibregl-popup-close-button]:px-1! [&_.maplibregl-popup-content]:pt-5!",
	});
	const clusterLabel = document.createElement("span");
	const clusterTooltip = new Popup({
		closeButton: false,
		focusAfterOpen: false,
		className:
			"[&_.maplibregl-popup-content]:pointer-events-none! [&_.maplibregl-popup-content]:p-2!",
		offset: 13,
	}).setDOMContent(clusterLabel);
	let displayed: MapPlaces | undefined;
	let focusMarker: Marker | undefined;
	popup.on("close", () => {
		focusMarker?.remove();
		focusMarker = undefined;
	});

	function placeAt(event: MapMouseEvent) {
		if (!map.getLayer(pointLayers[0])) return;
		const [feature] = map.queryRenderedFeatures(event.point, {
			layers: pointLayers,
		});
		if (feature?.geometry.type !== "Point") return;
		const kind = placeKinds.find((kind) => feature.source === `places-${kind}`);
		if (kind)
			return { coordinates: feature.geometry.coordinates, feature, kind };
	}

	function hideClusterTooltip() {
		if (clusterTooltip.isOpen()) clusterTooltip.remove();
	}

	map.on("mousemove", (event) => {
		const place = placeAt(event);
		const count = place?.feature.properties.point_count;
		if (!place || typeof count !== "number") {
			hideClusterTooltip();
			return;
		}
		const { label, singular } = placeLayers[place.kind];
		const text = `${count.toLocaleString()} ${count === 1 ? singular : label.toLowerCase()}`;
		if (clusterLabel.textContent !== text) clusterLabel.textContent = text;
		const [lon, lat] = place.coordinates;
		clusterTooltip.setLngLat([lon, lat]);
		if (!clusterTooltip.isOpen()) clusterTooltip.addTo(map);
	});
	map.on("mouseout", hideClusterTooltip);
	map.on("movestart", hideClusterTooltip);

	function add() {
		for (const kind of placeKinds) {
			const source = `places-${kind}`;
			addPlaceIcon(map, kind);
			map.addSource(source, {
				type: "geojson",
				data: empty,
				cluster: true,
				clusterRadius: 38,
				attribution: `<a href="${placeAttributionUrl}">${placeAttribution}</a>`,
			});
			for (const cluster of [true, false]) {
				map.addLayer({
					id: `${kind}-${cluster ? "clusters" : "points"}`,
					type: "symbol",
					source,
					filter: cluster
						? ["has", "point_count"]
						: ["!", ["has", "point_count"]],
					layout: {
						"icon-image": `place-${kind}`,
						"icon-size": cluster
							? ["interpolate", ["linear"], ["zoom"], 0, 0.7, 7, 1]
							: 0.65,
						"icon-allow-overlap": true,
						"icon-ignore-placement": true,
						"icon-padding": 0,
					},
				});
			}
		}
	}

	function setLocations(locations: MapPlaces | undefined) {
		for (const kind of placeKinds) {
			const next = locations?.[kind];
			if (next === displayed?.[kind]) continue;
			popup.remove();
			hideClusterTooltip();
			map.getSource<GeoJSONSource>(`places-${kind}`)?.setData(next ?? empty);
		}
		displayed = locations;
	}

	function showOutdoorPlace(
		kind: OutdoorPlaceKind,
		placeName: string,
		coordinates: [number, number],
		offset = 0,
	) {
		const [lon, lat] = coordinates;
		const details = document.createElement("div");
		const name = document.createElement("strong");
		name.textContent = placeName;
		const position = document.createElement("div");
		position.textContent = `${placeLayers[kind].singular} · ${lat.toFixed(5)}, ${lon.toFixed(5)}`;
		const params = new URLSearchParams({
			api: "1",
			query: `${lat},${lon}`,
		});
		const mapsLink = document.createElement("a");
		mapsLink.href = `https://www.google.com/maps/search/?${params}`;
		mapsLink.target = "_blank";
		mapsLink.rel = "noopener noreferrer";
		mapsLink.className =
			"mt-2 inline-block font-semibold text-[var(--lagoon-deep)] underline";
		mapsLink.textContent = "View in Google Maps";
		details.append(name, position, mapsLink);
		popup
			.setOffset(offset)
			.setLngLat(coordinates)
			.setDOMContent(details)
			.addTo(map);
	}

	function focusPlace({ kind, location }: OutdoorPlaceSelection) {
		if (!displayed?.[kind]?.features.includes(location)) return;
		const [lon, lat] = location.geometry.coordinates;
		const coordinates: [number, number] = [lon, lat];
		popup.remove();
		map.jumpTo({ center: coordinates, zoom: Math.max(14, map.getZoom()) });
		showOutdoorPlace(kind, location.properties.name, coordinates, 28);
		// A list selection needs a visible pin even when the source is clustered.
		focusMarker = new Marker({
			color: placeLayers[kind].color,
			className: "outdoor-place-focus",
		})
			.setLngLat(coordinates)
			.addTo(map);
		focusMarker.getElement().style.pointerEvents = "none";
	}

	function select(event: MapMouseEvent) {
		const place = placeAt(event);
		if (!place) return false;
		const {
			feature,
			kind,
			coordinates: [lon, lat],
		} = place;
		const {
			cluster_id: cluster,
			name,
			lon: placeLon,
			lat: placeLat,
		} = feature.properties;
		if (typeof cluster === "number") {
			const source = map.getSource<GeoJSONSource>(feature.source);
			void source
				?.getClusterExpansionZoom(cluster)
				.then((zoom) => {
					if (map.getSource(feature.source) === source)
						map.easeTo({ center: [lon, lat], zoom });
				})
				.catch(() => {});
		} else if (typeof name === "string") {
			if (
				kind !== "fuel" &&
				typeof placeLon === "number" &&
				typeof placeLat === "number"
			) {
				showOutdoorPlace(kind, name, [placeLon, placeLat]);
			} else {
				popup.setOffset(0).setLngLat([lon, lat]).setText(name).addTo(map);
			}
		}
		return true;
	}

	return {
		add,
		setLocations,
		select,
		focusPlace,
		hasFocusedPlace: () => focusMarker !== undefined,
		closePopup: () => {
			popup.remove();
			hideClusterTooltip();
		},
	};
}
