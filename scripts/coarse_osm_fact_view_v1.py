"""Compose a complete read-only native fact view from closed field groups.

Returns metadata for Docker file binds; it never copies, links or reads data.
A replaced field uses only its complete overlay group, including a shorter tail.
"""
from pathlib import PurePosixPath
import re

REPLACED=frozenset({'ways','arcs','flags'})
WIDTHS={'ids':8,'xy':4,'anchors':4,'flags':1,'geometry':4,'ways':32,'arcs':32,'turns':40,'closures':8}


def groups(record):
    root=record['root'];assert isinstance(root,str);p=PurePosixPath(root)
    assert isinstance(root,str) and root.startswith('data/coarse-quality/') and not p.is_absolute() and '..' not in p.parts
    result={}
    for name,pin in record['roster'].items():
        if not name.startswith('cost-facts/'):continue
        match=re.fullmatch(r'cost-facts/([a-z][a-z-]*)-([0-9]{4})\.bin',name);assert match,name
        prefix,part=match.group(1),int(match.group(2))
        size=pin['bytes'];digest=pin['sha256']
        assert type(size) is int and 0<size<=16777216 and re.fullmatch('[0-9a-f]{64}',digest)
        if prefix in WIDTHS:assert size%WIDTHS[prefix]==0
        result.setdefault(prefix,[]).append((part,name,pin))
    assert result
    for rows in result.values():
        rows.sort();assert [row[0] for row in rows]==list(range(len(rows)))
        assert all(pin['bytes']==16777216 for _,_,pin in rows[:-1])
    return result


def compose(base,overlay):
    old,new=groups(base),groups(overlay)
    assert set(new)==REPLACED and REPLACED<=set(old),'Exactly complete ways/arcs/flags overrides required'
    result={'format':'geo-planner-readonly-native-fact-view-v1','nativeRoot':'/facts/cost-facts','files':{},'fields':{}}
    for prefix in sorted(old):
        replacement=prefix in REPLACED;record=overlay if replacement else base;rows=new[prefix] if replacement else old[prefix]
        result['fields'][prefix]={'source':'overlay' if replacement else 'base','files':len(rows),'bytes':sum(pin['bytes'] for _,_,pin in rows)}
        for _,name,pin in rows:
            target='/facts/cost-facts/'+PurePosixPath(name).name;assert target not in result['files']
            result['files'][target]={'source':record['root']+'/'+name,'bytes':pin['bytes'],'sha256':pin['sha256']}
    assert set(result['fields'])==set(old)
    for prefix in ('ways','flags'):assert result['fields'][prefix]['bytes']==sum(row[2]['bytes'] for row in old[prefix])
    return result
