import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtemp, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { type TestContext, test } from "node:test";
import { joinBenchmarkReport } from "./coarse-benchmark";
import {
	captureBenchmarkRun,
	readCapturePlan,
	replayBenchmarkRun,
} from "./coarse-benchmark-capture";
import { buildBenchmarkPlan } from "./coarse-benchmark-plan";

const plan = await readCapturePlan();
const savedEngine = plan.control.cases[0].ors?.engine;
assert.ok(savedEngine);
const key = "synthetic-benchmark-secret+never-real";
type Runtime = NonNullable<Parameters<typeof captureBenchmarkRun>[2]>;
function route(index: number, gap: number, snapOffset = 0) {
	const query = plan.queries[index];
	return {
		type: "FeatureCollection",
		features: [
			{
				geometry: {
					type: "LineString",
					coordinates: query.request.coordinates.map(([lon, lat], i) => [
						lon + (i === 0 ? snapOffset : 0),
						lat,
					]),
				},
				properties: {
					summary: {
						duration: (query.existingValhallaMinutes + gap) * 60,
						distance: (query.existingValhallaKm + 1) * 1000,
					},
				},
			},
		],
		metadata: { engine: savedEngine },
	};
}
function runtime(handler: (index: number) => Response | Promise<Response>) {
	let now = Date.UTC(2026, 9, 24);
	const starts: number[] = [],
		deadlines: number[] = [];
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
			assert.ok(index < 29, "No thirtieth request");
			assert.equal(
				url,
				"https://api.heigit.org/openrouteservice/v2/directions/driving-car/geojson",
			);
			assert.equal(init?.method, "POST");
			assert.equal(init.redirect, "error");
			assert.equal(init.credentials, "omit");
			assert.equal(new Headers(init.headers).get("Authorization"), key);
			assert.equal(init.body, JSON.stringify(plan.queries[index].request));
			return handler(index);
		},
	};
	return { io, starts, deadlines };
}
async function scratch(t: TestContext) {
	const parent = await mkdtemp(join(tmpdir(), "geo-benchmark-fixture-"));
	t.after(() => rm(parent, { recursive: true, force: true }));
	return join(parent, "capture");
}

