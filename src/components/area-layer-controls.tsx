import { Map as MapIcon, Mountain } from "lucide-react";
import type { ReactNode } from "react";
import { type AreaLayerKind, areaLayers } from "../lib/area-layers";
import type { useAreaLayer } from "../lib/use-area-layer";

const icons = { land: MapIcon, elevation: Mountain };
type Layer = ReturnType<typeof useAreaLayer>;

function AreaLayerControl({
	kind,
	layer,
	children,
}: {
	kind: AreaLayerKind;
	layer: Layer;
	children?: ReactNode;
}) {
	const { label, color, attribution, attributionUrl } = areaLayers[kind];
	const Icon = icons[kind];
	return (
		<div className="space-y-2">
			<label className="flex cursor-pointer items-center gap-2 text-sm font-semibold">
				<Icon size={16} color={`rgb(${color.join(" ")})`} aria-hidden="true" />
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
					{children}
					{layer.grid ? (
						<p className="text-xs text-[var(--sea-ink-soft)]">
							<a href={attributionUrl} className="underline">
								{attribution}
							</a>
							{" · Coarse grid (~2 km)"}
						</p>
					) : (
						<output className="block text-xs" aria-live="polite">
							{layer.loadError
								? "Layer could not load. Turn it off and back on to retry."
								: "Loading layer…"}
						</output>
					)}
				</>
			)}
		</div>
	);
}

export function AreaLayerControls({
	land,
	elevation,
	elevationDraft,
	validElevation,
	onElevationChange,
}: {
	land: Layer;
	elevation: Layer;
	elevationDraft: string;
	validElevation: boolean;
	onElevationChange: (value: string) => void;
}) {
	return (
		<section
			aria-label="Area layers"
			className="space-y-3 border-t border-[var(--line)] p-4"
		>
			<AreaLayerControl kind="land" layer={land}>
				<p className="text-xs text-[var(--sea-ink-soft)]">
					Mapped federal, state, and local ownership. Access varies.
				</p>
			</AreaLayerControl>
			<AreaLayerControl kind="elevation" layer={elevation}>
				<label className="flex items-center gap-2 text-xs text-[var(--sea-ink-soft)]">
					Minimum elevation (ft)
					<input
						type="number"
						min={0}
						max={15000}
						aria-invalid={!validElevation}
						value={elevationDraft}
						onChange={(event) => onElevationChange(event.target.value)}
						className="ml-auto w-24 rounded-lg border border-[var(--line)] bg-white px-2 py-1.5 outline-none focus:ring-2 focus:ring-[var(--lagoon-deep)]"
					/>
				</label>
				{!validElevation && (
					<p className="text-xs text-[var(--sea-ink-soft)]">
						Enter an elevation from 0 to 15,000 ft.
					</p>
				)}
			</AreaLayerControl>
		</section>
	);
}
