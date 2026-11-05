/** Fast cell flags away from decimal boundaries; exact reader handles every tie. */
import type {
	loadWaterRasterV2,
	RasterCoordinate,
} from "./coarse_osm_water_raster_loader_v2.ts";

type Packet = Pick<
	Awaited<ReturnType<typeof loadWaterRasterV2>>,
	"grid" | "lookup"
> &
	Partial<Pick<Awaited<ReturnType<typeof loadWaterRasterV2>>, "cellFlags">>;
function fastIndex(value: number, origin: number, step: number) {
	const scaled = value * 1e7,
		delta = scaled - origin;
	const index = Math.floor(delta / step),
		offset = delta - index * step;
	// Number's shortest decimal is within its rounding interval. This bound
	// also covers multiplication, subtraction, division and residual rounding.
	const guard =
		64 * Number.EPSILON * (Math.abs(scaled) + Math.abs(origin) + step);
	return offset <= guard || step - offset <= guard ? null : index;
}

export function waterCellFlags(
	packet: Packet,
	point: RasterCoordinate,
): number | null {
	if (
		packet.cellFlags &&
		point.length === 2 &&
		Number.isFinite(point[0]) &&
		Number.isFinite(point[1]) &&
		Math.abs(point[0]) <= 180 &&
		Math.abs(point[1]) <= 90
	) {
		const { grid } = packet;
		const column = fastIndex(point[0], grid.xE7, grid.stepE7),
			row = fastIndex(point[1], grid.yE7, grid.stepE7);
		if (column !== null && row !== null) return packet.cellFlags(column, row);
	}
	const cell = packet.lookup(point);
	return cell.kind === "outside-grid"
		? null
		: (cell.waterAtCenter ? 1 : 0) | (cell.sourceUncertainty ? 2 : 0);
}
