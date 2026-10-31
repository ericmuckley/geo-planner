"""Pinned artifact acquisition and bounded, private-URI-free receipts."""
import gzip
import hashlib
import http.client
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tarfile
import time
from urllib.parse import urlsplit

from coarse_osm_input import NativeResponse, absolute_timeout
from coarse_osm_native_lock_v1 import save, image_digest
from coarse_osm_native_lock_v2 import endpoint as blob_endpoint, public_uri, config_url
from coarse_osm_records import strict_json
from coarse_timing_input import PilotError, json_bytes, require

GIB = 1073741824
CAPS = {'attempts': 52, 'builderBodyBytes': 2*GIB, 'sourceBodyBytesEach': 134217728,
    'sourceBodyBytesTotal': 268435456, 'totalBodyBytes': 2415919104, 'requestSeconds': 120,
    'idleSeconds': 15, 'hostSeconds': 1800, 'workSeconds': 1740, 'tmpBytes': 268435456,
    'compressedBytes': 2*GIB, 'expandedBytes': 10*GIB, 'buildBytes': GIB, 'sourceBytes': GIB,
    'metadataReserveBytes': 268435456, 'reportBytes': 2097152, 'fileBytes': GIB,
    'entries': 250000, 'headerBytes': 67108864, 'sourceExpandedBytes': 536870912}
LOCK = 'docs/evidence/coarse-osm-native-lock-v2-2026-10-27/raw/acquire/lock.json'
LOCK_SHA = '424a4eb0c547844186534df099dd6efc52752a86a525fdad900bea04c134a216'


def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def source_url(source):
    return 'https://codeload.github.com/' + source['repository'] + '/tar.gz/' + source['commit']


def load_lock(path):
    require(sha(path) == LOCK_SHA, 'Build metadata lock drift')
    lock = strict_json(Path(path).read_bytes())
    require(len(lock['image']['layers']) == len(lock['image']['diffIds']) == 25, 'Build layer closure')
    require(lock['image']['platform'] == 'linux/arm64' and len(lock['sources']) == 2, 'Build platform/source closure')
    return lock


class Transport:
    def open(self, url, kind, headers, seconds):
        p = urlsplit(url)
        connection = http.client.HTTPSConnection(p.hostname, 443, timeout=min(seconds, CAPS['idleSeconds']))
        try:
            connection.request('GET', p.path + ('?' + p.query if p.query else ''), headers={
                'User-Agent': 'geo-planner-native-build/1', 'Accept-Encoding': 'identity', 'Connection': 'close', **headers})
            return NativeResponse(connection, connection.getresponse())
        except BaseException:
            connection.close()
            raise PilotError('Artifact connection failed; private details omitted') from None


