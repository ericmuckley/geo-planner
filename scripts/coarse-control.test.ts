import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtemp, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { type TestContext, test } from "node:test";
import {
	captureControlRun,
	readControlPlan,
	replayControlRun,
} from "./coarse-control";

const plan = await readControlPlan();
const key = "synthetic-control-secret+never-real";
type Runtime = NonNullable<Parameters<typeof captureControlRun>[2]>;
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
		metadata: { engine: { version: "SYNTHETIC", graph_date: "2026-10-01" } },
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
			assert.ok(index < 6, "No seventh request");
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
	const parent = await mkdtemp(join(tmpdir(), "geo-control-fixture-"));
	t.after(() => rm(parent, { recursive: true, force: true }));
	return join(parent, "capture");
}

test("six exact requests, hard cap, spacing/deadline and redaction; deterministic signed/percentage offline comparison", async (t) => {
	const directory = await scratch(t);
	const gaps = [5, 6, 7, 8, -1, -2];
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
	assert.deepEqual(await captureControlRun(directory, key, io), {
		attempted: 6,
		stopReason: null,
	});
	assert.equal(starts.length, 6);
	assert.ok(starts.slice(1).every((x, i) => x - starts[i] >= 6500));
	assert.deepEqual(deadlines, Array(6).fill(45000));
	for (const name of await readdir(directory)) {
		const text = await readFile(join(directory, name), "utf8");
		assert.ok(
			!text.includes(key) &&
				!text.includes(encodeURIComponent(key)) &&
				!text.includes("private=omit"),
		);
	}
	const report = await replayControlRun(directory);
	assert.deepEqual(report, await replayControlRun(directory));
	assert.equal(report.transport, "synthetic");
	assert.equal(report.overall.planned, 6);
	assert.equal(report.overall.pairedFinite, 6);
	assert.ok(Math.abs((report.overall.meanSignedMinutes ?? 0) - 23 / 6) < 1e-10);
	assert.ok(Math.abs((report.overall.medianSignedMinutes ?? 0) - 5.5) < 1e-10);
	assert.ok(
		Math.abs((report.overall.meanAbsoluteMinutes ?? 0) - 29 / 6) < 1e-10,
	);
	assert.equal(report.overall.materialPositiveDiscrepancy, true);
	assert.equal(report.overall.interpretationLimited, false);
	assert.ok(
		Math.abs(
			(report.cases[0].differencePercent ?? 0) -
				(5 / plan.queries[0].existingValhallaMinutes) * 100,
		) < 1e-10,
	);
	assert.ok(Math.abs((report.cases[0].distanceDifferenceKm ?? 0) - 1) < 1e-10);
	await assert.rejects(captureControlRun(directory, key, io));
	assert.equal(starts.length, 6);
});

for (const status of [401, 403, 429])
	test(`HTTP${status} stops once and retains five skipped cases`, async (t) => {
		const directory = await scratch(t);
		const { io, starts } = runtime(
			() => new Response(`synthetic error ${key}`, { status }),
		);
		assert.deepEqual(await captureControlRun(directory, key, io), {
			attempted: 1,
			stopReason: `http-${status}`,
		});
		assert.equal(starts.length, 1);
		const report = await replayControlRun(directory);
		assert.equal(report.cases.length, 6);
		assert.equal(report.cases.filter((r) => r.outcome === "skipped").length, 5);
		assert.equal(report.overall.unpaired, 6);
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
	assert.deepEqual(await captureControlRun(directory, key, io), {
		attempted: 1,
		stopReason: "quota-exhausted",
	});
	assert.equal(starts.length, 1);
	assert.equal((await replayControlRun(directory)).overall.pairedFinite, 1);
});

