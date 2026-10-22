import assert from "node:assert/strict";
import { createHash, randomUUID } from "node:crypto";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { config } from "dotenv";
import { eq } from "drizzle-orm";
import { defaultQuery, type SavedRun } from "../src/lib/reachability";
import { cloudHistorySchema } from "../src/lib/saved-runs";

config({ path: [".env.local", ".env"], quiet: true });
assert.ok(
	process.env.DATABASE_URL,
	"DATABASE_URL is required for the integration check",
);
const { db } = await import("../src/db/index");
const { savedHistories } = await import("../src/db/schema");
const vercel = process.argv.includes("--vercel");
const handleSavedRuns = vercel
	? (
			await import(
				pathToFileURL(
					resolve(".vercel/output/functions/__server.func/index.mjs"),
				).href
			)
		).default.fetch
	: (await import("../src/server/saved-runs.server")).handleSavedRuns;
const url = "https://history-check.example/api/saved-runs";
const initial = await handleSavedRuns(new Request(url));
assert.equal(
	initial.status,
	200,
	"History GET failed; check DB connectivity and migrations",
);
const cookie = initial.headers.get("Set-Cookie")?.split(";")[0];
assert.ok(cookie);
const ownerHash = createHash("sha256")
	.update(cookie.split("=")[1])
	.digest("hex");
const batch = Array.from(
	{ length: 20 },
	(_, minute): SavedRun => ({
		id: randomUUID(),
		createdAt: new Date(Date.UTC(2026, 9, 22, 0, minute)).toISOString(),
		query: { ...defaultQuery, budgetMinutes: 360 },
		model: "coarse",
	}),
);
async function save(runs: SavedRun[]) {
	const response = await handleSavedRuns(
		new Request(url, {
			method: "POST",
			headers: {
				Cookie: cookie ?? "",
				Origin: new URL(url).origin,
				"Content-Type": "application/json",
			},
			body: JSON.stringify(runs),
		}),
	);
	assert.equal(response.status, 200, "History POST failed");
	return cloudHistorySchema.parse(await response.json());
}
try {
	await save(batch);
	const concurrent = [20, 21].map(
		(minute): SavedRun => ({
			...batch[0],
			id: randomUUID(),
			createdAt: new Date(Date.UTC(2026, 9, 22, 0, minute)).toISOString(),
		}),
	);
	await Promise.all(concurrent.map((run) => save([run])));
	const restored = await handleSavedRuns(
		new Request(url, { headers: { Cookie: cookie } }),
	);
	const result = cloudHistorySchema.parse(await restored.json());
	assert.equal(result.runs.length, 20);
	for (const run of concurrent)
		assert.ok(result.runs.some((stored) => stored.id === run.id));
	assert.ok(
		!result.runs.some(
			(stored) => stored.id === batch[0].id || stored.id === batch[1].id,
		),
	);
	const otherBrowser = await handleSavedRuns(new Request(url));
	assert.deepEqual(
		cloudHistorySchema.parse(await otherBrowser.json()).runs,
		[],
	);
	const [stored] = await db
		.select({ runs: savedHistories.runs })
		.from(savedHistories)
		.where(eq(savedHistories.ownerHash, ownerHash));
	assert.deepEqual(stored.runs, result.runs);
	console.log(
		JSON.stringify(
			{
				cloudPersistence: true,
				target: vercel ? "generated-vercel-handler" : "source-handler",
				ownerIsolation: true,
				concurrentSavesRetained: true,
				historyLimit: 20,
				modelRetained: result.runs[0].model,
				scope:
					"Live PostgreSQL integration using one temporary test owner; only that owner's generated test history is removed afterward. This is not a cloud web deployment.",
			},
			null,
			2,
		),
	);
} finally {
	await db
		.delete(savedHistories)
		.where(eq(savedHistories.ownerHash, ownerHash));
	await db.$client.end();
}
