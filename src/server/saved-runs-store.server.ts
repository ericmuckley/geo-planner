import { eq } from "drizzle-orm";
import { db } from "../db";
import { savedHistories } from "../db/schema";
import type { SavedRun } from "../lib/reachability";
import { mergeSavedRuns, savedRunsSchema } from "../lib/saved-runs";

export interface SavedHistoryStore {
	read(ownerHash: string): Promise<SavedRun[]>;
	save(ownerHash: string, runs: SavedRun[]): Promise<SavedRun[]>;
}

export const historyStore: SavedHistoryStore = {
	async read(ownerHash) {
		const [history] = await db
			.select({ runs: savedHistories.runs })
			.from(savedHistories)
			.where(eq(savedHistories.ownerHash, ownerHash));
		return savedRunsSchema.parse(history?.runs ?? []);
	},
	async save(ownerHash, incoming) {
		return db.transaction(async (tx) => {
			await tx
				.insert(savedHistories)
				.values({ ownerHash, runs: [] })
				.onConflictDoNothing();
			// Lock this browser's history so concurrent tabs cannot overwrite new saves.
			const [history] = await tx
				.select({ runs: savedHistories.runs })
				.from(savedHistories)
				.where(eq(savedHistories.ownerHash, ownerHash))
				.for("update");
			const runs = mergeSavedRuns(
				incoming,
				savedRunsSchema.parse(history.runs),
			);
			await tx
				.update(savedHistories)
				.set({ runs, updatedAt: new Date() })
				.where(eq(savedHistories.ownerHash, ownerHash));
			return runs;
		});
	},
};
