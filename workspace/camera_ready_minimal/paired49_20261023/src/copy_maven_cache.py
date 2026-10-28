"""Create a workspace-owned byte-verified cache, never modify the source cache."""
import json,os,shutil,sys,time
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
src=Path('C:/Users/admin/.m2/repository');dst=audit.ROOT/'camera_ready_minimal/maven_cache_20261023'
assert not dst.exists();assert shutil.disk_usage(dst.parent).free>20_000_000_000
dst.mkdir();manifest=BASE/'e49_driver/cache_copy_manifest.jsonl';assert not manifest.exists()
audit.log('WORKSPACE_CACHE_COPY_START',source=str(src),target=str(dst),source_read_only=True)
start=time.monotonic();n=size=0
with manifest.open('x',encoding='utf-8') as out:
    for d,dirs,files in os.walk(src):
        dirs[:]=sorted(x for x in dirs if not Path(d,x).is_symlink())
        for name in sorted(files):
            p=Path(d,name)
            if p.is_symlink():continue
            rel=p.relative_to(src);dest=dst/rel;dest.parent.mkdir(parents=True,exist_ok=True)
            h=audit.sha(p);shutil.copy2(p,dest);assert audit.sha(dest)==h==audit.sha(p),str(p)
            out.write(json.dumps({'relative':rel.as_posix(),'sha256':h,'bytes':p.stat().st_size})+'\n')
            n+=1;size+=p.stat().st_size
            if n%10000==0:out.flush();print(n,size,flush=True)
report={'source':str(src),'target':str(dst),'files':n,'bytes':size,'seconds':time.monotonic()-start,'manifest_sha256':audit.sha(manifest),'all_copies_verified':True,'original_cache_modified_by_this_copy':False}
p=BASE/'e49_driver/cache_copy_result.json'
with p.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
audit.log('WORKSPACE_CACHE_COPY_COMPLETE',**report);print(json.dumps(report,indent=2))
