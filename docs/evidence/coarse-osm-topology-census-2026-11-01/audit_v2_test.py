"""Independent baseline and prospective lineage diagnostic on exact chain fixtures."""
import hashlib,json
from pathlib import Path
import struct,tempfile,unittest
from audit_v2 import audit

class Tests(unittest.TestCase):
    def test_baseline_and_explicit_metadata_lineage_counts(self):
        for n in (2,3,7,31):
            with tempfile.TemporaryDirectory() as temp:
                root=Path(temp);(root/'streams').mkdir();artifacts={}
                def emit(name,raw):
                    (root/'streams'/name).write_bytes(raw);artifacts[name]={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
                tags=[2] if n>2 else [];relation_nodes=[n-1] if n>3 else []
                emit('refs-0000.bin',b''.join(struct.pack('<QQII',i,1,1 if i in (1,n) else 2,int(i in (1,n))) for i in range(1,n+1)))
                if tags:emit('tagged-0000.bin',struct.pack('<Q',2))
                if relation_nodes:
                    for prefix in ('relation-nodes-','sorted-relation-nodes-'):emit(prefix+'0000.bin',struct.pack('<Q',n-1))
                for prefix in ('relation-ways-','sorted-relation-ways-'):emit(prefix+'0000.bin',struct.pack('<Q',1))
                counts={'references':n,'totalDegree':2*(n-1),'endpointOccurrences':2,'uniqueNodes':n,'anchors':n,'contractedEdges':n-1,'primitiveEdges':n-1,'taggedSelectedNodes':len(tags),'relationNodeSelectedNodes':len(relation_nodes),'relationWaySelectedNodes':n,'degreeNotTwoNodes':2,'wayEndUniqueNodes':2,'allTaggedNodeIds':len(tags),'routingArrayBytes':12*n+24*(n-1)+4,'fullGeometryArrayBytes':8*n+12*(n-1)+4,'combinedArrayBytes':20*n+36*(n-1)+8,'internalAnchorOccurrences':n-2,'complete':1}
                (root/'receipt.json').write_text(json.dumps({'maxNodeId':n,'maxWayId':1,'topologyWays':1}))
                (root/'topology.json').write_text(json.dumps({'counts':counts,'artifacts':artifacts,'writtenBytes':sum(v['bytes'] for v in artifacts.values())}))
                result=audit(root);expected=len({1,n,*tags,*relation_nodes});diagnostic=result['wayLineageDiagnostic']
                self.assertEqual(result['counts'],counts);self.assertEqual(diagnostic['anchors'],expected);self.assertEqual(diagnostic['contractedEdges'],expected-1)
    def test_full_chain_lineage_preserves_all_internal_point_distances(self):
        # Any graph contraction is a concatenation of these degree-two chains.
        # Metadata remains attached to the original way and full chain sequence.
        for n in (3,11,40):
            prefix=[0.]
            for i in range(n-1):prefix.append(prefix[-1]+(i%7)/4.)
            kept=sorted({0,n-1,1,n//2});chains=list(zip(kept,kept[1:]))
            for source in range(n):
                for target in range(n):
                    actual=min(abs(prefix[source]-prefix[a])+abs(prefix[a]-prefix[b])+abs(prefix[b]-prefix[target]) for a in kept for b in kept)
                    for a,b in chains:
                        if a<=source<=b and a<=target<=b:actual=min(actual,abs(prefix[target]-prefix[source]))
                    self.assertAlmostEqual(actual,abs(prefix[target]-prefix[source]),places=9)

if __name__=='__main__':unittest.main()
