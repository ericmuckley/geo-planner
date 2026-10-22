import { z } from "zod";
import { type SavedRun, savedRunSchema } from "./reachability";

const storageKey = "geo-planner:runs:v1";
export const maxSavedRuns = 20;
export const savedRunsSchema = z.array(savedRunSchema).max(maxSavedRuns);
export const cloudHistorySchema = z.object({
	configured: z.boolean(),
	runs: savedRunsSchema,
});

export function getRunModel(run: SavedRun, fallback: "coarse" | "connected") {
	return (
		run.model ??
		(run.metadata
			? run.metadata.engine === "coarse"
				? "coarse"
				: "connected"
			: fallback)
	);
}

export function mergeSavedRuns(...groups: SavedRun[][]): SavedRun[] {
	const runs = new Map<string, SavedRun>();
	for (const group of groups)
		for (const run of group) if (!runs.has(run.id)) runs.set(run.id, run);
	return [...runs.values()]
		.sort(
			(a, b) =>
				b.createdAt.localeCompare(a.createdAt) || a.id.localeCompare(b.id),
		)
		.slice(0, maxSavedRuns);
}

export function readSavedRuns(): SavedRun[] {
	const stored = localStorage.getItem(storageKey);
	if (!stored) return [];
	return savedRunsSchema.parse(JSON.parse(stored));
}

export function writeSavedRuns(runs: SavedRun[]) {
	localStorage.setItem(storageKey, JSON.stringify(runs.slice(0, maxSavedRuns)));
}
