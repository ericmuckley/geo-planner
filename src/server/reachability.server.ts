import { z } from "zod";
import {
	contoursSchema,
	coverageBoundsSchema,
	engineConfigSchema,
	querySchema,
} from "../lib/reachability";

const statusSchema = z.object({
	version: z.string().min(1),
	available_actions: z.array(z.string()),
});

const orsMetadataSchema = z.object({
	engine: z
		.object({
			version: z.string().optional(),
			graph_date: z.string().optional(),
			osm_date: z.string().optional(),
			build_date: z.string().optional(),
		})
		.optional(),
});

function engineEndpoint(base: string, action: string) {
	const endpoint = new URL(`${base.replace(/\/$/, "")}/${action}`);
	if (!["http:", "https:"].includes(endpoint.protocol))
		throw new Error("Invalid routing protocol");
	return endpoint;
}

function getSettings() {
	const provider = z
		.enum(["valhalla", "openrouteservice"])
		.parse(process.env.ROUTING_PROVIDER || "valhalla");
	if (provider === "openrouteservice") {
		const key = process.env.ORS_API_KEY?.trim();
		return {
			provider,
			key,
			url: key ? "https://api.heigit.org/openrouteservice/v2" : undefined,
			config: engineConfigSchema.parse({
				provider,
				configured: Boolean(key),
				maxMinutes: 60,
				engineVersion: "unrecorded",
				graphVersion: "unrecorded",
				coverage:
					"US focus; hosted OpenStreetMap routing; completeness and border behavior unverified",
			}),
		};
	}
	const url = process.env.VALHALLA_URL;
	const config = engineConfigSchema.parse({
		configured: Boolean(url),
		maxMinutes: Number(process.env.VALHALLA_MAX_MINUTES || 120),
		graphVersion: process.env.VALHALLA_GRAPH_VERSION || "unrecorded",
		engineVersion: process.env.VALHALLA_ENGINE_VERSION || "unrecorded",
		coverage:
			process.env.VALHALLA_COVERAGE || "unrecorded; completeness unknown",
		coverageBounds: process.env.VALHALLA_COVERAGE_BOUNDS
			? coverageBoundsSchema.parse(
					JSON.parse(process.env.VALHALLA_COVERAGE_BOUNDS),
				)
			: undefined,
	});
	return { provider, key: undefined, url, config };
}

const configurationError =
	"Invalid routing configuration. Check ROUTING_PROVIDER, VALHALLA_MAX_MINUTES (1–720) and VALHALLA_COVERAGE_BOUNDS.";

function json(data: unknown, status = 200) {
	return Response.json(data, {
		status,
		headers: { "Cache-Control": "no-store" },
	});
}

export async function getEngineConfig() {
	let settings: ReturnType<typeof getSettings>;
	try {
		settings = getSettings();
	} catch {
		return json(
			{
				error: configurationError,
			},
			503,
		);
	}
	const { url, config } = settings;
	if (!url) return json({ ...config, health: "unconfigured" });
	if (settings.provider === "openrouteservice") {
		return json({
			...config,
			health: "unchecked",
			healthMessage:
				"API key configured. Compute a contour to check the connection; loading this page does not use your request quota.",
		});
	}
	const checkedAt = new Date().toISOString();
	try {
		const response = await fetch(engineEndpoint(url, "status"), {
			signal: AbortSignal.timeout(3_000),
			cache: "no-store",
		});
		if (!response.ok) throw new Error("Routing status unavailable");
		const status = statusSchema.parse(await response.json());
		if (!status.available_actions.includes("isochrone"))
			throw new Error("Reachability unavailable");
		if (
			config.engineVersion !== "unrecorded" &&
			status.version !== config.engineVersion
		) {
			return json({
				...config,
				health: "mismatch",
				checkedAt,
				healthMessage:
					"The routing engine version differs from the configured version. Check the service and provenance before computing.",
			});
		}
		return json({ ...config, health: "ready", checkedAt });
	} catch {
		return json({
			...config,
			health: "unavailable",
			checkedAt,
			healthMessage:
				"The routing service did not pass its health check. Check the service and reload to retry.",
		});
	}
}

