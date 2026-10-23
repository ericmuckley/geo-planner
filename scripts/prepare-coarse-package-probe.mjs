// Prepare an isolated local package check; never switch the active app/model.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import {
	copyFile,
	cp,
	mkdir,
	readFile,
	symlink,
	writeFile,
} from "node:fs/promises";
import { join, resolve } from "node:path";

const [artifact, output] = process.argv.slice(2);
assert.ok(
	artifact && output,
	"Pass a candidate artifact and a fresh probe directory",
);
assert.ok(resolve(output).startsWith(`${resolve("data/coarse-quality")}/`));
await mkdir(output); // A new directory preserves earlier package checks.
await cp("src", join(output, "src"), {
	recursive: true,
	filter: (path) =>
		!path.endsWith(".test.ts") && resolve(path) !== resolve("src/server/data"),
});
await mkdir(join(output, "src/server/data"));
const raw = await readFile(artifact);
await writeFile(
	join(output, "src/server/data/coarse-grid-candidate.json"),
	raw,
	{ flag: "wx" },
);
for (const path of [
	"package.json",
	"package-lock.json",
	"tsconfig.json",
	"vite.config.ts",
])
	await copyFile(path, join(output, path));
await symlink(resolve("node_modules"), join(output, "node_modules"), "dir");
const route = join(output, "src/server/coarse-estimate.server.ts");
const original = await readFile(route, "utf8");
assert.ok(original.includes("./data/coarse-grid-v5.json"));
assert.ok(original.includes('"coarse-road-grid-v5"'));
await writeFile(
	route,
	original
		.replace("./data/coarse-grid-v5.json", "./data/coarse-grid-candidate.json")
		.replace('"coarse-road-grid-v5"', '"coarse-road-grid-candidate"'),
);
const record = {
	artifact,
	artifactSha256: createHash("sha256").update(raw).digest("hex"),
	output,
	expectedEngine: "coarse-road-grid-candidate",
	scope:
		"Isolated local package/handler probe only. Copies project source/config plus this artifact, symlinks existing node_modules, and changes only the copied estimator import/engine label. No env files, credentials, raw sources, deployment or active model change. Candidate source notices/UI wording still require review before activation.",
};
await writeFile(
	join(output, "probe.json"),
	`${JSON.stringify(record, null, 2)}\n`,
	{ flag: "wx" },
);
console.log(JSON.stringify(record, null, 2));
