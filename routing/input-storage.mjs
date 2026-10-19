import { resolve } from "node:path";
import { runOfflineNoSwap } from "./offline-no-swap.mjs";
import { root } from "./settings.mjs";

const options = { case: "downtown-v2", series: "input-v1" };
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
	else if (option === "--series" && value && /^[a-zA-Z0-9_-]+$/.test(value))
		options.series = value;
	else
		throw new Error(
			"Usage: npm run routing:inputs -- [--case downtown-v2|corridor-v2|corridor-v3|wide-v3|buffer-v3] [--series name]",
		);
}
await runOfflineNoSwap({
	directory: "input-pilot",
	name: `${options.series}-${options.case}`,
	worker: "input_capacity.py",
	memory: "4g",
	args: ["--case", options.case, "--series", options.series],
	readOnlyMounts: [{ source: resolve(root, "data"), target: "/inputs" }],
});
