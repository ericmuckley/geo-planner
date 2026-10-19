import gzip
import json
from pathlib import Path
import struct
import tempfile
import unittest

from analyze_anchors import analyze
from anchors import (
    atomic_write, digest, read_row, save_row, select_anchors, validate_response,
    verify_artifacts,
)


def response():
    return {
        "units": "kilometers", "algorithm": "costmatrix",
        "sources": [{"lat": 32, "lon": -117}],
        "targets": [{"lat": 32, "lon": -117}, {"lat": 33, "lon": -117}],
        "sources_to_targets": [[
            {"from_index": 0, "to_index": 0, "time": 0, "distance": 0, "cost": 0},
            {"from_index": 0, "to_index": 1, "time": None, "distance": None, "cost": None},
        ]],
    }


def analysis_dataset(directory):
    manifest = {"anchors": [{}, {}, {}]}
    dataset_id = digest(manifest)
    (directory / "manifest.json").write_text(json.dumps({"datasetId": dataset_id, **manifest}))
    (directory / "rows").mkdir()
    matrix = [[0, 5, 20], [7, 0, 5], [11, 8, 0]]
    for i, times in enumerate(matrix):
        row = response()
        row["targets"] = [{}, {}, {}]
        row["sources_to_targets"] = [[
            {"from_index": 0, "to_index": j, "time": value, "distance": value, "cost": value}
            for j, value in enumerate(times)
        ]]
        save_row(directory / "rows" / f"{i:05}.json",
                 {"datasetId": dataset_id, "rowIndex": i, "response": row})
    packed = b"".join(struct.pack("<I", value) for times in matrix for value in times)
    (directory / "times.u32le").write_bytes(packed)
    (directory / "times.u32le.gz").write_bytes(gzip.compress(packed, mtime=0))


class AnchorPilotTests(unittest.TestCase):
    def test_geographic_selection_is_deterministic_and_does_not_repeat(self):
        candidates = [{"osmNodeId": i, "lat": 32 + i / 2, "lon": -117} for i in range(8)]
        selected = select_anchors(candidates, 4)
        self.assertEqual([p["osmNodeId"] for p in selected], [0, 7, 3, 5])
        self.assertEqual(selected, select_anchors(candidates, 4))
        with self.assertRaises(ValueError):
            select_anchors(candidates, 9)

    def test_response_retains_unknown_and_rejects_partial_or_misordered_rows(self):
        self.assertIsNone(validate_response(response(), 2)[1]["time"])
        malformed = response()
        malformed["sources_to_targets"][0].pop()
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            validate_response(malformed, 2)
        malformed = response()
        malformed["sources_to_targets"][0][1]["to_index"] = 0
        with self.assertRaisesRegex(ValueError, "indices"):
            validate_response(malformed, 2)

    def test_invalid_or_lossy_durations_fail(self):
        for invalid in (-1, float("nan"), float("inf"), 1.25, 0xFFFFFFFF, True):
            malformed = response()
            malformed["sources_to_targets"][0][0]["time"] = invalid
            with self.assertRaises(ValueError):
                validate_response(malformed, 2)
        malformed = response()
        del malformed["sources_to_targets"][0][0]["time"]
        with self.assertRaisesRegex(ValueError, "Missing"):
            validate_response(malformed, 2)

    def test_resume_rejects_tampering_and_other_dataset(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "00000.json"
            data = {"datasetId": "first", "rowIndex": 0, "response": response()}
            save_row(path, data)
            self.assertEqual(read_row(path, "first", 0, 2), data)
            with self.assertRaisesRegex(ValueError, "identity"):
                read_row(path, "second", 0, 2)
            envelope = json.loads(path.read_text())
            envelope["data"]["response"]["sources_to_targets"][0][0]["time"] = 99
            path.write_text(json.dumps(envelope))
            with self.assertRaisesRegex(ValueError, "checksum"):
                read_row(path, "first", 0, 2)

    def test_atomic_checkpoint_ignores_incomplete_temporary_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "row.json"
            path.with_suffix(".json.part").write_text("interrupted")
            atomic_write(path, b"finished")
            self.assertEqual(path.read_bytes(), b"finished")
            self.assertFalse(path.with_suffix(".json.part").exists())

    def test_preflight_checks_all_required_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            artifacts = {}
            for name in ("region.osm.pbf", "tiles.tar", "valhalla.json", "admin.sqlite"):
                (directory / name).write_bytes(b"{}")
                artifacts[name] = {"bytes": 2, "sha256": digest({})}
            verify_artifacts(directory, {"artifacts": artifacts})
            (directory / "tiles.tar").write_bytes(b"!!")
            with self.assertRaisesRegex(ValueError, "tiles.tar"):
                verify_artifacts(directory, {"artifacts": artifacts})

    def test_analysis_detects_noncomposable_costs_and_preserves_direction(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            analysis_dataset(directory)
            result = analyze(directory)
            self.assertTrue(result["packedMatchesEveryCheckpoint"])
            self.assertEqual(result["asymmetricUnorderedPairs"], 3)
            self.assertEqual(result["triangleViolationsOverTwoSeconds"], 1)
            self.assertEqual(result["largestTriangleViolations"][0]["excessSeconds"], 10)

    def test_analysis_rejects_corrupt_packed_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            analysis_dataset(directory)
            (directory / "times.u32le").write_bytes(b"corrupt")
            with self.assertRaisesRegex(ValueError, "Packed"):
                analyze(directory)


if __name__ == "__main__":
    unittest.main()
