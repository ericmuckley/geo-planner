// New 29-query producer version; sealed six/48-query producers stay unchanged.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { z } from "zod";
import { distanceKm } from "../src/server/coarse-grid";

import { planSha256, readBenchmarkPlan } from "./coarse-benchmark-plan";

export { planPath, planSha256 } from "./coarse-benchmark-plan";

const endpoint =
	"https://api.heigit.org/openrouteservice/v2/directions/driving-car/geojson";
const maximumBodyBytes = 2_000_000;
const json = (value: unknown) => `${JSON.stringify(value, null, 2)}\n`;
const hash = (bytes: string | Buffer) =>
	createHash("sha256").update(bytes).digest("hex");
const prefix = (i: number) => String(i).padStart(2, "0");
const pointSchema = z.tuple([
	z.number().min(-180).max(180),
	z.number().min(-90).max(90),
]);
const querySchema = z.object({
	id: z.string(),
	existingValhallaMinutes: z.number().positive(),
	existingValhallaKm: z.number().positive(),
	v8Minutes: z.number().positive(),
	request: z.object({
		coordinates: z.tuple([pointSchema, pointSchema]),
		instructions: z.literal(false),
		preference: z.literal("fastest"),
		radiuses: z.tuple([z.literal(350), z.literal(350)]),
		options: z.object({
			avoid_borders: z.literal("all"),
			avoid_features: z.tuple([z.literal("ferries")]),
		}),
	}),
});
const resultSchema = z.object({
	id: z.string(),
	attempt: z.number().int().min(1).max(29),
	requestSha256: z.string(),
	startedAt: z.iso.datetime(),
	finishedAt: z.iso.datetime(),
	httpAndBodyMs: z.number().nonnegative(),
	status: z.number().int().nullable(),
	headers: z.record(z.string(), z.string()),
	bodySha256: z.string().nullable(),
	bodyBytes: z.number().int().nonnegative(),
	bodyRedacted: z.boolean(),
	error: z.enum(["network-or-timeout", "body-limit"]).nullable(),
});
type CaptureResult = z.infer<typeof resultSchema>;
type CaptureRuntime = {
	transport: typeof fetch;
	now: () => number;
	wait: (ms: number) => Promise<unknown>;
	timeout: (ms: number) => AbortSignal;
};
const runtime: CaptureRuntime = {
	transport: fetch,
	now: Date.now,
	wait: delay,
	timeout: AbortSignal.timeout,
};
export async function readCapturePlan() {
	const inputs = await readBenchmarkPlan();
	return {
		...inputs,
		queries: z.array(querySchema).length(29).parse(inputs.queries),
	};
}

const referenceSchema = z.object({
	type: z.literal("FeatureCollection"),
	features: z
		.array(
			z.object({
				geometry: z.object({
					type: z.literal("LineString"),
					coordinates: z.array(pointSchema).min(2),
				}),
				properties: z.object({
					summary: z.object({
						duration: z.number().positive(),
						distance: z.number().positive(),
					}),
				}),
			}),
		)
		.length(1),
	metadata: z
		.object({
			engine: z
				.object({
					version: z.string().optional(),
					build_date: z.string().optional(),
					graph_date: z.string().optional(),
					osm_date: z.string().optional(),
				})
				.optional(),
		})
		.optional(),
});
type Query = z.infer<typeof querySchema>;
function reference(raw: string, query: Query) {
	const response = referenceSchema.parse(JSON.parse(raw));
	const feature = response.features[0],
		points = feature.geometry.coordinates;
	const snapMeters = [points[0], points[points.length - 1]].map(
		(p, i) => distanceKm(p, query.request.coordinates[i]) * 1000,
	);
	return {
		minutes: feature.properties.summary.duration / 60,
		distanceKm: feature.properties.summary.distance / 1000,
		snapMeters,
		snapOver100m: snapMeters.some((m) => m > 100),
		engine: response.metadata?.engine ?? null,
	};
}

