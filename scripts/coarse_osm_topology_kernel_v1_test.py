"""Independent graph incidence/anchor/edge-partition oracle for the disk kernel."""
from array import array
from collections import Counter
import hashlib
from pathlib import Path
import random
import struct
import tempfile
import unittest

from coarse_osm_topology_kernel_v1 import Kernel,REF
from coarse_timing_input import PilotError

ARTIFACT=None


def occurrence_rows(ways):
    return [(node,way,1 if index in (0,len(nodes)-1) else 2,int(index in (0,len(nodes)-1)))
            for way,nodes in ways.items() for index,node in enumerate(nodes)]


def oracle(ways,tags,relation_nodes,relation_ways):
    degree=Counter();ends=set();selected=set();protected=set(tags)|set(relation_nodes)
    for way,nodes in ways.items():
        selected.update(nodes);ends.update((nodes[0],nodes[-1]))
        for a,b in zip(nodes,nodes[1:]):degree[a]+=1;degree[b]+=1
        if way in relation_ways:protected.update(nodes)
    anchors={n for n in selected if degree[n]!=2 or n in ends or n in protected}
    # Count actual successive anchor positions in every source-way sequence.
    edges=sum(len([n for n in nodes if n in anchors])-1 for nodes in ways.values())
    primitive=sum(len(nodes)-1 for nodes in ways.values())
    return {'uniqueNodes':len(selected),'anchors':len(anchors),'contractedEdges':edges,'primitiveEdges':primitive,
        'routingArrayBytes':12*len(anchors)+24*edges+4,
        'fullGeometryArrayBytes':8*len(selected)+4*primitive+8*edges+4}


class Tests(unittest.TestCase):
    def setUp(self):
        if ARTIFACT is None:self.skipTest('Explicit compiled topology kernel required')
        self.kernel=Kernel(*ARTIFACT);temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.index=0
    def file(self,raw):
        self.index+=1;path=self.root/str(self.index);path.write_bytes(raw);return path
    def count(self,ways,tags=(),relation_nodes=(),relation_ways=(),chunk=3):
        rows=occurrence_rows(ways);parts=[]
        for i in range(0,len(rows),chunk):parts.append(self.file(self.kernel.sort(bytearray(b''.join(REF.pack(*r) for r in rows[i:i+chunk])))))
        tags=sorted(tags);tag_parts=[self.file(struct.pack('<'+'Q'*len(tags),*tags))] if tags else []
        actual=self.kernel.count(parts,tag_parts,array('Q',sorted(relation_nodes)),array('Q',sorted(relation_ways)),references=len(rows),ways=len(ways),tagged_nodes=len(tags))
        expected=oracle(ways,tags,relation_nodes,relation_ways)
        for key,value in expected.items():self.assertEqual(actual[key],value,key)
        self.assertEqual(actual['totalDegree'],2*actual['primitiveEdges']);self.assertEqual(actual['endpointOccurrences'],2*len(ways))
        self.assertEqual(actual['combinedArrayBytes'],actual['routingArrayBytes']+actual['fullGeometryArrayBytes'])
        return actual
    def test_loops_parallel_repeated_and_distinct_native_ids_with_metadata(self):
        ways={1:[1,2,3,4],2:[4,5,6],3:[3,7,3],4:[8,9,8],5:[10,10],6:[1,2,3,4],7:[2**63-1,42]}
        self.count(ways,tags=[2,8,999],relation_nodes=[5,444],relation_ways=[3,666])
    def test_seeded_graphs_and_chunk_boundaries_match_independent_partition(self):
        rng=random.Random(20261101)
        for _ in range(100):
            ways={i+1:[rng.randrange(1,30) for _ in range(rng.randrange(2,20))] for i in range(rng.randrange(1,12))}
            self.count(ways,tags=[1,10,99],relation_nodes=[2,999],relation_ways=[1,3,88],chunk=rng.randrange(1,20))
    def test_empty_graph_and_tag_only_rows_have_explicit_zero_counts(self):
        self.count({},tags=[1,2])
    def test_sort_is_exact_multiset_and_typed_id_boundary(self):
        rows=[(2**63-1,2**63-1,1,1),(1,2,2,0),(1,1,1,1),(1,1,1,1)]
        raw=self.kernel.sort(bytearray(b''.join(REF.pack(*r) for r in rows)))
        self.assertEqual(list(REF.iter_unpack(raw)),sorted(rows,key=lambda r:(r[0],r[1],r[3],r[2])))
        ids=bytearray(struct.pack('<5Q',2**63-1,1,2,2,99));self.kernel.sort(ids,ids=True)
        self.assertEqual(struct.unpack('<5Q',ids),(1,2,2,99,2**63-1))
    def test_invalid_records_ids_flags_truncation_and_order_stop(self):
        for row in ((0,1,1,1),(1,0,1,1),(2**63,1,1,1),(1,1,2,1),(1,1,1,0),(1,1,1,2)):
            with self.assertRaises(PilotError):self.kernel.sort(bytearray(REF.pack(*row)))
        for raw in (b'x',REF.pack(2,1,1,1)+REF.pack(1,1,1,1)):
            path=self.file(raw)
            with self.assertRaises(PilotError):self.kernel.count([path],[],array('Q'),array('Q'),references=2,ways=1,tagged_nodes=0)
    def test_tag_order_duplicates_cap_and_metadata_sort_stop(self):
        for ids in ([2,1],[1,1],[0],[2**63]):
            path=self.file(struct.pack('<'+'Q'*len(ids),*ids))
            with self.assertRaises(PilotError):self.kernel.count([], [path],array('Q'),array('Q'),references=0,ways=0,tagged_nodes=len(ids))
        path=self.file(struct.pack('<Q',1))
        for count in (0,2):
            with self.assertRaises(PilotError):self.kernel.count([],[path],array('Q'),array('Q'),references=0,ways=0,tagged_nodes=count)
        with self.assertRaises(PilotError):self.kernel.count([],[],array('Q',[2,1]),array('Q'),references=0,ways=0,tagged_nodes=0)
    def test_accounting_caps_and_symlink_input_stop(self):
        path=self.file(REF.pack(1,1,1,1)+REF.pack(2,1,1,1))
        for refs,ways in ((1,0),(3,1),(2,0)):
            with self.assertRaises(PilotError):self.kernel.count([path],[],array('Q'),array('Q'),references=refs,ways=ways,tagged_nodes=0)
        link=self.root/'link';link.symlink_to(path)
        with self.assertRaises(PilotError):self.kernel.count([link],[],array('Q'),array('Q'),references=2,ways=1,tagged_nodes=0)
    def test_library_drift_and_buffer_alignment_bounds_stop(self):
        with self.assertRaises(PilotError):Kernel(ARTIFACT[0],'0'*64)
        with self.assertRaises(PilotError):self.kernel.sort(bytearray(b'x'))
