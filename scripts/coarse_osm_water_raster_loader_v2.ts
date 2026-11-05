/** Offline packet reader; observations carry uncertainty and imply no land policy. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { lstat, readFile } from "node:fs/promises";
import path from "node:path";
import { gunzipSync } from "node:zlib";

const sha = (raw: Uint8Array) => createHash("sha256").update(raw).digest("hex");
const integer = (value: unknown, low: number, high: number): value is number =>
	typeof value === "number" &&
	Number.isSafeInteger(value) &&
	value >= low &&
	value <= high;
const digest = (value: unknown): value is string =>
	typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
const object = (value: unknown): Record<string, unknown> => {
	assert.ok(
		value !== null && typeof value === "object" && !Array.isArray(value),
	);
	return value as Record<string, unknown>;
};
const popcount = (byte: number) => {
	const a = byte - ((byte >>> 1) & 0x55);
	const b = (a & 0x33) + ((a >>> 2) & 0x33);
	return (b + (b >>> 4)) & 0x0f;
};

export type RasterCoordinate = readonly [number, number];
export type RasterGrid = Readonly<{
	xE7: number;
	yE7: number;
	stepE7: number;
	columns: number;
	rows: number;
	cells: number;
	bitOrder: "row-major-lsb-first";
}>;

function validateGrid(raw: unknown): RasterGrid {
	const grid = object(raw);
	assert.ok(integer(grid.xE7, -1800000000, 1800000000));
	assert.ok(integer(grid.yE7, -900000000, 900000000));
	assert.ok(integer(grid.stepE7, 1, 3600000000));
	assert.ok(
		integer(grid.columns, 1, 61360000) && integer(grid.rows, 1, 61360000),
	);
	assert.ok(
		integer(grid.cells, 1, 61360000) && grid.cells === grid.columns * grid.rows,
	);
	assert.ok(grid.xE7 + grid.columns * grid.stepE7 <= 1800000000);
	assert.ok(grid.yE7 + grid.rows * grid.stepE7 <= 900000000);
	assert.equal(grid.bitOrder, "row-major-lsb-first");
	return Object.freeze({
		xE7: grid.xE7,
		yE7: grid.yE7,
		stepE7: grid.stepE7,
		columns: grid.columns,
		rows: grid.rows,
		cells: grid.cells,
		bitOrder: "row-major-lsb-first",
	});
}

function incompleteFeatures(raw: unknown) {
	assert.ok(Array.isArray(raw) && raw.length <= 1000);
	const ids = new Set<string>();
	return Object.freeze(
		raw.map((value) => {
			const row = object(value);
			assert.ok(
				(row.kind === 1 || row.kind === 2) &&
					integer(row.id, 1, Number.MAX_SAFE_INTEGER),
			);
			assert.ok(
				row.rawRelationType === null ||
					(typeof row.rawRelationType === "string" &&
						row.rawRelationType.length <= 255),
			);
			const key = `${row.kind}/${row.id}`;
			assert.ok(!ids.has(key));
			ids.add(key);
			const members = (values: unknown) => {
				assert.ok(Array.isArray(values) && values.length <= 10000);
				assert.ok(
					values.every((v) => integer(v, 1, Number.MAX_SAFE_INTEGER)) &&
						new Set(values).size === values.length,
				);
				return Object.freeze(values as number[]);
			};
			return Object.freeze({
				kind: row.kind,
				id: row.id,
				rawRelationType: row.rawRelationType,
				missingSourceWayIds: members(row.missingSourceWayIds),
				missingSourceRelationIds: members(row.missingSourceRelationIds),
			});
		}),
	);
}

async function boundedFile(filename: string, maximum: number) {
	const before = await lstat(filename);
	assert.ok(
		before.isFile() &&
			!before.isSymbolicLink() &&
			before.size > 0 &&
			before.size <= maximum,
	);
	const raw = await readFile(filename);
	const after = await lstat(filename);
	assert.ok(after.isFile() && !after.isSymbolicLink());
	assert.deepEqual(
		[after.dev, after.ino, after.size, after.mtimeMs, after.ctimeMs],
		[before.dev, before.ino, before.size, before.mtimeMs, before.ctimeMs],
	);
	assert.equal(raw.length, before.size);
	return raw;
}

async function plane(root: string, raw: unknown, name: string, cells: number) {
	const record = object(raw),
		bytes = Math.ceil(cells / 8);
	assert.equal(record.file, `${name}.bits.gz`);
	assert.equal(record.rawFile, `${name}.bits`);
	assert.equal(record.rawBytes, bytes);
	assert.ok(digest(record.rawSha256) && digest(record.compressedSha256));
	assert.ok(integer(record.compressedBytes, 1, bytes + 1048576));
	assert.ok(integer(record.setCells, 0, cells));
	const compressed = await boundedFile(
		path.join(root, record.file as string),
		bytes + 1048576,
	);
	assert.equal(compressed.length, record.compressedBytes);
	assert.equal(sha(compressed), record.compressedSha256);
	const inflated = gunzipSync(compressed, { maxOutputLength: bytes });
	assert.equal(inflated.length, bytes);
	assert.equal(sha(inflated), record.rawSha256);
	if (cells % 8) assert.equal(inflated[bytes - 1] >>> (cells % 8), 0);
	let set = 0;
	for (const value of inflated) set += popcount(value);
	assert.equal(set, record.setCells);
	// Own only the declared bytes; small zlib outputs can share a larger buffer.
	const data = Uint8Array.from(inflated);
	assert.equal(data.buffer.byteLength, bytes);
	return {
		data,
		compressedBytes: compressed.length,
		setCells: set,
		rawSha256: record.rawSha256,
	};
}

/** Exact floor of a Number's canonical decimal value on an E7 grid. */
function cellAxis(value: number, origin: number, step: number) {
	const text = String(value),
		negative = text.startsWith("-");
	const [mantissa, exponentText = "0"] = (negative ? text.slice(1) : text)
		.toLowerCase()
		.split("e");
	const [whole, fraction = ""] = mantissa.split(".");
	const power = 7 + Number(exponentText) - fraction.length;
	let numerator = BigInt(whole + fraction) * (negative ? -1n : 1n),
		denominator = 1n;
	if (power >= 0) numerator *= 10n ** BigInt(power);
	else denominator = 10n ** BigInt(-power);
	const delta = numerator - BigInt(origin) * denominator,
		divisor = BigInt(step) * denominator;
	return Number(
		delta >= 0n ? delta / divisor : -((-delta + divisor - 1n) / divisor),
	);
}

