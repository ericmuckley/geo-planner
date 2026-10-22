import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { z } from "zod";
import { type Origin, originSchema } from "../src/lib/reachability";
import { decodeGrid } from "../src/server/coarse-data.server";
import {
	distanceKm,
	estimateGrid,
	type GridData,
	gridPosition,
} from "../src/server/coarse-grid";

const savedDirectory = "docs/evidence/coarse-regional-2026-10-22/reference";
const planSchema = z.object({
	id: z.string(),
	scope: z.string(),
	candidateSha256: z.string(),
	referenceBounds: z.array(z.number()).length(4),
	places: z.record(z.string(), originSchema),
	routes: z
		.array(z.object({ from: z.string(), to: z.string(), category: z.string() }))
		.length(24),
});
const tripSchema = z.object({
	trip: z.object({
		status: z.literal(0),
		summary: z.object({
			time: z.number().positive(),
			length: z.number().positive(),
		}),
		legs: z.array(z.object({ shape: z.string().min(1) })).min(1),
	}),
});
const hash = (text: string) => createHash("sha256").update(text).digest("hex");
const args = process.argv.slice(2);
const capture = args[0] === "--capture";
assert.ok(
	!args.length ||
		(capture && args.length === 2) ||
		(args[0] === "--replay" && args.length === 2),
	"Use no arguments for saved replay, --capture <unused-directory>, or --replay <directory>",
);
const directory = args[1] ?? savedDirectory;
const v1Raw = await readFile("src/server/data/coarse-grid-v1.json", "utf8");
const v2Raw = await readFile("src/server/data/coarse-grid-v2.json", "utf8");
const v1 = decodeGrid(JSON.parse(v1Raw));
const v2 = decodeGrid(JSON.parse(v2Raw));
const planRaw = await readFile(
	capture
		? "scripts/fixtures/coarse-regional-v1.json"
		: join(directory, "plan.json"),
	"utf8",
);
const plan = planSchema.parse(JSON.parse(planRaw));
assert.equal(
	hash(v2Raw),
	plan.candidateSha256,
	"This fixed validation set evaluates unchanged v2; version a new run for a changed model",
);
assert.equal(new Set(plan.routes.map((r) => r.from)).size, 12);
for (const route of plan.routes) {
	assert.ok(plan.places[route.from] && plan.places[route.to]);
	assert.ok(
		route.from !== "san-diego",
		"All validation origins must differ from the tuning origin",
	);
}

async function save(name: string, value: unknown) {
	await writeFile(
		join(directory, name),
		`${JSON.stringify(value, null, 2)}\n`,
		{ flag: "wx" },
	);
}

if (capture) {
	await mkdir(directory); // Refuse completed or failed-attempt directory reuse.
	await writeFile(join(directory, "plan.json"), planRaw, { flag: "wx" });
	await save("capture.json", {
		startedAt: new Date().toISOString(),
		planSha256: hash(planRaw),
		candidateSha256: hash(v2Raw),
		referenceUrl: "http://127.0.0.1:8002",
		publicRoutingApiCalls: 0,
	});
}

async function requestReference(path: string, body?: unknown) {
	// Fixed loopback only; no configurable hosted fallback or paid API.
	const response = await fetch(`http://127.0.0.1:8002/${path}`, {
		method: body ? "POST" : "GET",
		headers: body ? { "Content-Type": "application/json" } : undefined,
		body: body ? JSON.stringify(body) : undefined,
		signal: AbortSignal.timeout(20_000),
		redirect: "error",
	});
	return { status: response.status, body: JSON.parse(await response.text()) };
}

const status = capture
	? await requestReference("status")
	: JSON.parse(await readFile(join(directory, "status.json"), "utf8"));
if (capture) await save("status.json", status);
assert.equal(
	status.status,
	200,
	"The retained local reference must already be running",
);