class Download:
    def __init__(self, root, lock, *, transport=None, caps=CAPS, clock=time.monotonic, alarm=absolute_timeout):
        self.root = Path(root); self.root.mkdir()
        self.lock, self.caps, self.clock, self.alarm = lock, caps, clock, alarm
        self.transport = transport or Transport()
        self.events, self.bytes, self.builder_bytes, self.source_bytes = [], 0, 0, 0
        self.started, self.stopped = clock(), False
        self.checkpoint()

    def checkpoint(self):
        value = {'events': self.events, 'receivedBodyBytes': self.bytes, 'builderBodyBytes': self.builder_bytes,
            'sourceBodyBytes': self.source_bytes, 'stopped': self.stopped, 'elapsedSeconds': self.clock()-self.started,
            'scope': 'Delivered read1/IncompleteRead.partial payload, excluding headers/TLS/socket buffering. Redirect/error/unverified layer bytes and signed URL values never persisted.'}
        raw = json_bytes(value); require(len(raw) <= self.caps['reportBytes'], 'Download ledger cap')
        (self.root/'ledger.partial').write_bytes(raw); (self.root/'ledger.partial').replace(self.root/'ledger.json')

    def check(self):
        require(not self.stopped and self.clock()-self.started < self.caps['workSeconds'], 'Download stopped/deadline')

    def fetch(self, url, kind, identity):
        self.check()
        source = kind == 'archive'
        if source:
            require(identity in self.lock['sources'] and url == source_url(identity), 'Unlisted source archive')
            p = urlsplit(url)
            public = {'scheme': p.scheme, 'host': p.hostname, 'path': p.path, 'queryParameterNames': [],
                'urlBytes': len(url.encode()), 'urlSha256': hashlib.sha256(url.encode()).hexdigest(), 'queryValuesRedacted': True}
            maximum = self.caps['sourceBodyBytesEach']
        else:
            require(identity in self.lock['image']['layers'], 'Unlisted layer identity')
            require(kind in ('origin', 'cdn'), 'Unlisted artifact protocol')
            public = public_uri(url, 'config' if kind == 'origin' else 'cdn', identity)
            maximum = identity['size'] if kind == 'cdn' else max(identity['size'], 65536)
        require(len(self.events) < self.caps['attempts'], 'Artifact attempt cap')
        remaining = min(self.caps['totalBodyBytes']-self.bytes,
            self.caps['sourceBodyBytesTotal']-self.source_bytes if source else self.caps['builderBodyBytes']-self.builder_bytes)
        require(remaining > 0, 'Artifact aggregate body cap')
        event = {'number': len(self.events)+1, 'kind': kind, 'requestUri': public, 'status': None,
            'bodyBytes': 0, 'bodyFile': None, 'outcome': 'started'}
        self.events.append(event); self.checkpoint()
        response, location, stage = None, None, 'connection'
        body, hashed = bytearray(), hashlib.sha256()
        def receive(chunk, retain):
            require(isinstance(chunk, bytes), 'Nonbinary artifact response')
            self.bytes += len(chunk); event['bodyBytes'] += len(chunk)
            if source: self.source_bytes += len(chunk)
            else: self.builder_bytes += len(chunk)
            hashed.update(chunk)
            if retain: body.extend(chunk)
        seconds = min(self.caps['requestSeconds'], self.caps['workSeconds']-(self.clock()-self.started))
        try:
            with self.alarm(seconds):
                response = self.transport.open(url, kind, {'Accept': 'application/octet-stream'}, seconds)
                require(type(response.status) is int and 100 <= response.status <= 599, 'Artifact status')
                event['status'] = response.status; stage = 'headers'
                selected, seen = {}, set()
                for key, value in response.headers:
                    require(isinstance(key, str) and isinstance(value, str) and len(value) <= 4096, 'Artifact header bound')
                    key = key.lower()
                    if key not in ('location','content-length','content-encoding','transfer-encoding'): continue
                    require(key not in seen, 'Duplicate artifact header'); seen.add(key)
                    if key == 'location':
                        event['redirectReceipt'] = {'urlBytes': len(value.encode()), 'urlSha256': hashlib.sha256(value.encode()).hexdigest(), 'queryValuesRedacted': True}
                        require(kind == 'origin' and response.status == 302, 'Artifact redirect refused')
                        event['redirectReceipt'] = public_uri(value, 'cdn', identity)
                        location = value
                    else:
                        if key == 'content-length': require(re.fullmatch(r'[0-9]{1,20}', value), 'Artifact length')
                        elif key == 'content-encoding': require(value.lower() in ('','identity'), 'Artifact encoding')
                        else: require(value.lower() == 'chunked', 'Artifact framing')
                        selected[key] = value
                event['headers'] = selected
                require(not ('content-length' in selected and 'transfer-encoding' in selected), 'Conflicting artifact framing')
                expected = int(selected['content-length']) if 'content-length' in selected else None
                good = response.status == 200
                allowed = min(maximum if good else 65536, remaining)
                require(expected is None or expected <= allowed, 'Declared artifact cap')
                if good and not source:
                    require(expected == identity['size'], 'Layer declared size required')
                stage = 'body'
                next_checkpoint = 1048576
                while expected is None or event['bodyBytes'] < expected:
                    self.check(); size = min(1048576, allowed-event['bodyBytes'])
                    require(size > 0, 'Artifact cap before known EOF')
                    try: chunk = response.read1(size)
                    except http.client.IncompleteRead as error:
                        require(len(error.partial) <= size, 'Artifact partial bound')
                        receive(error.partial, good)
                        raise PilotError('Truncated artifact') from None
                    require(len(chunk) <= size, 'Artifact read bound')
                    if not chunk: break
                    receive(chunk, good)
                    if event['bodyBytes'] >= next_checkpoint:
                        self.checkpoint(); next_checkpoint = event['bodyBytes']+1048576
                require(expected is None or expected == event['bodyBytes'], 'Truncated artifact body')
                stage = 'identity'
                if good:
                    if not source:
                        require(len(body) == identity['size'] and 'sha256:'+hashed.hexdigest() == identity['digest'], 'Layer size/digest')
                    filename = f'{event["number"]:03d}.bin'
                    with (self.root/filename).open('xb') as stream: stream.write(body)
                    event['bodyFile'] = filename
                event['outcome'] = 'body_complete'
            return (self.root/event['bodyFile'] if event['bodyFile'] else None), response.status, location
        except Exception as error:
            self.stopped = True
            event.update(outcome='stopped', errorType=type(error).__name__, stopStage=stage, error='Artifact response refused; private details omitted')
            raise PilotError('Artifact response refused at '+stage+'; private details omitted') from None
        finally:
            try:
                if response is not None:
                    with self.alarm(2): response.close()
            except Exception:
                self.stopped = True; event['closeError'] = 'Artifact close failed; private details omitted'
                raise PilotError('Artifact close failed; private details omitted') from None
            finally:
                event['bodySha256'] = hashed.hexdigest(); event['privateBodyRedacted'] = event['bodyFile'] is None
                self.checkpoint()


