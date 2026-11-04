"""Regressions for dependencies hidden behind a deferred fixture/reader import."""
from pathlib import Path
import tempfile
import unittest

from coarse_osm_python_bindings_v1 import dependencies, require_bindings
from coarse_timing_input import PilotError


class Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.repo = Path(temp.name)
        for folder in ('scripts', 'routing', 'docs/proof'):(self.repo/folder).mkdir(parents=True)

    def write(self, name, text):
        (self.repo/name).write_text(text);return name

    def test_deferred_imports_include_the_complete_reader_chain(self):
        root = self.write('scripts/entry.py', 'def run():\n import oracle\n')
        self.write('docs/proof/oracle.py', 'from payload import Reader\n');self.write('scripts/payload.py', 'from costs import value\n')
        self.write('routing/costs.py', 'value=1\n')
        self.assertEqual(dependencies(self.repo, [root], ['docs/proof']), {root, 'docs/proof/oracle.py', 'scripts/payload.py', 'routing/costs.py'})

    def test_missing_payload_fails_before_execution(self):
        root = self.write('scripts/entry.py', 'from payload import Reader\n');self.write('scripts/payload.py', 'class Reader: pass\n')
        with self.assertRaisesRegex(PilotError, 'scripts/payload.py'):
            require_bindings(self.repo, [root], {root: '/code/entry.py'})

    def test_wrong_module_filename_fails(self):
        root = self.write('scripts/entry.py', 'pass\n')
        with self.assertRaises(PilotError):require_bindings(self.repo, [root], {root: '/code/wrong.py'})

    def test_standard_library_imports_and_cycles_are_bounded(self):
        root = self.write('scripts/entry.py', 'import json\nimport helper\n');self.write('scripts/helper.py', 'import entry\n')
        self.assertEqual(dependencies(self.repo, [root]), {root, 'scripts/helper.py'})

    def test_outside_repository_roots_fail(self):
        with self.assertRaises(PilotError):dependencies(self.repo, ['../outside.py'])
