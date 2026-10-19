import hashlib
import os
from pathlib import Path
import tempfile
import unittest

from paged_io import artifact, file_hash


class PagedIoTests(unittest.TestCase):
    def test_hash_and_artifact_metadata_preserve_exact_file_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.bin"
            payload = b"canonical source\x00\xff"
            path.write_bytes(payload)
            expected = hashlib.sha256(payload).hexdigest()
            self.assertEqual(file_hash(path), expected)
            self.assertEqual(artifact(path), {"bytes": len(payload), "sha256": expected})
            self.assertEqual(path.read_bytes(), payload)

    @unittest.skipUnless(hasattr(os, "posix_fadvise"), "Cache-advice check runs in Linux tools image")
    def test_large_advised_file_has_the_same_hash_and_bytes_as_normal_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.bin"
            payload = b"01234567" * (1024 ** 2)
            path.write_bytes(payload)
            self.assertEqual(file_hash(path), file_hash(path, advise=False))
            self.assertEqual(path.read_bytes(), payload)


if __name__ == "__main__": unittest.main()
