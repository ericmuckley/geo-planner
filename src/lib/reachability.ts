import { z } from "zod";

export const originSchema = z.strictObject({
	lat: z.number().finite().min(-85).max(85),
	lon: z.number().finite().min(-180).max(180),
});

export const querySchema = z.strictObject({
	version: z.literal(1),
	origin: originSchema,
	mode: z.literal("auto"),
	direction: z.literal("outbound"),
	metric: z.literal("time"),
	budgetMinutes: z.number().int().min(1).max(720),
});

export type Origin = z.infer<typeof originSchema>;
export type ReachabilityQuery = z.infer<typeof querySchema>;

export const coverageBoundsSchema = z
	.tuple([
		z.number().min(-180).max(180),
		z.number().min(-90).max(90),
		z.number().min(-180).max(180),
		z.number().min(-90).max(90),
	])
	.refine(
		([west, south, east, north]) => west !== east && south < north,
		"Invalid coverage bounds",
	);

export const defaultQuery: ReachabilityQuery = {
	version: 1,
	origin: { lat: 32.7157, lon: -117.1611 },
	mode: "auto",
	direction: "outbound",
	metric: "time",
	budgetMinutes: 60,
};

const position = z.tuple([
	z.number().finite().min(-180).max(180),
	z.number().finite().min(-90).max(90),
]);
const ring = z
	.array(position)
	.min(4)
	.refine((points) => {
		const first = points[0];
		const last = points.at(-1);
		return first[0] === last?.[0] && first[1] === last?.[1];
	}, "Polygon rings must be closed");
const polygon = z.array(ring).min(1);

export const contoursSchema = z.object({
	type: z.literal("FeatureCollection"),
	features: z
		.array(
			z.object({
				type: z.literal("Feature"),
				properties: z.record(z.string(), z.unknown()).nullable(),
				geometry: z.discriminatedUnion("type", [
					z.object({ type: z.literal("Point"), coordinates: position }),
					z.object({ type: z.literal("Polygon"), coordinates: polygon }),
					z.object({
						type: z.literal("MultiPolygon"),
						coordinates: z.array(polygon).min(1),
					}),
					z.object({
						type: z.literal("MultiPoint"),
						coordinates: z.array(position).min(1),
					}),
				]),
			}),
		)
		.min(1)
		.refine(
			(features) =>
				features.some(
					(feature) =>
						feature.geometry.type === "Polygon" ||
						feature.geometry.type === "MultiPolygon",
				),
			"No contour polygons returned",
		),
	warnings: z
		.array(
			z.object({
				code: z.number().optional(),
				description: z.string(),
			}),
		)
		.optional(),
});

export const engineConfigSchema = z.object({
	configured: z.boolean(),
	provider: z.enum(["valhalla", "openrouteservice", "coarse"]).optional(),
	health: z
		.enum(["unconfigured", "unchecked", "ready", "unavailable", "mismatch"])
		.optional(),
	healthMessage: z.string().optional(),
	checkedAt: z.iso.datetime().optional(),
	maxMinutes: z.number().int().min(1).max(720),
	minMinutes: z.number().int().min(1).max(720).optional(),
	graphVersion: z.string(),
	engineVersion: z.string(),
	coverage: z.string(),
	coverageBounds: coverageBoundsSchema.optional(),
});

export const resultMetadataSchema = z.object({
	engine: z.enum(["valhalla", "openrouteservice", "coarse"]),
	graphVersion: z.string(),
	engineVersion: z.string(),
	coverage: z.string(),
	coverageBounds: coverageBoundsSchema.optional(),
	coverageVerified: z.literal(false),
	profile: z.string().optional(),
	attribution: z.string().optional(),
	license: z.string().optional(),
	osmDate: z.string().optional(),
	graphDate: z.string().optional(),
	buildDate: z.string().optional(),
	smoothing: z.number().optional(),
	speedTypes: z.array(z.string()).optional(),
	generalizeMeters: z.number().optional(),
	denoise: z.number().optional(),
	upstreamBytes: z.number().nonnegative(),
	approximation: z
		.object({
			gridDegrees: z.number().positive(),
			localSpeedKph: z.number().positive(),
			reachedCells: z.number().int().nonnegative(),
			attachmentKm: z.number().nonnegative(),
			sourceRelease: z.string(),
		})
		.optional(),
	timings: z.object({
		engineRoundTripMs: z.number().nonnegative(),
		decodeValidateMs: z.number().nonnegative(),
		serverTotalMs: z.number().nonnegative(),
		searchMs: z.number().nonnegative().optional(),
		contourMs: z.number().nonnegative().optional(),
	}),
});

export const resultSchema = z.object({
	id: z.string(),
	createdAt: z.iso.datetime(),
	query: querySchema,
	contours: contoursSchema,
	metadata: resultMetadataSchema,
});

export type EngineConfig = z.infer<typeof engineConfigSchema>;
export type ReachabilityResult = z.infer<typeof resultSchema>;

export const savedRunSchema = z.object({
	id: z.string().min(1).max(128),
	createdAt: z.iso.datetime(),
	query: querySchema,
	model: z.enum(["coarse", "connected"]).optional(),
	metadata: resultMetadataSchema.optional(),
	clientRequestMs: z.number().nonnegative().optional(),
	sourceToMapIdleMs: z.number().nonnegative().optional(),
});

export type SavedRun = z.infer<typeof savedRunSchema>;
