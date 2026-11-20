import type { useAreaLayer } from "../lib/use-area-layer";
import {
	AreaLayerDataStatus,
	ElevationRangeSlider,
	type ElevationSliderProps,
} from "./area-layer-controls";

type Props = {
	publicLandOnly: boolean;
	onPublicLandOnlyChange: (checked: boolean) => void;
	elevationOnly: boolean;
	onElevationOnlyChange: (checked: boolean) => void;
	elevationSlider: ElevationSliderProps;
	land: ReturnType<typeof useAreaLayer>;
	elevation: ReturnType<typeof useAreaLayer>;
};

export function OutdoorPlaceFilters({
	publicLandOnly,
	onPublicLandOnlyChange,
	elevationOnly,
	onElevationOnlyChange,
	elevationSlider,
	land,
	elevation,
}: Props) {
	return (
		<fieldset className="space-y-2 rounded-lg border border-neutral-200 px-3 pb-3">
			<legend className="px-1 text-xs font-semibold">
				Filter trailheads and campgrounds
			</legend>
			<label className="flex cursor-pointer items-center gap-2 text-sm">
				<input
					type="checkbox"
					checked={publicLandOnly}
					onChange={(event) => onPublicLandOnlyChange(event.target.checked)}
					className="accent-neutral-900"
				/>
				On mapped public land
			</label>
			<label className="flex cursor-pointer items-center gap-2 text-sm">
				<input
					type="checkbox"
					checked={elevationOnly}
					onChange={(event) => onElevationOnlyChange(event.target.checked)}
					className="accent-neutral-900"
				/>
				Within elevation range
			</label>
			{elevationOnly && <ElevationRangeSlider {...elevationSlider} />}
			{publicLandOnly && <AreaLayerDataStatus kind="land" layer={land} />}
			{elevationOnly && (
				<AreaLayerDataStatus kind="elevation" layer={elevation} />
			)}
			{(publicLandOnly || elevationOnly) && (
				<p className="text-xs text-neutral-600">
					Approximate matches from USGS grid cells (~2 km).
				</p>
			)}
		</fieldset>
	);
}
