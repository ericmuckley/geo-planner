import { z } from "zod";
import {
	isContiguousState,
	isStreetAddress,
	type PlaceMatch,
	placeSearchLimit,
	placeSearchMaxLength,
} from "../lib/place-search";
import { readRequestJson } from "./read-request-json.server";

const addressRequestSchema = z.strictObject({
	query: z
		.string()
		.trim()
		.min(5)
		.max(placeSearchMaxLength)
		.refine(isStreetAddress),
});
const censusResponseSchema = z.object({
	result: z.object({
		addressMatches: z.array(
			z.object({
				matchedAddress: z.string().trim().min(1).max(240),
				coordinates: z.object({
					x: z.number().min(-180).max(180),
					y: z.number().min(-85).max(85),
				}),
				addressComponents: z.object({ state: z.string() }),
			}),
		),
	}),
});
const censusUrl =
	"https://geocoding.geo.census.gov/geocoder/locations/onelineaddress";

export async function handlePlaceSearch(request: Request, fetchCensus = fetch) {
	const json = (body: unknown, status = 200) =>
		Response.json(body, { status, headers: { "Cache-Control": "no-store" } });
	const origin = request.headers.get("Origin");
	if (
		(origin && origin !== new URL(request.url).origin) ||
		request.headers.get("Sec-Fetch-Site") === "cross-site"
	) {
		return json(
			{ error: "Place search is available only from this app." },
			403,
		);
	}

	let input: unknown;
	try {
		input = await readRequestJson(request, 2048);
	} catch {
		return json({ error: "Enter a street number and street name." }, 400);
	}
	const parsed = addressRequestSchema.safeParse(input);
	if (!parsed.success) {
		return json({ error: "Enter a street number and street name." }, 400);
	}

	try {
		const url = new URL(censusUrl);
		url.search = new URLSearchParams({
			address: parsed.data.query,
			benchmark: "Public_AR_Current",
			format: "json",
		}).toString();
		const response = await fetchCensus(url, {
			headers: { Accept: "application/json" },
			signal: AbortSignal.any([request.signal, AbortSignal.timeout(7000)]),
		});
		if (!response.ok) throw new Error("Census Geocoder could not respond");
		const { result } = censusResponseSchema.parse(await response.json());
		const matches: PlaceMatch[] = [];
		for (const match of result.addressMatches) {
			if (!isContiguousState(match.addressComponents.state)) continue;
			const { x, y } = match.coordinates;
			matches.push({
				label: match.matchedAddress,
				kind: "Street address",
				point: { lat: y, lon: x },
			});
			if (matches.length === placeSearchLimit) break;
		}
		return json({ matches });
	} catch {
		return json(
			{ error: "Address lookup is unavailable. Try again shortly." },
			502,
		);
	}
}
