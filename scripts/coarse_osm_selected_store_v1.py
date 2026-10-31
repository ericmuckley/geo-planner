"""Fixed-cache selected-state spool; primary and audit use separate databases."""
from contextlib import contextmanager
import hashlib
from pathlib import Path
import sqlite3

from coarse_osm_records import canonical,normalize,strict_json
from coarse_timing_input import require

PAGE_BYTES=4096
MAX_PAGES=327680
CACHE_BYTES=8*1024**2
KINDS={'node','way','relation'}


def typed_key(key):
    require(isinstance(key,tuple) and len(key)==2 and isinstance(key[0],str) and key[0] in KINDS and type(key[1]) is int and 0<key[1]<2**63,'Selected store typed key')
    return key


class SelectedStore:
    def __init__(self,path,windows,run,*,check=lambda:None,max_pages=MAX_PAGES):
        self.path=Path(path);self.run=run;self.check=check
        require(self.path.parent.resolve()==run.root.resolve() and not run.root.is_symlink(),'Selected store owned path')
        require(self.path.parent.is_dir() and not self.path.exists() and not self.path.is_symlink(),'Selected store fresh path')
        require(type(max_pages) is int and 0<max_pages<=MAX_PAGES,'Selected store page cap')
        self.max_pages=max_pages
        self.windows=[w['id'] for w in windows]
        require(0<len(self.windows)<=21 and all(isinstance(w,str) and 0<len(w)<=128 for w in self.windows) and len(set(self.windows))==len(self.windows),'Selected store window identity')
        self.window_ordinals={name:i for i,name in enumerate(self.windows)}
        self.unique=self.occurrences=self.objects=self.raw_bytes=self.pending=self.commits=0
        self.closed=self.failed=self.sealed=False;self.sealed_report=None
        self.conn=sqlite3.connect(self.path,isolation_level=None)
        self.conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH,16*1024**2)
        require(self.conn.execute('PRAGMA journal_mode=DELETE').fetchone()[0]=='delete','Selected store journal mode')
        self.conn.execute('PRAGMA page_size=4096')
        require(self.conn.execute(f'PRAGMA max_page_count={max_pages}').fetchone()[0]==max_pages,'Selected store page reservation')
        self.conn.execute('PRAGMA cache_size=-8192');self.conn.execute('PRAGMA temp_store=MEMORY');self.conn.execute('PRAGMA synchronous=FULL')
        self.conn.executescript('''
            CREATE TABLE selected_keys(kind TEXT,id INTEGER,PRIMARY KEY(kind,id)) WITHOUT ROWID;
            CREATE TABLE memberships(kind TEXT,id INTEGER,w INTEGER,PRIMARY KEY(kind,id,w)) WITHOUT ROWID;
            CREATE TABLE objects(kind TEXT,id INTEGER,raw BLOB NOT NULL,PRIMARY KEY(kind,id)) WITHOUT ROWID;
            CREATE TABLE way_hashes(id INTEGER PRIMARY KEY,digest TEXT NOT NULL) WITHOUT ROWID;
        ''')
        self.conn.execute('BEGIN');run.charge(CACHE_BYTES+65536)

    def ready(self,*,write=False):
        require(not self.closed and not self.failed and (not write or not self.sealed),'Selected store closed/failed/sealed')
        self.check()

    @contextmanager
    def change(self):
        self.ready(write=True)
        try:
            yield
            if self.pending>=4096:self.commit()
        except BaseException:
            self.failed=True
            raise

    def execute_write(self,sql,values):
        result=self.conn.execute(sql,values);self.pending+=1;return result

    def commit(self):
        self.ready();self.conn.commit();self.conn.execute('BEGIN');self.pending=0;self.commits+=1

    def contains(self,key):
        self.ready();return self.conn.execute('SELECT 1 FROM selected_keys WHERE kind=? AND id=?',typed_key(key)).fetchone() is not None

    def member_windows(self,key):
        self.ready();rows=self.conn.execute('SELECT w FROM memberships WHERE kind=? AND id=? ORDER BY w',typed_key(key))
        return [self.windows[row[0]] for row in rows]

    def add(self,window,key):
        with self.change():
            kind,identity=typed_key(key);require(window in self.window_ordinals,'Selected store unknown window');ordinal=self.window_ordinals[window]
            if self.conn.execute('SELECT 1 FROM memberships WHERE kind=? AND id=? AND w=?',(kind,identity,ordinal)).fetchone():return
            require(self.occurrences<self.run.caps['selectedWindowElementOccurrences'],'Selected store occurrence cap')
            if not self.contains(key):
                require(self.unique<self.run.caps['selectedUniqueTypedElements'],'Selected store unique cap')
                self.execute_write('INSERT INTO selected_keys VALUES(?,?)',(kind,identity));self.unique+=1
            self.execute_write('INSERT INTO memberships VALUES(?,?,?)',(kind,identity,ordinal));self.occurrences+=1

    def set_way_hash(self,identity,digest):
        with self.change():
            typed_key(('way',identity));require(isinstance(digest,str) and len(digest)==64 and all(c in '0123456789abcdef' for c in digest),'Selected store way hash')
            self.execute_write('INSERT INTO way_hashes VALUES(?,?) ON CONFLICT(id) DO UPDATE SET digest=excluded.digest',(identity,digest))

    def way_hash(self,identity):
        self.ready();typed_key(('way',identity));row=self.conn.execute('SELECT digest FROM way_hashes WHERE id=?',(identity,)).fetchone()
        require(row is not None,'Selected store missing way hash');return row[0]

    def keep(self,raw):
        with self.change():
            value=normalize(raw,self.run.state['publisherStateUtc'],self.run.caps['singleNormalizedElementBytes']);key=typed_key((value['type'],value['id']));encoded=canonical(value)
            require(self.objects<self.run.caps['selectedUniqueTypedElements'],'Selected store object cap')
            require(self.raw_bytes+len(encoded)<=self.run.caps['retainedNativeObjectBytes'],'Selected store native-byte cap')
            require(self.conn.execute('SELECT 1 FROM objects WHERE kind=? AND id=?',key).fetchone() is None,'Selected store duplicate raw object')
            self.execute_write('INSERT INTO objects VALUES(?,?,?)',(*key,encoded));self.objects+=1;self.raw_bytes+=len(encoded)

    def raw(self,key):
        """Return a detached snapshot; replace() performs an explicit checked edit."""
        self.ready();row=self.conn.execute('SELECT raw FROM objects WHERE kind=? AND id=?',typed_key(key)).fetchone()
        require(row is not None,'Selected store missing raw object');return strict_json(row[0])

    def replace(self,key,raw):
        with self.change():
            key=typed_key(key);value=normalize(raw,self.run.state['publisherStateUtc'],self.run.caps['singleNormalizedElementBytes'])
            require((value['type'],value['id'])==key,'Selected store replacement typed identity')
            row=self.conn.execute('SELECT length(raw) FROM objects WHERE kind=? AND id=?',key).fetchone();require(row is not None,'Selected store replacement missing object')
            encoded=canonical(value);size=self.raw_bytes-row[0]+len(encoded)
            require(size<=self.run.caps['retainedNativeObjectBytes'],'Selected store replacement byte cap')
            self.execute_write('UPDATE objects SET raw=? WHERE kind=? AND id=?',(encoded,*key));self.raw_bytes=size

    def node_ids(self):
        self.ready();return [row[0] for row in self.conn.execute("SELECT id FROM selected_keys WHERE kind='node' ORDER BY id")]

    def linked_windows(self,members):
        found=set()
        for member in members:
            if member['type'] in ('node','way'):found.update(self.member_windows((member['type'],member['ref'])))
        return [name for name in self.windows if name in found]

    def iter_objects(self):
        self.ready()
        for kind,identity,raw in self.conn.execute('SELECT kind,id,raw FROM objects ORDER BY kind,id'):
            self.check();yield (kind,identity),strict_json(raw)

    def complete(self):
        self.ready()
        require(self.conn.execute('SELECT count(*) FROM selected_keys').fetchone()[0]==self.unique==self.objects==self.conn.execute('SELECT count(*) FROM objects').fetchone()[0],'Selected store materialization count')
        missing=self.conn.execute('SELECT 1 FROM selected_keys k LEFT JOIN objects o ON k.kind=o.kind AND k.id=o.id WHERE o.id IS NULL LIMIT 1').fetchone()
        require(missing is None,'Selected store missing/extra materialization hints')

    def records(self):
        snapshot=self.run.state['publisherStateUtc']
        for key,element in self.iter_objects():
            row={'publisherStateUtc':snapshot,'element':element,'elementSha256':hashlib.sha256(canonical(element)).hexdigest(),'windowIds':self.member_windows(key)}
            if key[0]=='way':row['geometryDependencySha256']=hashlib.sha256(canonical([snapshot,[self.raw(('node',n)) for n in element['nodes']]])).hexdigest()
            yield row

    def seal(self):
        try:return self.seal_checked()
        except BaseException:
            self.failed=True
            raise

    def seal_checked(self):
        self.complete();self.commit()
        require(self.conn.execute('PRAGMA journal_mode').fetchone()[0]=='delete' and self.conn.execute('PRAGMA temp_store').fetchone()[0]==2 and self.conn.execute('PRAGMA cache_size').fetchone()[0]==-8192,'Selected store configuration drift')
        require(self.conn.execute('PRAGMA max_page_count').fetchone()[0]==self.max_pages,'Selected store page-cap drift')
        require(self.conn.execute('PRAGMA integrity_check').fetchall()==[('ok',)],'Selected store integrity check')
        require(self.conn.execute('SELECT count(*) FROM memberships').fetchone()[0]==self.occurrences,'Selected store membership accounting')
        require((self.conn.execute('SELECT coalesce(sum(length(raw)),0) FROM objects').fetchone()[0])==self.raw_bytes,'Selected store raw-byte accounting')
        pages=self.conn.execute('PRAGMA page_count').fetchone()[0]
        require(self.conn.execute('PRAGMA page_size').fetchone()[0]==PAGE_BYTES and self.path.stat().st_size==pages*PAGE_BYTES<=self.max_pages*PAGE_BYTES,'Selected store physical page bound')
        with self.path.open('rb') as stream:pin=hashlib.file_digest(stream,'sha256').hexdigest()
        self.sealed=True;self.sealed_report=self.report()|{'databaseSha256':pin,'databaseBytes':self.path.stat().st_size,'integrityOk':True,'sealed':True}
        return self.sealed_report

    def report(self):
        return {'unique':self.unique,'occurrences':self.occurrences,'objects':self.objects,'rawBytes':self.raw_bytes,'pendingMutations':self.pending,
                'commits':self.commits,'closed':self.closed,'sealed':self.sealed,'sqliteVersion':sqlite3.sqlite_version,
                'scope':'Received selected operations; failed close can roll back an uncommitted tail. Admission requires seal/integrity/count checks and independent output audit.'}

    def close(self):
        if not self.closed:self.conn.close();self.closed=True
