"""Read-only whole-country typed-fact/accounting audit; never decode the source PBF."""
from array import array
from bisect import bisect_left
from collections import Counter
import hashlib,json,struct,time
from pathlib import Path

HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2]
ROOT=REPO/'data/coarse-quality/us-osm-car-capacity-run-v2'
ROLE_NAMES=['motorway','motorway_link','trunk','trunk_link','primary','primary_link','secondary','secondary_link','tertiary','tertiary_link']
REASONS=['eligible','outside-major-profile','vehicle-ferry','access','area-ford-driveway-parking','conditional-or-way-restriction','lane-access','unsupported-oneway','unsupported-speed','directional-access']

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def load(path):return json.loads(path.read_bytes())
def audit():
    began=time.monotonic();result=load(ROOT/'result.json');receipt=load(ROOT/'receipt.json');roster=load(ROOT/'artifacts.json')
    for name,pin in roster.items():
        path=ROOT/name;assert path.is_file() and not path.is_symlink() and path.stat().st_size==pin['bytes'] and sha(path)==pin['sha256']
    closed=array('Q');closed.frombytes((ROOT/'way-facts/unsupported-member-ways.u64').read_bytes());assert all(a<b for a,b in zip(closed,closed[1:])) and all(0<n<2**63 for n in closed)
    missing=array('Q');missing.frombytes((ROOT/'way-facts/unlocatable-restrictions.u64').read_bytes());assert len(missing)==result['unlocatableRestrictions'] and all(a<b for a,b in zip(missing,missing[1:]))
    counts=Counter();reasons=Counter();roles=Counter();pre=Counter();post=Counter();previous=0
    files=sorted((ROOT/'way-facts').glob('ways-*.bin'));assert files
    for path in files:
        data=path.read_bytes();assert len(data)%32==0 and len(data)<=16777216
        for identity,first,last,segments,flags in struct.iter_unpack('<QQQII',data):
            assert previous<identity<=receipt['maxWayId'] and 0<first<=receipt['maxNodeId'] and 0<last<=receipt['maxNodeId']
            previous=identity;assert flags>>16==0
            direction,defaults,role,reason=flags&3,(flags>>2)&3,(flags>>4)&15,(flags>>8)&255
            assert role<10 and reason<10 and reason!=1 and bool(direction)==(reason==0)
            assert reason in (0,9) or defaults==0
            is_closed=bisect_left(closed,identity)
            is_closed=is_closed<len(closed) and closed[is_closed]==identity
            nd=int(bool(direction&1))+int(bool(direction&2));df=int(bool(direction&defaults&1))+int(bool(direction&defaults&2))
            counts['rows']+=1;counts['segments']+=segments;counts['preArcs']+=segments*nd;counts['postArcs']+=0 if is_closed else segments*nd
            counts['selectedClosedWays']+=is_closed;counts['eligibleWays']+=bool(nd);counts['eligiblePostWays']+=bool(nd and not is_closed)
            counts['directionSlots']+=nd;counts['defaultSlots']+=df;counts['defaultArcs']+=segments*df
            reasons[REASONS[reason]]+=1;roles[ROLE_NAMES[role]]+=1;pre[ROLE_NAMES[role]]+=segments*nd
            post[ROLE_NAMES[role]]+=0 if is_closed else segments*nd
        assert time.monotonic()-began<600
    assert counts['rows']==result['wayFactRows']==result['majorWays']==4227238 and counts['rows']*32==result['wayFactBytes']==135271616
    assert counts['segments']==result['nonzeroLineageSegments'] and counts['segments']+result['zeroNativeLinks']==result['lineageSegmentsIncludingZero']==6674747
    for key,other in [('preArcs','preClosureArcs'),('postArcs','postLocatableClosureArcs'),('selectedClosedWays','selectedMemberWays'),('eligibleWays','eligibleWaysBeforeClosures'),('eligiblePostWays','eligibleWaysAfterLocatableClosures'),('directionSlots','eligibleDirectionSlotsBeforeClosures'),('defaultSlots','defaultSpeedDirectionSlotsBeforeClosures'),('defaultArcs','preClosureDefaultSpeedArcs')]:assert counts[key]==result[other],key
    assert len(closed)==result['uniqueUnsupportedMemberWays']<=result['unsupportedWayMemberOccurrences']
    assert sum(result['wayReasons'].values())==receipt['ways']==162688797
    assert result['wayReasons']['outside-major-profile']==receipt['ways']-result['majorWays']
    for name in REASONS:
        if name!='outside-major-profile':assert reasons[name]==result['wayReasons'][name],name
    for name in ROLE_NAMES:
        assert roles[name]==receipt['histogram']['highwayRoles'][name]['ways']
        assert pre[name]==result['preClosureArcsByRole'][name] and post[name]==result['postLocatableClosureArcsByRole'][name]
    assert result['relations']==result['unsupportedRelations']+result['supportedViaNodeRules']+result['nonCarRelations']+result['unrelatedRelations']+result['unlocatableRestrictions']==1624265
    assert result['nodes']==1606229364 and result['maximumNativeNodeId']==receipt['maxNodeId']==14319708500
    assert result['allTaggedNodes']==receipt['histogram']['totals']['taggedNodes']==48142518
    assert result['majorReferences']==48163649 and result['primitiveEdges']==43936411 and result['partitionSplitsConsumed']==2447509
    assert result['routingBaseBytesPreClosures']==13*5731903+7*counts['preArcs']+4
    assert result['routingBaseBytesAfterLocatableClosures']==13*5731903+7*counts['postArcs']+4
    assert counts['postArcs']<=counts['preArcs']<=2*6674747<2**24
    assert receipt['nativeEof'] and receipt['pythonProjectionFrames']==0 and receipt['semanticSha256']=='209cc5927bdd36c667277afd06a4ba301c753797dbf518de7df84e78301d9b16'
    assert not any(result[k] for k in ('nationalGraphBuilt','etaQualified','vercelQualified','modelChanged','networkRequests','applicationDbReads'))
    return {'status':'independent_complete_car_capacity_fact_audit_passed','auditorSha256':sha(Path(__file__)),'resultSha256':sha(ROOT/'result.json'),'artifactsSha256':sha(ROOT/'artifacts.json'),
            'wayRowsChecked':counts['rows'],'factFiles':len(files),'preClosureArcsChecked':counts['preArcs'],'postLocatableClosureArcsChecked':counts['postArcs'],
            'unlocatableRestrictions':len(missing),'policyFullyLocatable':not missing,
            'method':'Every typed source-way fact, flag, role histogram, closure membership and both directed-arc sums; compare complete original source seals/counters. No native producer or source PBF replay. Pure-policy equivalence and original source guards are separately qualified.',
            'secondsIncludingAllFactHashesAndAccounting':time.monotonic()-began,'sourcePbfReads':0,'nativeLibraryExecutions':0,'networkRequests':0,'applicationDbReads':0,'nationalGraphBuilt':False,'modelChanged':False}
