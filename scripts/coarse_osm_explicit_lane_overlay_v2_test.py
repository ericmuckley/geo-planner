"""Same lane policy with exact original-source flag provenance regressions."""
import copy
import unittest

import coarse_osm_explicit_lane_overlay_v1_test as legacy
from coarse_osm_car_cost_math_v1 import NativeCosts
from coarse_osm_car_conditional_speed_v1 import way_policy as current_policy
from coarse_osm_explicit_lane_overlay_v2 import prepare
from coarse_osm_original_way_flags_v1 import original_way_prefix

ARTIFACT=None


class Tests(legacy.Tests):
    def kernel(self):return NativeCosts(*ARTIFACT) if ARTIFACT else legacy.ReferenceCosts()
    def run_case(self,args,records):return prepare(*args,records,self.kernel())

    def test_original_conditional_labels_match_raw_tags_and_current_lane_policy(self):
        for key in ('hgv:conditional','foot:conditional','bicycle:conditional','maxspeed:hgv:conditional'):
            args,records=legacy.fixture(**{key:'no @ night'})
            tags=records[0]['tags'];self.assertEqual(current_policy(tags).reason,'lane-access')
            row=args[4][0];prefix=original_way_prefix(tags);self.assertEqual(prefix[2]>>8,5)
            args[4][0]=(row[0],*prefix,row[4]);result=self.run_case(args,records)
            plain_args,plain_records=legacy.fixture();plain=self.run_case(plain_args,plain_records)
            self.assertEqual(result['wayRows'],plain['wayRows']);self.assertEqual(result['arcs'],plain['arcs'])
            self.assertEqual(result['counts']['sourcePolicyLabelRetainedFromEarlierVersion'],1)

    def test_historic_label_only_accepted_when_every_source_flag_matches_raw_tags(self):
        args,records=legacy.fixture();row=args[4][0]
        args[4][0]=(row[0],0.,0.,(5<<8)|(4<<4),row[4])
        with self.assertRaises(AssertionError):self.run_case(args,records)
        for forged in ((6<<8)|(4<<4),(5<<8)|(4<<4)|4,(5<<8)|(3<<4)):
            args,records=legacy.fixture(**{'hgv:conditional':'no @ night'});row=args[4][0]
            args[4][0]=(row[0],0.,0.,forged,row[4])
            with self.assertRaises(AssertionError):self.run_case(args,records)
        args,records=legacy.fixture(**{'motorcar:conditional':'no @ night'});row=args[4][0]
        args[4][0]=(row[0],*original_way_prefix(records[0]['tags']),row[4])
        with self.assertRaises(AssertionError):self.run_case(args,records)

    def test_cancellation_callback_runs_before_any_source_update(self):
        args,records=legacy.fixture();before=copy.deepcopy(args)
        def cancel():raise RuntimeError('cancel lane overlay')
        with self.assertRaisesRegex(RuntimeError,'cancel lane overlay'):prepare(*args,records,self.kernel(),cancel)
        self.assertEqual(args,before)