def acquire(root, lock, **kwargs):
    root = Path(root); meter = Download(root/'http', lock, **kwargs)
    receipts = {'layers': [], 'sources': [], 'status': 'started', 'sourceOrSampleReads': 0}
    try:
        for desc in lock['image']['layers']:
            path, status, location = meter.fetch(config_url(desc), 'origin', desc)
            if status == 302:
                require(location is not None, 'Layer Location absent')
                path, status, _ = meter.fetch(location, 'cdn', desc)
            require(status == 200, 'Layer HTTP refused; no auth/retry/extra hop')
            receipts['layers'].append({'descriptor': desc, 'path': str(path.relative_to(root)), 'bytes': path.stat().st_size, 'sha256': sha(path)})
        for source in lock['sources']:
            path, status, _ = meter.fetch(source_url(source), 'archive', source)
            require(status == 200, 'Source archive HTTP refused; no redirect/retry')
            receipts['sources'].append({'repository': source['repository'], 'commit': source['commit'], 'path': str(path.relative_to(root)), 'bytes': path.stat().st_size, 'sha256': sha(path)})
        receipts['status'] = 'acquired_unexpanded_unqualified'
        return 0
    except Exception as error:
        meter.stopped = True; receipts.update(status='stopped', errorType=type(error).__name__, error=str(error)[:512])
        return 2
    finally:
        meter.checkpoint(); receipts.update(requests=len(meter.events), receivedBodyBytes=meter.bytes)
        save(root/'result.json', receipts)


def safe_name(name):
    require(isinstance(name,str) and len(name.encode()) <= 4096 and not any(ord(c)<32 for c in name) and '\\' not in name and not name.startswith('/'), 'Unsafe archive name')
    if name.startswith('./'): name = name[2:]
    name = name.rstrip('/')
    if name in ('', '.'): return ''
    require(all(p not in ('','..','.') for p in name.split('/')), 'Unsafe archive components')
    return name


