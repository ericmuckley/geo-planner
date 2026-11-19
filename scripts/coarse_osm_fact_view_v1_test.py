"""Metadata-only complete-field replacement and exact namespace controls."""
import copy
import unittest
from coarse_osm_fact_view_v1 import compose,groups


def record(root,files):return {'root':'data/coarse-quality/'+root,'roster':{'cost-facts/'+n:{'bytes':size,'sha256':'a'*64} for n,size in files.items()}}

def fixture():
    base=record('base',{'ways-0000.bin':64,'flags-0000.bin':2,'arcs-0000.bin':16777216,'arcs-0001.bin':32,'ids-0000.bin':16,'geometry-0000.bin':16,'closures-0000.bin':8})
    overlay=record('new',{'ways-0000.bin':64,'flags-0000.bin':2,'arcs-0000.bin':64})
    return base,overlay


class Tests(unittest.TestCase):
    def test_overlay_replaces_whole_field_and_removes_stale_old_tail(self):
        base,new=fixture();view=compose(base,new)
        self.assertNotIn('/facts/cost-facts/arcs-0001.bin',view['files']);self.assertEqual(view['files']['/facts/cost-facts/arcs-0000.bin']['source'],'data/coarse-quality/new/cost-facts/arcs-0000.bin')
        self.assertEqual(view['fields']['arcs'],{'source':'overlay','files':1,'bytes':64})

    def test_every_other_base_field_preserved_with_exact_pin(self):
        base,new=fixture();view=compose(base,new)
        for prefix in ('ids','geometry','closures'):
            self.assertEqual(view['fields'][prefix]['source'],'base')
            self.assertEqual(view['files']['/facts/cost-facts/'+prefix+'-0000.bin']['sha256'],'a'*64)
        self.assertEqual(set(view['fields']),{'ways','arcs','flags','ids','geometry','closures'})

    def test_source_records_unmodified_and_result_deterministic(self):
        args=fixture();before=copy.deepcopy(args)
        self.assertEqual(compose(*args),compose(*args));self.assertEqual(args,before)

    def test_missing_or_additional_override_field_refused(self):
        base,new=fixture()
        for n in ['arcs-0000.bin','flags-0000.bin','ways-0000.bin']:
            bad=copy.deepcopy(new);del bad['roster']['cost-facts/'+n]
            with self.assertRaises(AssertionError):compose(base,bad)
        new['roster']['cost-facts/ids-0000.bin']={'bytes':8,'sha256':'a'*64}
        with self.assertRaises(AssertionError):compose(base,new)

    def test_path_traversal_noncanonical_name_and_pin_type_refused(self):
        base,new=fixture()
        for root in ('/absolute','data/coarse-quality/../escape','outside/source'):
            with self.assertRaises(AssertionError):groups(base|{'root':root})
        for name in ('cost-facts/../ways-0000.bin','cost-facts/ways-0.bin','cost-facts/ways-0000.bin/extra'):
            bad=copy.deepcopy(base);bad['roster'][name]={'bytes':32,'sha256':'a'*64}
            with self.assertRaises(AssertionError):groups(bad)
        for pin in ({'bytes':True,'sha256':'a'*64},{'bytes':32,'sha256':'bad'},{'bytes':16777217,'sha256':'a'*64}):
            bad=copy.deepcopy(new);bad['roster']['cost-facts/arcs-0000.bin']=pin
            with self.assertRaises(AssertionError):groups(bad)

    def test_gap_partial_interior_chunk_and_unaligned_records_refused(self):
        for files in ({'arcs-0001.bin':32},{'arcs-0000.bin':32,'arcs-0001.bin':32},{'arcs-0000.bin':33}):
            with self.assertRaises(AssertionError):groups(record('base',files))

    def test_original_way_and_flag_cardinalities_cannot_change(self):
        base,new=fixture()
        for name,size in [('ways-0000.bin',32),('flags-0000.bin',1)]:
            bad=copy.deepcopy(new);bad['roster']['cost-facts/'+name]['bytes']=size
            with self.assertRaises(AssertionError):compose(base,bad)
