"""Owned-container cleanup controls with fake Docker, no external processes."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from coarse_osm_bulk_pbf import stat_key
from coarse_osm_profile import CAPS, CASES
from coarse_timing_input import PilotError
from profile_osm_import_v2 import run, verify_source


class Tests(unittest.TestCase):
    def scenario(self, mode):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp); (repo/'docs/evidence').mkdir(parents=True); (repo/'data/coarse-quality').mkdir(parents=True)
            image = 'sha256:'+'a'*64; identity = 'b'*64; owner = None; name = None; removed = False; child = None
            source = repo/'source.pbf'; source.write_bytes(b'test')
            config = {'windows':[{'id':str(i)} for i in range(21)]}
            plan = {'phase':'offline_import_profile_v2','caps':CAPS,'cases':[list(case) for case in CASES],'network':'none','imagePull':'never','imageId':image,
                'output':'data/coarse-quality/us-osm-profile-v2','source':{'path':'source.pbf','bytes':12229320016,
                    'sha256':'1b127070917e2f4e5d9e778e2412bb44d24116519cf084ab72fe13e679eb11ff','md5':'c5abaec55e724255277f22fb97941e5a'},
                'extractConfig':config,'inputs':{},'basePlan':'base.json','site':'site','runtime':{},'mounts':{}}
            (repo/'base.json').write_text(json.dumps(plan)); path = repo/'docs/evidence/plan.json'; path.write_text(json.dumps(plan))
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            def inspection():
                running = mode == 'monitor-stop' and child is not None
                return {'Id':identity,'Image':image,'Architecture':'arm64','Config':{'Labels':{'geo-planner.profile-owner':owner}},
                    'State':{'Running':running,'ExitCode':2 if child is not None and not running else 0,'OOMKilled':False},
                    'HostConfig':{'NetworkMode':'none','Memory':4294967296,'MemorySwap':4294967296,'ReadonlyRootfs':True,
                        'NanoCpus':2000000000,'PidsLimit':64,'Tmpfs':{'/tmp':'rw,size=256m'},'Ulimits':[{'Name':'core','Soft':0,'Hard':0},{'Name':'fsize','Soft':CAPS['fileBytes'],'Hard':CAPS['fileBytes']}]},'Mounts':[]}
            def docker(args, **options):
                nonlocal owner,name,removed
                if args[:3] == ['docker','image','inspect']: return SimpleNamespace(stdout=json.dumps([{'Id':image,'Architecture':'arm64'}]),returncode=0)
                if args[:2] == ['docker','create']:
                    name=args[args.index('--name')+1];owner=args[args.index('--label')+1].split('=',1)[1]
                    if mode == 'create-timeout': raise subprocess.TimeoutExpired(args,1)
                    return SimpleNamespace(stdout=identity,returncode=0)
                if args[:2] == ['docker','inspect']:
                    if removed or owner is None: return SimpleNamespace(stdout='',stderr='No such container',returncode=1)
                    self.assertIn(args[2],(identity,name));return SimpleNamespace(stdout=json.dumps([inspection()]),returncode=0)
                if args[:3] == ['docker','rm','-f']:
                    self.assertEqual(args[3],identity);removed=True;return SimpleNamespace(stdout='',returncode=0)
                raise AssertionError(args)
            class Child:
                returncode=2
                killed=False
                calls=0
                def poll(self):
                    self.calls+=1
                    return None if mode=='monitor-stop' and not self.killed else 2
                def kill(self): self.killed=True
                def wait(self,timeout): return self.returncode
            def start(*args,**kwargs):
                nonlocal child
                child=Child();return child
            def storage(root):
                if mode=='monitor-stop' and child and not child.killed: raise PilotError('synthetic monitor stop')
                return 0
            observed={'hostDiskAvailableBytes':10*1024**3,'hostMemoryBytes':16*1024**3,'dockerMemoryBytes':8*1024**3,'hostCpuCount':2,'dockerCpuCount':2}
            with patch('profile_osm_import_v2.subprocess.run',side_effect=docker), patch('profile_osm_import_v2.subprocess.Popen',side_effect=start), \
                patch('profile_osm_import_v2.capacity',return_value=observed), patch('profile_osm_import_v2.verify_source',return_value=(stat_key(source),{'test':True})), \
                patch('profile_osm_import_v2.tree_bytes',side_effect=storage), \
                patch('profile_osm_import_v2.os.statvfs',return_value=SimpleNamespace(f_bavail=268435456 if mode=='small-temp-host' else 10*1024**3,f_frsize=1)):
                self.assertEqual(run(path,sha,plan['output'],repo=repo),2)
            root=repo/plan['output']
            if mode == 'small-temp-host':
                self.assertFalse(removed)
                self.assertTrue(json.loads((root/'cleanup.json').read_text())['ownedNameAbsent'])
                self.assertEqual(json.loads((root/'driver-failure.json').read_text())['error'],'Profile disk headroom')
                return
            self.assertTrue(removed)
            self.assertTrue(json.loads((root/'cleanup.json').read_text())['independentInspectAbsent'])
            self.assertEqual(json.loads((root/'run-summary.json').read_text())['status'],'stopped')
            self.assertTrue((root/'container-before-removal.json').exists())
            if mode == 'monitor-stop':
                self.assertTrue(child.killed);self.assertFalse((root/'container-result.json').exists())

    def test_create_timeout_recovers_only_labelled_owned_container(self): self.scenario('create-timeout')
    def test_nonzero_worker_exit_is_retained_and_owned_container_removed(self): self.scenario('worker-failure')
    def test_monitor_failure_kills_client_and_preserves_live_snapshot(self): self.scenario('monitor-stop')
    def test_small_tmpfs_host_assumption_is_reproduced_before_creation(self): self.scenario('small-temp-host')

    def test_source_hash_size_and_immutability_controls(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'source';path.write_bytes(b'bounded source')
            spec={'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'md5':hashlib.md5(path.read_bytes()).hexdigest()}
            self.assertEqual(verify_source(path,spec,lambda:None)[1]['sha256'],spec['sha256'])
            for key in ('bytes','sha256','md5'):
                bad=dict(spec);bad[key]=0 if key=='bytes' else 'bad'
                with self.assertRaises(PilotError): verify_source(path,bad,lambda:None)


if __name__ == '__main__': unittest.main()
