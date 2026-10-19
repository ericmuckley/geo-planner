"""Bind frozen parsers to cache advice after their file handles are finished."""

from pathlib import Path

from barrier_policy import prepare_barriers as original_prepare_barriers
from cache_lifetime import release_output, release_read
from input_storage import read_osm as original_read_osm


def read_osm(path):
    result = original_read_osm(path)
    release_read(Path(path), "decoded-input")
    return result


def prepare_barriers(source, destination, bounds):
    result = original_prepare_barriers(source, destination, bounds)
    release_read(Path(source), "barrier-source")
    release_output(Path(destination), "barrier-output")
    return result
