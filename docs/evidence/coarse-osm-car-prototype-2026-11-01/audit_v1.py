"""Independent source-SQLite car-policy/primitive-state/compact-array audit.

No car graph producer, compact codec, payload reader or lineage builder is imported.
"""
from array import array
from collections import Counter,defaultdict
import hashlib,heapq,json,math,sqlite3,struct,time
from pathlib import Path

from import_roads import DEFAULT_SPEEDS,TURN_KINDS,access_allowed,speed_kph
from barrier_policy import barrier_decision
from coverage_census import directions

HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2]
CAR=REPO/'data/coarse-quality/us-osm-car-run-v1';LINEAGE=REPO/'data/coarse-quality/us-osm-lineage-run-v1'
DB=REPO/'data/coarse-quality/us-osm-disk-capture-run-v1/extract/audit-selected.sqlite'

def load(p):return json.loads(p.read_bytes())
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def arr(p,code):
    a=array(code);a.frombytes(p.read_bytes());return a

def speeds(p):
    if p.get('route')=='ferry' or p.get('ferry') not in (None,'no','false','0') or not directions(p):return None,None
    role=p['highway'];oneway=p.get('oneway:motorcar',p.get('oneway:motor_vehicle',p.get('oneway')))
    if oneway is None:oneway='yes' if role=='motorway' or p.get('junction') in ('roundabout','circular') else 'no'
    f=speed_kph(p.get('maxspeed:forward',p.get('maxspeed')),DEFAULT_SPEEDS[role]);b=speed_kph(p.get('maxspeed:backward',p.get('maxspeed')),DEFAULT_SPEEDS[role])
    return (f if oneway!='-1' and access_allowed(p,'forward') else None,b if oneway in ('no','0','false','-1') and access_allowed(p,'backward') else None)

def relation(e):
    p=e['tags'];m=e['members'];typ=p.get('type','');mode=typ.partition(':')[2];excepts={v.strip() for v in p.get('except','').split(';')}
    if not typ.startswith('restriction'):return 'unrelated',None
    if excepts&{'motorcar','motor_vehicle','vehicle'} or mode and mode not in ('motorcar','motor_vehicle','vehicle'):return 'non-car',None
    kind=next((p[k] for k in ('restriction:motorcar','restriction:motor_vehicle','restriction:vehicle','restriction') if k in p),None)
    cond={'restriction:conditional','restriction:motorcar:conditional','restriction:motor_vehicle:conditional','restriction:vehicle:conditional'}
    if kind is None and not cond.intersection(p) and any(k.startswith('restriction:') for k in p):return 'non-car',None
    f=[v['ref'] for v in m if v['type']=='way' and v['role']=='from'];t=[v['ref'] for v in m if v['type']=='way' and v['role']=='to'];v=[v['ref'] for v in m if v['type']=='node' and v['role']=='via']
    if len(m)==3 and len(f)==len(t)==len(v)==1 and kind in TURN_KINDS and not any(k.endswith(':conditional') for k in p) and (f[0]!=t[0] or kind.endswith(('u_turn','straight_on'))):return 'via-node',(f[0],v[0],t[0],kind)
    return 'closed-unsupported',None

def rule_allows(in_way,out_way,reversal,rules):
    alternatives=[]
    for _,_,to,kind in rules:
        matches=out_way==to
        if in_way==to:matches=matches and (reversal if kind.endswith('u_turn') else not reversal)
        if kind.startswith('only_'):alternatives.append(matches)
        elif matches:return False
    return not alternatives or any(alternatives)

def milliseconds(a,b,speed):
    # Separate distance implementation over the original source coordinates.
    x1,y1,x2,y2=map(math.radians,(*a,*b));h=math.sin((y2-y1)/2)**2+math.cos(y1)*math.cos(y2)*math.sin((x2-x1)/2)**2
    return max(1,math.ceil(6371008.8*2*math.asin(math.sqrt(min(1,h)))*3600/speed))

