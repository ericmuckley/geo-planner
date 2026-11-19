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

export function PlaceLayerControls({
	layers,
	outdoorFilters,
	filtersActive,
	filtersPending,
	onOutdoorPlaceSelect,
}: {
	layers: Record<PlaceKind, ReturnType<typeof usePlaceLayer>>;
	outdoorFilters?: ReactNode;
	filtersActive: boolean;
	filtersPending: boolean;
	onOutdoorPlaceSelect: (selection: OutdoorPlaceSelection) => void;
}) {
	return (
		<section
			aria-label="Map layers"
			className="space-y-3 border-t border-[var(--line)] p-4"
		>
			{placeKinds.map((kind) => {
				const layer = layers[kind];
				const { label, singular, url, color } = placeLayers[kind];
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
							<Icon size={16} color={color} aria-hidden="true" />
							{label}
							<input
								type="checkbox"
								checked={layer.enabled}
								onChange={(event) => layer.setEnabled(event.target.checked)}
								className="ml-auto accent-[var(--lagoon-deep)]"
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
								{layer.sourceDate && (
									<p className="text-xs text-[var(--sea-ink-soft)]">
										<a href={placeAttributionUrl} className="underline">
											{placeAttribution}
										</a>
										{" · "}
										{layer.sourceDate}
										{" · "}
										<a
											href={url}
											download
											className="underline"
											aria-label={`Download ${plural} data`}
										>
											Download data
										</a>
									</p>
								)}
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
