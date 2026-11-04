"""Disk-selected capture resources retain every stopped attempt and accepted input."""
import hashlib
from pathlib import Path
import time

from coarse_osm_country_screen_v1 import OwnedStorage,MAX_VISITS,owned_usage,resource_metrics
from coarse_osm_country_screen_v4 import Resources
from coarse_osm_country_screen_v7 import NativeScreen
from coarse_timing_input import require

GIB=1024**3
TMP=256*1024**2
TOTAL=64*GIB
PRIOR_RETAINED=58226331751
QUALIFICATION_RESERVATION=64*1024**2
METADATA_RESERVATION=64*1024**2
RETAINED=PRIOR_RETAINED+QUALIFICATION_RESERVATION+METADATA_RESERVATION
OWNED_LIMIT=TOTAL-RETAINED-TMP
FILE_LIMIT=2*GIB
BANK_BYTES=938364831
WRITABLE_WORST_CASE=2*327680*4096+2*FILE_LIMIT+2*BANK_BYTES+GIB+64*1024**2
BANK_LABELS=('all-highway-primary-selection-cells','all-highway-independent-materialization-cells')


class FullScreen(NativeScreen):
    def scan(self,path,snapshot,caps,**options):
        return super().scan(path,snapshot,dict(caps,scanObjectVisitsTotal=min(caps['scanObjectVisitsTotal'],MAX_VISITS)),**options)


class FullResources(Resources):
    def check(self,*,force=False,projected=0):
        now=time.monotonic();require(now-self.began<self.seconds,'Disk capture worker deadline')
        if not force and not projected and now-self.last_sample<1:return
        work,tmp=owned_usage(self.root),owned_usage(self.tmp)
        require(work['conservativeAllocatedBytes']+projected+1048576<=OWNED_LIMIT,'Disk capture retained allocation cap')
        require(tmp['allocatedBytes']<=TMP and work['entries']+tmp['entries']+1<=4096,'Disk capture tmp/namespace cap')
        require(all(p.stat().st_size<=FILE_LIMIT for p in self.root.rglob('*') if p.is_file()),'Disk capture individual file cap')
        self.latest={'work':work,'tmp':tmp,'cgroup':resource_metrics(),'seconds':now-self.began}
        for name in self.peaks:self.peaks[name]=max(self.peaks[name],work[name])
        self.last_sample=now;self.samples+=1;self.sampled()

    def result(self):
        self.check(force=True)
        return {'latest':self.latest,'observedWorkPeaks':self.peaks,'samples':self.samples,'retainedReservationBytes':RETAINED,
                'ownedWorkLimitBytesExcludingTmp':OWNED_LIMIT,'retainedWorkingLimitBytes':TOTAL,'writableWorstCaseBytes':WRITABLE_WORST_CASE,
                'scope':'Conservative allocated owned bytes, retained inputs/failures/qualification reservation and tmp. Kernel memory includes file cache; not graph-search time.'}


class CaptureStorage(OwnedStorage):
    def __init__(self,root,resources,expected):
        super().__init__(root,limit=OWNED_LIMIT,file_limit=64*1024**2,entries=4096)
        self.resources=resources;self.expected=expected;self.written={label:set() for label in BANK_LABELS}
        require(expected and sum(row['bytes'] for row in expected.values())<=BANK_BYTES,'Disk capture accepted bank bound')

    def write(self,path,raw):
        path=Path(path);relative=path.resolve().relative_to(self.root)
        require(len(relative.parts)==2 and relative.parts[0] in BANK_LABELS,'Disk capture compact-bank namespace only')
        label,name=relative.parts;pin=self.expected.get(name)
        require(pin is not None and len(raw)==pin['bytes'] and hashlib.sha256(raw).hexdigest()==pin['sha256'],'Disk capture bank differs from accepted census')
        self.resources.check(force=True,projected=len(raw));super().write(path,raw);self.written[label].add(name);self.resources.check(force=True)

    def complete(self):
        require(all(names==set(self.expected) for names in self.written.values()),'Disk capture incomplete rebuilt bank')

    def remove(self,path,size):require(False,'Disk capture preserves every output part')
