import { Map as MapIcon, Mountain } from "lucide-react";
import type { ReactNode } from "react";
import { type AreaLayerKind, areaLayers } from "../lib/area-layers";
import type { useAreaLayer } from "../lib/use-area-layer";

const icons = { land: MapIcon, elevation: Mountain };
type Layer = ReturnType<typeof useAreaLayer>;

export function AreaLayerDataStatus({
	kind,
	layer,
}: {
	kind: AreaLayerKind;
	layer: Layer;
}) {
	const { label, attribution, attributionUrl } = areaLayers[kind];
	if (layer.grid) {
		return (
			<p className="text-xs text-[var(--sea-ink-soft)]">
				<a href={attributionUrl} className="underline">
					{attribution}
				</a>
				{" · Coarse grid (~2 km)"}
			</p>
		);
	}
	return (
		<div className="flex items-baseline gap-2 text-xs" aria-live="polite">
			<span>
				{layer.loadError
					? `${label} data could not load.`
					: `Loading ${label.toLowerCase()} data…`}
			</span>
			{layer.loadError && (
				<button
					type="button"
					className="underline"
					aria-label={`Retry ${label.toLowerCase()} data`}
					onClick={layer.retry}
				>
					Retry
				</button>
			)}
		</div>
	);
}

export type ElevationInputProps = {
	value: string;
	valid: boolean;
	onChange: (value: string) => void;
};

export function MinimumElevationInput({
	value,
	valid,
	onChange,
}: ElevationInputProps) {
	return (
		<>
			<label className="flex items-center gap-2 text-xs text-[var(--sea-ink-soft)]">
				Minimum elevation (ft)
				<input
					type="number"
					min={0}
					max={15000}
					aria-invalid={!valid}
					value={value}
					onChange={(event) => onChange(event.target.value)}
					className="ml-auto w-24 rounded-lg border border-[var(--line)] bg-white px-2 py-1.5 outline-none focus:ring-2 focus:ring-[var(--lagoon-deep)]"
				/>
			</label>
			{!valid && (
				<p className="text-xs text-[var(--sea-ink-soft)]">
					Enter an elevation from 0 to 15,000 ft.
				</p>
			)}
		</>
	);
}

function AreaLayerControl({
	kind,
	layer,
	children,
}: {
	kind: AreaLayerKind;
	layer: Layer;
	children?: ReactNode;
}) {
	const { label, color } = areaLayers[kind];
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
					<AreaLayerDataStatus kind={kind} layer={layer} />
				</>
			)}
		</div>
	);
}

export function AreaLayerControls({
	land,
	elevation,
	minimumElevation,
}: {
	land: Layer;
	elevation: Layer;
	minimumElevation?: ElevationInputProps;
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
				{minimumElevation && <MinimumElevationInput {...minimumElevation} />}
			</AreaLayerControl>
		</section>
	);
}
