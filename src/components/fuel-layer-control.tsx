import { Fuel } from "lucide-react";
import {
	fuelAttribution,
	fuelAttributionUrl,
	fuelCatalogUrl,
} from "../lib/fuel-locations";
import type { useFuelLayer } from "../lib/use-fuel-layer";

export function FuelLayerControl({
	layer,
}: {
	layer: ReturnType<typeof useFuelLayer>;
}) {
	const count = layer.locations?.features.length;
	return (
		<section
			aria-label="Fuel stops"
			className="space-y-2 border-t border-[var(--line)] p-4"
		>
			<label className="flex cursor-pointer items-center gap-2 text-sm font-semibold">
				<Fuel size={16} aria-hidden="true" />
				Fuel stops
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
							? "Fuel stops could not load. Turn the layer off and back on to retry."
							: !layer.sourceDate
								? "Loading fuel stops…"
								: count === undefined
									? "Waiting for an estimated area."
									: count === 0
										? "No mapped fuel stops in this area."
										: `${count.toLocaleString()} mapped fuel ${count === 1 ? "stop" : "stops"} in this area.`}
					</output>
					{layer.sourceDate && (
						<p className="text-xs text-[var(--sea-ink-soft)]">
							<a href={fuelAttributionUrl} className="underline">
								{fuelAttribution}
							</a>
							{" · "}
							{layer.sourceDate}
							{" · "}
							<a href={fuelCatalogUrl} download className="underline">
								Download data
							</a>
						</p>
					)}
				</>
			)}
		</section>
	);
}
