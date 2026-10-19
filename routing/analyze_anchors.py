"""Inspect completed pilot data offline without routing or network calls."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct

from anchors import UNKNOWN, digest, load_json, read_row


def analyze(directory):
    manifest = load_json(directory / "manifest.json")
    dataset_id = manifest.pop("datasetId")
    if digest(manifest) != dataset_id:
        raise ValueError("Manifest identity mismatch")
    count = len(manifest["anchors"])
    rows = [read_row(directory / "rows" / f"{i:05}.json", dataset_id, i, count) for i in range(count)]
    matrix = [[p["time"] for p in r["response"]["sources_to_targets"][0]] for r in rows]
    packed = (directory / "times.u32le").read_bytes()
    expected = b"".join(struct.pack("<I", UNKNOWN if time is None else time) for row in matrix for time in row)
    if packed != expected or gzip.decompress((directory / "times.u32le.gz").read_bytes()) != packed:
        raise ValueError("Packed matrix differs from checkpoints")
    asymmetry = [abs(matrix[i][j] - matrix[j][i]) for i in range(count) for j in range(i)
                 if matrix[i][j] is not None and matrix[j][i] is not None]
    violations = []
    triples = 0
    for source in range(count):
        for anchor in range(count):
            for target in range(count):
                if len({source, anchor, target}) != 3:
                    continue
                direct, first, second = matrix[source][target], matrix[source][anchor], matrix[anchor][target]
                if direct is None or first is None or second is None:
                    continue
                triples += 1
                excess = direct - first - second
                # Ignore <=2s to distinguish larger violations from integer output precision.
                if excess > 2:
                    violations.append({"source": source, "via": anchor, "target": target,
                                       "directSeconds": direct, "viaSeconds": first + second,
                                       "excessSeconds": excess})
    return {
        "datasetId": dataset_id, "pairCount": count * count,
        "packedMatchesEveryCheckpoint": True,
        "packedSha256": hashlib.sha256(packed).hexdigest(),
        "nonzeroDiagonalEntries": [i for i in range(count) if matrix[i][i] != 0],
        "finiteUnorderedPairs": len(asymmetry),
        "asymmetricUnorderedPairs": sum(value > 0 for value in asymmetry),
        "maxDirectionalDifferenceSeconds": max(asymmetry, default=0),
        "finiteDistinctTriples": triples,
        "triangleViolationsOverTwoSeconds": len(violations),
        "largestTriangleViolations": sorted(violations, key=lambda v: -v["excessSeconds"])[:5],
        "interpretation": "Coordinate elapsed times are not certified composable minimum-time state distances. Triangle violations may reflect objective, snapping/state, or search differences; causes are not isolated.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(analyze(args.directory), indent=2))