export async function loadWaterRasterV2(root: string, pin: string) {
	const began = performance.now();
	assert.ok(digest(pin));
	const bytes = await boundedFile(path.join(root, "manifest.json"), 1048576);
	assert.equal(sha(bytes), pin);
	const manifest = object(JSON.parse(bytes.toString("utf8")));
	assert.equal(
		manifest.format,
		"exact-water-centers-and-source-uncertainty-v1",
	);
	assert.ok(
		typeof manifest.semantics === "string" && manifest.semantics.length <= 4096,
	);
	const grid = validateGrid(manifest.grid),
		source = object(manifest.sourceCounts);
	for (const field of [
		"features",
		"rings",
		"points",
		"excludedFeatures",
		"knownExcludedBounds",
	])
		assert.ok(integer(source[field], 0, 500000000));
	assert.ok(
		(source.knownExcludedBounds as number) <=
			(source.excludedFeatures as number),
	);
	const incomplete = incompleteFeatures(manifest.sourceIncompleteFeatures);
	assert.equal(
		manifest.sourceGeometryCompletelyBounded,
		incomplete.length === 0,
	);
	assert.ok(incomplete.length <= (source.excludedFeatures as number));
	const records = object(manifest.planes);
	const water = await plane(root, records.water, "water-center", grid.cells);
	const uncertain = await plane(
		root,
		records.uncertainty,
		"source-uncertainty",
		grid.cells,
	);
	const backingBytes =
		water.data.buffer.byteLength + uncertain.data.buffer.byteLength;
	assert.equal(backingBytes, 2 * Math.ceil(grid.cells / 8));
	const cellFlags = (column: number, row: number): number | null => {
		assert.ok(Number.isSafeInteger(column) && Number.isSafeInteger(row));
		if (column < 0 || row < 0 || column >= grid.columns || row >= grid.rows)
			return null;
		const rank = row * grid.columns + column,
			mask = 1 << (rank % 8);
		return (
			(water.data[rank >>> 3] & mask ? 1 : 0) |
			(uncertain.data[rank >>> 3] & mask ? 2 : 0)
		);
	};
	const uncertaintyTouchesE7Box = (
		x1: number,
		y1: number,
		x2: number,
		y2: number,
	) => {
		assert.ok(
			[x1, y1, x2, y2].every(Number.isSafeInteger) && x1 <= x2 && y1 <= y2,
		);
		if (
			x1 <= grid.xE7 ||
			y1 <= grid.yE7 ||
			x2 >= grid.xE7 + grid.columns * grid.stepE7 ||
			y2 >= grid.yE7 + grid.rows * grid.stepE7
		)
			return true;
		const firstX = Math.max(0, Math.ceil((x1 - grid.xE7) / grid.stepE7) - 1),
			lastX = Math.min(
				grid.columns - 1,
				Math.floor((x2 - grid.xE7) / grid.stepE7),
			);
		const firstY = Math.max(0, Math.ceil((y1 - grid.yE7) / grid.stepE7) - 1),
			lastY = Math.min(
				grid.rows - 1,
				Math.floor((y2 - grid.yE7) / grid.stepE7),
			);
		for (let row = firstY; row <= lastY; row++) {
			const a = row * grid.columns + firstX,
				b = row * grid.columns + lastX,
				first = a >>> 3,
				last = b >>> 3;
			if (first === last) {
				if (
					uncertain.data[first] &
					((255 << (a % 8)) & (255 >>> (7 - (b % 8))))
				)
					return true;
				continue;
			}
			if (uncertain.data[first] & (255 << (a % 8))) return true;
			for (let index = first + 1; index < last; index++)
				if (uncertain.data[index]) return true;
			if (uncertain.data[last] & (255 >>> (7 - (b % 8)))) return true;
		}
		return false;
	};
	const lookup = (coordinate: RasterCoordinate) => {
		assert.ok(
			Array.isArray(coordinate) &&
				coordinate.length === 2 &&
				coordinate.every((v) => typeof v === "number" && Number.isFinite(v)),
		);
		assert.ok(Math.abs(coordinate[0]) <= 180 && Math.abs(coordinate[1]) <= 90);
		const column = cellAxis(coordinate[0], grid.xE7, grid.stepE7),
			row = cellAxis(coordinate[1], grid.yE7, grid.stepE7);
		const status = {
			sourceGeometryCompletelyBounded: incomplete.length === 0,
			sourceIncompleteFeatureCount: incomplete.length,
		};
		if (column < 0 || row < 0 || column >= grid.columns || row >= grid.rows)
			return { kind: "outside-grid" as const, ...status };
		const rank = row * grid.columns + column,
			mask = 1 << (rank % 8);
		return {
			kind: "cell" as const,
			column,
			row,
			waterAtCenter: Boolean(water.data[rank >>> 3] & mask),
			sourceUncertainty: Boolean(uncertain.data[rank >>> 3] & mask),
			centerE7: [
				grid.xE7 + (column + 0.5) * grid.stepE7,
				grid.yE7 + (row + 0.5) * grid.stepE7,
			] as const,
			...status,
		};
	};
	return {
		grid,
		lookup,
		cellFlags,
		uncertaintyTouchesE7Box,
		sourceIncompleteFeatures: incomplete,
		sourceCounts: Object.freeze({ ...source }),
		backingBytes,
		compressedBytes: water.compressedBytes + uncertain.compressedBytes,
		manifestBytes: bytes.length,
		planeFingerprints: Object.freeze({
			water: water.rawSha256,
			uncertainty: uncertain.rawSha256,
		}),
		setCells: Object.freeze({
			water: water.setCells,
			uncertainty: uncertain.setCells,
		}),
		loadMs: performance.now() - began,
	};
}