test("29 exact requests, hard cap, spacing/deadline and redaction; deterministic signed/percentage offline comparison", async (t) => {
	const directory = await scratch(t);
	const gaps = Array.from({ length: 29 }, (_, i) => (i % 2 ? -2 : 5));
	const { io, starts, deadlines } = runtime(
		(i) =>
			new Response(
				JSON.stringify({
					...route(i, gaps[i]),
					echo: `${key}/${encodeURIComponent(key)}`,
				}),
				{
					headers: {
						"x-ratelimit-remaining": "100",
						"set-cookie": "private=omit",
					},
				},
			),
	);
	assert.deepEqual(await captureBenchmarkRun(directory, key, io), {
		attempted: 29,
		stopReason: null,
	});
	assert.equal(starts.length, 29);
	assert.ok(starts.slice(1).every((x, i) => x - starts[i] >= 6500));
	assert.deepEqual(deadlines, Array(29).fill(45000));
	for (const name of await readdir(directory)) {
		const text = await readFile(join(directory, name), "utf8");
		assert.ok(
			!text.includes(key) &&
				!text.includes(encodeURIComponent(key)) &&
				!text.includes("private=omit"),
		);
	}
	const report = await replayBenchmarkRun(directory);
	assert.deepEqual(report, await replayBenchmarkRun(directory));
	assert.equal(report.transport, "synthetic");
	assert.equal(report.overall.planned, 29);
	assert.equal(report.overall.pairedFinite, 29);
	assert.ok(
		Math.abs((report.overall.meanSignedMinutes ?? 0) - 47 / 29) < 1e-10,
	);
	assert.ok(Math.abs((report.overall.medianSignedMinutes ?? 0) - 5) < 1e-10);
	assert.ok(
		Math.abs((report.overall.meanAbsoluteMinutes ?? 0) - 103 / 29) < 1e-10,
	);
	assert.equal(report.overall.interpretationLimited, false);
	assert.ok(
		Math.abs(
			(report.cases[0].differencePercent ?? 0) -
				(5 / plan.queries[0].existingValhallaMinutes) * 100,
		) < 1e-10,
	);
	assert.ok(Math.abs((report.cases[0].distanceDifferenceKm ?? 0) - 1) < 1e-10);
	await assert.rejects(captureBenchmarkRun(directory, key, io));
	assert.equal(starts.length, 29);
	const benchmark = await joinBenchmarkReport(report);
	assert.equal(benchmark.cases.length, 83);
	assert.equal(benchmark.denominators.pairedFinite, 83);
	assert.equal(benchmark.primary?.overall.planned, 83);
	assert.equal(benchmark.primary?.bySet.original.planned, 11);
	assert.equal(benchmark.primary?.bySet.regional.planned, 24);
	assert.equal(benchmark.primary?.bySet.frontier.planned, 48);
	assert.equal(benchmark.completedLiveBenchmark, false);
	assert.deepEqual(benchmark.savedFrontierV8Summary, plan.frontier.overall);
	assert.ok(benchmark.primary);
	assert.ok(
		Math.abs(
			(benchmark.savedValhallaSensitivity.bySet.original.v8
				.meanAbsoluteMinutes ?? 0) - 10.288166584892211,
		) < 1e-9,
	);
	assert.ok(
		Math.abs(
			(benchmark.savedValhallaSensitivity.bySet.regional.v8
				.meanAbsoluteMinutes ?? 0) - 12.011438254291809,
		) < 1e-9,
	);
	const frontier = benchmark.primary.bySet.frontier.models.v8;
	for (const metric of [
		"meanSignedMinutes",
		"meanAbsoluteMinutes",
		"medianAbsoluteMinutes",
		"p90AbsoluteMinutes",
	] as const) {
		assert.ok(
			Math.abs((frontier[metric] ?? 0) - (plan.frontier.overall[metric] ?? 0)) <
				1e-9,
		);
	}
	assert.deepEqual(
		frontier.classification,
		plan.frontier.overall.classification,
	);
	for (const saved of plan.control.cases) {
		assert.deepEqual(
			benchmark.cases.find((r) => r.id === saved.id)?.ors,
			saved.ors,
		);
	}
	const firstNew = benchmark.cases.find((r) => r.id === plan.queries[0].id);
	assert.ok(firstNew?.v8);
	const expected =
		plan.queries[0].v8Minutes - (plan.queries[0].existingValhallaMinutes + 5);
	assert.ok(Math.abs(firstNew.v8.signedMinutes - expected) < 1e-10);
	assert.ok(
		Math.abs(
			firstNew.v8.signedPercent -
				(expected / (plan.queries[0].existingValhallaMinutes + 5)) * 100,
		) < 1e-10,
	);
	assert.deepEqual(benchmark, await joinBenchmarkReport(report));
});

for (const status of [401, 403, 429])
	test(`HTTP${status} stops once and retains 28 skipped cases`, async (t) => {
		const directory = await scratch(t);
		const { io, starts } = runtime(
			() => new Response(`synthetic error ${key}`, { status }),
		);
		assert.deepEqual(await captureBenchmarkRun(directory, key, io), {
			attempted: 1,
			stopReason: `http-${status}`,
		});
		assert.equal(starts.length, 1);
		const report = await replayBenchmarkRun(directory);
		assert.equal(report.cases.length, 29);
		assert.equal(
			report.cases.filter((r) => r.outcome === "skipped").length,
			28,
		);
		assert.equal(report.overall.unpaired, 29);
		assert.equal(report.overall.interpretationLimited, true);
	});

test("returned zero quota stops after preserving the final successful response", async (t) => {
	const directory = await scratch(t);
	const { io, starts } = runtime(
		(i) =>
			new Response(JSON.stringify(route(i, 0)), {
				headers: { "x-ratelimit-remaining": "0" },
			}),
	);
	assert.deepEqual(await captureBenchmarkRun(directory, key, io), {
		attempted: 1,
		stopReason: "quota-exhausted",
	});
	assert.equal(starts.length, 1);
	assert.equal((await replayBenchmarkRun(directory)).overall.pairedFinite, 1);
});

