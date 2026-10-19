import { resolve } from "node:path";
import { runOffline } from "./offline.mjs";
import { manifest, root } from "./settings.mjs";

const options = {
	stage: "build",
	name: "san-diego-tijuana-corridor-v2",
	extractCache: null,
};
const args = process.argv.slice(2);
while (args.length) {
	const option = args.shift();
	const value = args.shift();
	if (option === "--stage" && ["extract", "build"].includes(value))
		options.stage = value;
	else if (option === "--run-name" && value) options.name = value;
	else if (
		option === "--extract-cache" &&
		value &&
		/^[a-zA-Z0-9_-]+$/.test(value)
	)
		options.extractCache = value;
	else
		throw new Error(
			"Usage: npm run routing:regional -- [--stage extract|build] [--run-name name] [--extract-cache name]",
		);
}
await runOffline({
	directory: "regional-pilot",
	name: options.name,
	worker: "regional.py",
	memory: "4g",
	args: [
		"--expected-graph",
		manifest.id,
		"--stage",
		options.stage,
		"--model-reference",
		"/model-reference",
		...(options.extractCache ? ["--extract-cache", "/extract-cache"] : []),
	],
	readOnlyMounts: [
		{
			source: resolve(root, "data/model-pilot/downtown-maneuvers-v2"),
			target: "/model-reference",
		},
		...(options.extractCache
			? [
					{
						source: resolve(root, "data/regional-pilot", options.extractCache),
						target: "/extract-cache",
					},
				]
			: []),
	],
});
