// Offline validation tooling only; never imported by the application.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { z } from "zod";
import { distanceKm } from "../src/server/coarse-grid";

export const planPath =
	"docs/evidence/coarse-holdout-plan-2026-10-23/plan.json";
export const planSha256 =
	"77360fec0906c5a3eeedc533eef55cbe8557659266c25badcc4b924412e4271e";
const maximumBodyBytes = 2_000_000;
const endpoint =
	"https://api.heigit.org/openrouteservice/v2/directions/driving-car/geojson";
const pointSchema = z.tuple([
	z.number().min(-180).max(180),
	z.number().min(-90).max(90),
]);
const querySchema = z.object({
	id: z.string().regex(/^[a-z0-9-]+$/),
	originId: z.string(),
	budgetMinutes: z.number(),
	expectedMapReachable: z.boolean(),
	modelPointMinutes: z.number().finite(),
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
const planSchema = z.object({ queries: z.array(querySchema).length(48) });
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
						duration: z.number().positive().finite(),
						distance: z.number().positive().finite(),
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
const hash = (bytes: string | Buffer) =>
	createHash("sha256").update(bytes).digest("hex");
const json = (value: unknown) => `${JSON.stringify(value, null, 2)}\n`;
const prefix = (index: number) => String(index).padStart(2, "0");
const resultSchema = z.object({
	id: z.string(),
	attempt: z.number().int().min(1).max(48),
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

export async function readFrozenPlan() {
	const raw = await readFile(planPath, "utf8");
	assert.equal(hash(raw), planSha256, "Frozen queries changed; refuse capture");
	const plan = planSchema.parse(JSON.parse(raw));
	return { raw, queries: plan.queries };
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
export async function captureReferenceRun(
	directory: string,
	apiKey: string,
	io: CaptureRuntime = runtime,
) {
	assert.ok(/^[\x21-\x7e]{8,512}$/.test(apiKey), "Missing/invalid ORS_API_KEY");
	const plan = await readFrozenPlan();
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
			maximumRequests: 48,
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
			planned: 48,
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

function referenceRoute(raw: string, query: Query) {
	const reference = referenceSchema.parse(JSON.parse(raw));
	const feature = reference.features[0];
	const points = feature.geometry.coordinates;
	const snaps = [points[0], points[points.length - 1]].map(
		(point, i) => distanceKm(point, query.request.coordinates[i]) * 1000,
	);
	return {
		minutes: feature.properties.summary.duration / 60,
		distanceKm: feature.properties.summary.distance / 1000,
		snapMeters: snaps,
		snapOver100m: snaps.some((meters) => meters > 100),
		engine: reference.metadata?.engine ?? null,
	};
}

type Case = {
	id: string;
	originId: string;
	budgetMinutes: number;
	predictedReachable: boolean;
	modelPointMinutes: number;
	status: number | null;
	outcome:
		| "paired"
		| "skipped"
		| "http-error"
		| "invalid-reference"
		| "capture-error";
	reference: ReturnType<typeof referenceRoute> | null;
	signedDifferenceMinutes: number | null;
	absoluteDifferenceMinutes: number | null;
	classification:
		| "correct"
		| "falseReachable"
		| "missedReachable"
		| "ambiguous"
		| null;
};
function summarize(cases: Case[]) {
	const paired = cases.filter((row) => row.reference !== null);
	const signed = paired.map(
		(r) => r.modelPointMinutes - (r.reference?.minutes ?? 0),
	);
	const absolute = signed.map(Math.abs).sort((a, b) => a - b);
	const n = absolute.length;
	const counts = {
		correct: 0,
		falseReachable: 0,
		missedReachable: 0,
		ambiguous: 0,
	};
	for (const row of paired)
		if (row.classification) counts[row.classification]++;
	return {
		planned: cases.length,
		pairedFinite: n,
		unpaired: cases.length - n,
		snapOver100m: paired.filter((r) => r.reference?.snapOver100m).length,
		meanSignedMinutes: n ? signed.reduce((a, b) => a + b, 0) / n : null,
		meanAbsoluteMinutes: n ? absolute.reduce((a, b) => a + b, 0) / n : null,
		medianAbsoluteMinutes: n
			? (absolute[Math.floor((n - 1) / 2)] + absolute[Math.floor(n / 2)]) / 2
			: null,
		p90AbsoluteMinutes: n ? absolute[Math.ceil(n * 0.9) - 1] : null,
		classification: counts,
	};
}

/** No network, environment/key read or writes. Reject altered/incomplete captures. */
export async function replayReferenceRun(directory: string) {
	const plan = await readFrozenPlan();
	const checksums = z
		.record(z.string(), z.string().regex(/^[a-f0-9]{64}$/))
		.parse(JSON.parse(await readFile(join(directory, "sha256.json"), "utf8")));
	assert.deepEqual(
		(await readdir(directory)).sort(),
		[...Object.keys(checksums), "sha256.json"].sort(),
		"Unsealed capture files",
	);
	for (const [name, expected] of Object.entries(checksums)) {
		assert.match(name, /^[a-zA-Z0-9.-]+$/);
		assert.equal(
			hash(await readFile(join(directory, name))),
			expected,
			`Changed capture: ${name}`,
		);
	}
	assert.equal(checksums["plan.json"], planSha256);
	const header = JSON.parse(
		await readFile(join(directory, "capture.json"), "utf8"),
	);
	assert.equal(header.planSha256, planSha256);
	assert.equal(header.endpoint, endpoint);
	assert.equal(header.maximumRequests, 48);
	assert.equal(header.minimumIntervalMs, 6500);
	assert.equal(header.timeoutMs, 45000);
	assert.equal(header.retries, 0);
	assert.equal(header.paidSpendCapEuro, 0);
	const ledger = z
		.object({
			planned: z.literal(48),
			attempted: z.number().int().min(0).max(48),
			stopReason: z.string().nullable(),
			cases: z
				.array(
					z.object({
						id: z.string(),
						outcome: z.enum(["attempted", "skipped"]),
					}),
				)
				.length(48),
		})
		.parse(JSON.parse(await readFile(join(directory, "ledger.json"), "utf8")));
	assert.ok(checksums["ledger.json"] && checksums["capture.json"]);
	assert.equal(
		ledger.attempted,
		ledger.cases.filter((r) => r.outcome === "attempted").length,
	);
	assert.ok(ledger.attempted > 0);
	if (ledger.stopReason === null) assert.equal(ledger.attempted, 48);
	const cases: Case[] = [];
	let previousStart: number | undefined;
	for (const [index, query] of plan.queries.entries()) {
		const entry = ledger.cases[index];
		assert.equal(entry.id, query.id);
		assert.equal(
			entry.outcome,
			index < ledger.attempted ? "attempted" : "skipped",
		);
		const row: Case = {
			id: query.id,
			originId: query.originId,
			budgetMinutes: query.budgetMinutes,
			predictedReachable: query.expectedMapReachable,
			modelPointMinutes: query.modelPointMinutes,
			status: null,
			outcome: "skipped",
			reference: null,
			signedDifferenceMinutes: null,
			absoluteDifferenceMinutes: null,
			classification: null,
		};
		if (entry.outcome === "attempted") {
			const name = `${prefix(index)}-result.json`;
			assert.ok(checksums[name]);
			assert.equal(
				checksums[`${prefix(index)}-request.json`],
				hash(JSON.stringify(query.request)),
			);
			const result = resultSchema.parse(
				JSON.parse(await readFile(join(directory, name), "utf8")),
			);
			assert.equal(result.id, query.id);
			assert.equal(result.attempt, index + 1);
			assert.equal(result.requestSha256, hash(JSON.stringify(query.request)));
			const started = Date.parse(result.startedAt);
			assert.ok(previousStart === undefined || started - previousStart >= 6500);
			assert.ok(Date.parse(result.finishedAt) >= started);
			previousStart = started;
			row.status = result.status;
			row.outcome = "capture-error";
			if (result.bodySha256 !== null) {
				assert.equal(
					checksums[`${prefix(index)}-response.txt`],
					result.bodySha256,
				);
				assert.equal(
					(await readFile(join(directory, `${prefix(index)}-response.txt`)))
						.length,
					result.bodyBytes,
				);
			}
			if (!result.error) {
				assert.ok(result.bodySha256 !== null && result.status !== null);
				row.outcome =
					result.status === 200 ? "invalid-reference" : "http-error";
				if (result.status === 200) {
					try {
						row.reference = referenceRoute(
							await readFile(
								join(directory, `${prefix(index)}-response.txt`),
								"utf8",
							),
							query,
						);
						row.outcome = "paired";
						row.signedDifferenceMinutes =
							row.modelPointMinutes - row.reference.minutes;
						row.absoluteDifferenceMinutes = Math.abs(
							row.signedDifferenceMinutes,
						);
						const minutes = row.reference.minutes;
						row.classification =
							Math.abs(minutes - row.budgetMinutes) <= 5
								? "ambiguous"
								: row.predictedReachable === minutes < row.budgetMinutes
									? "correct"
									: row.predictedReachable
										? "falseReachable"
										: "missedReachable";
					} catch {
						/* Malformed/unroutable references stay in the denominator. */
					}
				}
			}
		}
		cases.push(row);
	}
	return {
		planSha256,
		attempted: ledger.attempted,
		stopReason: ledger.stopReason,
		scope:
			"Frozen v8 model-conditioned frontier point probes, not random national or area accuracy; signed error = model minus reference; p90 uses nearest rank. Snap >100m remains in primary results. HTTP/body time is not provider search time.",
		overall: summarize(cases),
		byHorizon: Object.fromEntries(
			[360, 600, 720].map((h) => [
				h,
				summarize(cases.filter((r) => r.budgetMinutes === h)),
			]),
		),
		byOrigin: Object.fromEntries(
			[...new Set(cases.map((r) => r.originId))].map((id) => [
				id,
				summarize(cases.filter((r) => r.originId === id)),
			]),
		),
		snapAtMost100mSensitivity: summarize(
			cases.filter((r) => r.reference && !r.reference.snapOver100m),
		),
		cases,
	};
}
