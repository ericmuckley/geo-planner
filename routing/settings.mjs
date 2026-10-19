import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const root = fileURLToPath(new URL("../", import.meta.url));
export const dataDir = resolve(
	root,
	process.env.VALHALLA_DATA_DIR || "data/valhalla-v2",
);
export const sourceDir = resolve(
	root,
	process.env.VALHALLA_SOURCE_DIR || "data/valhalla/sources",
);
export const manifestPath = resolve(
	root,
	process.env.VALHALLA_MANIFEST || "routing/profiles/california-baja-v2.json",
);

async function readManifest(path, parents = new Set()) {
	if (parents.has(path))
		throw new Error("Circular routing manifest inheritance");
	parents.add(path);
	const { extends: parent, ...current } = JSON.parse(
		await readFile(path, "utf8"),
	);
	return parent
		? {
				...(await readManifest(resolve(dirname(path), parent), parents)),
				...current,
			}
		: current;
}

export const manifest = await readManifest(manifestPath);