type Case = {
	id: string;
	valhallaMinutes: number;
	valhallaKm: number;
	v8Minutes: number;
	status: number | null;
	outcome:
		| "skipped"
		| "capture-error"
		| "http-error"
		| "invalid-reference"
		| "paired";
	ors: ReturnType<typeof reference> | null;
	differenceMinutes: number | null;
	absoluteDifferenceMinutes: number | null;
	differencePercent: number | null;
	distanceDifferenceKm: number | null;
};
function summary(rows: Case[]) {
	const paired = rows.filter((r) => r.ors !== null);
	const signed = paired
		.map((r) => r.differenceMinutes ?? 0)
		.sort((a, b) => a - b);
	const absolute = paired
		.map((r) => r.absoluteDifferenceMinutes ?? 0)
		.sort((a, b) => a - b);
	const n = paired.length;
	const median = (values: number[]) =>
		n
			? (values[Math.floor((n - 1) / 2)] + values[Math.floor(n / 2)]) / 2
			: null;
	const medianSignedMinutes = median(signed);
	return {
		planned: rows.length,
		pairedFinite: n,
		unpaired: rows.length - n,
		snapOver100m: paired.filter((r) => r.ors?.snapOver100m).length,
		meanSignedMinutes: n ? signed.reduce((a, b) => a + b, 0) / n : null,
		medianSignedMinutes,
		meanAbsoluteMinutes: n ? absolute.reduce((a, b) => a + b, 0) / n : null,
		medianAbsoluteMinutes: median(absolute),
		interpretationLimited: n !== 29 || paired.some((r) => r.ors?.snapOver100m),
	};
}

/** Offline only; require a complete, unchanged capture, including skipped cases. */
export async function replayBenchmarkRun(directory: string) {
	const plan = await readCapturePlan();
	const checksums = z
		.record(z.string(), z.string().regex(/^[a-f0-9]{64}$/))
		.parse(JSON.parse(await readFile(join(directory, "sha256.json"), "utf8")));
	assert.deepEqual(
		(await readdir(directory)).sort(),
		[...Object.keys(checksums), "sha256.json"].sort(),
	);
	for (const [name, expected] of Object.entries(checksums)) {
		assert.match(name, /^[a-zA-Z0-9.-]+$/);
		assert.equal(
			hash(await readFile(join(directory, name))),
			expected,
			`Changed capture:${name}`,
		);
	}
	assert.equal(checksums["plan.json"], planSha256);
	assert.ok(checksums["capture.json"] && checksums["ledger.json"]);
	const header = z
		.object({
			planSha256: z.literal(planSha256),
			endpoint: z.literal(endpoint),
			maximumRequests: z.literal(29),
			minimumIntervalMs: z.literal(6500),
			timeoutMs: z.literal(45000),
			retries: z.literal(0),
			paidSpendCapEuro: z.literal(0),
			maximumBodyBytes: z.literal(maximumBodyBytes),
			captureTransport: z.enum(["live", "synthetic"]),
		})
		.parse(JSON.parse(await readFile(join(directory, "capture.json"), "utf8")));
	const ledger = z
		.object({
			planned: z.literal(29),
			attempted: z.number().int().min(1).max(29),
			stopReason: z.string().nullable(),
			cases: z
				.array(
					z.object({
						id: z.string(),
						outcome: z.enum(["attempted", "skipped"]),
					}),
				)
				.length(29),
		})
		.parse(JSON.parse(await readFile(join(directory, "ledger.json"), "utf8")));
	assert.equal(
		ledger.cases.filter((r) => r.outcome === "attempted").length,
		ledger.attempted,
	);
	if (ledger.stopReason === null) assert.equal(ledger.attempted, 29);
	const cases: Case[] = [];
	const expectedFiles = new Set(["plan.json", "capture.json", "ledger.json"]);
	let previousStart: number | undefined;
	let expectedStop: string | null = null;
	for (const [i, query] of plan.queries.entries()) {
		const entry = ledger.cases[i];
		assert.equal(entry.id, query.id);
		assert.equal(entry.outcome, i < ledger.attempted ? "attempted" : "skipped");
		const row: Case = {
			id: query.id,
			valhallaMinutes: query.existingValhallaMinutes,
			valhallaKm: query.existingValhallaKm,
			v8Minutes: query.v8Minutes,
			status: null,
			outcome: "skipped",
			ors: null,
			differenceMinutes: null,
			absoluteDifferenceMinutes: null,
			differencePercent: null,
			distanceDifferenceKm: null,
		};
		if (entry.outcome === "attempted") {
			assert.equal(expectedStop, null, "A request followed a stop condition");
			const resultName = `${prefix(i)}-result.json`;
			expectedFiles.add(resultName);
			expectedFiles.add(`${prefix(i)}-request.json`);
			assert.ok(checksums[resultName]);
			const result = resultSchema.parse(
				JSON.parse(await readFile(join(directory, resultName), "utf8")),
			);
			assert.equal(result.id, query.id);
			assert.equal(result.attempt, i + 1);
			assert.equal(result.requestSha256, hash(JSON.stringify(query.request)));
			assert.equal(
				checksums[`${prefix(i)}-request.json`],
				result.requestSha256,
			);
			const started = Date.parse(result.startedAt);
			assert.ok(previousStart === undefined || started - previousStart >= 6500);
			assert.ok(Date.parse(result.finishedAt) >= started);
			previousStart = started;
			if (result.status !== null && [401, 403, 429].includes(result.status))
				expectedStop = `http-${result.status}`;
			if (result.headers["x-ratelimit-remaining"] === "0")
				expectedStop ??= "quota-exhausted";
			if (result.error === "body-limit") expectedStop ??= "body-limit";
			let body: string | null = null;
			if (result.bodySha256 !== null) {
				const name = `${prefix(i)}-response.txt`;
				expectedFiles.add(name);
				assert.equal(checksums[name], result.bodySha256);
				const bytes = await readFile(join(directory, name));
				assert.equal(bytes.length, result.bodyBytes);
				body = bytes.toString();
			}
			row.status = result.status;
			row.outcome = "capture-error";
			if (!result.error) {
				assert.ok(body !== null && result.status !== null);
				row.outcome =
					result.status === 200 ? "invalid-reference" : "http-error";
				if (result.status === 200) {
					try {
						row.ors = reference(body, query);
					} catch {
						/* Preserve invalid JSON/routes in the denominator. */
					}
					if (row.ors) {
						row.outcome = "paired";
						row.differenceMinutes = row.ors.minutes - row.valhallaMinutes;
						row.absoluteDifferenceMinutes = Math.abs(row.differenceMinutes);
						row.differencePercent =
							(row.differenceMinutes / row.valhallaMinutes) * 100;
						row.distanceDifferenceKm = row.ors.distanceKm - row.valhallaKm;
					}
				}
			}
		}
		cases.push(row);
	}
	assert.equal(ledger.stopReason, expectedStop);
	assert.deepEqual(
		Object.keys(checksums).sort(),
		[...expectedFiles].sort(),
		"Unexpected capture entries",
	);
	return {
		planSha256,
		transport: header.captureTransport,
		attempted: ledger.attempted,
		stopReason: ledger.stopReason,
		referenceSourceHashes: plan.plan.inputs,
		overall: summary(cases),
		snapAtMost100mSensitivity: summary(
			cases.filter((r) => r.ors && !r.ors.snapOver100m),
		),
		cases,
		scope:
			"29 fixed remaining public OD pairs; signed differences here are ORS minus saved Valhalla. All failures/skips retained. Use the benchmark join for all83 model comparisons and metadata cohorts. Synthetic transport is a fixture, never provider observation. HTTP-plus-body elapsed excludes persistence and is not routing-engine search time.",
	};
}

