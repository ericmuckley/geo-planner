"""Lossless native-OSM facts for later review; no permissions or timing costs."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import math
import re

from coarse_osm_records import canonical,normalize
from coarse_timing_input import require

RECORD_LIMIT=1024**2
SPEED=re.compile(r'([0-9]+(?:\.[0-9]+)?)(?: (mph|km/h))?')
ANNOTATIONS={'maxspeed:type','maxspeed:reason'}
ROAD_ROLES={'motorway','trunk','primary','secondary','tertiary','residential','living_street','unclassified','service'}
ACCESS=('access','vehicle','motor_vehicle','motorcar')


def numeric_speed(raw):
    result={'raw':raw,'status':'missing','kmh':None,'sourceUnit':None,'usableForTiming':False}
    if raw is None:return result
    require(isinstance(raw,str),'Native speed tag type')
    if len(raw)>256:return result|{'status':'unrecognized'}
    match=SPEED.fullmatch(raw)
    if match is None:return result|{'status':'unrecognized'}
    value=Decimal(match[1]);unit=match[2] or 'km/h'
    kmh=float(value*(Decimal('1.609344') if unit=='mph' else 1))
    if not math.isfinite(kmh) or kmh<=0:return result|{'status':'nonpositive_or_nonfinite'}
    return result|{'status':'plain_numeric','kmh':kmh,'sourceUnit':unit}


def family(tags,names):
    return {key:value for key,value in tags.items() if any(key==name or key.startswith(name+':') for name in names)}


def validate_record(record,snapshot):
    require(isinstance(record,dict) and len(canonical(record))<=RECORD_LIMIT,'Native attribute record bound')
    require(record.get('publisherStateUtc')==snapshot,'Native attribute snapshot drift')
    element=record.get('element');normalize(element,snapshot,RECORD_LIMIT)
    require(element['id']<2**63 and hashlib.sha256(canonical(element)).hexdigest()==record.get('elementSha256'),'Native attribute typed identity/field seal')
    windows=record.get('windowIds')
    require(isinstance(windows,list) and 0<len(windows)<=21 and all(isinstance(w,str) and 0<len(w)<=128 for w in windows) and len(set(windows))==len(windows),'Native attribute window identity')
    return element


def way_facts(record,nodes,*,snapshot):
    way=validate_record(record,snapshot)
    require(way['type']=='way' and 2<=len(way['nodes'])<=65536 and all(type(n) is int and 0<n<2**63 for n in way['nodes']),'Native attribute ordered way references')
    ordered=[];hashes=[];barriers=[]
    for identity in way['nodes']:
        require(identity in nodes,'Native attribute missing geometry node')
        node=validate_record(nodes[identity],snapshot)
        require(node['type']=='node' and node['id']==identity,'Native attribute node identity drift')
        ordered.append(node);hashes.append(nodes[identity]['elementSha256'])
        if (node.get('tags') or {}).get('barrier') is not None:barriers.append(identity)
    require(hashlib.sha256(canonical([snapshot,ordered])).hexdigest()==record.get('geometryDependencySha256'),'Native attribute geometry dependency drift')
    tags=way['tags'];role=tags['highway'];scopes={k:v for k,v in tags.items() if k.startswith('maxspeed:') and k not in ANNOTATIONS}
    speed=numeric_speed(tags.get('maxspeed'))
    return {'format':'native-osm-road-facts-v1','sourceRecord':deepcopy(record),
            'coordinates':[[node['lon'],node['lat']] for node in ordered],'orderedNodeElementSha256':hashes,
            'highway':role,'roadRoleSupportedForLaterScreen':role in ROAD_ROLES or role.removesuffix('_link') in {'motorway','trunk','primary','secondary','tertiary'},
            'speed':speed,'speedScopeTags':scopes,'plainNumericWithoutSpeedScopes':speed['status']=='plain_numeric' and not scopes,
            'accessTags':family(tags,ACCESS),'directionTags':family(tags,('oneway',)),
            'structureTags':family(tags,('layer','level','bridge','tunnel','location','junction','construction','proposed')),
            'barrierNodeIds':barriers,'carPermission':'unreviewed','usableForTiming':False}