test("network exceptions, invalid JSON/routes and HTTP failures retain their original denominators without retries", async (t) => {
	const directory = await scratch(t);
	const { io, starts } = runtime((i) => {
		if (i === 0) throw new Error(key);
		return i < 3
			? new Response(i === 1 ? "not-json" : "{}")
			: new Response("no route", { status: 404 });
	});
	await captureControlRun(directory, key, io);
	assert.equal(starts.length, 6);
	const r = await replayControlRun(directory);
	assert.equal(r.overall.pairedFinite, 0);
	assert.equal(r.overall.meanAbsoluteMinutes, null);
	assert.equal(r.overall.unpaired, 6);
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
		await captureControlRun(directory, key, io);
		assert.equal(starts.length, 2);
		assert.equal(
			(await replayControlRun(directory)).cases[0].outcome,
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
	assert.deepEqual(await captureControlRun(directory, key, io), {
		attempted: 1,
		stopReason: "body-limit",
	});
	assert.equal(starts.length, 1);
	assert.equal(
		(await readFile(join(directory, "00-response.txt"))).length,
		2_000_000,
	);
	assert.equal(
		(await replayControlRun(directory)).cases[0].outcome,
		"capture-error",
	);
});

test("disk failure stops before another request", async (t) => {
	const directory = await scratch(t);
	const { io, starts } = runtime(async () => {
		await rm(directory, { recursive: true });
		return new Response("fixture");
	});
	await assert.rejects(captureControlRun(directory, key, io));
	assert.equal(starts.length, 1);
});

test("all pairs and >100m snaps remain primary; sensitivity and incomplete-pair limits are explicit", async (t) => {
	const directory = await scratch(t);
	const { io } = runtime(
		(i) => new Response(JSON.stringify(route(i, 10, i === 0 ? 0.01 : 0))),
	);
	await captureControlRun(directory, key, io);
	const r = await replayControlRun(directory);
	assert.equal(r.overall.pairedFinite, 6);
	assert.equal(r.overall.snapOver100m, 1);
	assert.equal(r.overall.materialPositiveDiscrepancy, true);
	assert.equal(r.overall.interpretationLimited, true);
	assert.equal(r.snapAtMost100mSensitivity.pairedFinite, 5);
	const partial = `${await scratch(t)}-partial`;
	const fake = runtime((i) =>
		i < 4
			? new Response(JSON.stringify(route(i, 10)))
			: new Response("missing", { status: 404 }),
	);
	await captureControlRun(partial, key, fake.io);
	const p = await replayControlRun(partial);
	assert.equal(p.overall.materialPositiveDiscrepancy, true);
	assert.equal(p.overall.interpretationLimited, true);
	assert.equal(p.overall.unpaired, 2);
});

test("replay rejects changed, incomplete and unsealed captures", async (t) => {
	const directory = await scratch(t);
	const { io } = runtime(() => new Response("stop", { status: 401 }));
	await captureControlRun(directory, key, io);
	await writeFile(join(directory, "extra.txt"), "unsealed");
	await assert.rejects(replayControlRun(directory));
	await rm(join(directory, "extra.txt"));
	await writeFile(join(directory, "00-response.txt"), "changed");
	await assert.rejects(replayControlRun(directory), /Changed capture/);
	await rm(join(directory, "sha256.json"));
	await assert.rejects(replayControlRun(directory));
});

test("replay rejects a checksum-bound seventh request file outside its ledger", async (t) => {
	const directory = await scratch(t);
	const { io } = runtime(() => new Response("stop", { status: 401 }));
	await captureControlRun(directory, key, io);
	await writeFile(join(directory, "06-request.json"), "{}");
	const manifest = JSON.parse(
		await readFile(join(directory, "sha256.json"), "utf8"),
	);
	manifest["06-request.json"] = createHash("sha256").update("{}").digest("hex");
	await writeFile(join(directory, "sha256.json"), JSON.stringify(manifest));
	await assert.rejects(
		replayControlRun(directory),
		/Unexpected capture entries/,
	);
});

test("CLI inspection is offline; capture cannot bypass the six-request confirmation argument", () => {
	const run = (args: string[]) =>
		spawnSync(
			process.execPath,
			["--import", "tsx", "scripts/compare-coarse-control.ts", ...args],
			{ encoding: "utf8", env: { ...process.env, ORS_API_KEY: key } },
		);
	const check = run(["--check"]);
	assert.equal(check.status, 0);
	assert.equal(JSON.parse(check.stdout).plannedRequests, 6);
	assert.equal(JSON.parse(check.stdout).keyRead, false);
	assert.equal(JSON.parse(check.stdout).providerRequests, 0);
	for (const args of [
		["--capture", "data/coarse-quality/control-not-approved-fixture"],
		[
			"--capture",
			"data/coarse-quality/control-not-approved-fixture",
			"--confirm-48-requests",
		],
	]) {
		const rejected = run(args);
		assert.equal(rejected.status, 1);
		assert.ok(!rejected.stderr.includes(key));
	}
});
