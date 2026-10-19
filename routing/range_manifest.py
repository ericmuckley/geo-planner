"""Frozen proof-manifest checks with bounded checksum-read cache advice."""

from pathlib import Path

from anchors import load_json
from range_hash import artifact, file_hash


def checked_manifest(directory):
    manifest = load_json(directory / "manifest.json")
    for name, expected in manifest["artifacts"].items():
        if artifact(directory / name) != expected: raise ValueError(f"Frozen artifact changed: {directory / name}")
    for name, expected in manifest["scripts"].items():
        if file_hash(directory / "recipe" / name) != expected or file_hash(Path(__file__).parent / name) != expected:
            raise ValueError(f"Frozen recipe changed: {name}")
    return manifest

