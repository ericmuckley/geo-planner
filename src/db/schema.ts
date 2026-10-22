import {
	jsonb,
	pgTable,
	serial,
	text,
	timestamp,
	varchar,
} from "drizzle-orm/pg-core";
import type { SavedRun } from "../lib/reachability";

export const todos = pgTable("todos", {
	id: serial().primaryKey(),
	title: text().notNull(),
	createdAt: timestamp("created_at").defaultNow(),
});

export const savedHistories = pgTable("saved_histories", {
	ownerHash: varchar("owner_hash", { length: 64 }).primaryKey(),
	runs: jsonb("runs").$type<SavedRun[]>().notNull().default([]),
	updatedAt: timestamp("updated_at", { withTimezone: true })
		.notNull()
		.defaultNow(),
});
