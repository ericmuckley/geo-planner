"""Bounded national cost facts using the already qualified native constructor."""
from array import array
import hashlib
import json
from pathlib import Path
import time

from coarse_osm_car_cost_graph_v1 import CostGraph
from coarse_timing_input import require
from run_osm_car_capacity_v3 import SOURCE, SCAN, PRIOR

ARTIFACT_SHA = '96f23e4b81646ec824a30ca1ccc1763664184bc2ae5f3a4e1c42ebcdb1f9d30e'
ARTIFACT_PATH = 'data/coarse-quality/us-osm-car-cost-graph-build-v1/car-cost-graph.so'
STREAM_ROOT = 'data/coarse-quality/us-osm-topology-run-v1/streams'
REFERENCES = [f'{STREAM_ROOT}/refs-{i:04}.bin' for i in range(25)]
TAGS = [f'{STREAM_ROOT}/tagged-{i:04}.bin' for i in range(6)]
RELATION_NODES = STREAM_ROOT+'/sorted-relation-nodes-0000.bin'
EXPECTED = {'reference_count': 48163649, 'way_count': 4227238, 'tag_count': 48142518,
            'maximum': 14319708500, 'selected': 42993567, 'anchors': 5731903}
REPORT = 'docs/evidence/coarse-osm-car-capacity-2026-11-01'
COMPARISONS = {
    PRIOR: '/inputs/original-source-summary.json',
    'docs/evidence/coarse-osm-national-footprint-2026-11-01/raw-run-v1/receipt.json': '/inputs/footprint-receipt.json',
    REPORT+'/capacity-raw/run-v3/result.json': '/inputs/capacity-result.json',
    REPORT+'/capacity-raw/run-v3/receipt.json': '/inputs/capacity-receipt.json',
    REPORT+'/graph-raw/controls-v1/controls.json': '/inputs/constructor-controls.json',
    REPORT+'/graph-capture-raw/audit-v5/audit.json': '/inputs/captured-audit.json',
}


def required_mounts():
    return COMPARISONS | {name: '/inputs/topology/'+Path(name).name for name in REFERENCES+TAGS+[RELATION_NODES]} | {
        SOURCE['path']: '/inputs/country.pbf', ARTIFACT_PATH: '/artifacts/car-cost-graph.so'}


def validate(plan):
    require(plan['phase'] == 'national_native_car_cost_facts_v1' and plan['sourceDescription'] == SOURCE and plan['scanCaps'] == SCAN,
            'Country cost exact source/scan configuration')
    require(plan['artifactSha256'] == ARTIFACT_SHA, 'Country cost qualified native artifact')
    require(plan['topology'] == {'references': REFERENCES, 'tags': TAGS, 'relationNodes': RELATION_NODES, 'expected': EXPECTED},
            'Country cost exact complete typed topology')
    for name, destination in required_mounts().items():
        require(plan['mounts'].get(name) == destination, 'Country cost missing required input mount: '+name)
        if name != SOURCE['path']:
            require(name in plan['hostFiles'] and len(plan['hostFiles'][name]) == 64, 'Country cost missing required input seal: '+name)
    require(SOURCE['path'] not in plan['hostFiles'], 'Country source authenticated inside guarded scan, never an extra host hash pass')


def save(root, name, value):
    raw = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
    require(len(raw) <= 2097152 and Path(name).name == name, 'Country cost bounded metadata record')
    with (root/name).open('xb') as stream:stream.write(raw)


