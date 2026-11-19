import struct
import coarse_osm_entry_graph_audit_v1_test as fixtures
from coarse_osm_incoming_entry_graph_audit_v1 import audit


class Controls(fixtures.Controls):
    def run_audit(self):
        return audit(self.original,self.view,self.routing,self.extra,self.final,self.dims,self.counts,baseline_post=1)

    def test_closed_incoming_open_outgoing_preserves_old_allowed_transitions(self):
        (self.original/'closures-0000.bin').write_bytes(struct.pack('<QQ',10,30))
        proof = audit(self.original,self.view,self.routing,self.extra,self.final,self.dims,self.counts,baseline_post=2)
        self.assertTrue(proof['newEntryPairsIncomingArcOriginallyClosed'])
        self.assertTrue(proof['oldAllowedTransitionsPreserved'])

    def test_open_incoming_closed_outgoing_still_refuses(self):
        (self.original/'closures-0000.bin').write_bytes(struct.pack('<QQ',20,30))
        with self.assertRaises(AssertionError):
            audit(self.original,self.view,self.routing,self.extra,self.final,self.dims,self.counts,baseline_post=2)