export async function runReachability(request: Request) {
	const started = performance.now();
	let input: unknown;
	try {
		input = await request.json();
	} catch {
		return json({ error: "Expected a JSON query." }, 400);
	}
	const parsed = querySchema.safeParse(input);
	if (!parsed.success) {
		return json({ error: "Invalid query.", issues: parsed.error.issues }, 422);
	}
	let settings: ReturnType<typeof getSettings>;
	try {
		settings = getSettings();
	} catch {
		return json(
			{
				error: configurationError,
			},
			503,
		);
	}
	const { url, config } = settings;
	const hosted = settings.provider === "openrouteservice";
	const providerName = hosted ? "Openrouteservice" : "Valhalla";
	if (!url) {
		return json(
			{
				error: hosted
					? "Routing is not connected. Set the server-only ORS_API_KEY and restart the app."
					: "Routing is not connected. Set VALHALLA_URL to a self-hosted service and restart the app.",
			},
			503,
		);
	}
	const query = parsed.data;
	if (config.coverageBounds) {
		const [west, south, east, north] = config.coverageBounds;
		const { lat, lon } = query.origin;
		const longitudeInside =
			west < east ? lon >= west && lon <= east : lon >= west || lon <= east;
		if (lat < south || lat > north || !longitudeInside) {
			return json(
				{
					error:
						"This origin is outside the connected routing dataset. Choose an origin within its coverage or connect a broader dataset.",
				},
				422,
			);
		}
	}
	if (query.budgetMinutes > config.maxMinutes) {
		return json(
			{
				error: hosted
					? "Openrouteservice's hosted driving contours support at most 60 minutes. Longer budgets require revisiting the routing backend."
					: `This service is configured for at most ${config.maxMinutes} minutes. Raise both app and engine limits after verifying graph coverage.`,
			},
			422,
		);
	}
	const speedTypes = ["freeflow", "constrained"];
	const generalizeMeters = 100;
	const denoise = 0;
	try {
		const endpoint = engineEndpoint(
			url,
			hosted ? "isochrones/driving-car" : "isochrone",
		);
		const engineStarted = performance.now();
		const upstream = await fetch(endpoint, {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				...(settings.key ? { Authorization: settings.key } : {}),
			},
			body: JSON.stringify(
				hosted
					? {
							locations: [[query.origin.lon, query.origin.lat]],
							location_type: "start",
							range_type: "time",
							range: [query.budgetMinutes * 60],
							smoothing: 0,
						}
					: {
							locations: [{ lat: query.origin.lat, lon: query.origin.lon }],
							costing: query.mode,
							costing_options: { auto: { speed_types: speedTypes } },
							contours: [{ time: query.budgetMinutes }],
							polygons: true,
							show_locations: true,
							reverse: false,
							generalize: generalizeMeters,
							denoise,
						},
			),
			signal: AbortSignal.any([request.signal, AbortSignal.timeout(30_000)]),
		});
		if (hosted && upstream.status === 429) {
			return json(
				{
					error:
						"Openrouteservice's free request limit was reached. Wait before retrying; revisit self-hosting if limits become a problem.",
				},
				429,
			);
		}
		if (!upstream.ok) {
			return json(
				{
					error:
						hosted && [401, 403].includes(upstream.status)
							? "Openrouteservice rejected access. Check the API key, its permissions and the account's remaining daily quota."
							: `${providerName} rejected the request (HTTP ${upstream.status}). Check service limits and origin coverage.`,
				},
				502,
			);
		}
		const body = await upstream.text();
		const engineRoundTripMs = performance.now() - engineStarted;
		const decodeStarted = performance.now();
		const decoded = JSON.parse(body);
		const contours = contoursSchema.safeParse(decoded);
		if (!contours.success) {
			return json(
				{
					error: `${providerName} returned an invalid or empty polygon result.`,
				},
				502,
			);
		}
		const orsMetadata = hosted
			? orsMetadataSchema.parse(decoded.metadata || {})
			: undefined;
		const decodeValidateMs = performance.now() - decodeStarted;
		return json({
			id: crypto.randomUUID(),
			createdAt: new Date().toISOString(),
			query,
			contours: contours.data,
			metadata: {
				engine: settings.provider,
				graphVersion: orsMetadata?.engine?.graph_date || config.graphVersion,
				engineVersion: orsMetadata?.engine?.version || config.engineVersion,
				coverage: config.coverage,
				coverageBounds: config.coverageBounds,
				coverageVerified: false,
				...(hosted
					? {
							profile: "driving-car",
							smoothing: 0,
							attribution:
								"© openrouteservice by HeiGIT | Data from OpenStreetMap",
							license: "CC-BY-SA-4.0",
							osmDate: orsMetadata?.engine?.osm_date,
							graphDate: orsMetadata?.engine?.graph_date,
							buildDate: orsMetadata?.engine?.build_date,
						}
					: { speedTypes, generalizeMeters, denoise }),
				upstreamBytes: new TextEncoder().encode(body).byteLength,
				timings: {
					engineRoundTripMs,
					decodeValidateMs,
					serverTotalMs: performance.now() - started,
				},
			},
		});
	} catch (error) {
		if (request.signal.aborted)
			return json({ error: "Request cancelled." }, 408);
		if (error instanceof Error && error.name === "TimeoutError") {
			return json(
				{ error: `${providerName} exceeded the 30-second request timeout.` },
				504,
			);
		}
		return json(
			{
				error: `Could not read a valid response from ${providerName}. Check server configuration, connectivity, and service status.`,
			},
			502,
		);
	}
}
