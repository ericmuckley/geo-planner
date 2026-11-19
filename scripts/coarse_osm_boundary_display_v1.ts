/** Add paid boundary coverage between sealed local fill and contour construction. */
import {
	addPaidBoundaryCoverage,
	type BoundaryCoverageWitness,
} from "./coarse_osm_boundary_coverage_v1.ts";
import { reusedContextDisplay } from "./coarse_osm_reused_display_v2.ts";

type Inputs = Parameters<typeof reusedContextDisplay>;
type Options = NonNullable<Inputs[6]> & {
	beforeBoundary?: NonNullable<Inputs[6]>["probe"];
	boundaryWitness?: (value: BoundaryCoverageWitness) => void;
};

export function boundaryContextDisplay(
	graph: Inputs[0],
	geometry: Inputs[1],
	contexts: Inputs[2],
	geography: Inputs[3],
	connection: Inputs[4],
	starts: Inputs[5],
	options: Options = {},
	diagnostic = false,
) {
	let horizon = -1;
	let boundary: ReturnType<typeof addPaidBoundaryCoverage> | undefined;
	const result = reusedContextDisplay(
		graph,
		geometry,
		contexts,
		geography,
		connection,
		starts,
		{
			...options,
			beforeSeed: (field) => {
				horizon = Math.floor(field.horizonTicks / 8);
				options.beforeSeed?.(field);
			},
			probe: (grid) => {
				options.beforeBoundary?.(grid);
				boundary = addPaidBoundaryCoverage(
					geography,
					grid,
					horizon,
					options.check,
					options.boundaryWitness,
				);
				options.probe?.(grid);
			},
		},
		diagnostic,
	);
	if (!boundary) throw new Error("Boundary display probe did not run");
	return {
		...result,
		boundary,
		stats: {
			...result.stats,
			roadOnlyCells: result.stats.roadOnlyCells - boundary.addedCells,
			paidBoundaryCells: boundary.addedCells,
		},
	};
}
