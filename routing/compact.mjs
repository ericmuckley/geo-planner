import { resolve } from "node:path";
import { runOffline } from "./offline.mjs";
import { root } from "./settings.mjs";

const options = { case: "downtown-v2", name: null };
const args = process.argv.slice(2);
while (args.length) {
	const option = args.shift();
	const value = args.shift();
	if (
		option === "--case" &&
		[
			"downtown-v2",
			"corridor-v2",
			"corridor-v3",
			"wide-v3",
			"buffer-v3",
		].includes(value)
	)
		options.case = value;
	else if (option === "--run-name" && value) options.name = value;
	else
		throw new Error(
			"Usage: npm run routing:compact -- [--case downtown-v2|corridor-v2|corridor-v3|wide-v3|buffer-v3] [--run-name name]",
		);
}
await runOffline({
	directory: "compact-pilot",
	name: options.name ?? `compact-v1-${options.case}`,
	worker: "compact.py",
	memory: "4g",
	args: ["--case", options.case],
	readOnlyMounts: [{ source: resolve(root, "data"), target: "/inputs" }],
});
