import assert from "node:assert/strict";
import test from "node:test";
import { createPlaceLookup } from "../lib/place-search";
import { handlePlaceSearch } from "./place-search.server";

const lookup = createPlaceLookup([
	["Springfield", "MA", 42.1015, -72.5898, 0],
	["Springfield", "IL", 39.7817, -89.6501, 0],
	["Lake Springfield", "IL", 39.695, -89.613, 1],
	["Mount Washington", "NH", 44.2706, -71.3033, 1],
	["Mount Adams", "WA", 46.2024, -121.4907, 1],
	["San José", "CA", 37.3382, -121.8863, 0],
]);

test("place lookup ranks exact names and supports state abbreviations, state names, and accents", () => {
	assert.deepEqual(
		lookup("Springfield").map((match) => match.label),
		["Springfield, MA", "Springfield, IL", "Lake Springfield, IL"],
	);
	assert.deepEqual(
		lookup("springfield il").map((match) => match.label),
		["Springfield, IL", "Lake Springfield, IL"],
	);
	assert.deepEqual(
		lookup("Springfield, Massachusetts").map((match) => match.label),
		["Springfield, MA"],
	);
	assert.equal(lookup("Mount Washington")[0]?.label, "Mount Washington, NH");
	assert.equal(lookup("san jose")[0]?.label, "San José, CA");
	assert.deepEqual(lookup("None Found"), []);
});

function searchRequest(body: unknown, origin = "https://example.test") {
	return new Request("https://example.test/api/place-search", {
		method: "POST",
		headers: { Origin: origin, "Content-Type": "application/json" },
		body: JSON.stringify(body),
	});
}

test("Census lookup forwards a submitted address and returns validated local coordinates", async () => {
	const query = "4600 Silver Hill Rd, Suitland, MD";
	const response = await handlePlaceSearch(
		searchRequest({ query }),
		async (input) => {
			const url = new URL(String(input));
			assert.equal(url.hostname, "geocoding.geo.census.gov");
			assert.equal(url.searchParams.get("address"), query);
			assert.equal(url.searchParams.get("benchmark"), "Public_AR_Current");
			return Response.json({
				result: {
					addressMatches: [
						{
							matchedAddress: "4600 SILVER HILL RD, SUITLAND, MD, 20746",
							coordinates: { x: -76.92836, y: 38.84505 },
							addressComponents: { state: "MD" },
						},
						{
							matchedAddress: "1 OTHER ST, ANCHORAGE, AK",
							coordinates: { x: -149, y: 61 },
							addressComponents: { state: "AK" },
						},
					],
				},
			});
		},
	);
	assert.equal(response.status, 200);
	assert.equal(response.headers.get("cache-control"), "no-store");
	assert.deepEqual(await response.json(), {
		matches: [
			{
				label: "4600 SILVER HILL RD, SUITLAND, MD, 20746",
				kind: "Street address",
				point: { lat: 38.84505, lon: -76.92836 },
			},
		],
	});
});

test("invalid or cross-site requests skip Census and upstream failure is handled", async () => {
	const neverFetch = async () => assert.fail("Unexpected Census request");
	const invalid = await handlePlaceSearch(
		searchRequest({ query: "Flagstaff AZ" }),
		neverFetch,
	);
	assert.equal(invalid.status, 400);
	const oversized = await handlePlaceSearch(
		searchRequest({ query: `4600 ${"A".repeat(2048)}` }),
		neverFetch,
	);
	assert.equal(oversized.status, 400);
	const crossSite = await handlePlaceSearch(
		searchRequest({ query: "4600 Silver Hill Rd, MD" }, "https://another.test"),
		neverFetch,
	);
	assert.equal(crossSite.status, 403);
	const upstream = await handlePlaceSearch(
		searchRequest({ query: "4600 Silver Hill Rd, MD" }),
		async () => new Response("Unavailable", { status: 503 }),
	);
	assert.equal(upstream.status, 502);
});
