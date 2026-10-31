"""Diagnostic driver isolation and exact packed-member size controls."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import diagnose_osm_member_v2 as diagnostic
from coarse_osm_records import canonical
from coarse_osm_native_smoke import field, varint


def pack(number,wire,value):
    return field(number,value)


class Tests(unittest.TestCase):
    def test_input_names_cannot_replace_owned_container_name(self):
        with tempfile.TemporaryDirectory() as folder:
            repo=Path(folder);(repo/'scripts').mkdir();source=repo/'scripts/input.py';source.write_bytes(b'fixture')
            (repo/'data/coarse-quality').mkdir(parents=True)
            plan={'output':diagnostic.OUTPUT,'inputs':{'scripts/input.py':hashlib.sha256(source.read_bytes()).hexdigest()},
                  'mounts':{},'source':{'path':'source.pbf'}}
            recipe=repo/'recipe.json';recipe.write_text(json.dumps(plan))
            pin=hashlib.sha256(recipe.read_bytes()).hexdigest()
            rejected=subprocess.CompletedProcess([],1,'','intentional create refusal')
            with patch.object(diagnostic,'__file__',str(repo/'scripts/diagnose.py')), patch.object(diagnostic.subprocess,'run',return_value=rejected) as run, patch('prepare_osm_native_lock_v1.cleanup_owned'), patch('prepare_osm_native_lock_v1.settle_error'):
                self.assertEqual(diagnostic.driver(recipe,pin),2)
            args=run.call_args_list[0].args[0]
            name=args[args.index('--name')+1]
            self.assertRegex(name,r'^geo-planner-member-diag-[0-9a-f]{12}$')
            self.assertIn('--network=none',args)
            self.assertIn('--memory=4g',args)
            self.assertIn('--read-only',args)

    def test_packed_members_exact_fast_canonical_size(self):
        # Two zigzag deltas: +5, -2, with roles containing escaped text.
        raw=pack(1,0,31)+pack(4,2,pack(1,0,2)+pack(2,0,1700000000))+pack(8,2,varint(1)+varint(2))+pack(9,2,varint(10)+varint(3))+pack(10,2,varint(1)+varint(0))
        strings=[b'',b'outer',b'a"\\b']
        row,full=diagnostic.decode_relation(raw,strings,1000)
        _,fast=diagnostic.decode_relation(raw,strings,1000,materialize=False)
        self.assertEqual(fast,full)
        self.assertEqual(full['canonicalBytes'],len(canonical(row)))
        self.assertEqual([m['ref'] for m in row['members']],[5,3])
        self.assertEqual(full['invalidMemberIdentitiesOrTypes'],0)


if __name__=='__main__':unittest.main()
