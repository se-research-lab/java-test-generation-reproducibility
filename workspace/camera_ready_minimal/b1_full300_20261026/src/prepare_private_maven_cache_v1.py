"""Copy the accepted E49 cache into B1; exact bytes, no hardlinks or dependency resolution."""
import json,sys,os,shutil,hashlib,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from snapshot_store_v1 import safe_relative,IntegrityError
R=Path(__file__).resolve().parents[1];B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
SOURCE=B/'e1_compatibility_diagnostic_v1/maven_cache';MANIFEST=B/'e1_compatibility_diagnostic_v1/cache_copy_manifest.json'
OUT=R/'cache_preparation_v1';OUT.mkdir(exist_ok=False);DEST=OUT/'maven_cache';DEST.mkdir()
rows=json.loads(MANIFEST.read_text(encoding='utf-8'));total=sum(r['bytes'] for r in rows)
assert shutil.disk_usage(R).free-total>12_000_000_000,'Insufficient disk for independent cache with12GB reserve'
def dump(p,x):
 with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2)
def stop():
 if (R/'STOP_REQUESTED.json').exists():raise IntegrityError('Explicit stop, preserve partial cache')
def copy(row):
 stop();rel=safe_relative(row['relative']);src=SOURCE/rel;dest=DEST/rel
 assert not src.is_symlink() and src.resolve().is_relative_to(SOURCE.resolve()),'Cache link outside source'
 before=src.stat();assert before.st_size==row['bytes'],'Cache size drift'
 dest.parent.mkdir(parents=True,exist_ok=True);h=hashlib.sha256()
 with src.open('rb') as f,dest.open('xb') as out:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk);out.write(chunk)
 after=src.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns),'Cache source changed during read'
 assert h.hexdigest()==row['sha256'] and audit.sha(dest)==row['sha256'],'Cache hash drift'
 assert src.stat().st_ino!=dest.stat().st_ino,'Cache must not share writable inode'
 return row
protocol={'source':str(SOURCE),'manifest_sha256':audit.sha(MANIFEST),'files':len(rows),'bytes':total,'copy_workers':4,'benchmark_workers':1,'network_calls':0,'policy':'independent exact copy; no shared hardlinks; keep original cache immutable','script_sha256':audit.sha(__file__)}
dump(OUT/'protocol.json',protocol);audit.log('B1_PRIVATE_CACHE_COPY_START',**protocol)
completed=0;tick=time.monotonic()
try:
 with ThreadPoolExecutor(max_workers=4) as pool:
  with (OUT/'copied.jsonl').open('x',encoding='utf-8') as log:
   for offset in range(0,len(rows),128):
    stop();assert shutil.disk_usage(R).free>12_000_000_000,'Disk reserve reached'
    futures=[pool.submit(copy,row) for row in rows[offset:offset+128]]
    for future in futures:log.write(json.dumps(future.result(),ensure_ascii=False)+'\n');completed+=1
    log.flush()
    if time.monotonic()-tick>20 or completed==len(rows):
     print(json.dumps({'cache_files_copied_verified':completed,'target':len(rows),'experiment_calls':0}),flush=True);tick=time.monotonic()
 assert completed==len(rows)
 result={'status':'PASS','files':completed,'bytes':total,'manifest_sha256':audit.sha(MANIFEST),'copy_log_sha256':audit.sha(OUT/'copied.jsonl'),'independent_copy':True,'experiment_calls':0,'network_calls':0}
 dump(OUT/'complete.json',result);audit.log('B1_PRIVATE_CACHE_COPY_COMPLETE',**result);print(json.dumps(result,indent=2),flush=True)
except BaseException as ex:
 dump(OUT/'interrupted.json',{'completed':completed,'error_type':type(ex).__name__,'detail':str(ex),'auto_resume':False})
 audit.log('B1_PRIVATE_CACHE_COPY_INTERRUPTED',completed=completed,error_type=type(ex).__name__,detail=str(ex));raise