test("network exceptions, invalid JSON/routes and HTTP failures retain their original denominators without retries", async (t) => {
	const directory = await scratch(t);
	const { io, starts } = runtime((i) => {
		if (i === 0) throw new Error(key);
		return i < 3
			? new Response(i === 1 ? "not-json" : "{}")
			: new Response("no route", { status: 404 });
	});
	await captureBenchmarkRun(directory, key, io);
	assert.equal(starts.length, 29);
	const r = await replayBenchmarkRun(directory);
	assert.equal(r.overall.pairedFinite, 0);
	assert.equal(r.overall.meanAbsoluteMinutes, null);
	assert.equal(r.overall.unpaired, 29);
	assert.equal(r.cases[0].outcome, "capture-error");
	assert.equal(r.cases[1].outcome, "invalid-reference");
	assert.equal(r.cases[3].outcome, "http-error");
	assert.ok(
		!(await readFile(join(directory, "00-result.json"), "utf8")).includes(key),
	);
});

test("deadlines cover fetch/body and pre-aborted signals; partial bodies survive", async (t) => {
	for (const phase of ["fetch", "body", "pre-aborted"]) {
		const directory = `${await scratch(t)}-${phase}`;
		const { io, starts } = runtime((i) => {
			if (i > 0) return new Response("stop", { status: 401 });
			if (phase === "pre-aborted") return Promise.reject(new Error(key));
			if (phase === "fetch") return new Promise<Response>(() => {});
			return new Response(
				new ReadableStream({
					start(controller) {
						controller.enqueue(new TextEncoder().encode("partial fixture"));
					},
				}),
			);
		});
		io.timeout = () => {
			const c = new AbortController();
			if (starts.length === 0) {
				if (phase === "pre-aborted") c.abort();
				else setImmediate(() => c.abort());
			}
			return c.signal;
		};
		await captureBenchmarkRun(directory, key, io);
		assert.equal(starts.length, 2);
		assert.equal(
			(await replayBenchmarkRun(directory)).cases[0].outcome,
			"capture-error",
		);
		if (phase === "body")
			assert.equal(
				await readFile(join(directory, "00-response.txt"), "utf8"),
				"partial fixture",
			);
	}
});

test("response bound stops acquisition and retains its bounded prefix", async (t) => {
	const directory = await scratch(t);
	const { io, starts } = runtime(() => new Response("x".repeat(2_000_001)));
	assert.deepEqual(await captureBenchmarkRun(directory, key, io), {
		attempted: 1,
		stopReason: "body-limit",
	});
	assert.equal(starts.length, 1);
	assert.equal(
		(await readFile(join(directory, "00-response.txt"))).length,
		2_000_000,
	);
	assert.equal(
		(await replayBenchmarkRun(directory)).cases[0].outcome,
		"capture-error",
	);
});

test("disk failure stops before another request", async (t) => {
	const directory = await scratch(t);
	const { io, starts } = runtime(async () => {
		await rm(directory, { recursive: true });
		return new Response("fixture");
	});
	await assert.rejects(captureBenchmarkRun(directory, key, io));
	assert.equal(starts.length, 1);
});

test("all pairs and >100m snaps remain primary; sensitivity and incomplete-pair limits are explicit", async (t) => {
	const directory = await scratch(t);
	const { io } = runtime(
		(i) => new Response(JSON.stringify(route(i, 10, i === 0 ? 0.01 : 0))),
	);
	await captureBenchmarkRun(directory, key, io);
	const r = await replayBenchmarkRun(directory);
	assert.equal(r.overall.pairedFinite, 29);
	assert.equal(r.overall.snapOver100m, 1);
	assert.equal(r.overall.interpretationLimited, true);
	assert.equal(r.snapAtMost100mSensitivity.pairedFinite, 28);
	const joined = await joinBenchmarkReport(r);
	assert.equal(joined.primary?.overall.planned, 83);
	assert.equal(joined.primary?.overall.snapOver100m, 1);
	assert.equal(joined.snapAtMost100mSensitivity?.overall.planned, 82);
	assert.equal(joined.snapAtMost100mSensitivity?.plannedTotal, 83);
	const partial = `${await scratch(t)}-partial`;
	const fake = runtime((i) =>
		i < 4
			? new Response(JSON.stringify(route(i, 10)))
			: new Response("missing", { status: 404 }),
	);
	await captureBenchmarkRun(partial, key, fake.io);
	const p = await replayBenchmarkRun(partial);
	assert.equal(p.overall.pairedFinite, 4);
	assert.equal(p.overall.interpretationLimited, true);
	assert.equal(p.overall.unpaired, 25);
	const incomplete = await joinBenchmarkReport(p);
	assert.equal(incomplete.primary, null);
	assert.equal(incomplete.denominators.pairedFinite, 58);
	assert.equal(incomplete.denominators.unpaired, 25);
	assert.equal(incomplete.cases.length, 83);
});

