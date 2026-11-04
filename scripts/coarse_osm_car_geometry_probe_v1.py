"""Capacity measurement only; does not build geometry or qualify snapping."""
import json
from pathlib import Path
import time


def run(native,repo,check):
    source=repo/'data/coarse-quality/us-osm-car-cost-country-run-v1'
    counts=json.loads((source/'audit.json').read_bytes())['facts']
    expected=[counts[key] for key in ('selectedNodes','anchors','majorWays','majorReferences','preClosureArcs','postClosureArcs')]
    began=time.monotonic();result=native.probe(source/'cost-facts',expected);check()
    assert result['selectedCoordinates']==42993567 and result['sourceGeometryReferences']==48163649
    assert result['majorWays']==4227238 and result['preClosureArcs']==9837326 and result['postClosureArcs']==9620680
    assert sum(row['physicalSpans'] for row in result['lengthHistogram'])==result['activePhysicalSpans']
    assert result['maximumDiscardedPointErrorMeters']<=100.00001
    geometry=result['packedShapeAndPrefixBytesForecast']+result['longSpanIndexBytesForecast']
    forecast=129399391+geometry+8388608+4194304
    result.update(status='native_complete_active_geometry_capacity_measured',
                  sourceVertexSimplificationToleranceMeters=100,shortSpanFullLengthThresholdMeters=1000,
                  geometryAndLongSpanIndexBytesForecast=geometry,retainedCoreAndIndexBytesMeasured=129399391,
                  geographyReserveBytes=8388608,javascriptReserveBytes=4194304,
                  retainedTotalForecastBytes=forecast,retainedGateBytes=162238546,
                  forecastFitsRetainedGate=forecast<=162238546,secondsNativeGeometryMeasurement=time.monotonic()-began,
                  sourcePbfReads=0,sourceConstructorExecutions=0,ordinaryPythonNationalSourceObjects=0,
                  geometryArtifactBuilt=False,originSnapOrEtaOrAppQualified=False,modelChanged=False,
                  scope='Native all-active-span capacity and self-checked discarded-source-vertex errors, with independent synthetic geometry math controls. Byte layout is a forecast: packed exact E7 coordinate deltas, two u16 prefix fractions per retained interior point, u24 arc keys/u32 packet offsets, and u24+4*i32 long-span bounding records. No actual packet/prefix/bounding artifact, independent country shape audit, continuous-curve/shore/paid-snap proof, compression or complete app fit follows.')
    return result
