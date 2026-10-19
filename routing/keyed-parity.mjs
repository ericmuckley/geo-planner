import { resolve } from "node:path";
import { runOfflineNoSwap } from "./offline-no-swap.mjs";
import { root } from "./settings.mjs";

const options = { case: "downtown-v2", series: "keys-v1", name: null };
const args = process.argv.slice(2);
while (args.length) {
	const option = args.shift();
	const value = args.shift();
	if (
		option === "--case" &&
		["downtown-v2", "corridor-v3", "wide-v3", "hour-v3"].includes(value)
	)
		options.case = value;
	else if (option === "--series" && /^[a-zA-Z0-9_-]+$/.test(value ?? ""))
		options.series = value;
	else if (option === "--run-name" && value) options.name = value;
	else
		throw new Error(
			"Usage: npm run routing:keys -- [--case downtown-v2|corridor-v3|wide-v3|hour-v3] [--series name] [--run-name name]",
		);
}
await runOfflineNoSwap({
	directory: "keyed-pilot",
	name: options.name ?? `${options.series}-${options.case}`,
	worker: "keyed_parity.py",
	memory: "4g",
	args: ["--case", options.case, "--series", options.series],
	readOnlyMounts: [{ source: resolve(root, "data"), target: "/inputs" }],
});
