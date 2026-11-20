import { Fuel, Signpost, Tent } from "lucide-react";
import type { ReactNode } from "react";
import {
	type OutdoorPlaceSelection,
	type PlaceKind,
	placeAttribution,
	placeAttributionUrl,
	placeKinds,
	placeLayers,
} from "../lib/place-locations";
import type { usePlaceLayer } from "../lib/use-place-layer";
import { OutdoorPlaceResults } from "./outdoor-place-results";

const icons = { fuel: Fuel, trailheads: Signpost, campgrounds: Tent };
type PlaceLayers = Record<PlaceKind, ReturnType<typeof usePlaceLayer>>;

export function PlaceDataAttribution({ layers }: { layers: PlaceLayers }) {
	const dates = new Set(
		placeKinds.flatMap((kind) => {
			const { enabled, sourceDate } = layers[kind];
			return enabled && sourceDate ? [sourceDate] : [];
		}),
	);
	if (dates.size === 0) return null;
	return (
		<footer className="shrink-0 border-t border-neutral-200 px-4 py-2 text-xs text-neutral-600">
			<a href={placeAttributionUrl} className="underline">
				{placeAttribution}
			</a>
			{" · "}
			{Array.from(dates).join(" · ")}
		</footer>
	);
}

export function PlaceLayerControls({
	layers,
	onLayerChange,
	outdoorFilters,
	filtersActive,
	filtersPending,
	onOutdoorPlaceSelect,
}: {
	layers: PlaceLayers;
	onLayerChange: (kind: PlaceKind, checked: boolean) => void;
	outdoorFilters?: ReactNode;
	filtersActive: boolean;
	filtersPending: boolean;
	onOutdoorPlaceSelect: (selection: OutdoorPlaceSelection) => void;
}) {
	return (
		<section
			aria-label="Map layers"
			className="space-y-3 border-t border-neutral-200 p-4"
		>
			{placeKinds.map((kind) => {
				const layer = layers[kind];
				const { label, singular } = placeLayers[kind];
				const plural = label.toLowerCase();
				const Icon = icons[kind];
				const count = layer.locations?.features.length;
				const filtered = kind !== "fuel" && filtersActive;
				const countSuffix = !filtered
					? "in this area"
					: count === 1
						? "matches the filters"
						: "match the filters";
				return (
					<div className="space-y-2" key={kind}>
						<label className="flex cursor-pointer items-center gap-2 text-sm font-semibold">
							<Icon size={16} className="text-neutral-600" aria-hidden="true" />
							{label}
							<input
								type="checkbox"
								checked={layer.enabled}
								onChange={(event) => onLayerChange(kind, event.target.checked)}
								className="ml-auto accent-neutral-900"
							/>
						</label>
						{layer.enabled && (
							<>
								<output className="block text-xs" aria-live="polite">
									{layer.loadError
										? `${label} could not load. Turn the layer off and back on to retry.`
										: !layer.sourceDate
											? `Loading ${plural}…`
											: count === undefined
												? filtered && filtersPending
													? "Waiting for place filters."
													: "Waiting for an estimated area."
												: count === 0
													? `No mapped ${plural} ${filtered ? "match the filters" : "in this area"}.`
													: `${count.toLocaleString()} mapped ${count === 1 ? singular : plural} ${countSuffix}.`}
								</output>
								{kind !== "fuel" && layer.locations && (count ?? 0) > 0 && (
									<OutdoorPlaceResults
										kind={kind}
										locations={layer.locations}
										onSelect={onOutdoorPlaceSelect}
									/>
								)}
							</>
						)}
					</div>
				);
			})}
			{outdoorFilters}
		</section>
	);
}
