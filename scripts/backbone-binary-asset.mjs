import { readFileSync } from "node:fs";

export const backboneAssetId = "#geo-backbone-binary";
const resolvedId = "\0geo-backbone-binary";

/**
 * Emit one server-side binary asset through Nitro's final bundler.
 * @param {string} path
 * @returns {import("rolldown").Plugin}
 */
export function backboneBinaryAsset(path) {
	let reference;
	return {
		name: "geo-backbone-binary",
		resolveId(id) {
			if (id === backboneAssetId) return resolvedId;
		},
		load(id) {
			if (id !== resolvedId) return;
			reference = this.emitFile({
				type: "asset",
				fileName: "server-data/backbone.bin",
				source: readFileSync(path),
			});
			return `export default import.meta.ROLLUP_FILE_URL_${reference};`;
		},
		resolveFileUrl({ referenceId, relativePath }) {
			if (referenceId === reference)
				return `new URL(${JSON.stringify(relativePath)}, import.meta.url)`;
		},
	};
}
