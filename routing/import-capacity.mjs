import { resolve } from "node:path";
import { runOffline } from "./offline.mjs";
import { root } from "./settings.mjs";

const args = process.argv.slice(2);
const options = { case: "downtown-v2", name: null };
while (args.length) {
	const option = args.shift();
	const value = args.shift();
	if (
		option === "--case" &&
		["downtown-v2", "corridor-v2", "corridor-v3", "wide-v2"].includes(value)
	)
		options.case = value;
	else if (option === "--run-name" && value) options.name = value;
	else
		throw new Error(
			"Usage: npm run routing:import -- [--case downtown-v2|corridor-v2|corridor-v3|wide-v2] [--run-name name]",
		);
}
await runOffline({
	directory: "import-pilot",
	name: options.name ?? `stream-v1-${options.case}`,
	worker: "import_capacity.py",
	memory: "4g",
	args: ["--case", options.case],
	readOnlyMounts: [
		["reference-pilot/downtown-static-v1", "/reference"],
		["model-pilot/downtown-maneuvers-v2", "/downtown"],
		["regional-pilot/san-diego-tijuana-corridor-v2", "/corridor"],
		["barrier-pilot/san-diego-tijuana-barriers-v3", "/barriers"],
		["regional-pilot/san-diego-tijuana-v2", "/wide"],
	].map(([path, target]) => ({ source: resolve(root, "data", path), target })),
});
