import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { type TestContext, test } from "node:test";
import {
	captureReferenceRun,
	readFrozenPlan,
	replayReferenceRun,
} from "./coarse-holdout";

const key = "synthetic-secret+not-a-real-key";
const plan = await readFrozenPlan();
type Query = (typeof plan.queries)[number];
type Runtime = NonNullable<Parameters<typeof captureReferenceRun>[2]>;
function route(query: Query, minutes: number, offset = 0) {
	const coordinates = query.request.coordinates.map(([lon, lat], i) => [
		lon + (i === 0 ? offset : 0),
		lat,
	]);
	return {
		type: "FeatureCollection",
		features: [
			{
				geometry: { type: "LineString", coordinates },
				properties: { summary: { duration: minutes * 60, distance: 100_000 } },
			},
		],
		metadata: {
			engine: { version: "synthetic-fixture", graph_date: "2026-10-01" },
		},
	};
}
function fakeRuntime(handler: (index: number) => Response | Promise<Response>) {
	let now = Date.UTC(2026, 9, 23);
	const starts: number[] = [];
	const deadlines: number[] = [];
	const io: Runtime = {
		now: () => now,
		wait: async (ms) => {
			now += ms;
		},
		timeout: (ms) => {
			deadlines.push(ms);
			return new AbortController().signal;
		},
		transport: async (url, init) => {
			const index = starts.length;
			starts.push(now);
			assert.equal(
				url,
				"https://api.heigit.org/openrouteservice/v2/directions/driving-car/geojson",
			);
			assert.equal(init?.method, "POST");
			assert.equal(init?.redirect, "error");
			assert.equal(init?.credentials, "omit");
			assert.equal(new Headers(init.headers).get("Authorization"), key);
			assert.equal(init.body, JSON.stringify(plan.queries[index].request));
			return handler(index);
		},
	};
	return { io, starts, deadlines };
}
async function scratch(t: TestContext) {
	const parent = await mkdtemp(join(tmpdir(), "geo-frontier-fixture-"));
	t.after(() => rm(parent, { recursive: true, force: true }));
	return join(parent, "capture");
}

test("48-request cap, exact bodies, interval/deadline, redaction and deterministic offline scoring", async (t) => {
	const directory = await scratch(t);
	const { io, starts, deadlines } = fakeRuntime((index) => {
		const query = plan.queries[index];
		const minutes =
			query.budgetMinutes + (index % 4 === 3 ? 5 : index % 4 === 2 ? 30 : -30);
		return new Response(
			JSON.stringify({
				...route(query, minutes, index === 0 ? 0.01 : 0),
				echo: `${key} / ${encodeURIComponent(key)}`,
			}),
			{
				headers: {
					"x-ratelimit-remaining": "99",
					"set-cookie": "private=do-not-save",
				},
			},
		);
	});
	assert.deepEqual(await captureReferenceRun(directory, key, io), {
		attempted: 48,
		stopReason: null,
	});
	assert.equal(starts.length, 48);
	assert.ok(starts.slice(1).every((start, i) => start - starts[i] >= 6500));
	assert.deepEqual(deadlines, Array(48).fill(45000));
	for (const name of await readdir(directory)) {
		const raw = await readFile(join(directory, name), "utf8");
		assert.ok(!raw.includes(key) && !raw.includes(encodeURIComponent(key)));
		assert.ok(!raw.includes("do-not-save"));
	}
	const report = await replayReferenceRun(directory);
	assert.deepEqual(report, await replayReferenceRun(directory));
	assert.equal(report.overall.planned, 48);
	assert.equal(report.overall.pairedFinite, 48);
	assert.equal(report.overall.snapOver100m, 1);
	assert.equal(report.snapAtMost100mSensitivity.pairedFinite, 47);
	assert.deepEqual(report.overall.classification, {
		correct: 12,
		falseReachable: 12,
		missedReachable: 12,
		ambiguous: 12,
	});
	const errors = plan.queries
		.map((q, i) =>
			Math.abs(
				q.modelPointMinutes -
					(q.budgetMinutes + (i % 4 === 3 ? 5 : i % 4 === 2 ? 30 : -30)),
			),
		)
		.sort((a, b) => a - b);
	assert.equal(
		report.overall.meanAbsoluteMinutes,
		errors.reduce((a, b) => a + b, 0) / 48,
	);
	assert.equal(
		report.overall.medianAbsoluteMinutes,
		(errors[23] + errors[24]) / 2,
	);
	assert.equal(report.overall.p90AbsoluteMinutes, errors[43]);
	assert.equal(report.byHorizon[360].planned, 16);
	assert.equal(Object.keys(report.byOrigin).length, 8);
	await assert.rejects(captureReferenceRun(directory, key, io));
	assert.equal(
		starts.length,
		48,
		"Existing directory must never spend quota again",
	);
});

for (const status of [401, 403, 429]) {
	test(`HTTP ${status} stops without retries and retains all skipped cases`, async (t) => {
		const directory = await scratch(t);
		const { io, starts } = fakeRuntime((index) =>
			index === 0
				? new Response(JSON.stringify(route(plan.queries[index], 350)))
				: new Response(JSON.stringify({ error: `synthetic ${key}` }), {
						status,
					}),
		);
		assert.deepEqual(await captureReferenceRun(directory, key, io), {
			attempted: 2,
			stopReason: `http-${status}`,
		});
		assert.equal(starts.length, 2);
		const report = await replayReferenceRun(directory);
		assert.equal(report.cases.length, 48);
		assert.equal(
			report.cases.filter((r) => r.outcome === "skipped").length,
			46,
		);
		assert.equal(report.cases[1].status, status);
		assert.equal(report.overall.pairedFinite, 1);
		assert.equal(report.overall.unpaired, 47);
	});
}

