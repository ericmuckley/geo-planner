import {
	type GeoJSONSource,
	type Map as MapLibreMap,
	type MapMouseEvent,
	Marker,
	Popup,
} from "maplibre-gl";
import {
	type MapPlaces,
	type OutdoorPlaceSelection,
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

export function createPlaceMapLayers(map: MapLibreMap) {
	const popup = new Popup({ closeOnClick: false, maxWidth: "220px" });
	let displayed: MapPlaces | undefined;
	let focusMarker: Marker | undefined;
	popup.on("close", () => {
		focusMarker?.remove();
		focusMarker = undefined;
	});

	function add() {
		for (const kind of placeKinds) {
			const source = `places-${kind}`;
			const color = placeLayers[kind].color;
			map.addSource(source, {
				type: "geojson",
				data: empty,
				cluster: true,
				clusterRadius: 38,
				attribution: `<a href="${placeAttributionUrl}">${placeAttribution}</a>`,
			});
			map.addLayer({
				id: `${kind}-clusters`,
				type: "circle",
				source,
				filter: ["has", "point_count"],
				paint: {
					"circle-color": color,
					"circle-radius": [
						"step",
						["get", "point_count"],
						10,
						25,
						14,
						100,
						18,
					],
					"circle-stroke-color": "#fff",
					"circle-stroke-width": 2,
				},
			});
			map.addLayer({
				id: `${kind}-points`,
				type: "circle",
				source,
				filter: ["!", ["has", "point_count"]],
				paint: {
					"circle-color": color,
					"circle-radius": 5,
					"circle-stroke-color": "#fff",
					"circle-stroke-width": 1.5,
				},
			});
		}
	}

	function setLocations(locations: MapPlaces | undefined) {
		for (const kind of placeKinds) {
			const next = locations?.[kind];
			if (next === displayed?.[kind]) continue;
			popup.remove();
			map.getSource<GeoJSONSource>(`places-${kind}`)?.setData(next ?? empty);
		}
		displayed = locations;
	}

	function focusPlace({ kind, location }: OutdoorPlaceSelection) {
		if (!displayed?.[kind]?.features.includes(location)) return;
		const [lon, lat] = location.geometry.coordinates;
		const coordinates: [number, number] = [lon, lat];
		popup.remove();

		const details = document.createElement("div");
		const name = document.createElement("strong");
		name.textContent = location.properties.name;
		const position = document.createElement("div");
		position.textContent = `${placeLayers[kind].singular} · ${lat.toFixed(5)}, ${lon.toFixed(5)}`;
		details.append(name, position);

		map.easeTo({ center: coordinates, zoom: Math.max(14, map.getZoom()) });
		popup
			.setOffset(28)
			.setLngLat(coordinates)
			.setDOMContent(details)
			.addTo(map);
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
		if (!map.getLayer(pointLayers[0])) return false;
		const [feature] = map.queryRenderedFeatures(event.point, {
			layers: pointLayers,
		});
		if (feature?.geometry.type !== "Point") return false;
		const [lon, lat] = feature.geometry.coordinates;
		const { cluster_id: cluster, name } = feature.properties;
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
			popup.setOffset(0).setLngLat([lon, lat]).setText(name).addTo(map);
		}
		return true;
	}

	return {
		add,
		setLocations,
		select,
		focusPlace,
		closePopup: () => popup.remove(),
	};
}
