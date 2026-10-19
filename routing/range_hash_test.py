import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import range_hash
from range_manifest import checked_manifest


class RangeHashTests(unittest.TestCase):
    def setUp(self):
        range_hash.REQUESTS.clear()

    def test_digest_and_completed_range_boundaries_match_for_empty_tail_and_large_reads(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(os, "posix_fadvise", create=True) as advice, \
             patch.object(os, "POSIX_FADV_DONTNEED", 4, create=True), \
             patch.object(range_hash, "THRESHOLD", 1), \
             patch.object(range_hash, "WINDOW", 100):
            path = Path(tmp) / "input"
            for size in [0, 100, 201, 1257]:
                path.write_bytes(bytes(index % 256 for index in range(size)))
                advice.reset_mock()
                actual = range_hash.file_hash(path)
                self.assertEqual(actual, hashlib.sha256(path.read_bytes()).hexdigest())
                ranges = [(row.args[1], row.args[2]) for row in advice.call_args_list]
                self.assertEqual(sum(length for _, length in ranges), size)
                self.assertTrue(all(length <= 100 for _, length in ranges))
                self.assertEqual([start for start, _ in ranges], list(range(0, size, 100)))
                advice.reset_mock()
                self.assertEqual(range_hash.file_hash(path, advise=False), actual)
                advice.assert_not_called()

    @unittest.skipUnless(hasattr(os, "posix_fadvise"), "Linux file cache advice")
    def test_linux_readonly_source_digest_permissions_and_bytes_remain_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source"
            payload = b"source" * (range_hash.THRESHOLD // 6 + 1)
            path.write_bytes(payload);path.chmod(0o444)
            self.assertEqual(range_hash.artifact(path), {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()})
            self.assertEqual(path.read_bytes(), payload)
            self.assertEqual(path.stat().st_mode & 0o777, 0o444)
            self.assertEqual(range_hash.REQUESTS[0]["bytes"], len(payload))

    def test_manifest_rejects_artifact_and_recipe_changes_with_the_same_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);(root / "recipe").mkdir()
            source = Path(__file__).with_name("range_hash.py")
            shutil.copyfile(source, root / "recipe/range_hash.py")
            (root / "data").write_bytes(b"frozen")
            record = {"artifacts": {"data": range_hash.artifact(root / "data")},
                      "scripts": {"range_hash.py": range_hash.file_hash(source)}}
            (root / "manifest.json").write_text(json.dumps(record))
            self.assertEqual(checked_manifest(root), record)
            (root / "data").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "Frozen artifact changed"): checked_manifest(root)
            (root / "data").write_bytes(b"frozen")
            (root / "recipe/range_hash.py").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "Frozen recipe changed"): checked_manifest(root)