def target(root, name):
    parts = safe_name(name).split('/') if name else []
    p = root
    for part in parts[:-1]:
        p = p/part
        require(not p.is_symlink() and (not p.exists() or p.is_dir()), 'Archive symlink/non-directory ancestor')
        p.mkdir(exist_ok=True)
    return root.joinpath(*parts)


def remove(path):
    if path.is_symlink() or path.is_file(): path.unlink()
    elif path.exists(): shutil.rmtree(path)


def link_valid(name, value, hard=False):
    require(isinstance(value,str) and 0 < len(value.encode()) <= 4096 and not any(ord(c)<32 for c in value) and '\\' not in value, 'Unsafe archive link')
    parts = [] if hard or value.startswith('/') else name.split('/')[:-1]
    for part in value.lstrip('/').split('/'):
        if part in ('','.'): continue
        if part == '..':
            require(parts, 'Archive link escapes root'); parts.pop()
        else: parts.append(part)
    require(parts, 'Archive link to root refused')
    return '/'.join(parts)


class Expanded:
    def __init__(self, stream, limit, check): self.stream,self.limit,self.check,self.count,self.hashed = stream,limit,check,0,hashlib.sha256()
    def read(self, size=-1):
        self.check(); require(size >= 0, 'Unbounded expanded read')
        remaining = self.limit-self.count
        require(remaining > 0, 'Expanded archive cap before EOF')
        value = self.stream.read(min(size, remaining))
        self.count += len(value); self.hashed.update(value)
        return value


def member_row(member):
    require(member.sparse is None and set(member.pax_headers) <= {'path','linkpath','mtime','atime','ctime','comment','SCHILY.xattr.security.capability','SCHILY.xattr.security.selinux'}, 'Unsupported sparse/PAX metadata')
    name = safe_name(member.name)
    require(member.isdir() or member.isreg() or member.issym() or member.islnk(), 'Archive special type refused')
    require(type(member.size) is int and 0 <= member.size <= CAPS['fileBytes'], 'Archive file size')
    if not member.isreg(): require(member.size == 0, 'Archive nonfile payload')
    if member.issym() or member.islnk(): link_valid(name,member.linkname,member.islnk())
    return {'name':name,'type':member.type.decode('ascii'),'mode':member.mode & 0o777,'size':member.size,'link':member.linkname}


def tar_scan(path, limit, check, visit):
    with gzip.open(path,'rb') as stream:
        expanded = Expanded(stream,limit,check)
        with tarfile.open(fileobj=expanded,mode='r|') as archive:
            for member in archive:
                visit(archive,member)
                archive.members.clear()
        while expanded.read(1048576): pass
        return expanded.count,expanded.hashed.hexdigest()