function redact(text: string, apiKey: string) {
	for (const value of new Set([
		apiKey,
		encodeURIComponent(apiKey),
		JSON.stringify(apiKey).slice(1, -1),
	]))
		text = text.split(value).join("[REDACTED]");
	return text;
}

async function abortable<T>(promise: Promise<T>, signal: AbortSignal) {
	return new Promise<T>((resolve, reject) => {
		const abort = () => {
			signal.removeEventListener("abort", abort);
			reject(new Error("Request deadline exceeded"));
		};
		signal.addEventListener("abort", abort, { once: true });
		promise.then(resolve, reject).finally(() => {
			signal.removeEventListener("abort", abort);
		});
		if (signal.aborted) abort();
	});
}

async function responseBody(response: Response, signal: AbortSignal) {
	const reader = response.body?.getReader();
	if (!reader) return { body: "", error: null };
	const chunks: Buffer[] = [];
	let bytes = 0;
	let error: CaptureResult["error"] = null;
	try {
		while (true) {
			const { done, value } = await abortable(reader.read(), signal);
			if (done) break;
			const remaining = maximumBodyBytes - bytes;
			chunks.push(Buffer.from(value.subarray(0, remaining)));
			bytes += Math.min(value.length, remaining);
			if (value.length > remaining) {
				error = "body-limit";
				break;
			}
		}
	} catch {
		error = "network-or-timeout";
	} finally {
		// Cancel without waiting for a broken/stalled upstream stream.
		void reader.cancel().catch(() => {});
	}
	return { body: Buffer.concat(chunks).toString(), error };
}

