import assert from "node:assert/strict";
import { resolve } from "node:path";
import { compareBenchmarkRun } from "./coarse-benchmark";
import { captureBenchmarkRun } from "./coarse-benchmark-capture";
import { planSha256, readBenchmarkPlan } from "./coarse-benchmark-plan";

try {
	const args = process.argv.slice(2);
	let result: unknown;
	if (args.length === 1 && args[0] === "--check") {
		const { queries } = await readBenchmarkPlan();
		result = {
			planSha256,
			plannedRequests: queries.length,
			reusedReferences: 54,
			totalCases: 83,
			providerRequests: 0,
			keyRead: false,
		};
	} else {
		assert.ok(
			(args[0] === "--replay" && args.length === 2) ||
				(args[0] === "--capture" &&
					args.length === 3 &&
					args[2] === "--confirm-29-requests"),
		);
		const directory = resolve(args[1]);
		assert.ok(directory.startsWith(`${resolve("data/coarse-quality")}/`));
		if (args[0] === "--capture") {
			const { config } = await import("dotenv");
			config({ path: [".env.local", ".env"], quiet: true });
			result = await captureBenchmarkRun(
				directory,
				process.env.ORS_API_KEY?.trim() ?? "",
			);
		} else result = await compareBenchmarkRun(directory);
	}
	console.log(JSON.stringify(result, null, 2));
} catch {
	console.error(
		"Benchmark command failed. Preserve partial files; do not retry/reuse a run. Use --check or --replay <data/coarse-quality/run>; only after exact new quota approval use --capture <fresh-data/coarse-quality/run> --confirm-29-requests. Check frozen source/plan/capture bindings and existing server-only ORS_API_KEY locally. Raw exceptions are suppressed to protect credentials.",
	);
	process.exitCode = 1;
}