test("a returned zero quota stops, preserving the final successful response", async (t) => {
	const directory = await scratch(t);
	const { io, starts } = fakeRuntime(
		(i) =>
			new Response(JSON.stringify(route(plan.queries[i], 350)), {
				headers: { "x-ratelimit-remaining": "0" },
			}),
	);
	assert.deepEqual(await captureReferenceRun(directory, key, io), {
		attempted: 1,
		stopReason: "quota-exhausted",
	});
	assert.equal(starts.length, 1);
	assert.equal((await replayReferenceRun(directory)).overall.pairedFinite, 1);
});

test("network errors, HTTP failures and invalid references retain the full denominator, without retries", async (t) => {
	const directory = await scratch(t);
	const { io, starts } = fakeRuntime((i) => {
		if (i % 3 === 0)
			throw new Error(`Synthetic transport exception includes ${key}`);
		return i % 3 === 1
			? new Response("invalid json")
			: new Response("no route", { status: 404 });
	});
	await captureReferenceRun(directory, key, io);
	assert.equal(starts.length, 48);
	const report = await replayReferenceRun(directory);
	assert.equal(report.overall.pairedFinite, 0);
	assert.equal(report.overall.meanAbsoluteMinutes, null);
	assert.equal(report.overall.unpaired, 48);
	for (const outcome of ["capture-error", "invalid-reference", "http-error"])
		assert.equal(report.cases.filter((r) => r.outcome === outcome).length, 16);
	assert.ok(
		!(await readFile(join(directory, "00-result.json"), "utf8")).includes(key),
	);
});

test("the deadline covers both fetch and a stalled response body; partial body is preserved", async (t) => {
	for (const phase of ["fetch", "body", "pre-aborted"]) {
		const directory = `${await scratch(t)}-${phase}`;
		const { io, starts } = fakeRuntime((i) => {
			if (i > 0) return new Response("stop", { status: 401 });
			if (phase === "pre-aborted") return Promise.reject(new Error(key));
			if (phase === "fetch") return new Promise<Response>(() => {});
			return new Response(
				new ReadableStream({
					start(controller) {
						controller.enqueue(
							new TextEncoder().encode("partial public fixture"),
						);
					},
				}),
			);
		});
		io.timeout = () => {
			const controller = new AbortController();
			if (starts.length === 0) {
				if (phase === "pre-aborted") controller.abort();
				else setImmediate(() => controller.abort());
			}
			return controller.signal;
		};
		await captureReferenceRun(directory, key, io);
		assert.equal(starts.length, 2);
		const report = await replayReferenceRun(directory);
		assert.equal(report.cases[0].outcome, "capture-error");
		if (phase === "body")
			assert.equal(
				await readFile(join(directory, "00-response.txt"), "utf8"),
				"partial public fixture",
			);
	}
});

test("oversized responses are bounded and stop the run", async (t) => {
	const directory = await scratch(t);
	const { io, starts } = fakeRuntime(() => new Response("x".repeat(2_000_001)));
	assert.deepEqual(await captureReferenceRun(directory, key, io), {
		attempted: 1,
		stopReason: "body-limit",
	});
	assert.equal(starts.length, 1);
	assert.equal(
		(await readFile(join(directory, "00-response.txt"))).length,
		2_000_000,
	);
	assert.equal(
		(await replayReferenceRun(directory)).cases[0].outcome,
		"capture-error",
	);
});

test("a disk-write failure stops before any further provider request", async (t) => {
	const directory = await scratch(t);
	const { io, starts } = fakeRuntime(async () => {
		await rm(directory, { recursive: true });
		return new Response("public fixture");
	});
	await assert.rejects(captureReferenceRun(directory, key, io));
	assert.equal(starts.length, 1);
});

test("offline replay rejects changed and incomplete evidence", async (t) => {
	const directory = await scratch(t);
	const { io } = fakeRuntime(() => new Response("stop", { status: 401 }));
	await captureReferenceRun(directory, key, io);
	await writeFile(join(directory, "00-response.txt"), "changed");
	await assert.rejects(replayReferenceRun(directory), /Changed capture/);
	await rm(join(directory, "sha256.json"));
	await assert.rejects(replayReferenceRun(directory));
});

test("CLI inspection is offline and capture requires the explicit request-budget flag", () => {
	const run = (args: string[]) =>
		spawnSync(
			process.execPath,
			["--import", "tsx", "scripts/compare-coarse-holdout.ts", ...args],
			{ encoding: "utf8", env: { ...process.env, ORS_API_KEY: key } },
		);
	const check = run(["--check"]);
	assert.equal(check.status, 0);
	assert.equal(JSON.parse(check.stdout).keyRead, false);
	assert.equal(JSON.parse(check.stdout).providerRequests, 0);
	const rejected = run([
		"--capture",
		"data/coarse-quality/not-authorized-fixture",
	]);
	assert.equal(rejected.status, 1);
	assert.ok(!rejected.stderr.includes(key));
});