test("fixed29 is exactly the complement of saved6; plan/source reconstruction repeats without key/network", async () => {
	const repeated = await buildBenchmarkPlan();
	assert.deepEqual(repeated.plan, plan.plan);
	const older = repeated.records.filter((r) => r.set !== "frontier");
	assert.equal(older.length, 35);
	assert.equal(
		new Set(older.map((r) => JSON.stringify(r.request.coordinates))).size,
		35,
	);
	const union = [...plan.plan.reuse.control, ...plan.queries.map((r) => r.id)];
	assert.equal(new Set(union).size, 35);
	assert.deepEqual(union.sort(), older.map((r) => r.id).sort());
	assert.equal(plan.plan.reuse.frontier.length, 48);
});

test("changed/missing engine metadata suppresses pooled primary; cohorts and all83 cases remain", async (t) => {
	for (const missing of [false, true]) {
		const directory = `${await scratch(t)}-metadata`;
		const { io } = runtime((i) => {
			const value = route(i, 0);
			if (i === 0)
				value.metadata.engine = missing
					? {}
					: { ...savedEngine, graph_date: "different-graph" };
			return new Response(JSON.stringify(value));
		});
		await captureBenchmarkRun(directory, key, io);
		const report = await joinBenchmarkReport(
			await replayBenchmarkRun(directory),
		);
		assert.equal(report.cases.length, 83);
		assert.equal(report.denominators.pairedFinite, 83);
		assert.equal(report.primary, null);
		assert.equal(report.compatibility.matchesSavedEngineBuildGraphOsm, false);
		assert.equal(report.compatibility.cohortCount, 2);
		assert.equal(report.compatibility.missingMetadata, missing ? 1 : 0);
		assert.equal(report.completedLiveBenchmark, false);
	}
});

test("replay rejects changed, incomplete and unsealed captures", async (t) => {
	const directory = await scratch(t);
	const { io } = runtime(() => new Response("stop", { status: 401 }));
	await captureBenchmarkRun(directory, key, io);
	await writeFile(join(directory, "extra.txt"), "unsealed");
	await assert.rejects(replayBenchmarkRun(directory));
	await rm(join(directory, "extra.txt"));
	await writeFile(join(directory, "00-response.txt"), "changed");
	await assert.rejects(replayBenchmarkRun(directory), /Changed capture/);
	await rm(join(directory, "sha256.json"));
	await assert.rejects(replayBenchmarkRun(directory));
});

test("replay rejects a checksum-bound thirtieth request file outside its ledger", async (t) => {
	const directory = await scratch(t);
	const { io } = runtime(() => new Response("stop", { status: 401 }));
	await captureBenchmarkRun(directory, key, io);
	await writeFile(join(directory, "29-request.json"), "{}");
	const manifest = JSON.parse(
		await readFile(join(directory, "sha256.json"), "utf8"),
	);
	manifest["29-request.json"] = createHash("sha256").update("{}").digest("hex");
	await writeFile(join(directory, "sha256.json"), JSON.stringify(manifest));
	await assert.rejects(
		replayBenchmarkRun(directory),
		/Unexpected capture entries/,
	);
});

test("CLI inspection is offline; capture cannot bypass the 29-request confirmation argument", () => {
	const run = (args: string[]) =>
		spawnSync(
			process.execPath,
			["--import", "tsx", "scripts/compare-coarse-benchmark.ts", ...args],
			{ encoding: "utf8", env: { ...process.env, ORS_API_KEY: key } },
		);
	const check = run(["--check"]);
	assert.equal(check.status, 0);
	assert.equal(JSON.parse(check.stdout).plannedRequests, 29);
	assert.equal(JSON.parse(check.stdout).keyRead, false);
	assert.equal(JSON.parse(check.stdout).providerRequests, 0);
	for (const args of [
		["--capture", "data/coarse-quality/benchmark-not-approved-fixture"],
		[
			"--capture",
			"data/coarse-quality/benchmark-not-approved-fixture",
			"--confirm-48-requests",
		],
		[
			"--capture",
			"data/coarse-quality/benchmark-not-approved-fixture",
			"--confirm-6-requests",
		],
	]) {
		const rejected = run(args);
		assert.equal(rejected.status, 1);
		assert.ok(!rejected.stderr.includes(key));
	}
});