/** One fresh, non-resumable run. Tests inject transport/time; CLI uses defaults. */
export async function captureBenchmarkRun(
	directory: string,
	apiKey: string,
	io: CaptureRuntime = runtime,
) {
	assert.ok(/^[\x21-\x7e]{8,512}$/.test(apiKey), "Missing/invalid ORS_API_KEY");
	const plan = await readCapturePlan();
	await mkdir(directory, { mode: 0o700 }); // Never reuse successful/failed runs.
	async function save(name: string, value: string) {
		await writeFile(join(directory, name), value, { flag: "wx", mode: 0o600 });
	}
	await save("plan.json", plan.raw);
	await save(
		"capture.json",
		json({
			startedAt: new Date(io.now()).toISOString(),
			planSha256,
			endpoint,
			maximumRequests: 29,
			captureTransport: io === runtime ? "live" : "synthetic",
			minimumIntervalMs: 6500,
			timeoutMs: 45000,
			maximumBodyBytes,
			retries: 0,
			paidSpendCapEuro: 0,
			attribution: "© openrouteservice by HeiGIT | Data from OpenStreetMap",
			license: "CC-BY-SA-4.0; separate from the shipped NE/Census model",
		}),
	);
	let previousStart: number | undefined;
	let stopReason: string | null = null;
	const ledger: Array<{ id: string; outcome: "attempted" | "skipped" }> = [];
	for (const [index, query] of plan.queries.entries()) {
		if (stopReason) {
			ledger.push({ id: query.id, outcome: "skipped" });
			continue;
		}
		// Persist intent before spending quota; interrupted runs are never resumed.
		const body = JSON.stringify(query.request);
		await save(`${prefix(index)}-request.json`, body);
		while (previousStart !== undefined && io.now() - previousStart < 6500)
			await io.wait(6500 - (io.now() - previousStart));
		const started = io.now();
		previousStart = started;
		const result: CaptureResult = {
			id: query.id,
			attempt: index + 1,
			requestSha256: hash(body),
			startedAt: new Date(started).toISOString(),
			finishedAt: "",
			httpAndBodyMs: 0,
			status: null,
			headers: {},
			bodySha256: null,
			bodyBytes: 0,
			bodyRedacted: false,
			error: null,
		};
		let safeBody: string | undefined;
		try {
			const signal = io.timeout(45000);
			const response = await abortable(
				io.transport(endpoint, {
					method: "POST",
					headers: {
						"Content-Type": "application/json",
						Authorization: apiKey,
					},
					body,
					redirect: "error",
					credentials: "omit",
					signal,
				}),
				signal,
			);
			result.status = response.status;
			for (const name of [
				"content-type",
				"retry-after",
				"x-ratelimit-limit",
				"x-ratelimit-remaining",
				"x-ratelimit-reset",
			]) {
				const value = response.headers.get(name);
				if (value) result.headers[name] = redact(value, apiKey).slice(0, 512);
			}
			if ([401, 403, 429].includes(response.status))
				stopReason = `http-${response.status}`;
			if (response.headers.get("x-ratelimit-remaining") === "0")
				stopReason ??= "quota-exhausted";
			const received = await responseBody(response, signal);
			safeBody = redact(received.body, apiKey);
			result.bodyRedacted = safeBody !== received.body;
			result.bodyBytes = Buffer.byteLength(safeBody);
			result.bodySha256 = hash(safeBody);
			result.error = received.error;
			if (received.error === "body-limit") {
				stopReason ??= "body-limit";
			}
		} catch {
			// Errors can contain credentials or URLs; retain a fixed diagnostic only.
			result.error = "network-or-timeout";
		}
		result.finishedAt = new Date(io.now()).toISOString();
		result.httpAndBodyMs = Math.max(0, io.now() - started);
		// Disk failures must stop capture, rather than silently spend more quota.
		if (safeBody !== undefined)
			await save(`${prefix(index)}-response.txt`, safeBody);
		await save(`${prefix(index)}-result.json`, json(result));
		ledger.push({ id: query.id, outcome: "attempted" });
	}
	await save(
		"ledger.json",
		json({
			finishedAt: new Date(io.now()).toISOString(),
			stopReason,
			attempted: ledger.filter((row) => row.outcome === "attempted").length,
			planned: 29,
			cases: ledger,
		}),
	);
	const checksums: Record<string, string> = {};
	for (const name of (await readdir(directory)).sort())
		checksums[name] = hash(await readFile(join(directory, name)));
	await save("sha256.json", json(checksums));
	return {
		attempted: ledger.filter((r) => r.outcome === "attempted").length,
		stopReason,
	};
}
