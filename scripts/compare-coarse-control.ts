import assert from "node:assert/strict";
import { resolve } from "node:path";
import {
	captureControlRun,
	planSha256,
	readControlPlan,
	replayControlRun,
} from "./coarse-control";

try {
	const args = process.argv.slice(2);
	let result: unknown;
	if (args.length === 1 && args[0] === "--check") {
		const plan = await readControlPlan();
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
					args[2] === "--confirm-6-requests"),
		);
		const directory = resolve(args[1]);
		assert.ok(directory.startsWith(`${resolve("data/coarse-quality")}/`));
		if (args[0] === "--capture") {
			const { config } = await import("dotenv");
			config({ path: [".env.local", ".env"], quiet: true });
			result = await captureControlRun(
				directory,
				process.env.ORS_API_KEY?.trim() ?? "",
			);
		} else result = await replayControlRun(directory);
	}
	console.log(JSON.stringify(result, null, 2));
} catch {
	console.error(
		"Control command failed. Preserve partial files; do not retry/reuse a run. Use --check or --replay <data/coarse-quality/run>; only after exact quota approval use --capture <fresh-data/coarse-quality/run> --confirm-6-requests. Inspect plan/checksums/permissions and existing ORS_API_KEY locally. Raw exceptions are suppressed to protect credentials.",
	);
	process.exitCode = 1;
}
