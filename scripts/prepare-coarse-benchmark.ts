import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { buildBenchmarkPlan } from "./coarse-benchmark-plan";

const directory = process.argv[2];
assert.equal(process.argv.length, 3);
assert.ok(
	directory &&
		resolve(directory).startsWith(`${resolve("data/coarse-quality")}/`),
);
const { plan } = await buildBenchmarkPlan();
await mkdir(directory);
await writeFile(
	`${directory}/plan.json`,
	`${JSON.stringify(plan, null, 2)}\n`,
	{ flag: "wx" },
);
console.log(
	JSON.stringify(
		{
			plannedRequests: plan.queries.length,
			reusedReferences: 54,
			totalCases: 83,
			providerRequests: 0,
			keyRead: false,
		},
		null,
		2,
	),
);
