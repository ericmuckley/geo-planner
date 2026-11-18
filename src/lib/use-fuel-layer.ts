import { useEffect, useMemo, useState } from "react";
import {
	type FuelCatalog,
	fuelCatalogSchema,
	fuelCatalogUrl,
	fuelLocationsInArea,
} from "./fuel-locations";
import type { ReachabilityResult } from "./reachability";

export function useFuelLayer(
	contours: ReachabilityResult["contours"] | undefined,
) {
	const [enabled, setEnabled] = useState(false);
	const [catalog, setCatalog] = useState<FuelCatalog | null>(null);
	const [loadError, setLoadError] = useState(false);

	useEffect(() => {
		if (!enabled || catalog) return;
		const abort = new AbortController();
		setLoadError(false);
		fetch(fuelCatalogUrl, { signal: abort.signal })
			.then(async (response) => {
				if (!response.ok) throw new Error("Could not load fuel locations");
				return fuelCatalogSchema.parse(await response.json());
			})
			.then((data) => {
				if (!abort.signal.aborted) setCatalog(data);
			})
			.catch(() => {
				if (!abort.signal.aborted) setLoadError(true);
			});
		return () => abort.abort();
	}, [enabled, catalog]);

	const locations = useMemo(
		() =>
			enabled && catalog && contours
				? fuelLocationsInArea(catalog, contours)
				: null,
		[enabled, catalog, contours],
	);
	return {
		enabled,
		setEnabled,
		locations,
		loadError,
		sourceDate: catalog?.sourceDate,
	};
}