class Raw:
    def __init__(self,ids,flags,rules):
        self.ids=ids;self.flags=flags;self.rules=rules;self.arcs=[];self.out=defaultdict(list);self.reverse={};self.work=0
    def add(self,tail,head,way,part,direction,ms):
        i=len(self.arcs);self.arcs.append((tail,head,way,part,direction,ms));self.out[tail].append(i);self.reverse[way,part,direction]=i
    def query(self,source,target):
        if source==target:return 0
        labels={i:self.arcs[i][5] for i in self.out[source]};queue=[(cost,i) for i,cost in labels.items()];heapq.heapify(queue)
        while queue:
            cost,i=heapq.heappop(queue)
            if cost!=labels[i]:continue
            self.work+=1;assert self.work<=40000000
            _,head,way,part,direction,_=self.arcs[i]
            if head==target:return cost
            flag=self.flags[head]
            if flag&1:continue
            for j in self.out[head]:
                _,_,out_way,_,_,ms=self.arcs[j];reversal=self.reverse.get((way,part,-direction))==j
                if reversal and not flag&4 or not rule_allows(way,out_way,reversal,self.rules.get((way,self.ids[head]),())):continue
                new=cost+ms+(5000 if flag&2 else 0)+(20000 if reversal else 0)
                if new<labels.get(j,math.inf):labels[j]=new;heapq.heappush(queue,(new,j));assert len(queue)<=1000000
        return None

def self_test():
    assert speeds({'highway':'primary','oneway':'-1'})==(None,55)
    assert speeds({'highway':'primary','route':'ferry'})==(None,None)
    assert speeds({'highway':'primary','access:conditional':'yes @ Mo'})==(None,None)
    assert speeds({'highway':'primary','maxspeed:forward':'25 mph'})==(40.2336,55)
    rules=[(1,2,3,'only_right_turn')];assert rule_allows(1,3,False,rules) and not rule_allows(1,4,False,rules)
    assert not rule_allows(1,1,True,[(1,2,1,'no_u_turn')]) and rule_allows(1,1,False,[(1,2,1,'no_u_turn')])
    g=Raw([1,2,3],bytearray([4,6,4]),{});g.add(0,1,1,0,1,1000);g.add(1,2,1,1,1,1000);assert g.query(0,2)==7000 and g.query(2,0) is None
    g.flags[1]=1;assert g.query(0,2) is None and g.query(0,1)==1000
    return {'checks':8,'successful':True}

