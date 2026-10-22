import { drizzle } from "drizzle-orm/node-postgres";

import * as schema from "./schema.ts";

export const db = drizzle({
	connection: {
		connectionString: process.env.DATABASE_URL,
		max: 3,
		connectionTimeoutMillis: 5_000,
		idleTimeoutMillis: 10_000,
		statement_timeout: 5_000,
	},
	schema,
});

db.$client.on("error", () => {
	console.error("A background database connection closed unexpectedly.");
});
