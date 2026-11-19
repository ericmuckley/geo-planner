import {
	type GeoJSONSource,
	type Map as MapLibreMap,
	type MapMouseEvent,
	Popup,
} from "maplibre-gl";
import {
	type MapPlaces,
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
			popup.setLngLat([lon, lat]).setText(name).addTo(map);
		}
		return true;
	}

	return { add, setLocations, select, closePopup: () => popup.remove() };
}
