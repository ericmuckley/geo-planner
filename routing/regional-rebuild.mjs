import { runOffline } from "./offline.mjs";

const args = process.argv.slice(2);
if (args.length && (args.length !== 2 || args[0] !== "--run-name"))
	throw new Error(
		"Usage: npm run routing:regional:rebuild -- [--run-name name]",
	);
await runOffline({
	directory: "regional-pilot",
	name: args[1] ?? "san-diego-tijuana-corridor-v2",
	worker: "regional_rebuild.py",
	memory: "4g",
	args: [],
});
