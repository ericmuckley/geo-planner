import { createHash, randomBytes } from "node:crypto";
import type { SavedRun } from "../lib/reachability";
import { savedRunsSchema } from "../lib/saved-runs";
import {
	historyStore,
	type SavedHistoryStore,
} from "./saved-runs-store.server";

const cookieName = "geo-planner-history";
const maxBodyBytes = 262_144;

async function readBody(request: Request) {
	const reader = request.body?.getReader();
	if (!reader) throw new Error("Missing body");
	const decoder = new TextDecoder();
	let bytes = 0;
	let body = "";
	try {
		while (true) {
			const chunk = await reader.read();
			if (chunk.done) break;
			bytes += chunk.value.byteLength;
			if (bytes > maxBodyBytes) {
				await reader.cancel();
				throw new Error("Body too large");
			}
			body += decoder.decode(chunk.value, { stream: true });
		}
		return JSON.parse(body + decoder.decode());
	} finally {
		reader.releaseLock();
	}
}

export async function handleSavedRuns(
	request: Request,
	store: SavedHistoryStore = historyStore,
) {
	const headers = new Headers({
		"Cache-Control": "private, no-store",
		Vary: "Cookie",
	});
	const json = (body: unknown, status = 200) =>
		Response.json(body, { status, headers });
	if (request.method !== "GET" && request.method !== "POST")
		return json({ error: "Method not allowed." }, 405);
	if (!process.env.DATABASE_URL)
		return request.method === "GET"
			? json({ configured: false, runs: [] })
			: json(
					{
						error:
							"Cloud history is not configured. Your query is still saved in this browser.",
					},
					503,
				);
	const origin = request.headers.get("Origin");
	if (
		(origin && origin !== new URL(request.url).origin) ||
		request.headers.get("Sec-Fetch-Site") === "cross-site"
	)
		return json(
			{ error: "Cloud history is available only from this app." },
			403,
		);
	let incoming: SavedRun[] | undefined;
	if (request.method === "POST") {
		if (
			request.headers.get("Content-Type")?.split(";")[0].trim() !==
			"application/json"
		)
			return json({ error: "Expected application/json." }, 415);
		let body: unknown;
		try {
			body = await readBody(request);
		} catch {
			return json(
				{ error: "Expected a JSON history batch smaller than 256 KiB." },
				400,
			);
		}
		const parsed = savedRunsSchema.min(1).safeParse(body);
		if (!parsed.success)
			return json(
				{
					error:
						"Expected between 1 and 20 valid saved queries or run summaries.",
				},
				422,
			);
		incoming = parsed.data;
	}
	const match = request.headers
		.get("Cookie")
		?.match(/(?:^|;\s*)geo-planner-history=([a-f0-9]{64})(?:;|$)/);
	const token = match?.[1] ?? randomBytes(32).toString("hex");
	if (!match)
		headers.set(
			"Set-Cookie",
			`${cookieName}=${token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=31536000${new URL(request.url).protocol === "https:" ? "; Secure" : ""}`,
		);
	const ownerHash = createHash("sha256").update(token).digest("hex");
	try {
		const runs = incoming
			? await store.save(ownerHash, incoming)
			: await store.read(ownerHash);
		return json({ configured: true, runs });
	} catch {
		return json(
			{
				configured: true,
				error:
					"Cloud history is unavailable. Your queries remain in this browser; retry the backup shortly.",
			},
			503,
		);
	}
}
