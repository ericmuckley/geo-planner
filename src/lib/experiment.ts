import { z } from "zod";
import { coverageBoundsSchema, originSchema } from "./reachability";

export const experimentQuerySchema = z.strictObject({
	origin: originSchema,
	budgetMinutes: z.number().int().min(1).max(720),
});

const position = z.tuple([
	z.number().finite().min(-180).max(180),
	z.number().finite().min(-90).max(90),
]);
const line = z.array(position).min(2);
export const experimentConfigSchema = z.object({
	ready: z.literal(true),
	graphIdentity: z.string().regex(/^[a-f0-9]{64}$/),
	bounds: coverageBoundsSchema,
	maxMinutes: z.literal(720),
	model: z.string(),
	sourceDate: z.iso.datetime(),
	publicApiCalls: z.literal(0),
});

export const experimentResultSchema = z.object({
	id: z.string(),
	query: experimentQuerySchema,
	geometry: z.object({
		type: z.literal("FeatureCollection"),
		features: z
			.array(
				z.object({
					type: z.literal("Feature"),
					properties: z.record(z.string(), z.unknown()),
					geometry: z.discriminatedUnion("type", [
						z.object({ type: z.literal("Point"), coordinates: position }),
						z.object({ type: z.literal("LineString"), coordinates: line }),
						z.object({
							type: z.literal("MultiLineString"),
							coordinates: z.array(line).max(30000),
						}),
					]),
				}),
			)
			.min(2)
			.max(100000),
	}),
	metadata: experimentConfigSchema.extend({
		coverageVerified: z.literal(false),
		truncated: z.boolean(),
		reachedCutNodes: z.number().int().nonnegative(),
		auditedCutNodes: z.number().int().nonnegative(),
		cutsBySide: z.object({
			north: z.number().int().nonnegative(),
			east: z.number().int().nonnegative(),
			south: z.number().int().nonnegative(),
			west: z.number().int().nonnegative(),
		}),
		firstReachedCutMs: z.number().nonnegative().nullable(),
		settledStates: z.number().int().nonnegative(),
		snap: z.object({
			input: position,
			snapped: position,
			distanceMeters: z.number().nonnegative(),
		}),
		display: z.object({
			reachableDirectedRoads: z.number().int().nonnegative(),
			displayedSegments: z.number().int().min(0).max(30000),
			sampleStride: z.number().int().min(1),
			displayLimit: z.literal(30000),
			reachableBounds: z.array(z.number().finite()).length(4).nullable(),
		}),
		warnings: z.array(z.string()),
		timings: z.object({
			snapMs: z.number().nonnegative(),
			nativeSearchMs: z.number().nonnegative(),
			nativeRoundTripMs: z.number().nonnegative(),
			geometryMs: z.number().nonnegative(),
			workerTotalMs: z.number().nonnegative(),
			appProxyMs: z.number().nonnegative().optional(),
		}),
	}),
});

export type ExperimentResult = z.infer<typeof experimentResultSchema>;
export type ExperimentConfig = z.infer<typeof experimentConfigSchema>;