def expand_layer(path, root, diff_id, remaining, check=lambda:None):
    rows, seen, whiteouts = [], set(), []
    header_bytes = 0
    def inspect(archive, member):
        nonlocal header_bytes
        row = member_row(member); name=row['name']
        require(name not in seen, 'Duplicate layer member'); seen.add(name)
        if not name: require(member.isdir(), 'Layer root must be a directory')
        header_bytes += len(json_bytes(row))
        require(len(rows) < CAPS['entries'] and header_bytes <= CAPS['headerBytes'], 'Layer header/count cap')
        rows.append(row)
        if PurePosixPath(name).name.startswith('.wh.'):
            require(member.isreg() and member.size == 0, 'Whiteout type/size')
            parent, base = str(PurePosixPath(name).parent), PurePosixPath(name).name
            if base == '.wh..wh..opq': whiteouts.append(('opaque','' if parent=='.' else parent))
            else:
                victim = base[4:]; require(victim not in ('','.','..') and not victim.startswith('.wh.'),'Whiteout target')
                whiteouts.append(('remove',('/'.join([parent,victim]) if parent!='.' else victim)))
    count, hashed = tar_scan(path,remaining,check,inspect)
    require('sha256:'+hashed == diff_id, 'Layer uncompressed diff ID')
    require(count+len(rows)*8192<=remaining,'Expanded namespace reservation cap')
    # OCI whiteouts affect only earlier layers, regardless of their tar position.
    for kind,name in whiteouts:
        p=target(root,name)
        if kind=='remove': remove(p)
        else:
            require(not p.is_symlink() and (not p.exists() or p.is_dir()),'Opaque directory type')
            p.mkdir(exist_ok=True)
            for child in p.iterdir(): remove(child)
    index, copied = 0,0
    def apply(archive,member):
        nonlocal index,copied
        row=member_row(member); require(row==rows[index],'Layer second-pass header drift'); index+=1
        name=row['name']
        if not name or PurePosixPath(name).name.startswith('.wh.'): return
        p=target(root,name)
        if member.isdir():
            if p.is_symlink() or p.exists() and not p.is_dir(): remove(p)
            p.mkdir(exist_ok=True); p.chmod(0o755)
        elif member.isreg():
            remove(p)
            with archive.extractfile(member) as source, p.open('xb') as out:
                remaining_file=member.size
                while remaining_file:
                    check(); chunk=source.read(min(1048576,remaining_file)); require(chunk,'Truncated layer member')
                    out.write(chunk); remaining_file-=len(chunk); copied+=len(chunk)
            p.chmod(row['mode'])
        elif member.issym():
            remove(p); p.symlink_to(member.linkname)
        else:
            source=target(root,link_valid(name,member.linkname,True))
            require(not source.is_symlink() and source.is_file(),'Layer hardlink target')
            remove(p); os.link(source,p)
    second,second_hash=tar_scan(path,count+1,check,apply)
    require(second==count and second_hash==hashed and index==len(rows),'Layer second-pass identity')
    return {'tarBytes':count,'reservedExpandedBytes':count+len(rows)*8192,'tarSha256':hashed,'entries':len(rows),'whiteouts':len(whiteouts),'fileBytesWritten':copied,
        'scope':'Two streamed passes; no expanded layer copy/image store. Directories0755, file modes0777 (setid removed), no ownership/xattr restoration. File bytes/links from verified layer; no general OCI runtime qualification.'}


def extract_source(path, root, source, check=lambda:None):
    expected={r['path']:r for r in source['selectedFiles']}; seen=set(); all_seen=set(); prefix=source['repository'].split('/')[1]+'-'+source['commit']
    root.mkdir()
    def visit(archive,member):
        row=member_row(member); name=row['name']; require(name not in all_seen,'Duplicate source member'); all_seen.add(name)
        require(len(all_seen)<=CAPS['entries'],'Source member cap')
        require(name==prefix or name.startswith(prefix+'/'),'Source commit archive prefix')
        relative=name[len(prefix)+1:]
        if not relative: require(member.isdir(),'Source root type'); return
        if relative not in expected:
            require(not (relative.startswith('include/osmium/') or relative.startswith('include/protozero/') or relative in ('LICENSE','LICENSE.md','LICENSE.txt','COPYING')) or member.isdir(),'Unexpected selected source member')
            return
        item=expected[relative]
        require(member.isreg() and member.size==item['size'] and bool(member.mode&0o111)==(item['mode']=='100755'),'Selected source type/size/mode')
        with archive.extractfile(member) as stream: body=stream.read(item['size']+1)
        require(len(body)==item['size'] and hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()==item['sha'],'Selected source Git blob identity')
        p=target(root,relative)
        with p.open('xb') as out: out.write(body)
        p.chmod(0o755 if item['mode']=='100755' else 0o644); seen.add(relative)
    expanded,hashed=tar_scan(path,CAPS['sourceExpandedBytes'],check,visit)
    require(seen==set(expected),'Source selected closure incomplete')
    return {'repository':source['repository'],'commit':source['commit'],'selectedFiles':len(seen),'selectedBytes':sum(r['size'] for r in expected.values()),'expandedArchiveBytes':expanded,'expandedArchiveSha256':hashed,'gitBlobIdentitiesVerified':True}


