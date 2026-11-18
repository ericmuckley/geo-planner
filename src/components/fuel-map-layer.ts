import {
	type GeoJSONSource,
	type Map as MapLibreMap,
	type MapMouseEvent,
	Popup,
} from "maplibre-gl";
import {
	type FuelLocations,
	fuelAttribution,
	fuelAttributionUrl,
} from "../lib/fuel-locations";

const sourceId = "fuel-stops";
const clusterId = "fuel-clusters";
const pointId = "fuel-locations";
const empty: FuelLocations = { type: "FeatureCollection", features: [] };

export function createFuelMapLayer(map: MapLibreMap) {
	const popup = new Popup({ maxWidth: "220px" });

	function add() {
		map.addSource(sourceId, {
			type: "geojson",
			data: empty,
			cluster: true,
			clusterRadius: 38,
			attribution: `<a href="${fuelAttributionUrl}">${fuelAttribution}</a>`,
		});
		map.addLayer({
			id: clusterId,
			type: "circle",
			source: sourceId,
			filter: ["has", "point_count"],
			paint: {
				"circle-color": "#a55315",
				"circle-radius": ["step", ["get", "point_count"], 10, 25, 14, 100, 18],
				"circle-stroke-color": "#fff",
				"circle-stroke-width": 2,
			},
		});
		map.addLayer({
			id: pointId,
			type: "circle",
			source: sourceId,
			filter: ["!", ["has", "point_count"]],
			paint: {
				"circle-color": "#a55315",
				"circle-radius": 5,
				"circle-stroke-color": "#fff",
				"circle-stroke-width": 1.5,
			},
		});
	}

	function setLocations(locations: FuelLocations | null | undefined) {
		popup.remove();
		map.getSource<GeoJSONSource>(sourceId)?.setData(locations ?? empty);
	}

	function select(event: MapMouseEvent) {
		if (!map.getLayer(pointId)) return false;
		const [feature] = map.queryRenderedFeatures(event.point, {
			layers: [pointId, clusterId],
		});
		if (feature?.geometry.type !== "Point") return false;
		const [lon, lat] = feature.geometry.coordinates;
		const { cluster_id: cluster, name } = feature.properties;
		if (typeof cluster === "number") {
			const source = map.getSource<GeoJSONSource>(sourceId);
			void source
				?.getClusterExpansionZoom(cluster)
				.then((zoom) => {
					if (map.getSource(sourceId) === source)
						map.easeTo({ center: [lon, lat], zoom });
				})
				.catch(() => {});
		} else {
			popup
				.setLngLat([lon, lat])
				.setText(typeof name === "string" ? name : "Fuel stop")
				.addTo(map);
		}
		return true;
	}

	return { add, setLocations, select };
}
