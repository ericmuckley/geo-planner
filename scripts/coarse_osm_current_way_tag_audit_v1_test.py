"""Refuse source identity/tag/accounting drift and distinguish atime from mutation."""
import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import coarse_osm_conditional_census_v1_test as fixtures
from coarse_osm_current_way_tag_audit_v1 import audit
from coarse_timing_input import PilotError


class Tests(unittest.TestCase):
    def exercise(self, records=None, selected=None, cached=None, mutate=None, kind=1):
        records = [(1, {'highway': 'primary', 'name': 'Café'})] if records is None else records
        selected = {1: 'primary'} if selected is None else selected
        raw = b''.join(fixtures.RecordTests.encoded(kind=kind, identity=i, tags=tuple(sorted(t.items()))) for i, t in records)
        counters = dict(requestedWays=len(selected), selectedRecords=len(records), encodedBytes=len(raw),
                        tagUtf8Bytes=sum(len(k.encode())+len(v.encode()) for _, t in records for k, v in t.items()))
        if mutate:
            mutate(counters)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'tags'
            path.write_bytes(raw)
            return audit(path, counters, selected, cached or {}, lambda: None)

    def test_all_original_fields_and_large_ids_exact(self):
        identity = 2**53+1
        tags = {'highway': 'motorway', 'surface': 'asphalt', 'name': 'Café'}
        result = self.exercise([(identity, tags)], {identity: 'motorway'}, {identity: tags})
        self.assertEqual(result['wayTags'], {str(identity): tags})
        self.assertEqual(result['cachedOriginalsChecked'], 1)
        self.assertFalse(result['sourcePermissionsOrPricesChanged'])

    def test_missing_extra_and_unknown_selection_rejected(self):
        for records in ([], [(2, {'highway': 'primary'})]):
            with self.assertRaises((PilotError, AssertionError)):
                self.exercise(records)
        with self.assertRaises(PilotError):
            self.exercise(selected={1: 'residential'})

    def test_duplicate_and_reordered_records_rejected(self):
        for identities in ((1, 1), (2, 1)):
            with self.assertRaises((PilotError, AssertionError)):
                self.exercise([(i, {'highway': 'primary'}) for i in identities], {1: 'primary', 2: 'primary'})

    def test_wrong_source_type_rejected(self):
        with self.assertRaises(PilotError):
            self.exercise(kind=0)

    def test_wrong_current_role_rejected(self):
        with self.assertRaises(PilotError):
            self.exercise(selected={1: 'trunk'})

    def test_every_accounting_field_reconciles(self):
        for key in ('requestedWays', 'selectedRecords', 'encodedBytes', 'tagUtf8Bytes'):
            with self.assertRaises(PilotError):
                self.exercise(mutate=lambda c: c.update({key: c[key]+1}))

    def test_cached_tag_and_membership_drift_rejected(self):
        for cache in ({1: {'highway': 'primary'}}, {2: {'highway': 'primary'}}):
            with self.assertRaises(PilotError):
                self.exercise(cached=cache)

    def metadata_case(self, field):
        raw = fixtures.RecordTests.encoded(kind=1, identity=1, tags=(('highway', 'primary'),))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'tags'
            path.write_bytes(raw)
            before = path.stat()
            calls = 0
            def observed(p, *args, **kwargs):
                nonlocal calls
                calls += 1
                values = {k: getattr(before, k) for k in dir(before) if k.startswith('st_')}
                if calls > 2:
                    values[field] += 1
                return SimpleNamespace(**values)
            counters = dict(requestedWays=1, selectedRecords=1, encodedBytes=len(raw), tagUtf8Bytes=14)
            with patch.object(Path, 'stat', observed):
                return audit(path, counters, {1: 'primary'}, {}, lambda: None)

    def test_access_time_only_is_allowed(self):
        self.assertEqual(self.metadata_case('st_atime_ns')['selectedWays'], 1)

    def test_identity_size_and_change_times_are_guarded(self):
        for key in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns'):
            with self.assertRaises((PilotError, AssertionError)):
                self.metadata_case(key)

    def test_changed_content_digest_rejected(self):
        original = hashlib.file_digest
        calls = 0
        def digest(stream, algorithm):
            nonlocal calls
            calls += 1
            return original(stream, algorithm) if calls == 1 else SimpleNamespace(hexdigest=lambda: '0'*64)
        with patch.object(hashlib, 'file_digest', digest), self.assertRaisesRegex(PilotError, 'output stable'):
            self.exercise()


if __name__ == '__main__':
    unittest.main()
