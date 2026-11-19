import { z } from "zod";
import { originSchema } from "./reachability";

const stateNames = {
	AL: "Alabama",
	AZ: "Arizona",
	AR: "Arkansas",
	CA: "California",
	CO: "Colorado",
	CT: "Connecticut",
	DE: "Delaware",
	DC: "District of Columbia",
	FL: "Florida",
	GA: "Georgia",
	ID: "Idaho",
	IL: "Illinois",
	IN: "Indiana",
	IA: "Iowa",
	KS: "Kansas",
	KY: "Kentucky",
	LA: "Louisiana",
	ME: "Maine",
	MD: "Maryland",
	MA: "Massachusetts",
	MI: "Michigan",
	MN: "Minnesota",
	MS: "Mississippi",
	MO: "Missouri",
	MT: "Montana",
	NE: "Nebraska",
	NV: "Nevada",
	NH: "New Hampshire",
	NJ: "New Jersey",
	NM: "New Mexico",
	NY: "New York",
	NC: "North Carolina",
	ND: "North Dakota",
	OH: "Ohio",
	OK: "Oklahoma",
	OR: "Oregon",
	PA: "Pennsylvania",
	RI: "Rhode Island",
	SC: "South Carolina",
	SD: "South Dakota",
	TN: "Tennessee",
	TX: "Texas",
	UT: "Utah",
	VT: "Vermont",
	VA: "Virginia",
	WA: "Washington",
	WV: "West Virginia",
	WI: "Wisconsin",
	WY: "Wyoming",
};

const stateAliases = new Map(
	Object.entries(stateNames).flatMap(([code, name]) => [
		[code.toLowerCase(), code],
		[name.toLowerCase(), code],
	]),
);

export const placeSearchLimit = 6;
export const placeSearchMinLength = 2;
export const placeSearchMaxLength = 160;
export const placeCatalogUrl = "/places/search-us-v2.json";

export function isContiguousState(code: string) {
	return Object.hasOwn(stateNames, code);
}

export function isStreetAddress(query: string) {
	return /^\d+[a-z]?(?:-\d+)?\s+\S/iu.test(query);
}

const placeRowsSchema = z
	.array(
		z.tuple([
			z.string().min(1).max(200),
			z.string().refine(isContiguousState),
			z.number().min(24).max(50),
			z.number().min(-125).max(-66),
			z.union([z.literal(0), z.literal(1)]),
		]),
	)
	.max(300_000);

const placeMatchSchema = z.object({
	label: z.string().min(1).max(240),
	kind: z.enum(["Community", "Landmark", "Street address"]),
	point: originSchema,
});
export const placeSearchResponseSchema = z.object({
	matches: z.array(placeMatchSchema).max(placeSearchLimit),
});
export type PlaceMatch = z.infer<typeof placeMatchSchema>;

function normalizeName(value: string) {
	return value
		.normalize("NFKD")
		.toLowerCase()
		.replace(/[\p{M}'’]/gu, "")
		.replace(/[^\p{L}\p{N}]+/gu, " ")
		.trim();
}

function splitPlaceQuery(query: string) {
	const comma = query.lastIndexOf(",");
	if (comma !== -1) {
		const state = stateAliases.get(normalizeName(query.slice(comma + 1)));
		if (state) return { name: normalizeName(query.slice(0, comma)), state };
	}
	const words = normalizeName(query).split(" ");
	for (let size = Math.min(3, words.length - 1); size >= 1; size--) {
		const suffix = stateAliases.get(words.slice(-size).join(" "));
		if (suffix) {
			return {
				name: words.slice(0, -size).join(" "),
				state: suffix,
				fullName: words.join(" "),
			};
		}
	}
	return { name: words.join(" "), state: undefined };
}

export function createPlaceLookup(data: unknown) {
	const places = placeRowsSchema.parse(data).map((row) => ({
		row,
		name: normalizeName(row[0]),
	}));

	return (query: string): PlaceMatch[] => {
		const { name, state, fullName } = splitPlaceQuery(query);
		if (name.length < placeSearchMinLength) return [];
		const matches: Array<{
			row: (typeof places)[number]["row"];
			rank: number;
		}> = [];
		for (const place of places) {
			if (place.name === fullName) {
				matches.push({ row: place.row, rank: place.row[4] - 2 });
				continue;
			}
			if (state && place.row[1] !== state) continue;
			const offset = place.name.indexOf(name);
			if (offset < 0 || (offset > 0 && place.name[offset - 1] !== " "))
				continue;
			const rank =
				(place.name === name ? 0 : offset === 0 ? 2 : 4) + place.row[4];
			matches.push({ row: place.row, rank });
		}

		return matches
			.sort((first, second) => first.rank - second.rank)
			.slice(0, placeSearchLimit)
			.map(({ row: [label, state, lat, lon, kind] }) => ({
				label: `${label}, ${state}`,
				kind: kind === 0 ? "Community" : "Landmark",
				point: { lat, lon },
			}));
	};
}
