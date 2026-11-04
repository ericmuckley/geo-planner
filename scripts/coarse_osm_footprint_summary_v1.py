"""Decode bounded native counters and derive explicit uncontracted upper bounds."""
import struct

from coarse_timing_input import require

TOTALS = ('nodes','taggedNodes','ways','highwayWays','nonHighwayWays','relations','restrictionRelations',
          'relationNodeMembers','relationWayMembers','relationRelationMembers',
          'restrictionNodeMembers','restrictionWayMembers','restrictionRelationMembers','taggedWays','taggedRelations',
          'allWayReferences','nonHighwayReferences','allWayPrimitiveEdges','nonHighwayPrimitiveEdges')
ROAD = ('ways','references','primitiveEdges','wayEndOccurrences','closedWays','longWays','maxReferences')
MAJOR = tuple(role+suffix for role in ('motorway','trunk','primary','secondary','tertiary') for suffix in ('','_link'))


def decode_histogram(body):
    require(isinstance(body,bytes) and 164<=len(body)<=2097152 and body[:4]==b'GPH1','Footprint histogram framing')
    position=4
    def numbers(count):
        nonlocal position
        require(position+count*8<=len(body),'Footprint truncated counters')
        values=struct.unpack_from('<'+'Q'*count,body,position);position+=8*count
        return values
    totals=dict(zip(TOTALS,numbers(len(TOTALS))));key_bytes=0;entries=0
    def mapping(fields):
        nonlocal position,key_bytes,entries
        require(position+4<=len(body),'Footprint truncated map')
        count=struct.unpack_from('<I',body,position)[0];position+=4;entries+=count
        require(entries<=4096,'Footprint map cap');result={};last=None
        for _ in range(count):
            require(position+4<=len(body),'Footprint truncated key length')
            size=struct.unpack_from('<I',body,position)[0];position+=4
            require(size<=4096 and position+size<=len(body),'Footprint key cap')
            raw=body[position:position+size];position+=size;key_bytes+=size
            require(key_bytes<=1048576 and (last is None or last<raw),'Footprint key bytes/order')
            last=raw;key=raw.decode('utf-8');result[key]=dict(zip(fields,numbers(len(fields))))
        return result
    roads=mapping(ROAD);restrictions=mapping(('node','way','relation'))
    require(position==len(body),'Footprint trailing histogram bytes')
    return {'totals':totals,'highwayRoles':roads,'restrictionMemberRoles':restrictions}


def profile(roads,roles=None):
    rows=[row for role,row in roads.items() if roles is None or role in roles]
    return {key:(max((row[key] for row in rows),default=0) if key=='maxReferences' else sum(row[key] for row in rows)) for key in ROAD}


def reconcile(histogram,receipt):
    t=histogram['totals'];roads=histogram['highwayRoles'];all_roads=profile(roads)
    for kind in ('node','way','relation'):
        require(t[kind+'s']==receipt['counts'].get(kind,0),'Footprint typed count reconciliation')
        require(t['tagged'+kind.title()+'s']<=t[kind+'s'],'Footprint tagged count')
    require(t['highwayWays']==all_roads['ways']==receipt['highwayWays'] and t['ways']==t['highwayWays']+t['nonHighwayWays'],'Footprint highway denominator')
    require(t['allWayReferences']==receipt['references']==all_roads['references']+t['nonHighwayReferences'],'Footprint full reference denominator')
    require(t['allWayPrimitiveEdges']==t['allWayReferences']-t['ways']==all_roads['primitiveEdges']+t['nonHighwayPrimitiveEdges'],'Footprint primitive edge denominator')
    for row in roads.values():
        require(row['ways']>0 and row['references']>=2*row['ways'] and row['primitiveEdges']==row['references']-row['ways'] and row['wayEndOccurrences']==2*row['ways'],'Footprint role accounting')
        require(max(row['closedWays'],row['longWays'])<=row['ways'] and 2<=row['maxReferences']<=65536,'Footprint role bounds')
    require(sum(t['relation'+kind.title()+'Members'] for kind in ('node','way','relation'))==receipt['members'],'Footprint member denominator')
    require(t['restrictionRelations']<=t['relations'],'Footprint restriction denominator')
    for kind in ('node','way','relation'):
        require(t['restriction'+kind.title()+'Members']==sum(row[kind] for row in histogram['restrictionMemberRoles'].values())<=t['relation'+kind.title()+'Members'],'Footprint restriction role accounting')
    return True


def storage_bounds(histogram):
    result={}
    for name,roles in (('all-highways',None),('major-roads',MAJOR)):
        counts=profile(histogram['highwayRoles'],roles);refs=counts['references'];edges=counts['primitiveEdges']
        # Unique nodes <= delivered references. Contraction edges <= primitive edges.
        result[name]={'counts':counts,'referenceIdSpoolBytes':8*refs,'degreeRecordSpoolBytes':16*refs,
            'rawRoutingArrayUpperBytes':12*refs+24*edges+4,
            'rawFullGeometryArrayUpperBytes':8*refs+12*edges+4,
            'routingAndGeometryUpperBytes':20*refs+36*edges+8,
            'u32IndicesSufficientForUpperBounds':max(refs,2*edges)<2**32,
            'scope':'Uncontracted conservative upper bounds; no unique-ID, contraction, compression, JS retained-memory or Vercel fit claim.'}
    return result
