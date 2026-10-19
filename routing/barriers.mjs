import { resolve } from "node:path";
import { runOffline } from "./offline.mjs";
import { root } from "./settings.mjs";

const args = process.argv.slice(2);
const options = { name: "san-diego-tijuana-barriers-v3", stage: "build" };
while (args.length) {
	const option = args.shift();
	const value = args.shift();
	if (option === "--run-name" && value) options.name = value;
	else if (option === "--stage" && ["build", "rebuild"].includes(value))
		options.stage = value;
	else
		throw new Error(
			"Usage: npm run routing:barriers -- [--run-name name] [--stage build|rebuild]",
		);
}
await runOffline({
	directory: "barrier-pilot",
	name: options.name,
	worker: options.stage === "build" ? "barriers.py" : "barriers_rebuild.py",
	memory: "4g",
	args: [],
	readOnlyMounts: [
		{
			source: resolve(
				root,
				"data/regional-pilot/san-diego-tijuana-corridor-v2",
			),
			target: "/previous",
		},
		{
			source: resolve(root, "data/model-pilot/downtown-maneuvers-v2"),
			target: "/model-reference",
		},
	],
});
