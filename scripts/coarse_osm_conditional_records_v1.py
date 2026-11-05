"""Decode bounded changed source ID/tag records; coordinates are absent."""
import struct
from pathlib import Path


def read_records(filename):
    path=Path(filename);assert path.is_file() and not path.is_symlink() and path.stat().st_size<=48*1048576
    count=0;previous=None
    with path.open('rb') as stream:
        while head:=stream.read(4):
            assert len(head)==4;size=struct.unpack('<I',head)[0];assert 20<=size<=8388608
            body=stream.read(size);assert len(body)==size and body[:4]==b'CST1' and body[4]<2 and body[5:8]==bytes(3)
            kind=body[4];identity,n=struct.unpack_from('<QI',body,8);assert 0<identity<=2**63-1 and n<=65536
            key=(kind,identity);assert previous is None or key>previous;previous=key
            count+=1;assert count<=250000
            tags={};cursor=20
            def text():
                nonlocal cursor
                assert cursor+4<=size;length=struct.unpack_from('<I',body,cursor)[0];cursor+=4
                assert length<=size-cursor;value=body[cursor:cursor+length].decode('utf8');cursor+=length;return value
            last=None
            for _ in range(n):
                k,v=text(),text();assert last is None or k>last;last=k;tags[k]=v
            assert cursor==size
            yield {'type':'node' if kind==0 else 'way','id':identity,'tags':tags}
