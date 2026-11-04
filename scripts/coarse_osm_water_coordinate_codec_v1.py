"""Streaming exact E7 coordinate format/oracle, not a qualified national worker.

Each present row stores positive native-ID delta and zigzag X/Y deltas. Missing
IDs remain a separate explicit stream. No coordinate quantization is added.
"""
import struct

from coarse_timing_input import require

MAGIC=b'WXY1'


def uint(value):
    require(type(value) is int and 0<=value<2**64,'Water coordinate unsigned integer')
    out=bytearray()
    while value>=128:out.append((value&127)|128);value>>=7
    out.append(value);return bytes(out)


def encode_rows(rows):
    yield MAGIC
    previous=x=y=0
    for identity,next_x,next_y in rows:
        require(type(identity) is int and previous<identity<2**63 and type(next_x) is int and type(next_y) is int and
                -1800000000<=next_x<=1800000000 and -900000000<=next_y<=900000000,'Water coordinate row order/domain/E7 range')
        dx,dy=next_x-x,next_y-y
        yield uint(identity-previous)+uint(2*dx if dx>=0 else -2*dx-1)+uint(2*dy if dy>=0 else -2*dy-1)
        previous,x,y=identity,next_x,next_y


def decode_rows(chunks):
    header=bytearray();value=shift=field=previous=x=y=0;delta_id=delta_x=0
    for raw in chunks:
        require(isinstance(raw,bytes) and 0<len(raw)<=1048576,'Water coordinate encoded chunk cap/type')
        for byte in raw:
            if len(header)<4:
                header.append(byte)
                require(MAGIC.startswith(header),'Water coordinate format header')
                continue
            require(shift<64 and (shift!=63 or byte<=1),'Water coordinate integer overflow')
            value|=(byte&127)<<shift
            if byte&128:shift+=7;continue
            require(shift==0 or byte!=0,'Water coordinate canonical integer')
            if field==0:delta_id=value
            elif field==1:delta_x=value//2 if value%2==0 else -(value//2)-1
            else:
                delta_y=value//2 if value%2==0 else -(value//2)-1
                identity=previous+delta_id;next_x=x+delta_x;next_y=y+delta_y
                require(0<delta_id and identity<2**63 and -1800000000<=next_x<=1800000000 and -900000000<=next_y<=900000000,'Water coordinate decoded order/domain/E7 range')
                yield identity,next_x,next_y
                previous,x,y=identity,next_x,next_y
            field=(field+1)%3;value=shift=0
    require(bytes(header)==MAGIC and field==0 and shift==0,'Water coordinate complete stream EOF')


def typed_rows(rows):
    for identity,x,y in rows:yield struct.pack('<Qii',identity,x,y)


def verify_partition(requested_ids,present_rows,missing_ids):
    present=iter(present_rows);missing=iter(missing_ids)
    current=next(present,None);absent=next(missing,None);previous=total=found=lost=0
    for identity in requested_ids:
        require(type(identity) is int and previous<identity<2**63,'Water coordinate requested-ID order/domain')
        have=current is not None and current[0]==identity
        lack=absent==identity
        require(have!=lack,'Water coordinate exact present/missing partition')
        if have:found+=1;current=next(present,None)
        else:lost+=1;absent=next(missing,None)
        previous=identity;total+=1
    require(current is None and absent is None,'Water coordinate partition EOF')
    return {'requested':total,'present':found,'missing':lost}
