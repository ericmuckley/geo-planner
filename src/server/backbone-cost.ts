// Isolated cost policy; sealed routing/data readers and production stay unchanged.
import type { Origin } from "../lib/reachability";
import {
	type Backbone,
	cellArcs,
	interpolate,
	nodePoint,
	type Point,
	pointCell,
	pointCells,
	project,
	sourceMinutes,
	sourceSegments,
} from "./backbone-geometry";
import { landConnection } from "./coarse-geography";
import {
	distanceKm,
	type GridData,
	gridAttachments,
	type RoadVisits,
} from "./coarse-grid";

export const sourceRoadTimeFactor = 1.1;
export type BaseRoadProof = {
	key: number;
	roadKm: number;
	localKm: number;
	speedKph: number;
	connectorSpeedKph: number;
	deciseconds: number;
	kind: string;
};
const priced = new WeakSet<Backbone>();
const rounded = (minutes: number) => Math.ceil(minutes * 600) / 600;
const size = (model: Backbone) => model.base.width * model.base.height;
type Access = {
	arc: number;
	point: Point;
	km: number;
	localMinutes: number;
	localKm: number;
};
type Seed = { node: number; minutes: number };

export function baseRoadPrice(proof: BaseRoadProof, factor: number) {
	if (
		!(
			proof.roadKm > 0 &&
			proof.localKm >= 0 &&
			proof.speedKph > 0 &&
			factor >= 1
		) ||
		![proof.roadKm, proof.localKm, proof.speedKph, factor].every(
			Number.isFinite,
		) ||
		!["natural-earth", "census"].includes(proof.kind) ||
		proof.connectorSpeedKph !== (proof.kind === "natural-earth" ? 55 : 25)
	)
		throw new RangeError("Invalid road cost components");
	const price = Math.max(
		1,
		Math.ceil(
			((factor * proof.roadKm) / proof.speedKph +
				proof.localKm / proof.connectorSpeedKph) *
				36000,
		),
	);
	if (price > 65535)
		throw new RangeError("Road price exceeds packed word range");
	return price;
}

export function validateRoadCosts(model: Backbone, proofs: BaseRoadProof[]) {
	const { base, graph } = model;
	if (
		base.roadLayer ||
		base.supplementalRoadVisits ||
		!base.roadDeciseconds ||
		base.localSpeedKph !== 25
	)
		throw new RangeError("Expected the unchanged kept base");
	let maximumArcRounding = 0;
	for (let arc = 0; arc < graph.arcMinutes.length; arc++) {
		const road = (graph.arcRoadKm[arc] / graph.arcSpeedKph[arc]) * 60;
		const remainder = graph.arcMinutes[arc] - road;
		if (
			!(
				road > 0 &&
				Number.isFinite(road) &&
				remainder >= -1e-8 &&
				remainder <= 1 / 600 + 1e-8
			)
		)
			throw new RangeError("Source road/rounding costs do not reproduce");
		maximumArcRounding = Math.max(maximumArcRounding, remainder);
	}
	let previous = -1;
	for (const proof of proofs) {
		if (
			!Number.isSafeInteger(proof.key) ||
			proof.key <= previous ||
			proof.key >= base.roadDeciseconds.length ||
			base.roadDeciseconds[proof.key] !== proof.deciseconds ||
			baseRoadPrice(proof, 1) !== proof.deciseconds
		)
			throw new RangeError("Base source/connector costs do not reproduce");
		// Check candidate range before changing any model buffer.
		baseRoadPrice(proof, sourceRoadTimeFactor);
		previous = proof.key;
	}
	let links = 0;
	for (const time of base.roadDeciseconds) if (time) links++;
	if (links !== proofs.length)
		throw new RangeError("Base road proof coverage differs");
	return {
		sourceArcs: graph.arcMinutes.length,
		baseLinks: links,
		roadVisits: base.roadVisits?.size ?? 0,
		maximumArcRounding,
	};
}

export function bufferedRoadVisits(
	visits: RoadVisits | undefined,
	factor = sourceRoadTimeFactor,
): RoadVisits | undefined {
	if (!(factor >= 1 && Number.isFinite(factor)))
		throw new RangeError("Invalid road-time factor");
	if (!visits || factor === 1) return visits;
	return {
		size: visits.size,
		get(cell) {
			const visit = visits.get(cell);
			return visit
				? { ...visit, speedKph: visit.speedKph / factor }
				: undefined;
		},
		*[Symbol.iterator]() {
			for (const [cell, visit] of visits)
				yield [cell, { ...visit, speedKph: visit.speedKph / factor }] as [
					number,
					typeof visit,
				];
		},
	};
}

