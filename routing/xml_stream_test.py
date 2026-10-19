import ast
import hashlib
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from xml_fixtures import qualify
from xml_stream import RangeReader, WINDOW, parse_xml, report


def events(iterator):
    result = []
    for event, element in iterator:
        result.append((event, element.tag, dict(element.attrib), element.text, element.tail))
    return result


class XmlStreamTests(unittest.TestCase):
    def test_read_results_and_completed_ranges_match_original_bytes(self):
        data = '0123456789 México 🌎 0123456789'.encode()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'source.osm'; path.write_bytes(data)
            calls = []
            with patch('xml_stream.discard_range', side_effect=lambda fd, offset, length: calls.append((offset, length, reader.consumed))):
                with RangeReader(path, threshold=0, window=8) as reader:
                    self.assertEqual(reader.stream.mode, 'rb')
                    self.assertEqual(reader.read(0), b'')
                    actual = reader.read(3) + reader.read(10) + reader.read(None)
                    self.assertEqual(reader.read(), b'')
            self.assertEqual(actual, data)
            self.assertEqual(path.read_bytes(), data)
            self.assertEqual([(a, b) for a, b, _ in calls], [(offset, min(8, len(data) - offset)) for offset in range(0, len(data), 8)])
            self.assertTrue(all(offset + length <= consumed for offset, length, consumed in calls))
            self.assertEqual(report()['requests'][-1]['successfulAdviceBytes'], len(data))

    def test_early_close_advises_only_bytes_already_read(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'source.osm'; path.write_bytes(b'x' * 100)
            with patch('xml_stream.discard_range') as discard:
                with RangeReader(path, threshold=0, window=8) as reader: self.assertEqual(len(reader.read(9)), 9)
            self.assertEqual([(call.args[1], call.args[2]) for call in discard.call_args_list], [(0, 8), (8, 1)])
            row = report()['requests'][-1]
            self.assertEqual(row['readBytes'], 9); self.assertFalse(row['eofObserved']); self.assertTrue(row['closed'])

    def test_zero_reads_repeated_eof_and_close_are_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'source.osm'; path.write_bytes(b'123')
            before = len(report()['requests'])
            with patch('xml_stream.discard_range') as discard:
                with RangeReader(path, threshold=0, window=8) as reader:
                    self.assertEqual(reader.read(3), b'123')
                    self.assertEqual(reader.read(0), b''); self.assertFalse(reader.eof)
                    discard.assert_not_called()
                    self.assertEqual(reader.read(), b''); self.assertEqual(reader.read(), b'')
                reader.close()
            self.assertEqual(discard.call_count, 1)
            self.assertEqual(len(report()['requests']), before + 1)
            with self.assertRaises(ValueError): reader.read()

    def test_small_files_and_disabled_advice_do_not_request_eviction(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'source.osm'; path.write_bytes(b'123')
            for options in ({'threshold': 4}, {'advise': False, 'threshold': 0}):
                with patch('xml_stream.discard_range') as discard:
                    with RangeReader(path, **options) as reader: self.assertEqual(reader.read(), b'123')
                    discard.assert_not_called()
                self.assertFalse(report()['requests'][-1]['enabled'])

    def test_xml_events_unicode_boundaries_eof_and_errors_match_frozen_parser(self):
        prefix = b'<osm><node id="1" name="'
        unicode_source = prefix + b'x' * (16383 - len(prefix)) + 'é🌎"/></osm>'.encode()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'source.osm'
            for source in (unicode_source, b'', b'<osm>', b'<osm><node', b'<osm><node id="1"/></osm>trailing', b'<osm/>'):
                path.write_bytes(source)
                traces, errors = [], []
                for streamed in (False, True):
                    try:
                        if streamed:
                            with parse_xml(path, ('start', 'end')) as parser: traces.append(events(parser))
                        else: traces.append(events(ET.iterparse(path, events=('start', 'end'))))
                        errors.append(None)
                    except ET.ParseError as error:
                        traces.append(None); errors.append((type(error), str(error)))
                self.assertEqual(traces[0], traces[1]); self.assertEqual(errors[0], errors[1])
                self.assertTrue(report()['requests'][-1]['closed'])

    def test_consumer_failure_closes_stream_and_missing_file_errors_match(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'source.osm'; path.write_text('<osm><node id="1"/></osm>')
            with self.assertRaisesRegex(RuntimeError, 'consumer'):
                with parse_xml(path, ('start', 'end')) as parser:
                    next(parser); raise RuntimeError('consumer')
            self.assertTrue(report()['requests'][-1]['closed'])
            missing = path.with_name('missing.osm'); errors = []
            for streamed in (False, True):
                try:
                    if streamed:
                        with parse_xml(missing, ('start', 'end')) as parser: next(parser)
                    else: next(ET.iterparse(missing, events=('start', 'end')))
                except FileNotFoundError as error: errors.append(str(error))
            self.assertEqual(len(errors), 2); self.assertEqual(errors[0], errors[1])

    def test_advice_failure_is_recorded_without_masking_xml_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'source.osm'; path.write_bytes(b'<osm><node')
            with self.assertRaises(ET.ParseError) as expected: events(ET.iterparse(path, events=('start', 'end')))
            factory = lambda path: RangeReader(path, threshold=0, window=8)
            with patch('xml_stream.RangeReader', side_effect=factory), patch('xml_stream.discard_range', side_effect=OSError('advice unavailable')):
                with self.assertRaises(ET.ParseError) as caught:
                    with parse_xml(path, ('start', 'end')) as parser: events(parser)
            self.assertEqual(str(caught.exception), str(expected.exception))
            row = report()['requests'][-1]
            self.assertGreater(row['adviceErrors'], 0); self.assertEqual(row['successfulAdviceBytes'], 0); self.assertTrue(row['closed'])

    def test_large_xml_uses_bounded_advice_with_identical_events_and_source_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'source.osm'
            with path.open('wb') as stream:
                stream.write(b'<osm>')
                for _ in range(WINDOW // 4096 + 1): stream.write(b'<!--' + b'x' * 4089 + b'-->')
                stream.write('<node id="1" name="México 🌎"/></osm>'.encode())
            def sha():
                with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()
            before = sha()
            original = events(ET.iterparse(path, events=('start', 'end')))
            enabled = hasattr(os, 'posix_fadvise')
            with RangeReader(path, advise=enabled) as reader: actual = events(ET.iterparse(reader, events=('start', 'end')))
            self.assertEqual(actual, original); self.assertEqual(sha(), before)
            row = report()['requests'][-1]
            self.assertEqual(row['readBytes'], path.stat().st_size)
            self.assertTrue(row['eofObserved']); self.assertTrue(row['closed']); self.assertEqual(row['adviceErrors'], 0)
            self.assertLessEqual(row['maxReadBytes'], 65536)
            if enabled:
                self.assertEqual(row['successfulAdviceBytes'], row['fileBytes'])
                self.assertEqual(row['ranges'], math.ceil(row['fileBytes'] / WINDOW))
                self.assertLessEqual(row['maxRangeBytes'], WINDOW)

    def test_invalid_bounds_and_reusing_context_cannot_leak_an_open_file(self):
        for options in ({'window': 0}, {'window': True}, {'threshold': -1}, {'threshold': False}):
            with self.assertRaises(ValueError): RangeReader('unused', **options)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'source.osm'; path.write_bytes(b'123')
            with RangeReader(path) as reader:
                with self.assertRaisesRegex(ValueError, 'single-use'): reader.__enter__()
                self.assertEqual(reader.read(), b'123')
            with self.assertRaisesRegex(ValueError, 'single-use'): reader.__enter__()

    def test_source_control_and_uncertainty_excerpt_fixture_parity(self):
        result = qualify()
        self.assertEqual(result['caseCount'], 17); self.assertEqual(result['successes'], 9); self.assertEqual(result['failuresMatched'], 8)

    def test_xml_processing_bodies_change_only_to_explicit_read_contexts(self):
        root = Path(__file__).parent
        def function(file, name):
            return next(node for node in ast.parse((root / file).read_text()).body if isinstance(node, ast.FunctionDef) and node.name == name)
        class UnwrapReadContext(ast.NodeTransformer):
            def visit_With(self, node):
                node = self.generic_visit(node)
                context = node.items[0]
                if isinstance(context.context_expr, ast.Call) and isinstance(context.context_expr.func, ast.Name) and context.context_expr.func.id == 'parse_xml':
                    call = context.context_expr
                    call.func = ast.Attribute(value=ast.Name(id='ET', ctx=ast.Load()), attr='iterparse', ctx=ast.Load())
                    return [ast.Assign(targets=[context.optional_vars], value=call)] + node.body
                return node
        for old, name in (('targeted_evidence.py', 'source_examples'), ('crossing_audit.py', 'source_uncertainties')):
            self.assertEqual(ast.dump(function(old, name)), ast.dump(UnwrapReadContext().visit(function('xml_evidence.py', name))))


if __name__ == '__main__': unittest.main()
