"""Regression controls for the controls-only wrapper correction."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from coarse_timing_input import PilotError


class Tests(unittest.TestCase):
    def test_reused_qualification_cannot_recompile_or_change_artifact(self):
        from run_osm_country_screen_v3 import validate
        repo=Path(__file__).resolve().parents[1]
        path=Path('/inputs/recipe-v2.json') if Path('/inputs/recipe-v2.json').exists() else repo/'docs/evidence/coarse-osm-country-exec-2026-10-30/qualification-plan-v3.json'
        if not path.exists():self.skipTest('New V3 recipe not frozen yet')
        plan=json.loads(path.read_text());validate(plan)
        bad=deepcopy(plan);bad['phases']=['build','controls']
        with self.assertRaises(PilotError):validate(bad)

    def test_binding_helper_returns_exact_fixture_identity(self):
        import hashlib,tempfile
        from coarse_osm_country_screen_v1_test import binding
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'fixture';path.write_bytes(b'abc')
            self.assertEqual(binding(path),{'bytes':3,'sha256':hashlib.sha256(b'abc').hexdigest(),'md5':hashlib.md5(b'abc').hexdigest()})
