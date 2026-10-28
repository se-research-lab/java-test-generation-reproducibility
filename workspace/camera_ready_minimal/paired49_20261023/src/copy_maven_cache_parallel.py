"""Continue the owned cache copy with bounded parallel file verification."""
import concurrent.futures,json,os,shutil,sys,time
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
src=Path('C:/Users/admin/.m2/repository');dst=audit.ROOT/'camera_ready_minimal/maven_cache_20261023'
assert dst.is_dir() and dst.resolve().is_relative_to(audit.ROOT)
old=BASE/'e49_driver/cache_copy_manifest.jsonl';known={}
for line in old.read_text(encoding='utf-8').splitlines():
    try:r=json.loads(line);known[r['relative']]=r
    except json.JSONDecodeError:pass
manifest=BASE/'e49_driver/cache_copy_parallel_manifest.jsonl';assert not manifest.exists()
audit.log('CACHE_COPY_EXECUTION_AMENDMENT',reason='Serial file verification throughput too low; same source/target bytes, continue with8 workers; no Java/GPT benchmark started',prior_manifest_sha256=audit.sha(old),prior_verified_entries=len(known),original_cache_read_only=True)
start=time.monotonic()
def copy_one(pair):
    p,rel=pair;dest=dst/rel
    if rel.as_posix() in known:
        r=known[rel.as_posix()];assert audit.sha(p)==r['sha256']==audit.sha(dest)
        return r
    h=audit.sha(p);dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists() and audit.sha(dest)!=h:
        backup=dst.parent/'cache_partial_backup_20261023'/rel;backup.parent.mkdir(parents=True,exist_ok=True)
        assert not backup.exists();shutil.copy2(dest,backup)
    if not dest.exists() or audit.sha(dest)!=h:shutil.copy2(p,dest)
    assert h==audit.sha(dest)==audit.sha(p)
    return {'relative':rel.as_posix(),'sha256':h,'bytes':p.stat().st_size}
def inputs():
    for d,dirs,files in os.walk(src):
        dirs[:]=sorted(x for x in dirs if not Path(d,x).is_symlink())
        for name in sorted(files):
            p=Path(d,name)
            if not p.is_symlink():yield p,p.relative_to(src)
n=size=0
with manifest.open('x',encoding='utf-8') as f,concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    # Bounded queue: do not create116k pending futures or hold every hash in RAM.
    pending=set()
    for item in inputs():
        pending.add(pool.submit(copy_one,item))
        if len(pending)<64:continue
        done,pending=concurrent.futures.wait(pending,return_when=concurrent.futures.FIRST_COMPLETED)
        for future in done:
            r=future.result();f.write(json.dumps(r)+'\n');n+=1;size+=r['bytes']
        if n//10000!=(n-len(done))//10000:f.flush();print(n,size,flush=True)
    for future in concurrent.futures.as_completed(pending):
        r=future.result();f.write(json.dumps(r)+'\n');n+=1;size+=r['bytes']
report={'status':'PASS','files':n,'bytes':size,'seconds':time.monotonic()-start,'workers':8,'target':str(dst),'manifest_sha256':audit.sha(manifest),'all_copies_verified':True,'source_cache_writes':0}
p=BASE/'e49_driver/cache_copy_parallel_result.json'
with p.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
audit.log('WORKSPACE_CACHE_COPY_COMPLETE',**report);print(json.dumps(report,indent=2))
