import {
	createPlaceLookup,
	isStreetAddress,
	type PlaceMatch,
	placeCatalogUrl,
	placeSearchResponseSchema,
} from "./place-search";

let placeLookup: Promise<ReturnType<typeof createPlaceLookup>> | undefined;

export async function searchPlaces(
	query: string,
	signal: AbortSignal,
): Promise<PlaceMatch[]> {
	if (isStreetAddress(query)) {
		const response = await fetch("/api/place-search", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ query }),
			signal,
		});
		if (!response.ok) throw new Error("Address lookup failed");
		return placeSearchResponseSchema.parse(await response.json()).matches;
	}

	placeLookup ??= fetch(placeCatalogUrl)
		.then(async (response) => {
			if (!response.ok) throw new Error("Place catalog could not load");
			return createPlaceLookup(await response.json());
		})
		.catch((error) => {
			placeLookup = undefined;
			throw error;
		});
	const lookup = await placeLookup;
	signal.throwIfAborted();
	return lookup(query);
}
