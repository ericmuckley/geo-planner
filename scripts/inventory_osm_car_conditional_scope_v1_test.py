"""Captured selector completeness and immutable source metadata are enforced."""
from array import array
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from inventory_osm_car_conditional_scope_v1 import inventory,selected_ordinals


class InventoryTests(unittest.TestCase):
    def test_all_selected_tags_are_classified_without_source_writes(self):
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'source.sqlite';db=sqlite3.connect(path)
            db.execute('CREATE TABLE objects (kind TEXT,id INTEGER,raw TEXT,PRIMARY KEY(kind,id))')
            items=[('node',1,{'hgv:conditional':'no @ night'}),('node',2,{'motorcar:conditional':'no @ night'}),('node',3,{'foot:conditional':'no @ night','access':'no'}),('way',10,{'highway':'secondary','hgv:conditional':'no @ night'}),('way',11,{'highway':'residential','bicycle:conditional':'no @ night'})]
            db.executemany('INSERT INTO objects VALUES (?,?,?)',[(kind,identity,json.dumps({'tags':tags,'lat':1,'lon':2}).encode('utf8')) for kind,identity,tags in items]);db.commit();db.close()
            before=hashlib.sha256(path.read_bytes()).hexdigest();records=[]
            r=inventory(path,[0,2],{'node':3,'way':2,'majorWays':1},records.append)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)
            self.assertEqual(r['counts']['nodeMetadataClassified'],2);self.assertEqual(r['counts']['wayMetadataClassified'],1)
            self.assertEqual(r['counts']['nodeNewPositive'],1);self.assertEqual(r['counts']['wayNewPositive'],1)
            self.assertEqual(len(records),3);self.assertTrue(all('lat' not in row and 'lon' not in row for row in records))
            with self.assertRaises(AssertionError):inventory(path,[0,0],{'node':3,'way':2,'majorWays':1},lambda _:None)
            with self.assertRaises(AssertionError):inventory(path,[0,2],{'node':4,'way':2,'majorWays':1},lambda _:None)

    def test_ordinal_bytes_cannot_be_truncated(self):
        self.assertEqual(list(selected_ordinals(bytes.fromhex('0000000002000000'))),[0,2])
        with self.assertRaises(AssertionError):selected_ordinals(b'123')


if __name__=='__main__':unittest.main()
