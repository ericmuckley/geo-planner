import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cache_lifetime
from compact_storage import JsonSequence, save_json as original_save


class Rows(JsonSequence):
    def __len__(self): return 3
    def __getitem__(self, index):
        if not 0 <= index < len(self): raise IndexError(index)
        return {"id": index, "label": "México", "point": [-117.1, 32.7]}


class CacheLifetimeTests(unittest.TestCase):
    def setUp(self):
        cache_lifetime.REQUESTS.clear()

    def test_canonical_streams_bound_pending_ranges_and_publish_exact_bytes(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(os, "fdatasync", create=True) as sync, \
             patch.object(os, "posix_fadvise", create=True) as advice, \
             patch.object(os, "POSIX_FADV_DONTNEED", 4, create=True), \
             patch.object(cache_lifetime, "WINDOW", 100):
            root = Path(tmp)
            payload = [b"a" * 97, b"b" * 257, b"c" * 17]
            result = cache_lifetime.write_blocks(root / "bytes", payload)
            self.assertEqual((root / "bytes").read_bytes(), b"".join(payload))
            self.assertEqual(result["bytes"], 371)
            self.assertEqual([(c.args[1], c.args[2]) for c in advice.call_args_list], [(0, 100), (100, 100), (200, 100), (300, 71)])
            self.assertEqual(sync.call_count, 4)
            value = {"roads": Rows(), "z": None, "a": [True, False, {"é": "南"}]}
            original_save(root / "original.json", value)
            cache_lifetime.save_json(root / "new.json", value)
            self.assertEqual((root / "original.json").read_bytes(), (root / "new.json").read_bytes())
            self.assertFalse((root / "new.json.part").exists())

    def test_failed_export_preserves_partial_and_never_replaces_existing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "output"
            target.write_bytes(b"keep")
            with self.assertRaises(FileExistsError): cache_lifetime.write_blocks(target, [b"replace"])
            self.assertEqual(target.read_bytes(), b"keep")

            def failing():
                yield b"partial"
                raise ValueError("producer failed")

            target = root / "failed"
            with self.assertRaisesRegex(ValueError, "producer failed"): cache_lifetime.write_blocks(target, failing())
            self.assertFalse(target.exists())
            self.assertEqual((root / "failed.part").read_bytes(), b"partial")
            with self.assertRaises(FileExistsError): cache_lifetime.write_blocks(target, [b"retry"])
            self.assertEqual((root / "failed.part").read_bytes(), b"partial")

    @unittest.skipUnless(hasattr(os, "posix_fadvise") and hasattr(os, "fdatasync"), "Linux file cache advice")
    def test_real_linux_advice_keeps_readonly_input_and_owned_output_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = b"data" * (cache_lifetime.THRESHOLD // 4 + 1)
            source, output = root / "source", root / "output"
            source.write_bytes(payload); source.chmod(0o444)
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            cache_lifetime.release_read(source, "test-read")
            cache_lifetime.write_blocks(output, [payload])
            cache_lifetime.release_output(output, "test-output")
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)
            self.assertEqual(output.read_bytes(), payload)
            self.assertEqual(source.stat().st_mode & 0o777, 0o444)
            self.assertEqual([r["kind"] for r in cache_lifetime.REQUESTS], ["completed-read", "streamed-output", "completed-output"])
