import { z } from "zod";
import { maximumElevationFeet } from "./area-layers";
import { coarseBudgetMinutesSchema, originSchema } from "./reachability";

const exampleOrigin = { lat: 35.1983, lon: -111.6513 };
// Accept the earlier URL range and cap it at the slider's maximum.
const minimumElevationSchema = z
	.number()
	.min(0)
	.max(15_000)
	.transform((feet) => Math.min(Math.round(feet), maximumElevationFeet));

const mapSearchSchema = z.object({
	lat: originSchema.shape.lat.optional().catch(undefined),
	lon: originSchema.shape.lon.optional().catch(undefined),
	minutes: coarseBudgetMinutesSchema.optional().catch(undefined),
	fuel: z.boolean().catch(false),
	trailheads: z.boolean().optional().catch(undefined),
	campgrounds: z.boolean().optional().catch(undefined),
	land: z.boolean().optional().catch(undefined),
	elevation: z.boolean().catch(false),
	publicLandOnly: z.boolean().catch(false),
	elevationOnly: z.boolean().catch(false),
	minElevation: minimumElevationSchema.catch(5000),
	maxElevation: z
		.number()
		.min(0)
		.max(maximumElevationFeet)
		.transform(Math.round)
		.catch(maximumElevationFeet),
});

export function validateMapSearch(search: Record<string, unknown>) {
	const params = mapSearchSchema.parse(search);
	const { lat, lon, minElevation, maxElevation } = params;
	const demo = Object.keys(search).length === 0;
	const hasOrigin = lat !== undefined && lon !== undefined;
	return {
		...params,
		...(hasOrigin ? { lat, lon } : exampleOrigin),
		minutes: params.minutes ?? 120,
		trailheads: params.trailheads ?? demo,
		campgrounds: params.campgrounds ?? demo,
		land: params.land ?? demo,
		minElevation: Math.min(minElevation, maxElevation),
		maxElevation: Math.max(minElevation, maxElevation),
	};
}

export type MapSearch = ReturnType<typeof validateMapSearch>;