export function attachRoadTimePolicy(base: GridData) {
	base.roadVisits = bufferedRoadVisits(base.roadVisits);
}

export function repriceRoadCosts(model: Backbone, proofs: BaseRoadProof[]) {
	if (priced.has(model)) throw new Error("Road costs already repriced");
	const reproduction = validateRoadCosts(model, proofs);
	const times = model.base.roadDeciseconds;
	if (!times) throw new Error("Base road costs are missing");
	for (let arc = 0; arc < model.graph.arcMinutes.length; arc++)
		model.graph.arcMinutes[arc] +=
			(((sourceRoadTimeFactor - 1) * model.graph.arcRoadKm[arc]) /
				model.graph.arcSpeedKph[arc]) *
			60;
	for (const proof of proofs)
		times[proof.key] = baseRoadPrice(proof, sourceRoadTimeFactor);
	attachRoadTimePolicy(model.base);
	priced.add(model);
	return reproduction;
}

// Independent attachment replay below mirrors the frozen enumeration but does
// no label/queue search. Its inputs are the already-accepted saved endpoints.
function roadAccesses(model: Backbone, point: Point): Access[] {
	const { base, graph } = model;
	const own = pointCell(base, point),
		x = own % base.width,
		y = Math.floor(own / base.width);
	const cells = new Set<number>();
	for (let dy = -1; dy <= 1; dy++)
		for (let dx = -1; dx <= 1; dx++)
			if (
				x + dx >= 0 &&
				x + dx < base.width &&
				y + dy >= 0 &&
				y + dy < base.height
			)
				cells.add((y + dy) * base.width + x + dx);
	const arcs = new Set<number>();
	for (const cell of cells)
		for (const arc of cellArcs(graph, cell)) arcs.add(arc);
	const result: Access[] = [];
	for (const arc of [...arcs].sort((a, b) => a - b)) {
		const seen = new Set<string>();
		for (const segment of sourceSegments(graph, arc)) {
			for (const t of new Set([0, project(point, segment.a, segment.b), 1])) {
				const projected = interpolate(segment.a, segment.b, t);
				const km = segment.startKm + (segment.endKm - segment.startKm) * t;
				const key = `${km}/${projected[0]}/${projected[1]}`;
				if (
					seen.has(key) ||
					!pointCells(base, projected).some((cell) => cells.has(cell))
				)
					continue;
				seen.add(key);
				const localKm = distanceKm(point, projected);
				if (landConnection(base, point, projected, 1 / Math.max(localKm, 1)))
					result.push({
						arc,
						point: projected,
						km,
						localKm,
						localMinutes: (localKm / 25) * 60,
					});
			}
		}
	}
	return result;
}

export function replayCostAttachments(model: Backbone, origin: Origin) {
	const point: Point = [origin.lon, origin.lat];
	if (!point.every(Number.isFinite) || pointCell(model.base, point) < 0)
		throw new RangeError("Invalid saved endpoint");
	const { base, graph } = model;
	const best = new Map<number, Seed>();
	const add = (seed: Seed) => {
		if (seed.minutes < (best.get(seed.node)?.minutes ?? Infinity))
			best.set(seed.node, seed);
	};
	for (const seed of gridAttachments(base, origin))
		add({ node: seed.cell, minutes: seed.minutes });
	const accesses = roadAccesses(model, point);
	for (const access of accesses)
		for (const [node, km] of [
			[graph.arcFrom[access.arc], access.km],
			[graph.arcTo[access.arc], graph.arcRoadKm[access.arc] - access.km],
		])
			add({
				node: size(model) + node,
				minutes: rounded(
					access.localMinutes +
						sourceMinutes(
							graph,
							access.arc,
							km,
							access.point,
							nodePoint(graph, node),
						),
				),
			});
	return {
		point,
		seeds: [...best.values()].sort(
			(a, b) => a.minutes - b.minutes || a.node - b.node,
		),
		accesses,
	};
}
