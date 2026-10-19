from io import BytesIO
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from lifetime_io import WINDOW, copy_advised, partition_ids, stream_command


class LifetimeTests(unittest.TestCase):
    def test_partition_preserves_all_ids_in_order_and_handles_empty_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'ids.txt';source.write_text('w1\nw2\nw3\nw4\nw5\nr10\nr11\n')
            parts=partition_ids(source,root,4)
            self.assertEqual(len(parts),4)
            self.assertEqual(''.join(p.read_text() for p in parts),source.read_text())
            empty=root/'empty';empty.mkdir();source.write_text('')
            self.assertEqual(partition_ids(source,empty,4)[0].read_bytes(),b'')
            with self.assertRaises(ValueError):partition_ids(source,root,2)

    @unittest.skipUnless(hasattr(os,'posix_fadvise') and hasattr(os,'fdatasync'),'Linux output advice')
    def test_output_advice_preserves_bytes_across_multiple_windows_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'output';payload=b'x'*(WINDOW+123)
            report=copy_advised(BytesIO(payload),output)
            self.assertEqual(output.read_bytes(),payload)
            self.assertEqual(report['bytes'],len(payload));self.assertEqual(report['syncs'],2)
            with self.assertRaises(FileExistsError):copy_advised(BytesIO(b'new'),output)

    @unittest.skipUnless(sys.platform=='linux','Linux time/output advice')
    def test_failed_native_child_preserves_partial_output_and_reports_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);output=root/'partial'
            with self.assertRaises(subprocess.CalledProcessError):
                stream_command([sys.executable,'-c',"import sys;sys.stdout.write('partial');sys.exit(3)"],output,root,'failed')
            self.assertEqual(output.read_bytes(),b'partial')
            self.assertTrue((root/'failed-resources.txt').exists())
