"""Independent bounded Python decoder for the frozen TypeScript storage codec."""
import gzip
import hashlib
import json
from pathlib import Path
import time

FILES=['xy.i32','offsets.u24','targets.u24','costs.u16','cost-overflow-arcs.u24',
       'cost-overflow-ticks.u32','reverse.u8','reverse-overflow-arcs.u24',
       'reverse-overflow-targets.u24','node-flags.u8','forbidden-turns.u24','cell-keys.u24','cell-offsets.u24']


def decode(encoded,width,lanes):
    assert width in (1,2,3,4) and lanes in (1,2) and len(encoded)<=67108864 and len(encoded)%(width*lanes)==0
    if width==1:return bytes(encoded)
    count=len(encoded)//width;mask=(1<<(8*width))-1;previous=[0]*lanes;out=bytearray(len(encoded))
    for i in range(count):
        value=0
        for plane in range(width):value+=encoded[plane*count+i]<<(8*plane)
        delta=-(value//2)-1 if value&1 else value//2
        lane=i%lanes;word=(previous[lane]+delta)&mask;previous[lane]=word
        for byte in range(width):out[width*i+byte]=(word>>(8*byte))&255
    return out


def audit(source,codec,roster):
    began=time.monotonic();source=Path(source);codec=Path(codec)
    manifest=json.loads((codec/'manifest.json').read_bytes())
    assert manifest['format']=='packed-integer-delta-byteplanes-gzip-v1'
    fields=manifest['fields'];assert set(fields)=={'routing/'+name for name in FILES}
    total=compressed_total=0
    for name in FILES:
        key='routing/'+name;row=fields[key];pin=roster[key]
        width=4 if name.endswith(('.i32','.u32')) else 3 if name.endswith('.u24') else 2 if name.endswith('.u16') else 1
        lanes=2 if name=='xy.i32' else 1
        assert (row['wordBytes'],row['lanes'])==(width,lanes)
        assert row['file']=='fields/'+name+'.gz' and row['rawBytes']==pin['bytes']<=67108864 and row['rawSha256']==pin['sha256']
        path=codec/row['file'];original=source/key
        assert path.is_file() and not path.is_symlink() and path.stat().st_size==row['compressedBytes']<=67108864
        assert original.is_file() and not original.is_symlink() and original.stat().st_size==pin['bytes']
        compressed=path.read_bytes();assert hashlib.sha256(compressed).hexdigest()==row['compressedSha256']
        with gzip.open(path,'rb') as stream:encoded=stream.read(row['rawBytes']+1)
        assert len(encoded)==row['rawBytes']
        decoded=decode(encoded,width,lanes);raw=original.read_bytes()
        assert decoded==raw and hashlib.sha256(decoded).hexdigest()==pin['sha256'],name
        total+=len(decoded);compressed_total+=len(compressed)
        assert total<=201326592 and compressed_total<=201326592
    return {'status':'independent_complete_storage_codec_all_bytes_passed','fields':len(fields),
            'bytesIndependentlyDecodedAndCompared':total,'compressedBytes':compressed_total,
            'secondsIndependentDecodeAndComparison':time.monotonic()-began,
            'sourcePbfReads':0,'sourceConstructorExecutions':0,'nativeLibraryExecutions':0,
            'appOrEtaQualified':False}
