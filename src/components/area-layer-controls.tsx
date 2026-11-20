import { Map as MapIcon, Mountain } from "lucide-react";
import { type CSSProperties, type ReactNode, useState } from "react";
import {
	type AreaLayerKind,
	areaLayers,
	type ElevationRange,
	maximumElevationFeet,
} from "../lib/area-layers";
import type { useAreaLayer } from "../lib/use-area-layer";
import { Slider } from "./ui/slider";

const icons = { land: MapIcon, elevation: Mountain };
type Layer = ReturnType<typeof useAreaLayer>;

function areaLayerColor(kind: AreaLayerKind) {
	return `rgb(${areaLayers[kind].color.join(" ")})`;
}

const elevationSliderTheme = {
	"--primary": areaLayerColor("elevation"),
	"--muted": "color-mix(in srgb, var(--primary) 14%, transparent)",
	"--ring": "var(--primary)",
} as CSSProperties;

export function AreaLayerDataStatus({
	kind,
	layer,
}: {
	kind: AreaLayerKind;
	layer: Layer;
}) {
	if (layer.grid) return null;
	const { label } = areaLayers[kind];
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

export type ElevationSliderProps = {
	value: ElevationRange;
	onChange: (value: ElevationRange) => void;
};

function formatElevation(feet: number) {
	return `${feet.toLocaleString("en-US")} ft`;
}

export function ElevationRangeSlider({
	value,
	onChange,
}: ElevationSliderProps) {
	const [draft, setDraft] = useState<{
		saved: ElevationRange;
		range: ElevationRange;
	}>();
	const range = draft?.saved === value ? draft.range : value;

	return (
		<fieldset aria-label="Elevation range" style={elevationSliderTheme}>
			<div
				className="flex items-center justify-between gap-2 text-xs text-neutral-700"
				aria-hidden="true"
			>
				<span>Elevation range</span>
				<span className="rounded-md bg-muted px-2 py-0.5 font-semibold text-primary tabular-nums">
					{formatElevation(range[0])} – {formatElevation(range[1])}
				</span>
			</div>
			<Slider
				min={0}
				max={maximumElevationFeet}
				value={range}
				preserveThumbOrder
				thumbLabels={["Minimum elevation", "Maximum elevation"]}
				formatValue={formatElevation}
				onValueChange={([min, max]) =>
					setDraft({ saved: value, range: [min, max] })
				}
				onValueCommit={([min, max]) => onChange([min, max])}
				onPointerCancel={() => setDraft(undefined)}
				className="h-8 cursor-pointer [&_[data-slot=slider-thumb]]:bg-primary"
			/>
			<div
				className="flex justify-between text-xs text-neutral-600"
				aria-hidden="true"
			>
				<span>0 ft</span>
				<span>{formatElevation(maximumElevationFeet)}</span>
			</div>
		</fieldset>
	);
}

function AreaLayerControl({
	kind,
	layer,
	onLayerChange,
	children,
}: {
	kind: AreaLayerKind;
	layer: Layer;
	onLayerChange: (kind: AreaLayerKind, checked: boolean) => void;
	children?: ReactNode;
}) {
	const { label } = areaLayers[kind];
	const Icon = icons[kind];
	const layerColor = areaLayerColor(kind);
	return (
		<div className="space-y-2">
			<label className="flex cursor-pointer items-center gap-2 text-sm font-semibold">
				<Icon size={16} style={{ color: layerColor }} aria-hidden="true" />
				{label}
				<input
					type="checkbox"
					checked={layer.enabled}
					onChange={(event) => onLayerChange(kind, event.target.checked)}
					className="ml-auto"
					style={{ accentColor: layerColor }}
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
	onLayerChange,
	elevationSlider,
}: {
	land: Layer;
	elevation: Layer;
	onLayerChange: (kind: AreaLayerKind, checked: boolean) => void;
	elevationSlider?: ElevationSliderProps;
}) {
	return (
		<section
			aria-label="Area layers"
			className="space-y-3 border-t border-neutral-200 p-4"
		>
			<AreaLayerControl kind="land" layer={land} onLayerChange={onLayerChange}>
				<p className="text-xs text-neutral-600 hidden">
					Mapped federal, state, and local ownership. Access varies.
				</p>
			</AreaLayerControl>
			<AreaLayerControl
				kind="elevation"
				layer={elevation}
				onLayerChange={onLayerChange}
			>
				{elevationSlider && <ElevationRangeSlider {...elevationSlider} />}
			</AreaLayerControl>
		</section>
	);
}
