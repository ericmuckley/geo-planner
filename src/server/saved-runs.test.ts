import assert from "node:assert/strict";
import { test } from "node:test";
import { defaultQuery, type SavedRun } from "../lib/reachability";
import { maxSavedRuns, mergeSavedRuns } from "../lib/saved-runs";
import { handleSavedRuns } from "./saved-runs.server";
import type { SavedHistoryStore } from "./saved-runs-store.server";

function run(id = "query-1", createdAt = "2026-10-22T00:00:00.000Z"): SavedRun {
	return {
		id,
		createdAt,
		query: { ...defaultQuery, budgetMinutes: 360 },
		model: "coarse",
	};
}

function memoryStore() {
	const histories = new Map<string, SavedRun[]>();
	const store: SavedHistoryStore = {
		async read(owner) {
			return histories.get(owner) ?? [];
		},
		async save(owner, incoming) {
			const runs = mergeSavedRuns(incoming, histories.get(owner) ?? []);
			histories.set(owner, runs);
			return runs;
		},
	};
	return { store, histories };
}

function request(
	cookie?: string,
	body?: unknown,
	headers: Record<string, string> = {},
) {
	return new Request("https://app.example/api/saved-runs", {
		method: body === undefined ? "GET" : "POST",
		headers: {
			...(cookie ? { Cookie: cookie } : {}),
			...(body === undefined
				? {}
				: {
						"Content-Type": "application/json",
						Origin: "https://app.example",
					}),
			...headers,
		},
		body: body === undefined ? undefined : JSON.stringify(body),
	});
}

async function configured(task: () => Promise<void>) {
	const previous = process.env.DATABASE_URL;
	process.env.DATABASE_URL = "postgresql://test.invalid/not-contacted";
	try {
		await task();
	} finally {
		if (previous === undefined) delete process.env.DATABASE_URL;
		else process.env.DATABASE_URL = previous;
	}
}

test("cloud history survives a new request and isolates browser owners without storing their raw tokens", async () =>
	configured(async () => {
		const { store, histories } = memoryStore();
		const first = await handleSavedRuns(request(), store);
		assert.equal(first.status, 200);
		assert.match(first.headers.get("Cache-Control") ?? "", /private, no-store/);
		assert.equal(first.headers.get("Vary"), "Cookie");
		const setCookie = first.headers.get("Set-Cookie") ?? "";
		assert.match(setCookie, /HttpOnly; SameSite=Lax; Max-Age=31536000; Secure/);
		const cookie = setCookie.split(";")[0];
		assert.equal(
			(await handleSavedRuns(request(cookie, [run()]), store)).status,
			200,
		);
		const restored = await handleSavedRuns(request(cookie), store);
		assert.deepEqual((await restored.json()).runs, [run()]);
		const other = await handleSavedRuns(request(), store);
		assert.deepEqual((await other.json()).runs, []);
		assert.notEqual(other.headers.get("Set-Cookie"), setCookie);
		assert.equal(histories.size, 1);
		assert.notEqual([...histories.keys()][0], cookie.split("=")[1]);
		assert.equal(restored.headers.get("Set-Cookie"), null);
	}));

test("history merges by ID, retains query model, and bounds every owner's history to 20", async () =>
	configured(async () => {
		const { store } = memoryStore();
		const cookie = `geo-planner-history=${"a".repeat(64)}`;
		for (let i = 0; i < 25; i++) {
			const entry = run(
				`query-${i}`,
				new Date(Date.UTC(2026, 9, 22, 0, i)).toISOString(),
			);
			assert.equal(
				(await handleSavedRuns(request(cookie, [entry]), store)).status,
				200,
			);
		}
		const data = await (await handleSavedRuns(request(cookie), store)).json();
		assert.equal(data.runs.length, maxSavedRuns);
		assert.equal(data.runs[0].id, "query-24");
		assert.equal(data.runs[19].id, "query-5");
		const updated = { ...data.runs[0], model: "connected" };
		const saved = await (
			await handleSavedRuns(request(cookie, [updated]), store)
		).json();
		assert.equal(saved.runs.length, 20);
		assert.equal(saved.runs[0].model, "connected");
	}));

test("cross-origin and invalid history requests never reach storage", async () =>
	configured(async () => {
		const store: SavedHistoryStore = {
			async read() {
				assert.fail("Unexpected read");
			},
			async save() {
				assert.fail("Unexpected write");
			},
		};
		assert.equal(
			(
				await handleSavedRuns(
					request(undefined, [run()], { Origin: "https://evil.example" }),
					store,
				)
			).status,
			403,
		);
		assert.equal(
			(
				await handleSavedRuns(
					request(undefined, undefined, { "Sec-Fetch-Site": "cross-site" }),
					store,
				)
			).status,
			403,
		);
		assert.equal(
			(
				await handleSavedRuns(
					request(undefined, [run()], { "Content-Type": "text/plain" }),
					store,
				)
			).status,
			415,
		);
		for (const body of [
			[],
			Array(21).fill(run()),
			[{ ...run(), query: { ...defaultQuery, budgetMinutes: 721 } }],
			[{ ...run(), id: "x".repeat(129) }],
		])
			assert.equal(
				(await handleSavedRuns(request(undefined, body), store)).status,
				422,
			);
		for (const body of ["{", " ".repeat(262_145)]) {
			const req = new Request("https://app.example/api/saved-runs", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body,
			});
			assert.equal((await handleSavedRuns(req, store)).status, 400);
		}
	}));

test("missing or failing database returns safe local fallback without exposing credentials", async () => {
	const previous = process.env.DATABASE_URL;
	delete process.env.DATABASE_URL;
	try {
		assert.deepEqual(await (await handleSavedRuns(request())).json(), {
			configured: false,
			runs: [],
		});
		assert.equal(
			(await handleSavedRuns(request(undefined, [run()]))).status,
			503,
		);
		await configured(async () => {
			const store: SavedHistoryStore = {
				async read() {
					throw new Error("postgresql://private-secret");
				},
				async save() {
					throw new Error("postgresql://private-secret");
				},
			};
			for (const req of [request(), request(undefined, [run()])]) {
				const response = await handleSavedRuns(req, store);
				assert.equal(response.status, 503);
				assert.ok(!(await response.text()).includes("private-secret"));
			}
		});
	} finally {
		if (previous !== undefined) process.env.DATABASE_URL = previous;
	}
});
