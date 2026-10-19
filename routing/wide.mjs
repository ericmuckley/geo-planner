import { resolve } from "node:path";
import { runOffline } from "./offline.mjs";
import { root } from "./settings.mjs";

const args = process.argv.slice(2);
const options = { name: "san-diego-tijuana-wide-v3", stage: "build" };
while (args.length) {
	const option = args.shift();
	const value = args.shift();
	if (option === "--run-name" && value) options.name = value;
	else if (option === "--stage" && ["build", "rebuild"].includes(value))
		options.stage = value;
	else
		throw new Error(
			"Usage: npm run routing:wide -- [--run-name name] [--stage build|rebuild]",
		);
}
await runOffline({
	directory: "barrier-pilot",
	name: options.name,
	worker: "wide.py",
	memory: "4g",
	args: ["--stage", options.stage],
	readOnlyMounts: [
		["import-pilot/stream-v1-wide-v2", "/wide-v2"],
		["regional-pilot/san-diego-tijuana-v2", "/source"],
		["model-pilot/downtown-maneuvers-v2", "/fixture"],
	].map(([path, target]) => ({ source: resolve(root, "data", path), target })),
});
