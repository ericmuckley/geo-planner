import { useEffect, useMemo, useState } from "react";
import {
	type PlaceCatalog,
	type PlaceKind,
	type PlaceTerrainFilter,
	parsePlaceCatalog,
	placeLayers,
	placeLocationsInArea,
} from "./place-locations";
import type { ReachabilityResult } from "./reachability";

export function usePlaceLayer(
	kind: PlaceKind,
	enabled: boolean,
	contours: ReachabilityResult["contours"] | undefined,
	filter?: PlaceTerrainFilter | null,
) {
	const [catalog, setCatalog] = useState<PlaceCatalog | null>(null);
	const [loadError, setLoadError] = useState(false);

	useEffect(() => {
		if (!enabled || catalog) return;
		const abort = new AbortController();
		setLoadError(false);
		fetch(placeLayers[kind].url, { signal: abort.signal })
			.then(async (response) => {
				if (!response.ok) throw new Error("Could not load mapped places");
				return parsePlaceCatalog(kind, await response.json());
			})
			.then((data) => {
				if (!abort.signal.aborted) setCatalog(data);
			})
			.catch(() => {
				if (!abort.signal.aborted) setLoadError(true);
			});
		return () => abort.abort();
	}, [enabled, catalog, kind]);

	const placesInArea = useMemo(
		() =>
			enabled && catalog && contours
				? placeLocationsInArea(kind, catalog, contours)
				: null,
		[enabled, catalog, contours, kind],
	);
	const locations = useMemo(() => {
		if (!placesInArea || filter === null) return null;
		return filter ? filter(placesInArea) : placesInArea;
	}, [placesInArea, filter]);
	return {
		enabled,
		locations,
		loadError,
		sourceDate: catalog?.sourceDate,
	};
}
