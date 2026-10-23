import assert from "node:assert/strict";
import { resolve } from "node:path";
import { config } from "dotenv";
import {
	captureReferenceRun,
	planSha256,
	readFrozenPlan,
	replayReferenceRun,
} from "./coarse-holdout";

try {
	const args = process.argv.slice(2);
	let result: unknown;
	if (args.length === 1 && args[0] === "--check") {
		const plan = await readFrozenPlan();
		result = {
			planSha256,
			plannedRequests: plan.queries.length,
			providerRequests: 0,
			keyRead: false,
		};
	} else {
		assert.ok(
			(args[0] === "--replay" && args.length === 2) ||
				(args[0] === "--capture" &&
					args.length === 3 &&
					args[2] === "--confirm-48-requests"),
		);
		const directory = resolve(args[1]);
		assert.ok(directory.startsWith(`${resolve("data/coarse-quality")}/`));
		if (args[0] === "--capture") {
			// Read existing configuration only after explicit capture arguments.
			config({ path: [".env.local", ".env"], quiet: true });
			result = await captureReferenceRun(
				directory,
				process.env.ORS_API_KEY?.trim() ?? "",
			);
		} else result = await replayReferenceRun(directory);
	}
	console.log(JSON.stringify(result, null, 2));
} catch {
	// Never print raw exceptions: fetch/provider errors can contain the key.
	console.error(
		"Reference command failed. Preserve any partial run; do not retry or reuse its directory. Use --check, --replay <data/coarse-quality/run>, or (only after quota authorization) --capture <fresh-data/coarse-quality/run> --confirm-48-requests. Check the frozen plan, file permissions, checksums and existing ORS_API_KEY locally.",
	);
	process.exitCode = 1;
}
