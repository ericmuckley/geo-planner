"""Independent packed-output audit refusal controls; synthetic input only."""
from pathlib import Path
import struct
import tempfile
import unittest

from coarse_osm_car_packed_audit_v1 import audit
from coarse_osm_packed_capture_v1 import encode


class PackedAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'facts';self.source.mkdir();self.routing=self.root/'routing';self.routing.mkdir()
        ids=[11,12,13];anchors=[0,1,2];flags=b'\4\6\4';geometry=[0,1,1,2]
        ways=[(10,100.,100.,3,2),(20,100.,0.,1,4)]
        arcs=[(0,1,0,0,1,1,1),(1,0,0,0,1,-1,1),(1,2,1,0,1,1,1)]
        turns=[(1000,10,12,999,6)]
        fields,_,_=encode(ids,[0]*6,anchors,flags,geometry,ways,arcs,set(),turns,[])
        for name,raw in fields.items():(self.routing/name).write_bytes(raw)
        def save(prefix,fmt,values):
            (self.source/(prefix+'-0000.bin')).write_bytes(b''.join(struct.pack(fmt,*row) for row in values))
        save('ids','<Q',[(n,) for n in ids]);save('anchors','<I',[(n,) for n in anchors]);save('xy','<ii',[(0,0)]*3)
        save('flags','<B',[(n,) for n in flags]);save('ways','<QddII',ways);save('arcs','<IIIIIb3xQ',arcs);save('turns','<QQQQB7x',turns)
        self.expected=[3,3,2,3,3,1]

    def test_complete_independent_fields(self):
        result=audit(self.source,self.routing,self.expected)
        self.assertEqual(result['directedCostsAndPhysicalReversesChecked'],3)
        self.assertEqual(result['forbiddenTurnPairsChecked'],2)

    def test_corrupt_cost_rejected(self):
        (self.routing/'costs.u16').write_bytes(struct.pack('<HHH',2,1,1))
        with self.assertRaises(AssertionError):audit(self.source,self.routing,self.expected)

    def test_wrong_physical_reverse_rejected(self):
        (self.routing/'reverse.u8').write_bytes(b'\xff\xff\xff')
        with self.assertRaises(AssertionError):audit(self.source,self.routing,self.expected)

    def test_missing_and_surplus_turn_pairs_rejected(self):
        path=self.routing/'forbidden-turns.u24';raw=path.read_bytes()
        for invalid in (raw[:-6],raw+b'\1\0\0\0\0\0'):
            path.write_bytes(invalid)
            with self.assertRaises(AssertionError):audit(self.source,self.routing,self.expected)

    def test_coordinate_or_flag_mismatch_rejected(self):
        path=self.routing/'xy.i32';raw=path.read_bytes();path.write_bytes(struct.pack('<i',1)+raw[4:])
        with self.assertRaises(AssertionError):audit(self.source,self.routing,self.expected)
        path.write_bytes(raw);(self.routing/'node-flags.u8').write_bytes(b'\4\4\4')
        with self.assertRaises(AssertionError):audit(self.source,self.routing,self.expected)

    def test_redistributed_csr_and_wrong_target_rejected(self):
        path=self.routing/'offsets.u24';raw=path.read_bytes();path.write_bytes(b'\0\0\0\2\0\0\3\0\0\3\0\0')
        with self.assertRaises(AssertionError):audit(self.source,self.routing,self.expected)
        path.write_bytes(raw);(self.routing/'targets.u24').write_bytes(b'\2\0\0\0\0\0\2\0\0')
        with self.assertRaises(AssertionError):audit(self.source,self.routing,self.expected)


if __name__ == '__main__':unittest.main()
