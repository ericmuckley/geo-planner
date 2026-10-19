import { z } from "zod";
import { type SavedRun, savedRunSchema } from "./reachability";

const storageKey = "geo-planner:runs:v1";
export const maxSavedRuns = 20;

export function readSavedRuns(): SavedRun[] {
	const stored = localStorage.getItem(storageKey);
	if (!stored) return [];
	return z.array(savedRunSchema).max(maxSavedRuns).parse(JSON.parse(stored));
}

export function writeSavedRuns(runs: SavedRun[]) {
	localStorage.setItem(storageKey, JSON.stringify(runs.slice(0, maxSavedRuns)));
}
