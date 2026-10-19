"""Separate capped build admission from qualified-graph release requirements."""

import math

from hour_admission import peak


CAP = 4 * 1024 ** 3


def admission(phase, measured, scale, pressure):
    estimated = math.ceil(measured * scale)
    margin = math.ceil(estimated * 1.25)
    return {"phase": phase, "measuredReferencePeakBytes": measured, "scalingRatio": scale,
            "estimatedPeakBytes": estimated, "with25PercentMarginBytes": margin, "capBytes": CAP,
            "pressureObserved": pressure, "eligible": not pressure and margin < CAP,
            "scope": "Admission for one separately capped phase, not a graph release or measured candidate peak."}


def build_admission(prepared, built):
    measured, pressure = peak(built)
    _, prep_pressure = peak(prepared)
    return admission("build-only", measured, prepared["admission"]["scalingRatio"], pressure or prep_pressure)


def qualification_admission(prepared, calibrated):
    measured, pressure = peak(calibrated)
    return admission("independent-qualification", measured, prepared["admission"]["scalingRatio"], pressure)
