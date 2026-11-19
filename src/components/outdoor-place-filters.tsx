import type { useAreaLayer } from "../lib/use-area-layer";
import {
	AreaLayerDataStatus,
	type ElevationInputProps,
	MinimumElevationInput,
} from "./area-layer-controls";

type Props = {
	publicLandOnly: boolean;
	onPublicLandOnlyChange: (checked: boolean) => void;
	elevationOnly: boolean;
	onElevationOnlyChange: (checked: boolean) => void;
	minimumElevation: ElevationInputProps;
	land: ReturnType<typeof useAreaLayer>;
	elevation: ReturnType<typeof useAreaLayer>;
};

export function OutdoorPlaceFilters({
	publicLandOnly,
	onPublicLandOnlyChange,
	elevationOnly,
	onElevationOnlyChange,
	minimumElevation,
	land,
	elevation,
}: Props) {
	return (
		<fieldset className="space-y-2 rounded-lg border border-[var(--line)] px-3 pb-3">
			<legend className="px-1 text-xs font-semibold">
				Filter trailheads and campgrounds
			</legend>
			<label className="flex cursor-pointer items-center gap-2 text-sm">
				<input
					type="checkbox"
					checked={publicLandOnly}
					onChange={(event) => onPublicLandOnlyChange(event.target.checked)}
					className="accent-[var(--lagoon-deep)]"
				/>
				On mapped public land
			</label>
			<label className="flex cursor-pointer items-center gap-2 text-sm">
				<input
					type="checkbox"
					checked={elevationOnly}
					onChange={(event) => onElevationOnlyChange(event.target.checked)}
					className="accent-[var(--lagoon-deep)]"
				/>
				At or above minimum elevation
			</label>
			{elevationOnly && <MinimumElevationInput {...minimumElevation} />}
			{publicLandOnly && !land.grid && (
				<AreaLayerDataStatus kind="land" layer={land} />
			)}
			{elevationOnly && !elevation.grid && (
				<AreaLayerDataStatus kind="elevation" layer={elevation} />
			)}
			{(publicLandOnly || elevationOnly) && (
				<p className="text-xs text-[var(--sea-ink-soft)]">
					Approximate matches from USGS grid cells (~2 km).
				</p>
			)}
		</fieldset>
	);
}