def run(plan, work, check=lambda: None):
    validate(plan)
    began = time.monotonic()
    load = lambda name: json.loads(Path('/inputs/'+name).read_bytes())
    # Every comparison is parsed before the large source/index construction.
    prior = load('original-source-summary.json')['receipt']
    footprint = load('footprint-receipt.json');capacity = load('capacity-result.json');capacity_receipt = load('capacity-receipt.json')
    controls = load('constructor-controls.json');captured = load('captured-audit.json')
    require(controls == {'tests': 83, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}, 'Country constructor Linux qualification')
    require(captured['queries']['originalDirectionalCases'] == 82 and captured['queries']['unreachableCasesPreserved'] == 14 and
            captured['queries']['exactRawCostsAllMatch'] and captured['queries']['quantizedCostsNeverWorse'] and
            captured['selectedNativeCoordinatesChecked'] == 143560, 'Country captured source/query qualification')
    require(capacity_receipt['nativeEof'] and capacity_receipt['sourceIdentity']['sourceSha256'] == SOURCE['sha256'] and
            capacity_receipt['semanticSha256'] == SOURCE['semanticSha256'], 'Country original complete source binding')
    source = Path('/inputs/country.pbf');require(source.stat().st_size == SOURCE['bytes'], 'Country cost exact source byte length')
    relations = array('Q');relations.frombytes(Path('/inputs/topology/'+Path(RELATION_NODES).name).read_bytes())
    require(len(relations) == 1201443, 'Country complete relation-node metadata denominator')
    output = work/'cost-facts';output.mkdir()
    save(work, 'preflight-inputs.json', {'constructorTests': 83, 'capturedOriginalQueries': 82, 'sourceSha256': SOURCE['sha256'],
                                       'typedTopology': EXPECTED, 'comparisonInputsParsedBeforeSource': True})
    engine = CostGraph('/artifacts/car-cost-graph.so', ARTIFACT_SHA, aggregate_visits=1770542426)
    try:
        preparing = time.monotonic()
        engine.begin([Path('/inputs/topology/'+Path(n).name) for n in REFERENCES],
                     [Path('/inputs/topology/'+Path(n).name) for n in TAGS], relations, output, **EXPECTED)
        preparation_seconds = time.monotonic()-preparing
        save(work, 'prepared.json', {'secondsNativeIndexAndTypedSourcePreparation': preparation_seconds,
                                     'sourceGuardedScanStarted': False, 'ordinaryPythonNationalSourceObjects': 0})
        scanning = time.monotonic()
        last_progress = scanning
        def scan_check():
            nonlocal last_progress
            check();now = time.monotonic()
            if now-last_progress >= 15:
                print(json.dumps({'guardedSourceScanSeconds': now-scanning, 'sourceProgress': engine.progress()}), flush=True)
                last_progress = now
        receipt = engine.scan(source, SOURCE['state'], SCAN, source=SOURCE, check=scan_check, fallback=False)
        scan_seconds = time.monotonic()-scanning
        save(work, 'receipt.json', receipt)
        require(receipt['nativeEof'] and receipt['pythonProjectionFrames'] == 0 and receipt['counts'] ==
                {'node': 1606229364, 'way': 162688797, 'relation': 1624265}, 'Country cost complete source/zero-projection receipt')
        require(receipt['semanticSha256'] == SOURCE['semanticSha256'] and receipt['sourceIdentity'] == capacity_receipt['sourceIdentity'] and
                receipt['metadata'] == prior['metadata'] and receipt['histogram'] == footprint['histogram'], 'Country cost exact original source seals/metadata/histogram')
        for key in ('references', 'members', 'tags', 'tagUtf8Bytes', 'maxReferences', 'maxMembers', 'maxTags', 'highwayWays', 'examinedHighwayReferences'):
            require(receipt[key] == prior[key], 'Country cost original source counter: '+key)
        facts = engine.finish()
    finally:
        if engine.last is not None and not (work/'receipt.json').exists():save(work, 'partial-receipt.json', engine.last)
        engine.release()
    expected = {'selectedNodes': 42993567, 'selectedCoordinatesSeen': 42993567, 'anchors': 5731903,
                'majorWays': 4227238, 'majorReferences': 48163649, 'nonzeroLineageSegments': 6674747,
                'preClosureArcs': 9837326, 'postClosureArcs': 9620680, 'supportedViaNodeRules': 409178,
                'unsupportedRelations': 70376, 'unsupportedWayMemberOccurrences': 189854,
                'uniqueUnsupportedMemberWays': 149699, 'invalidUnlocatableRestrictions': 2,
                'allTaggedNodes': 48142518, 'allSignalNodes': 548448, 'allBlockedNodes': 3347883}
    require(all(facts[key] == value for key, value in expected.items()), 'Country cost unchanged complete capacity/profile')
    require(facts['wayReasons'] == capacity['wayReasons'] and facts['preClosureArcsByRole'] == capacity['preClosureArcsByRole'] and
            facts['postClosureArcsByRole'] == capacity['postLocatableClosureArcsByRole'], 'Country cost all permission/direction/role capacity counts')
    save(work, 'fact-summary.json', facts)
    artifacts = {}
    for path in sorted(output.iterdir()):
        check()
        with path.open('rb') as stream:pin = hashlib.file_digest(stream, 'sha256').hexdigest()
        artifacts[str(path.relative_to(work))] = {'bytes': path.stat().st_size, 'sha256': pin}
    save(work, 'artifacts.json', artifacts)
    return {'status': 'passed_guarded_national_native_geometry_cost_facts', 'facts': facts,
            'secondsNativePreparation': preparation_seconds,
            'secondsGuardedSourceScanIncludingFramingFullNativeGuardsAndConstruction': scan_seconds,
            'secondsIncludingInputBindingsPreparationSourceConstructionFinishAndOutputHashes': time.monotonic()-began,
            'guardedSourceScanInvocations': 1, 'ordinaryPythonNationalSourceObjects': 0,
            'independentDerivedAuditPending': True, 'appCsrReverseTurnPairsBuilt': False,
            'etaQualified': False, 'vercelQualified': False, 'modelChanged': False, 'networkRequests': 0, 'applicationDbReads': 0}
