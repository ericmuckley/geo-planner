import { spawn } from "node:child_process";
import { dataDir, root, sourceDir } from "./settings.mjs";

const [action] = process.argv.slice(2);
const commands = {
	build: ["run", "--build", "--rm", "build"],
	up: ["up", "-d", "--wait", "valhalla"],
	down: ["down"],
};
if (!commands[action])
	throw new Error("Expected routing action: build, up, down");
const child = spawn(
	"docker",
	["compose", "-f", "routing/compose.yml", ...commands[action]],
	{
		cwd: root,
		stdio: "inherit",
		env: {
			...process.env,
			VALHALLA_DATA_DIR: dataDir,
			VALHALLA_SOURCE_DIR: sourceDir,
		},
	},
);
child.on("exit", (code) => process.exit(code ?? 1));
for (const signal of ["SIGINT", "SIGTERM"])
	process.on(signal, () => child.kill(signal));
