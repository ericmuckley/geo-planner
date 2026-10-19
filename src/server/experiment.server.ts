import type { z } from "zod";
import {
	experimentConfigSchema,
	experimentQuerySchema,
	experimentResultSchema,
} from "../lib/experiment";

const workerUrl = "http://127.0.0.1:8787";

function enabled() {
	return process.env.LOCAL_ROUTING_EXPERIMENT === "1" && !process.env.VERCEL;
}

function error(message: string, status: number) {
	return Response.json(
		{ error: message },
		{ status, headers: { "Cache-Control": "no-store" } },
	);
}

export async function experimentConfig() {
	if (!enabled())
		return error(
			"Start npm run dev:experiment to use the local router. Hosted routing stays separate.",
			503,
		);
	try {
		const response = await fetch(`${workerUrl}/health`, {
			signal: AbortSignal.timeout(3000),
			redirect: "error",
		});
		if (!response.ok) throw new Error("Worker unavailable");
		return Response.json(experimentConfigSchema.parse(await response.json()), {
			headers: { "Cache-Control": "no-store" },
		});
	} catch {
		return error(
			"Local router is loading or unavailable. Check the experiment terminal and retry.",
			503,
		);
	}
}

export async function runExperiment(request: Request) {
	if (!enabled())
		return error(
			"Local experiment is disabled. Start npm run dev:experiment.",
			503,
		);
	let query: z.infer<typeof experimentQuerySchema>;
	try {
		const text = await request.text();
		if (text.length > 2048) return error("Query is too large.", 400);
		query = experimentQuerySchema.parse(JSON.parse(text));
	} catch {
		return error(
			"Choose valid coordinates and a whole-minute budget from 1 to 720.",
			400,
		);
	}
	const before = performance.now();
	try {
		const response = await fetch(`${workerUrl}/query`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(query),
			signal: AbortSignal.any([request.signal, AbortSignal.timeout(90000)]),
			redirect: "error",
		});
		if (!response.ok) {
			if (response.status === 400)
				return error(
					"Origin is outside the dataset or no supported road is within 100 m. Choose a point closer to a road inside the regional bounds.",
					400,
				);
			return error(
				"Local router failed. Check its terminal; no hosted fallback was used.",
				503,
			);
		}
		const result = experimentResultSchema.parse(await response.json());
		if (JSON.stringify(result.query) !== JSON.stringify(query))
			throw new Error("Query mismatch");
		result.metadata.timings.appProxyMs = performance.now() - before;
		return Response.json(result, { headers: { "Cache-Control": "no-store" } });
	} catch {
		return error(
			"Local request failed or timed out. Check the experiment terminal. No hosted fallback was used.",
			503,
		);
	}
}