function decodeShape(encoded: string) {
	let index = 0,
		lat = 0,
		lon = 0;
	const points: number[][] = [];
	function component() {
		let value = 0,
			shift = 0,
			byte: number;
		do {
			assert.ok(
				index < encoded.length && shift < 32,
				"Invalid reference shape",
			);
			byte = encoded.charCodeAt(index++) - 63;
			value |= (byte & 31) << shift;
			shift += 5;
		} while (byte >= 32);
		return value & 1 ? ~(value >>> 1) : value >>> 1;
	}
	while (index < encoded.length) {
		lat += component();
		lon += component();
		points.push([lon / 1e6, lat / 1e6]);
	}
	assert.ok(points.length > 1);
	return points;
}

const fields = new Map<string, ReturnType<typeof estimateGrid>>();
function measure(
	grid: GridData,
	version: string,
	from: string,
	destination: Origin,
) {
	const key = `${version}/${from}`;
	let field = fields.get(key);
	if (!field) {
		field = estimateGrid(grid, plan.places[from], 720);
		fields.set(key, field);
	}
	const cell =
		Math.floor((destination.lat - grid.bounds[1]) / grid.step) * grid.width +
		Math.floor((destination.lon - grid.bounds[0]) / grid.step);
	const node = gridPosition(grid, cell);
	const cellMinutes = field.labels[cell];
	assert.ok(
		Number.isFinite(cellMinutes),
		`Unreachable ${version} sample ${from}`,
	);
	const destinationAccessMinutes =
		(distanceKm(node, [destination.lon, destination.lat]) /
			grid.localSpeedKph) *
		60;
	return {
		node,
		cellMinutes,
		originAccessMinutes: (field.attachmentKm / grid.localSpeedKph) * 60,
		destinationAccessMinutes,
		pointMinutes: cellMinutes + destinationAccessMinutes,
		shaded: !!(grid.displayLand ?? grid.land)[cell],
	};
}

const samples = [];
for (const [index, route] of plan.routes.entries()) {
	const id = `${route.from}--${route.to}`;
	const origin = plan.places[route.from],
		destination = plan.places[route.to];
	const request = {
		locations: [origin, destination],
		costing: "auto",
		costing_options: { auto: { speed_types: ["freeflow", "constrained"] } },
		directions_options: { units: "kilometers" },
	};
	let record: {
		request: unknown;
		status?: number;
		body?: unknown;
		error?: string;
	};
	if (capture) {
		try {
			record = { request, ...(await requestReference("route", request)) };
		} catch (error) {
			record = {
				request,
				error: error instanceof Error ? error.message : String(error),
			};
		}
		await save(`${id}.json`, record);
		process.stderr.write(`${index + 1}/${plan.routes.length} captured ${id}\n`);
	} else
		record = JSON.parse(await readFile(join(directory, `${id}.json`), "utf8"));
	assert.deepEqual(record.request, request, `Request drift for ${id}`);
	assert.equal(
		record.status,
		200,
		`Reference failed for ${id}: ${record.error ?? JSON.stringify(record.body)}`,
	);
	const reference = tripSchema.parse(record.body).trip;
	const points = reference.legs.flatMap((leg) => decodeShape(leg.shape));
	const [west, south, east, north] = plan.referenceBounds;
	const minBoundaryDistanceKm = Math.min(
		...points.map((point) =>
			Math.min(
				distanceKm(point, [west, point[1]]),
				distanceKm(point, [east, point[1]]),
				distanceKm(point, [point[0], south]),
				distanceKm(point, [point[0], north]),
			),
		),
	);
	const outsideBounds = points.some(
		([lon, lat]) => lon < west || lon > east || lat < south || lat > north,
	);
	const referenceMinutes = reference.summary.time / 60;
	const baseline = measure(v1, "v1", route.from, destination);
	const candidate = measure(v2, "v2", route.from, destination);
	samples.push({
		id,
		...route,
		origin,
		destination,
		referenceMinutes,
		referenceKm: reference.summary.length,
		referenceSnapKm: {
			origin: distanceKm([origin.lon, origin.lat], points[0]),
			destination: distanceKm(
				[destination.lon, destination.lat],
				points.at(-1) ?? [],
			),
		},
		minReferenceBoundaryDistanceKm: minBoundaryDistanceKm,
		referenceOutsideBounds: outsideBounds,
		baseline,
		candidate,
		baselineCellDeltaMinutes: baseline.cellMinutes - referenceMinutes,
		candidateCellDeltaMinutes: candidate.cellMinutes - referenceMinutes,
		baselinePointDeltaMinutes: baseline.pointMinutes - referenceMinutes,
		candidatePointDeltaMinutes: candidate.pointMinutes - referenceMinutes,
	});
}

