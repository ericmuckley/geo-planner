// Offline validation fixtures only. Never imported by the routing application.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { decodeGrid } from "../src/server/coarse-data.server";
import {
	distanceKm,
	estimateGrid,
	gridAttachments,
	gridCellMinutes,
	gridPosition,
} from "../src/server/coarse-grid";

const output = process.argv[2];
assert.ok(
	output && resolve(output).startsWith(`${resolve("data/coarse-quality")}/`),
	"Pass a fresh directory under data/coarse-quality",
);
await mkdir(output);
const artifact = "src/server/data/coarse-grid-v8.json";
const raw = await readFile(artifact);
const artifactSha256 = createHash("sha256").update(raw).digest("hex");
assert.equal(
	artifactSha256,
	"2beb2fb6d9af6e07f37c5ba53acdeca2da1334c31a5fadd1371efd5453134910",
);
const data = JSON.parse(raw.toString());
const grid = decodeGrid(data);
assert.ok(grid.roadLayer && grid.displayLand);
const size = grid.width * grid.height;
const horizons = [360, 600, 720];
const sites = [
	{
		id: "astoria-or",
		lat: 46.1879,
		lon: -123.8313,
		category: "Pacific coast and hills",
	},
	{
		id: "missoula-mt",
		lat: 46.8721,
		lon: -113.994,
		category: "Rocky Mountain valley",
	},
	{
		id: "hays-ks",
		lat: 38.8792,
		lon: -99.3268,
		category: "rural Great Plains",
	},
	{
		id: "duluth-mn",
		lat: 46.7867,
		lon: -92.1005,
		category: "Great Lakes and northern border",
	},
	{
		id: "columbus-oh",
		lat: 39.9612,
		lon: -82.9988,
		category: "inland metropolitan",
	},
	{
		id: "asheville-nc",
		lat: 35.5951,
		lon: -82.5515,
		category: "Appalachian mountains",
	},
	{
		id: "portland-me",
		lat: 43.6591,
		lon: -70.2568,
		category: "Northeast coast and border",
	},
	{
		id: "savannah-ga",
		lat: 32.0809,
		lon: -81.0912,
		category: "Atlantic coastal plain",
	},
];
type Candidate = {
	cell: number;
	point: number[];
	cellMinutes: number;
	score: number;
};
type MeasuredCandidate = Candidate & {
	destination: { lat: number; lon: number };
	pointMinutes: number;
};
function sector(origin: { lat: number; lon: number }, point: number[]) {
	const radians = Math.PI / 180,
		a = origin.lat * radians,
		b = point[1] * radians,
		d = (point[0] - origin.lon) * radians;
	const bearing =
		(Math.atan2(
			Math.sin(d) * Math.cos(b),
			Math.cos(a) * Math.sin(b) - Math.sin(a) * Math.cos(b) * Math.cos(d),
		) /
			radians +
			360) %
		360;
	return Math.floor(bearing / 30);
}
const queries = [];
for (const [siteIndex, site] of sites.entries()) {
	const origin = { lat: site.lat, lon: site.lon };
	// Extra labels are diagnostic candidates outside the public 720-minute horizon.
	const field = estimateGrid(grid, origin, 750);
	const bins = horizons.map(() =>
		Array.from({ length: 12 }, () => [[], []] as Candidate[][]),
	);
	for (let cell = 0; cell < size; cell++) {
		if (!grid.roadLayer.transferDeciseconds[cell] || !grid.displayLand[cell])
			continue;
		const minutes = gridCellMinutes(grid, field.labels, cell);
		for (const [h, horizon] of horizons.entries()) {
			const gap = minutes - horizon;
			if (Math.abs(gap) < 5 || Math.abs(gap) > 20) continue;
			const point = gridPosition(grid, size + cell).map((v) =>
				Number(v.toFixed(5)),
			);
			const list = bins[h][sector(origin, point)][gap < 0 ? 0 : 1];
			list.push({
				cell,
				point,
				cellMinutes: minutes,
				score: Math.abs(Math.abs(gap) - 10),
			});
			list.sort((a, b) => a.score - b.score || a.cell - b.cell);
			if (list.length > 8) list.pop();
		}
	}
	for (const [h, budgetMinutes] of horizons.entries()) {
		const preferred = (siteIndex + h * 4) % 12;
		const sectors = Array.from({ length: 12 }, (_, i) => i).sort((a, b) => {
			const delta = (s: number) =>
				Math.min((s - preferred + 12) % 12, (preferred - s + 12) % 12);
			return delta(a) - delta(b) || a - b;
		});
		let selected:
			| { direction: number; pair: Array<MeasuredCandidate | undefined> }
			| undefined;
		for (const direction of sectors) {
			const pair = bins[h][direction].map((candidates, side) =>
				candidates
					.map((candidate) => {
						const destination = {
							lon: candidate.point[0],
							lat: candidate.point[1],
						};
						const pointMinutes = Math.min(
							...gridAttachments(grid, destination).map(
								(a) => field.labels[a.cell] + a.minutes,
							),
						);
						return { ...candidate, destination, pointMinutes };
					})
					.find(
						(c) =>
							Number.isFinite(c.pointMinutes) &&
							(side === 0
								? c.pointMinutes <= budgetMinutes - 2
								: c.pointMinutes >= budgetMinutes + 2),
					),
			);
			if (pair.every((c) => c !== undefined)) {
				selected = { direction, pair };
				break;
			}
		}
		assert.ok(
			selected,
			`No paired frontier for ${site.id}/${budgetMinutes}; preserve this failure rather than replacing the origin`,
		);
		for (const [side, candidate] of selected.pair.entries()) {
			assert.ok(candidate);
			const destinationCell =
				Math.floor((candidate.destination.lat - grid.bounds[1]) / grid.step) *
					grid.width +
				Math.floor((candidate.destination.lon - grid.bounds[0]) / grid.step);
			assert.equal(
				destinationCell,
				candidate.cell,
				"Quantized frontier point left its selected display cell",
			);
			queries.push({
				id: `${site.id}-${budgetMinutes}-${side === 0 ? "inside" : "outside"}`,
				originId: site.id,
				category: site.category,
				origin,
				budgetMinutes,
				expectedMapReachable: side === 0,
				destination: candidate.destination,
				modelCellMinutes: candidate.cellMinutes,
				modelPointMinutes: candidate.pointMinutes,
				preferredSector: preferred,
				selectedSector: selected.direction,
				straightKm: distanceKm([origin.lon, origin.lat], candidate.point),
				request: {
					coordinates: [[origin.lon, origin.lat], candidate.point],
					instructions: false,
					preference: "fastest",
					radiuses: [350, 350],
					options: { avoid_borders: "all", avoid_features: ["ferries"] },
				},
			});
		}
	}
	console.error(
		`Prepared ${site.id}: ${queries.length} frozen requests so far`,
	);
}
assert.equal(queries.length, 48);
const plan = {
	version: 1,
	model: data.version,
	artifact,
	artifactSha256,
	sites,
	horizons,
	queries,
	reference: {
		endpoint:
			"https://api.heigit.org/openrouteservice/v2/directions/driving-car/geojson",
		method: "POST",
		maximumRequests: 48,
		minimumIntervalMs: 6500,
		timeoutMs: 45000,
		retries: 0,
		paidSpendCapEuro: 0,
		authentication:
			"Existing server-only ORS_API_KEY, never embedded in this plan",
		stopOnStatus: [401, 403, 429],
	},
	scope:
		"Frozen pre-reference frontier probes: eight public non-Southern-California origins, 6/10/12h, one inside/outside pair each. Destinations use existing land-supported Census states, 5–20 model-cell minutes from the horizon; full point attachments must agree on side with a 2-minute margin. Preferred azimuth rotates generically, with deterministic available-sector fallback and cell tie-breaks. These model-conditioned frontier probes are not a random national sample, area accuracy, unseen software inputs, traffic truth or all-origin qualification. No source/service/provider/DB request or API-key read. Routing code never imports these locations.",
};
await writeFile(`${output}/plan.json`, `${JSON.stringify(plan, null, 2)}\n`, {
	flag: "wx",
});
console.log(
	JSON.stringify(
		{
			output,
			artifactSha256,
			origins: sites.length,
			requests: queries.length,
			publicRoutingApiCalls: 0,
		},
		null,
		2,
	),
);
