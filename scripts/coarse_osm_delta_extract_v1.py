"""Synthetic two-pass integration of the native delta codec; validator remains Python."""
from copy import deepcopy
import hashlib

from coarse_osm_bulk import Run, Selection, heap_size, records
from coarse_osm_stream_v1 import Audit
from coarse_osm_delta_v1 import Index, Storage
from coarse_osm_records import canonical, intersects, normalize
from coarse_osm_validation_v4 import checked_records
from coarse_timing_input import digest, require


def extract(reader, proposal, root, *, codec, blocks_per_shard=512, primary_hook=None):
    """Synthetic/raw-record prototype. The full-source native launcher is absent."""
    run = Run(root, proposal)
    state = proposal['source']['proposedPublisherReplicationStateUtc']
    run.state['publisherStateUtc'] = state
    storage = Storage(run.caps['workingBytesIncludingTmp'] - run.caps['tmpBytes'] - 8388608, run.caps['sqliteIndexBytesEach'])
    first = Index(run.root / 'primary-index', storage, codec=codec, blocks_per_shard=blocks_per_shard, index_limit=run.caps['sqliteIndexBytesEach'])
    second = None
    hashes = []
    try:
        primary = Selection(proposal['windows'], run)
        for_pass = hashlib.sha256()
        for raw in checked_records(reader, run, state, 'primary-selection'):
            for_pass.update(canonical(raw) + b'\n')
            if raw['type'] == 'node':
                first.add(raw)
                continue
            first.finish()
            if raw['type'] == 'way' and 'highway' in (raw.get('tags') or {}):
                normalize(raw, state, run.caps['singleNormalizedElementBytes'])
                points = first.points(raw['nodes'])
                for window in proposal['windows']:
                    if intersects(points, window['bbox']):
                        primary.add(window['id'], ('way', raw['id']))
                        for identity in raw['nodes']:
                            primary.add(window['id'], ('node', identity))
                if ('way', raw['id']) in primary.keys:
                    primary.ways[raw['id']] = deepcopy(raw)
                    run.charge(heap_size((raw['id'], raw)) + 256)
        first.finish()
        hashes.append(for_pass.hexdigest())
        if primary_hook is not None:
            primary_hook(primary)
        audit = Audit(proposal, run)
        second = Index(run.root / 'audit-index', storage, codec=codec, blocks_per_shard=blocks_per_shard, index_limit=run.caps['sqliteIndexBytesEach'], replacing=first)
        for_pass = hashlib.sha256()
        for raw in checked_records(reader, run, state, 'materialize-independent-audit'):
            for_pass.update(canonical(raw) + b'\n')
            key = raw['type'], raw['id']
            if key[0] == 'node':
                second.add(raw)
                if key in primary.keys:
                    audit.keep(raw)
            else:
                second.finish()
            if key[0] == 'way' and 'highway' in (raw.get('tags') or {}):
                audit.way(raw, second)
            if key[0] == 'relation' and (raw.get('tags') or {}).get('type') == 'restriction':
                audit.relation(raw)
                for window in primary.members:
                    if any((m['type'], m['ref']) in primary.members[window] and m['type'] in ('node', 'way') for m in raw['members']):
                        primary.add(window, key)
            if key in primary.keys:
                if key[0] == 'way':
                    require(raw == primary.ways[raw['id']], 'Primary way drift')
                primary.keep(raw)
        second.finish()
        hashes.append(for_pass.hexdigest())
        require(hashes[0] == hashes[1], 'Two-pass full-record drift')
        require(set(audit.objects) == audit.keys, 'Audit missing/extra materialization hints')
        require(set(primary.objects) == primary.keys, 'Primary dependency closure')
        run.state['windowOccurrences'] = primary.occurrences
        path = run.root / 'elements.jsonl'
        with path.open('xb') as output:
            for row in records(primary, state):
                line = canonical(row) + b'\n'
                require(len(line) <= run.caps['singleNormalizedElementBytes'] and run.state['extractBytes'] + len(line) <= run.caps['normalizedExtractBytes'], 'Two-pass output byte cap')
                run.check()
                output.write(line)
                run.state['extractBytes'] += len(line)
                run.state['retainedElements'] += 1
        audit.compare(path)
        require(len(run.state['passes']) == 2 and all(p['status'] == 'eof' and p['counts'] == run.state['passes'][0]['counts'] for p in run.state['passes']), 'Two-pass EOF/count drift')
        run.state.update(status='passed_native_delta_index_synthetic', independentAuditComplete=True, outputSha256=digest(path),
            sourceRecordHashes=hashes, coordinateStoragePeakBytes=storage.peak,
            coordinateStorageLiveBytes=storage.live, wholeExtractionQualified=False,nativeMetadataValidationQualified=False,indexFormat='block-id-delta-xy32-v1')
    except Exception as error:
        run.state.update(status='stopped', errorType=type(error).__name__, error=str(error), independentAuditComplete=False, derivedIndexesTrusted=False)
    finally:
        first.close()
        if second is not None:
            second.close()
    run.checkpoint()
    return run.state