function summarize(rows: typeof samples) {
	const mean = (
		key:
			| "baselineCellDeltaMinutes"
			| "candidateCellDeltaMinutes"
			| "baselinePointDeltaMinutes"
			| "candidatePointDeltaMinutes",
		absolute = true,
	) =>
		rows.reduce(
			(sum, row) => sum + (absolute ? Math.abs(row[key]) : row[key]),
			0,
		) / rows.length;
	return {
		cases: rows.length,
		baselineCellMeanAbsoluteDifferenceMinutes: mean("baselineCellDeltaMinutes"),
		candidateCellMeanAbsoluteDifferenceMinutes: mean(
			"candidateCellDeltaMinutes",
		),
		baselinePointMeanAbsoluteDifferenceMinutes: mean(
			"baselinePointDeltaMinutes",
		),
		candidatePointMeanAbsoluteDifferenceMinutes: mean(
			"candidatePointDeltaMinutes",
		),
		candidatePointMeanSignedDifferenceMinutes: mean(
			"candidatePointDeltaMinutes",
			false,
		),
		improvedCellCases: rows.filter(
			(r) =>
				Math.abs(r.candidateCellDeltaMinutes) <
				Math.abs(r.baselineCellDeltaMinutes),
		).length,
		improvedPointCases: rows.filter(
			(r) =>
				Math.abs(r.candidatePointDeltaMinutes) <
				Math.abs(r.baselinePointDeltaMinutes),
		).length,
		candidateFasterThanReferencePointCases: rows.filter(
			(r) => r.candidatePointDeltaMinutes < 0,
		).length,
		unshadedCandidateDestinations: rows.filter((r) => !r.candidate.shaded)
			.length,
		referenceBoundaryWarnings: rows.filter(
			(r) => r.referenceOutsideBounds || r.minReferenceBoundaryDistanceKm < 5,
		).length,
		referenceSnapWarnings: rows.filter(
			(r) =>
				r.referenceSnapKm.origin > 0.1 || r.referenceSnapKm.destination > 0.1,
		).length,
	};
}

console.log(
	JSON.stringify(
		{
			planId: plan.id,
			planSha256: hash(planRaw),
			baselineSha256: hash(v1Raw),
			candidateSha256: hash(v2Raw),
			mode: capture ? "capture" : "offline replay",
			referenceStatus: status.body,
			samples,
			summary: summarize(samples),
			categories: Object.fromEntries(
				[...new Set(samples.map((r) => r.category))].map((category) => [
					category,
					summarize(samples.filter((r) => r.category === category)),
				]),
			),
			publicRoutingApiCalls: 0,
			localServiceRequests: capture ? samples.length + 1 : 0,
			scope: plan.scope,
			limitations: [
				"One static regional reference with incomplete coverage guarantees; boundary proximity is a diagnostic, not a completeness proof.",
				"Both models attach exact endpoints by straight travel at 25 km/h. This is approximate point access; cell arrivals use different representative positions.",
				"No new model fitting, national accuracy, cloud deployment or six-hour boundary accuracy claim.",
			],
		},
		null,
		2,
	),
);
