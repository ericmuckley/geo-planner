import {
	engineConfigSchema,
	querySchema,
	type ReachabilityResult,
	resultSchema,
} from "../lib/reachability";
import { decodeGrid } from "./coarse-data.server";
import { estimateGrid, type GridData } from "./coarse-grid";
import data from "./data/coarse-grid-v4.json";

let grid: GridData | undefined;
function getGrid() {
	if (!grid) {
		grid = decodeGrid(data);
	}
	return grid;
}

const config = engineConfigSchema.parse({
	provider: "coarse",
	configured: true,
	health: "ready",
	minMinutes: 60,
	maxMinutes: 720,
	engineVersion: "coarse-road-grid-v4",
	graphVersion: data.version,
	coverage:
		"Contiguous United States; coarse estimated travel over land and major roads",
	coverageBounds: data.bounds,
	healthMessage:
		"Ready without a routing service or API key. Rough planning estimates; travel-time accuracy has not been calibrated.",
});

function json(body: unknown, status = 200) {
	return Response.json(body, {
		status,
		headers: { "Cache-Control": "no-store" },
	});
}

export function getEstimateConfig() {
	return json(config);
}

export async function runEstimate(request: Request) {
	const started = performance.now();
	let input: unknown;
	try {
		const body = await request.text();
		if (body.length > 2048) return json({ error: "Query is too large." }, 400);
		input = JSON.parse(body);
	} catch {
		return json({ error: "Expected a JSON query." }, 400);
	}
	const parsed = querySchema.safeParse(input);
	if (!parsed.success || parsed.data.budgetMinutes < 60)
		return json(
			{
				error:
					"Choose valid coordinates and a whole-minute budget from 60 to 720.",
			},
			422,
		);
	if (request.signal.aborted) return json({ error: "Request cancelled." }, 408);
	try {
		const query = parsed.data;
		const estimate = estimateGrid(getGrid(), query.origin, query.budgetMinutes);
		const contours: ReachabilityResult["contours"] = {
			type: "FeatureCollection",
			features: [
				{
					type: "Feature",
					properties: {
						contour: query.budgetMinutes,
						metric: "time",
						approximate: true,
					},
					geometry: { type: "MultiPolygon", coordinates: estimate.coordinates },
				},
			],
			warnings: [
				{
					description:
						"Very coarse estimate: 0.1° cells (about 7–11 km) merge nearby roads and crossings. This is display resolution, not a measured accuracy bound.",
				},
				{
					description:
						"Local travel is estimated at 25 km/h, including places without roads. Input access can follow its cell's retained road geometry at the existing road-class speed after checked local access. Generalized roads use geometry-based times at assumed 55–105 km/h speeds, including approximate transfers within cells. No traffic, one-way roads, turn restrictions, terrain or actual access checks.",
				},
				{
					description:
						"Natural Earth is a generalized cartographic dataset, not a current routable road inventory. US-only road features are used; international crossings and ferries are not modeled. Shore connections require continuous generalized land. Input access allows up to 1 km of initial shore tolerance; unsupported origins remain isolated. Whole-cell shading can extend across borders or water. Small islands and water crossings can be inaccurate.",
				},
			],
		};
		const computeMs = performance.now() - started;
		const result = resultSchema.parse({
			id: crypto.randomUUID(),
			createdAt: new Date().toISOString(),
			query,
			contours,
			metadata: {
				engine: "coarse",
				graphVersion: data.version,
				engineVersion: config.engineVersion,
				coverage: config.coverage,
				coverageBounds: data.bounds,
				coverageVerified: false,
				profile: "Static road-informed grid estimate",
				attribution: data.attribution,
				license: data.license,
				upstreamBytes: 0,
				approximation: {
					gridDegrees: data.step,
					localSpeedKph: data.localSpeedKph,
					reachedCells: estimate.reachedCells,
					attachmentKm: estimate.attachmentKm,
					sourceRelease: data.sourceRelease,
				},
				timings: {
					engineRoundTripMs: computeMs,
					decodeValidateMs: 0,
					serverTotalMs: computeMs,
					searchMs: estimate.searchMs,
					contourMs: estimate.contourMs,
				},
			},
		});
		result.metadata.timings.decodeValidateMs =
			performance.now() - started - computeMs;
		result.metadata.timings.serverTotalMs = performance.now() - started;
		return json(result);
	} catch (error) {
		if (error instanceof RangeError) return json({ error: error.message }, 422);
		console.error("Coarse estimate failed", error);
		return json(
			{
				error:
					"The estimate could not be computed. Try a nearby mainland origin.",
			},
			500,
		);
	}
}
