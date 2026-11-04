"""Audit saved way endpoints and relation chains, without PBF or coordinates."""
from collections import Counter
import gzip
import json
from pathlib import Path

from coarse_osm_water_endpoints_v1 import extract,audit,ROW,relation_chains
from coarse_osm_water_reference_store_v1 import Budget,Shards,Reader
from coarse_timing_input import require


def relations(path):
    total=count=0
    with gzip.open(path,'rb') as stream:
        while raw:=stream.readline(8*1048576+1):
            total+=len(raw);count+=1
            require(raw.endswith(b'\n') and len(raw)<=8*1048576 and total<=64*1048576 and count<=70000,'Water endpoint relation metadata cap')
            yield json.loads(raw)


def output_rows(reader):
    pending=b''
    while raw:=reader.read(1048576):
        lines=(pending+raw).split(b'\n');pending=lines.pop()
        for line in lines:
            require(0<len(line)<=1048576,'Water endpoint diagnostic row cap')
            yield json.loads(line)
        require(len(pending)<=1048576,'Water endpoint diagnostic pending bound')
    require(not pending and reader.finished,'Water endpoint diagnostic exact EOF')


def replay_chains(source,result,facts):
    require(source['id']==result['relationId'] and not result['polygonValidityEstablished'],'Water endpoint source relation identity/scope')
    if result['status']!='explicit_role_degree2_closed_chains':return 0
    members=[m for m in source['members'] if m['type']=='way']
    require(not any(m['type']=='relation' for m in source['members']) and all(m['role'] in ('outer','inner') for m in members),'Water endpoint independent raw-role eligibility')
    require(len({m['ref'] for m in members})==len(members) and result['outer']['closedChains'],'Water endpoint independent member multiplicity/outer')
    checked=0
    for role in ('outer','inner'):
        expected={m['ref'] for m in members if m['role']==role};seen=set()
        for chain in result[role]['closedChains']:
            first=last=None;require(chain,'Water endpoint independent nonempty chain')
            for identity,direction in chain:
                require(identity in expected and identity not in seen and direction in (-1,1),'Water endpoint independent source member/direction')
                row=facts.lookup(identity);require(row is not None,'Water endpoint independent complete source way')
                _,head,tail,_=row
                if direction==-1:head,tail=tail,head
                if first is None:first=head
                else:require(head==last,'Water endpoint independent native-ID continuation')
                last=tail;seen.add(identity);checked+=1
            require(last==first,'Water endpoint independent native-ID closed chain')
        require(seen==expected,'Water endpoint independent every source role member exact')
    return checked


def analyze(root,way_root,way_report,member_ids,relation_sources,check=lambda:None):
    root=Path(root)
    with Reader(way_root,way_report) as reader:
        facts,captured=extract(reader,member_ids,check);require(reader.finished,'Water endpoint source GPF EOF')
    with Reader(way_root,way_report) as reader:
        independently_checked=audit(reader,facts,check);require(reader.finished,'Water endpoint independent source GPF EOF')
    endpoint_writer=Shards(root,'member-way-endpoints',Budget(16*1048576));buffer=bytearray()
    try:
        for row in facts.rows():
            buffer.extend(row)
            if len(buffer)==1048576:endpoint_writer.write(bytes(buffer));buffer.clear()
        if buffer:endpoint_writer.write(bytes(buffer))
        endpoint_report=endpoint_writer.finish()
    finally:endpoint_writer.close()
    with Reader(root,endpoint_report) as reader:
        for row in facts.rows():require(reader.read(ROW.size)==row,'Water endpoint every serialized field independently reopened')
        require(not reader.read(1) and reader.finished,'Water endpoint serialized facts EOF')
    writer=Shards(root,'relation-chain-diagnostics',Budget(32*1048576));counts={True:Counter(),False:Counter()};seen=set()
    try:
        for is_root,path in relation_sources:
            for row in relations(path):
                check();require(row['id'] not in seen,'Water endpoint unique complete relation input');seen.add(row['id'])
                result=relation_chains(row,facts)|{'rootWaterRelation':is_root};counts[is_root][result['status']]+=1
                raw=(json.dumps(result,separators=(',',':'),allow_nan=False)+'\n').encode()
                require(len(raw)<=1048576,'Water endpoint bounded relation-chain output');writer.write(raw)
        chain_report=writer.finish()
    finally:writer.close()
    replayed=checked_members=0
    with Reader(root,chain_report) as reader:
        outputs=iter(output_rows(reader))
        for is_root,path in relation_sources:
            for row in relations(path):
                check();result=next(outputs,None);require(result is not None and result['rootWaterRelation']==is_root,'Water endpoint independent diagnostic population/order')
                checked_members+=replay_chains(row,result,facts);replayed+=1
        require(next(outputs,None) is None and reader.finished,'Water endpoint independent all diagnostics EOF')
    return {'captured':captured,'independentEndpointAudit':independently_checked,'endpointStore':endpoint_report,'chainStore':chain_report,
            'rootStatusCounts':dict(counts[True]),'additionalStatusCounts':dict(counts[False]),
            'allRelationDiagnosticsReopened':replayed,'explicitRoleChainMemberOccurrencesIndependentlyReplayed':checked_members,
            'compressedBytes':endpoint_report['compressedBytes']+chain_report['compressedBytes'],
            'sourcePbfReads':0,'coordinatesExamined':False,'polygonValidityEstablished':False,'maskOrModelChanged':False}