def inventory(root, check=lambda:None):
    """No symlink following; charge each inode once plus generous namespace overhead."""
    root=Path(root); hashed=hashlib.sha256(); files=logical=allocated=entries=0; inodes=set()
    def walk(path):
        nonlocal files,logical,allocated,entries
        for child in sorted(path.iterdir(),key=lambda p:p.name):
            check(); s=child.lstat(); entries+=1
            require(entries<=CAPS['entries'] and not stat.S_ISSOCK(s.st_mode),'Output inventory type/count')
            row={'path':str(child.relative_to(root)),'mode':stat.S_IMODE(s.st_mode),'size':s.st_size}
            inode=(s.st_dev,s.st_ino)
            if inode not in inodes:
                allocated+=s.st_blocks*512; inodes.add(inode)
            if child.is_symlink(): row['link']=os.readlink(child)
            elif child.is_dir(): row['directory']=True; walk(child)
            else:
                require(stat.S_ISREG(s.st_mode),'Output inventory special file'); files+=1;logical+=s.st_size;row['sha256']=sha(child)
            hashed.update(json_bytes(row))
    walk(root)
    return {'files':files,'entries':entries,'logicalFileBytes':logical,'allocatedInodeBytes':allocated,
        'conservativeBytesWithNamespaceReserve':max(logical,allocated)+entries*8192+1048576,'treeSha256':hashed.hexdigest(),
        'scope':'SHA256 of sorted postorder path/mode/size/content-or-link rows, no symlink following. Allocation deduplicates hardlinked inodes;8KiB/entry+1MiB namespace reserve, not physical filesystem metadata measurement.'}


def prepare(root, downloads, lock, check=lambda:None):
    root=Path(root); downloads=Path(downloads); result={'status':'started','layers':[],'sources':[],'sourceOrSampleReads':0}
    try:
        acquired=strict_json((downloads/'result.json').read_bytes());require(acquired['status']=='acquired_unexpanded_unqualified','Artifacts incomplete')
        filesystem=root/'rootfs';filesystem.mkdir()
        expanded=reserved=0
        for record,diff_id in zip(acquired['layers'],lock['image']['diffIds'],strict=True):
            path=downloads/record['path'];require(sha(path)==record['descriptor']['digest'][7:],'Layer file drift')
            value=expand_layer(path,filesystem,diff_id,CAPS['expandedBytes']-CAPS['metadataReserveBytes']-reserved,check)
            expanded+=value['tarBytes'];reserved+=value['reservedExpandedBytes'];result['layers'].append(value)
            save(root/f'layer-{len(result["layers"]):02d}.json',value)
        for name in ('work','tmp','inputs','inputs/libosmium','inputs/protozero'):
            p=target(filesystem,name);require(not p.is_symlink() and (not p.exists() or p.is_dir()),'Builder mountpoint type');p.mkdir(exist_ok=True)
        for index,(record,source) in enumerate(zip(acquired['sources'],lock['sources'],strict=True)):
            path=downloads/record['path'];require(sha(path)==record['sha256'],'Source archive drift')
            result['sources'].append(extract_source(path,root/f'source-{index+1}',source,check))
        result['rootfs']=inventory(filesystem,check)
        require(result['rootfs']['conservativeBytesWithNamespaceReserve']<=CAPS['expandedBytes'],'Actual rootfs storage cap')
        result.update(status='prepared_build_unqualified',expandedTarBytes=expanded,reservedExpandedBytes=reserved,imageStoreBytes=0,expandedLayerCopiesBytes=0)
        return 0
    except Exception as error:
        result.update(status='stopped',errorType=type(error).__name__,error=str(error)[:1000]);return 2
    finally: save(root/'result.json',result)
