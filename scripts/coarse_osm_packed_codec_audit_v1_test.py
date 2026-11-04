import gzip
import hashlib
import json
from pathlib import Path
import random
import struct
import tempfile
import unittest

from coarse_osm_packed_codec_audit_v1 import FILES,audit,decode


def reference_encode(raw,width,lanes):
    if width==1:return bytes(raw)
    modulus=1<<(8*width);previous=[0]*lanes;words=[]
    for i in range(len(raw)//width):
        word=int.from_bytes(raw[i*width:(i+1)*width],'little');lane=i%lanes;delta=(word-previous[lane])%modulus
        if delta>=modulus//2:delta-=modulus
        previous[lane]=word;words.append(2*delta if delta>=0 else -2*delta-1)
    return bytes((word>>(plane*8))&255 for plane in range(width) for word in words)


class CodecAuditTests(unittest.TestCase):
    def test_independent_golden_u16(self):
        self.assertEqual(decode(bytes([2,4,1,5,0,0,0,0]),2,1),struct.pack('<4H',1,3,2,65535))

    def test_signed_coordinate_axis_wrap(self):
        values=[0xfffffffe,0xffffffff,2,1];encoded=bytes((v>>(8*p))&255 for p in range(4) for v in values)
        self.assertEqual(decode(encoded,4,2),struct.pack('<4i',2147483647,-2147483648,-2147483648,2147483647))

    def test_seeded_all_word_and_lane_types(self):
        randomizer=random.Random(20261102)
        for width in (1,2,3,4):
            for lanes in (1,2):
                raw=bytes(randomizer.getrandbits(8) for _ in range(10000*width))
                self.assertEqual(decode(reference_encode(raw,width,lanes),width,lanes),raw)

    def test_malformed_length_or_layout(self):
        for data,width,lanes in [(b'x',3,1),(b'xxxx',4,2),(b'',5,1),(b'',2,3)]:
            with self.assertRaises(AssertionError):decode(data,width,lanes)

    def fixture(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name)
        source=root/'source';(source/'routing').mkdir(parents=True);codec=root/'codec';(codec/'fields').mkdir(parents=True)
        manifest={'format':'packed-integer-delta-byteplanes-gzip-v1','fields':{}};roster={}
        for name in FILES:
            width=4 if name.endswith(('.i32','.u32')) else 3 if name.endswith('.u24') else 2 if name.endswith('.u16') else 1
            lanes=2 if name=='xy.i32' else 1;raw=bytes(width*lanes);compressed=gzip.compress(reference_encode(raw,width,lanes))
            key='routing/'+name;(source/key).write_bytes(raw);file='fields/'+name+'.gz';(codec/file).write_bytes(compressed)
            pin=hashlib.sha256(raw).hexdigest();roster[key]={'bytes':len(raw),'sha256':pin}
            manifest['fields'][key]={'wordBytes':width,'lanes':lanes,'file':file,'rawBytes':len(raw),'rawSha256':pin,'compressedBytes':len(compressed),'compressedSha256':hashlib.sha256(compressed).hexdigest()}
        (codec/'manifest.json').write_text(json.dumps(manifest));return source,codec,roster,manifest

    def test_complete_roster_compared(self):
        source,codec,roster,_=self.fixture();self.assertEqual(audit(source,codec,roster)['fields'],13)

    def replace(self,codec,manifest,raw):
        row=manifest['fields']['routing/xy.i32'];path=codec/row['file'];path.write_bytes(raw)
        row['compressedBytes']=len(raw);row['compressedSha256']=hashlib.sha256(raw).hexdigest();(codec/'manifest.json').write_text(json.dumps(manifest))

    def test_truncated_gzip_refused(self):
        source,codec,roster,manifest=self.fixture();row=manifest['fields']['routing/xy.i32'];raw=(codec/row['file']).read_bytes()
        self.replace(codec,manifest,raw[:-4])
        with self.assertRaises((EOFError,OSError,AssertionError)):audit(source,codec,roster)

    def test_decoded_surplus_bounded_and_refused(self):
        source,codec,roster,manifest=self.fixture();self.replace(codec,manifest,gzip.compress(bytes(9)))
        with self.assertRaises(AssertionError):audit(source,codec,roster)

    def test_unknown_roster_or_layout_refused(self):
        source,codec,roster,manifest=self.fixture();manifest['fields']['routing/xy.i32']['lanes']=1
        (codec/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaises(AssertionError):audit(source,codec,roster)
        manifest['fields']['extra']={};(codec/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaises(AssertionError):audit(source,codec,roster)


if __name__=='__main__':unittest.main()
