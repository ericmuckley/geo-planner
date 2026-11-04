import io
import struct
import unittest

from coarse_osm_country_wire_v4 import framed_records
from coarse_osm_water_census_v2_test import way
from coarse_osm_water_endpoints_v1 import ROW,Endpoints,extract,audit,relation_chains,way_ends


class Controls(unittest.TestCase):
    def fixture(self):
        raw=framed_records([way(10,{},[1,2,3]),way(20,{},[3,4,1]),way(30,{},[9,10,11,9])])
        return raw,extract(io.BytesIO(raw),[1,10,20,30,99])[0]

    def test_all_member_endpoints_and_missing_before_after_source(self):
        raw,facts=self.fixture()
        self.assertEqual(facts.lookup(10),(10,1,3,3));self.assertIsNone(facts.lookup(1));self.assertIsNone(facts.lookup(99))
        proof=audit(io.BytesIO(raw),facts)
        self.assertEqual(proof['allMemberEndpointRowsChecked'],5)
        self.assertEqual(len(b''.join(facts.rows())),5*32)

    def test_truncation_wrong_kind_lengths_order_and_duplicate_inputs_fail(self):
        raw,facts=self.fixture()
        for bad in (raw[:-1],raw[:2],raw[:4]+b'XXXX'+raw[8:]):
            with self.assertRaises(Exception):extract(io.BytesIO(bad),facts.ids)
        with self.assertRaises(Exception):Endpoints([2,1])
        with self.assertRaises(Exception):Endpoints([1,1])
        with self.assertRaises(Exception):extract(io.BytesIO(framed_records([way(20,{}),way(10,{})])),[10,20])

    def test_independent_full_decoder_rejects_corrupt_endpoint_fact(self):
        raw,facts=self.fixture();facts.last[1]=999
        with self.assertRaises(Exception):audit(io.BytesIO(raw),facts)

    def test_explicit_outer_inner_chains_are_not_polygon_validity(self):
        _,facts=self.fixture()
        row={'id':7,'tags':{'type':'multipolygon'},'members':[{'type':'way','ref':i,'role':r} for i,r in [(10,'outer'),(20,'outer'),(30,'inner')]]}
        result=relation_chains(row,facts)
        self.assertEqual(result['status'],'explicit_role_degree2_closed_chains');self.assertFalse(result['polygonValidityEstablished'])
        self.assertEqual(len(result['inner']['closedChains']),1)

    def test_missing_unknown_role_duplicate_and_nested_cases_stay_explicit(self):
        _,facts=self.fixture()
        def row(members):return {'id':7,'tags':{'type':'multipolygon'},'members':members}
        member=lambda i,role='outer':{'type':'way','ref':i,'role':role}
        for members,status in [([member(99)],'missing_way_member'),([member(10,'')],'way_role_requires_explicit_policy'),
                               ([member(10),member(10)],'duplicate_way_member_occurrence'),
                               ([{'type':'relation','ref':9,'role':'outer'}],'nested_relation_roles_need_geometry_policy')]:
            self.assertEqual(relation_chains(row(members),facts)['status'],status)

    def test_no_outer_and_open_chains_do_not_become_polygons(self):
        _,facts=self.fixture()
        for members in ([],[{'type':'way','ref':10,'role':'outer'}],[{'type':'way','ref':30,'role':'inner'}]):
            result=relation_chains({'id':7,'tags':{'type':'multipolygon'},'members':members},facts)
            self.assertEqual(result['status'],'native_endpoint_topology_requires_geometry_or_missing_closure')

    def test_endpoint_parser_checks_exact_reference_layout(self):
        raw=framed_records([way(10,{'name':'雪'},[1,2,3,1])]);body=raw[4:]
        self.assertEqual(way_ends(body),(10,1,1,4))
        with self.assertRaises(Exception):way_ends(body+b'X')

    def test_unlisted_member_is_input_parity_error_not_silent_missing(self):
        _,facts=self.fixture()
        with self.assertRaises(Exception):facts.lookup(12345)


if __name__=='__main__':unittest.main()
