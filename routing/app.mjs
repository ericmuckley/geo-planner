import { spawn } from "node:child_process";
import { dataDir, root } from "./settings.mjs";

const [action = "dev", ...args] = process.argv.slice(2);
const scripts = {
	verify: "routing/verify.mjs",
	"check-vercel": "routing/check-vercel.mjs",
};
const target = scripts[action]
	? [scripts[action], ...args]
	: [
			"node_modules/vite/bin/vite.js",
			action,
			"--port",
			action === "preview" ? "4173" : "3000",
			...args,
		];
const child = spawn(
	process.execPath,
	[
		`--env-file=${dataDir}/app.env`,
		...(scripts[action] ? ["--import", "tsx"] : []),
		...target,
	],
	{
		cwd: root,
		stdio: "inherit",
		env: {
			...process.env,
			ROUTING_PROVIDER: process.env.ROUTING_PROVIDER || "valhalla",
		},
	},
);
child.on("exit", (code) => process.exit(code ?? 1));
for (const signal of ["SIGINT", "SIGTERM"])
	process.on(signal, () => child.kill(signal));
