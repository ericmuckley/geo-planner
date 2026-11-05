"""Every conditional-speed candidate is preserved, including unsupported values."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from inventory_osm_car_conditional_speed_v1 import inventory


class SpeedInventoryTests(unittest.TestCase):
    def test_supported_and_unknown_speed_records_survive_complete_readonly_census(self):
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'source.sqlite';db=sqlite3.connect(path)
            db.execute('CREATE TABLE objects (kind TEXT,id INTEGER,raw BLOB,PRIMARY KEY(kind,id))')
            items=[('node',1,{'hgv:conditional':'no @ night'}),('node',2,{'motorcar:conditional':'no @ night'}),('node',3,{'foot:conditional':'no @ night','access':'no'}),('way',10,{'highway':'secondary','maxspeed:conditional':'20 @ wet'}),('way',11,{'highway':'residential'}),('way',12,{'highway':'primary','maxspeed:conditional':'signals @ wet'})]
            db.executemany('INSERT INTO objects VALUES (?,?,?)',[(kind,identity,json.dumps({'tags':tags,'lat':1,'lon':2}).encode()) for kind,identity,tags in items]);db.commit();db.close()
            before=hashlib.sha256(path.read_bytes()).hexdigest();records=[]
            result=inventory(path,[0,2],{'node':3,'way':3,'majorWays':2},records.append)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)
            self.assertEqual(len(records),4);self.assertEqual(result['counts']['wayNewPositive'],1)
            self.assertEqual(result['counts']['wayStaticSpeedPriced'],1);self.assertEqual(result['counts']['waySpeedUnsupported'],1)
            rows={row['id']:row for row in records};self.assertEqual(rows[10]['after']['forward'],20)
            self.assertEqual(rows[12]['conditionalSpeedStatus'],'unsupported');self.assertFalse(rows[12]['eligibilityGained'])
            self.assertTrue(all('lat' not in row and 'lon' not in row for row in records))

    def test_every_source_ordinal_must_be_accounted_for(self):
        with self.assertRaises(AssertionError):inventory(Path('/not-opened'),[2,1],{'node':3,'way':0,'majorWays':0},lambda _:None)


if __name__=='__main__':unittest.main()