def audit():
    began=time.monotonic();assert self_test()['successful'];report=load(CAR/'report.json');parent=load(LINEAGE/'report.json');pins=load(LINEAGE/'artifacts.json');payload=load(CAR/'artifacts.json');closure=load(HERE/'car-closed-run-v1.json')
    for root,roster in ((LINEAGE,pins),(CAR,payload)):
        for name,pin in roster.items():assert (root/name).stat().st_size==pin['bytes'] and sha(root/name)==pin['sha256']
    assert all(closure['roster'][name]['sha256']==pin['sha256'] for name,pin in payload.items())
    capture=load(REPO/'docs/evidence/coarse-osm-extraction-2026-10-30/disk-capture-closed-run-v1.json');pin=capture['roster']['extract/audit-selected.sqlite'];assert DB.stat().st_size==pin['bytes'] and sha(DB)==pin['sha256']
    db=sqlite3.connect(DB.as_uri()+'?mode=ro&immutable=1',uri=True);db.execute('PRAGMA query_only=ON');db.execute('PRAGMA cache_size=-16384')
    selected=arr(LINEAGE/'provenance/selected-nodes.u32','I');all_ids=array('q',(row[0] for row in db.execute("SELECT id FROM objects WHERE kind='node' ORDER BY id")));assert len(all_ids)==1123919
    ids=array('q',(all_ids[i] for i in selected));index={identity:i for i,identity in enumerate(ids)};flags=bytearray(len(ids));xy=arr(LINEAGE/'geometry/xy.i32','i');node_counts=Counter()
    for i,identity in enumerate(ids):
        e=json.loads(db.execute("SELECT raw FROM objects WHERE kind='node' AND id=?",(identity,)).fetchone()[0]);p=e['tags'];assert [round(e['lon']*1e7),round(e['lat']*1e7)]==list(xy[2*i:2*i+2]);blocked=not access_allowed(p) or any(k.endswith(':conditional') for k in p) or bool(p.get('barrier') and not barrier_decision(p)['open'])
        flags[i]=(1 if blocked else 0)|(2 if p.get('highway')=='traffic_signals' else 0)|(4 if p else 0);node_counts['selectedTaggedNodes']+=bool(p);node_counts['selectedBlockedNodes']+=bool(blocked);node_counts['selectedSignalNodes']+=p.get('highway')=='traffic_signals'
    rules=defaultdict(list);closed=set();closed_nodes=set();rel_counts=Counter()
    for _,raw in db.execute("SELECT id,raw FROM objects WHERE kind='relation' ORDER BY id"):
        e=json.loads(raw)
        for member in e['members']:
            if member['type']=='node' and member['ref'] in index:flags[index[member['ref']]]|=4
        status,rule=relation(e);rel_counts['relations:'+status]+=1
        if rule is not None:rules[rule[:2]].append(rule)
        if status=='closed-unsupported':
            ways={m['ref'] for m in e['members'] if m['type']=='way'};closed.update(ways)
            if not ways:closed_nodes.update(m['ref'] for m in e['members'] if m['type']=='node')
    ways={};degree=array('I',[0])*len(ids);ends=set();roles=set(report['policy']['roles'])
    for identity,raw in db.execute("SELECT id,raw FROM objects WHERE kind='way' ORDER BY id"):
        e=json.loads(raw)
        if e['tags'].get('highway') not in roles:continue
        refs=[index[n] for n in e['nodes']];ends.update((refs[0],refs[-1]));ways[identity]=(refs,speeds(e['tags']))
        for a,b in zip(refs,refs[1:]):degree[a]+=1;degree[b]+=1
    for i,d in enumerate(degree):
        if d!=2 or i in ends:flags[i]|=4
    for identity in closed_nodes:
        if identity in index:flags[index[identity]]|=1
    assert len(ways)==report['selectedWays']==28995 and len(ids)==report['selectedNativeNodes']==143560
    for k,v in (node_counts|rel_counts).items():assert report['sourceMetadata'][k]==v,(k,v)
    assert report['sourceMetadata']['unsupportedMemberWaysPresent']==sum(w in ways for w in closed)
    anchors_global=arr(LINEAGE/'provenance/vertices.u32','I');ordinals={n:i for i,n in enumerate(selected)};anchors=[ordinals[n] for n in anchors_global];vertex={n:i for i,n in enumerate(anchors)}
    assert (CAR/'routing/node-flags.u8').read_bytes()==bytes(flags[n] for n in anchors)
    raw=Raw(ids,flags,rules);prefixes={}
    for identity,(refs,ss) in ways.items():
        pp={}
        for direction,speed in zip((1,-1),ss):
            sums=[0]
            if speed is not None:
                for part,(a,b) in enumerate(zip(refs,refs[1:])):
                    ms=0 if a==b else milliseconds([xy[2*a]/1e7,xy[2*a+1]/1e7],[xy[2*b]/1e7,xy[2*b+1]/1e7],speed);sums.append(sums[-1]+ms)
                    if a!=b and identity not in closed:raw.add(a if direction==1 else b,b if direction==1 else a,identity,part,direction,ms)
            pp[direction]=sums
        prefixes[identity]=pp
    edges=list(struct.iter_unpack('<QIIIId',(LINEAGE/'provenance/edges.bin').read_bytes()));shape=arr(LINEAGE/'geometry/nodes.u32','I');go=arr(LINEAGE/'geometry/offsets.u32','I');expected=[]
    for edge,(way,first,last,a,b,_) in enumerate(edges):
        refs,ss=ways[way];chain=refs[first:last+1];assert chain==list(shape[go[edge]:go[edge+1]]) and chain[0]==anchors[a] and chain[-1]==anchors[b]
        if way in closed:continue
        for direction,speed in zip((1,-1),ss):
            if speed is None or chain[0]==chain[-1] and all(n==chain[0] for n in chain):continue
            p=prefixes[way][direction];cost=p[last]-p[first];expected.append((chain[0] if direction==1 else chain[-1],chain[-1] if direction==1 else chain[0],way,edge,direction,cost))
    expected.sort(key=lambda a:(a[0],a[3],-a[4]));offset=arr(CAR/'routing/offsets.u32','I');targets=arr(CAR/'routing/targets.u32','I');words=arr(CAR/'routing/costs.u16','H');overflow=dict(zip(arr(CAR/'routing/cost-overflow-arcs.u32','I'),arr(CAR/'routing/cost-overflow-ticks.u32','I')));reverse=(CAR/'routing/reverse.u8').read_bytes();rev_overflow=dict(zip(arr(CAR/'routing/reverse-overflow-arcs.u32','I'),arr(CAR/'routing/reverse-overflow-targets.u32','I')))
    assert len(expected)==len(targets)==len(words)==len(reverse)==report['contractedArcs'] and len(raw.arcs)==report['rawArcs']
    by_key={(a[3],a[4]):i for i,a in enumerate(expected)};out=defaultdict(list);expected_pairs=[]
    for i,(tail,head,way,edge,direction,ms) in enumerate(expected):
        assert offset[vertex[tail]]<=i<offset[vertex[tail]+1] and targets[i]==vertex[head]
        assert (overflow[i] if words[i]==65535 else words[i])==(ms+124)//125
        rev=by_key.get((edge,-direction));actual=None if reverse[i]==255 else rev_overflow[i] if reverse[i]==254 else offset[vertex[head]]+reverse[i];assert rev==actual
        out[tail].append(i)
    for i,(tail,head,way,edge,direction,_) in enumerate(expected):
        for j in out[head]:
            out_way=expected[j][2];reversal=by_key.get((edge,-direction))==j
            if not flags[head]&1 and not(reversal and not flags[head]&4) and not rule_allows(way,out_way,reversal,rules.get((way,ids[head]),())):expected_pairs.extend((i,j))
    assert arr(CAR/'routing/forbidden-turns.u32','I')==array('I',expected_pairs)
    assert len(report['queries'])==82 and len(parent['queries'])==41
    for i,q in enumerate(report['queries']):
        original=parent['queries'][i//2];native=list(reversed(original['sourceNodeIds'])) if i%2 else original['sourceNodeIds'];assert q['sourceNodeIds']==native and q['windowId']==original['windowId'] and q['reverseOfOriginal']==bool(i%2)
        result=raw.query(*(index[n] for n in native));assert result==q['raw']['costMs']==q['contracted']['costMs'],(i,result,q['raw']['costMs'])
    db.close();assert time.monotonic()-began<600
    return {'status':'independent_source_static_car_audit_passed','auditorSha256':sha(Path(__file__)),'reportSha256':sha(CAR/'report.json'),'closedSha256':sha(HERE/'car-closed-run-v1.json'),
            'sourceWaysChecked':len(ways),'sourceNativeNodesChecked':len(ids),'sourceRelationsChecked':sum(rel_counts.values()),'rawArcsChecked':len(raw.arcs),'contractedArcCostsAndReverseIdentitiesChecked':len(expected),'nodeFlagsChecked':len(anchors),'forbiddenTurnPairsChecked':len(expected_pairs)//2,'originalPairsChecked':41,'directionalQueriesChecked':82,'independentSettles':raw.work,
            'selfTests':self_test(),'secondsIncludingSQLiteHashesSourcePoliciesArraysQueries':time.monotonic()-began,'method':'Separate sealed readonly SQLite; existing independent reference policy helpers; independent distance/source-way primitives and incoming-arc Dijkstra; every compact cost/reverse/flag/forbidden pair checked. No producer/codec/payload imports.',
            'sourcePbfReads':0,'networkRequests':0,'applicationDbReads':0,'etaQualified':False,'nationalArtifactBuilt':False,'vercelQualified':False,'modelChanged':False}
