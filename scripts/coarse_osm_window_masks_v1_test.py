"""Native primary/audit predicates, independent oracle and fail-closed budgets."""
import ctypes
import random
import unittest

from coarse_osm_bulk_audit import crossing
from coarse_osm_records import intersects
from coarse_osm_window_cells_v1 import Cells,SCALE
from coarse_osm_window_masks_v1 import Masks
from coarse_timing_input import PilotError

ARTIFACT=None
MASKERS=[]


def configure_native(path,sha):
    global ARTIFACT
    ARTIFACT=path,sha


class NativeTests(unittest.TestCase):
    def masks(self,windows=None,**caps):
        if ARTIFACT is None:self.skipTest('Compiled native window masks required')
        grid=Cells(windows or [{'id':'q','bbox':[0,0,1,1]}]);masker=Masks(*ARTIFACT,grid,**caps);MASKERS.append(masker);return masker

    def test_arbitrary_paths_match_python_outcodes_and_keep_both_clippers(self):
        windows=[{'id':str(i),'bbox':[-170+i*6,-80+i*3,-168+i*6,-79+i*3]} for i in range(21)]
        masks=self.masks(windows);rng=random.Random(73108);points=[];cells=[];counts=[];expected=[]
        for _ in range(1000):
            path=[[rng.randint(-180000,180000)/1000,rng.randint(-90000,90000)/1000] for _ in range(rng.randint(2,6))]
            values=[masks.grid.cell(round(x*SCALE),round(y*SCALE)) for x,y in path]
            possible=masks.grid.candidates(values);mask=sum(1<<i for i,w in enumerate(windows) if w['id'] in possible)
            for i,window in enumerate(windows):
                if intersects(path,window['bbox']) or crossing(path,window['bbox']):self.assertTrue(mask&(1<<i))
            points.append(path);cells.extend(values);counts.append(len(values));expected.append(mask)
        self.assertEqual(masks.masks(cells,counts),expected);self.assertEqual(masks.masks(cells,counts,audit=True),expected)

    def test_full_reference_and_way_ceilings_accept_crossings_and_degenerate_points(self):
        masks=self.masks();a=masks.grid.cell(-SCALE,SCALE//2);b=masks.grid.cell(2*SCALE,SCALE//2)
        self.assertEqual(masks.masks([a,b]*32768,[2]*32768),[1]*32768)
        self.assertEqual(masks.masks([a,b]*32768,[2]*32768,audit=True),[1]*32768)
        at=masks.grid.cell(0,0);self.assertEqual(masks.masks([at,at],[2]),[1])

    def test_audit_does_not_consume_a_corrupted_primary_table(self):
        masks=self.masks();cells=[masks.grid.cell(-SCALE,SCALE//2),masks.grid.cell(2*SCALE,SCALE//2)]
        for i in range(len(masks.table)):masks.table[i]=15
        self.assertEqual(masks.masks(cells,[2]),[0]);self.assertEqual(masks.masks(cells,[2],audit=True),[1])
        masks.table[0]=16
        with self.assertRaises(PilotError):masks.masks(cells,[2])
        self.assertEqual(masks.masks(cells,[2],audit=True),[1])

    def test_invalid_late_cells_or_counts_cannot_hide_behind_an_early_candidate(self):
        masks=self.masks();at=masks.grid.cell(0,0)
        for values,counts in [([at,True],[2]),([at,-1],[2]),([at,masks.grid.count],[2]),([at,at],[1,1]),([at,at],[3])]:
            with self.assertRaises(PilotError):masks.masks(values,counts)
        values=(ctypes.c_uint16*3)(at,at,masks.grid.count);ends=(ctypes.c_uint32*1)(3);out=(ctypes.c_uint32*1)(0xdeadbeef)
        self.assertNotEqual(masks.primary(masks.table,len(masks.table),1,masks.grid.count,values,3,ends,1,out,1),0)
        self.assertEqual(out[0],0xdeadbeef)

    def test_masks_budget_and_audit_edge_validation(self):
        masks=self.masks(reference_budget=3);at=masks.grid.cell(0,0);masks.masks([at,at],[2])
        with self.assertRaises(PilotError):masks.masks([at,at],[2],audit=True)
        self.assertEqual((masks.references,masks.calls),(2,1))
        masks=self.masks(call_budget=1);masks.masks([at,at],[2])
        with self.assertRaises(PilotError):masks.masks([at,at],[2])
        masks=self.masks();masks.boxes[0]=0
        with self.assertRaises(PilotError):masks.masks([at,at],[2],audit=True)

    def test_native_short_output_buffer_preserves_sentinels(self):
        masks=self.masks();at=masks.grid.cell(0,0);values=(ctypes.c_uint16*2)(at,at);ends=(ctypes.c_uint32*1)(2);out=(ctypes.c_uint32*1)(0xdeadbeef)
        self.assertNotEqual(masks.primary(masks.table,len(masks.table),1,masks.grid.count,values,2,ends,1,out,0),0)
        self.assertEqual(out[0],0xdeadbeef)
