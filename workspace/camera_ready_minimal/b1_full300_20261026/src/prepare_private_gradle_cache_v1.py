"""Independently seed a PRIVATE Gradle cache from exact allowlisted local files.
No Java/Gradle/EvoSuite/API/network execution. No source cache modifications.
"""
import hashlib,json,os,shutil,stat,sys,time
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor

R=Path(__file__).resolve().parents[1]
B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit

SOURCE=Path('C:/Users/admin/.gradle').resolve()
OUT=R/'cache_preparation_gradle_v1'
DEST=OUT/'gradle_user_home'
RESERVE=12_000_000_000
REPARSE=getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400)
DISTROS=[('gradle-2.13-all','1b9wlm73elu4cqnbc0rk7r7qn','2.13'),('gradle-5.2.1-bin','9lc4nzslqh3ep7ml2tp68fk8s','5.2.1'),('gradle-6.9.4-bin','5a0lguq60r1skx3y8d5qdl7d9','6.9.4'),('gradle-8.14.4-bin','92wwslzcyst3phie3o264zltu','8.14.4')]

def now():return datetime.now(timezone.utc).isoformat()
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def dump(p,data):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
def content_sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def ensure_safe(p):
    p=Path(p)
    assert p.resolve().is_relative_to(SOURCE),'Source escaped exact .gradle root'
    cursor=p
    while cursor!=SOURCE:
        s=cursor.lstat()
        assert not cursor.is_symlink() and not getattr(s,'st_file_attributes',0)&REPARSE,'Reparse/link source rejected: '+str(cursor)
        cursor=cursor.parent
def stop():
    assert not (R/'STOP_REQUESTED.json').exists() and not (OUT/'STOP_REQUESTED.json').exists(),'Explicit stop; retain partial cache, no auto-resume'
    assert shutil.disk_usage(R).free>RESERVE,'Workspace disk reserve reached; retain partial cache'
def metadata(p):
    s=p.stat()
    return {'bytes':s.st_size,'mtime_ns':s.st_mtime_ns}

assert not OUT.exists(),'Exclusive new cache output required; no resume/overwrite'
assert OUT.resolve().is_relative_to(R.resolve()) and OUT.resolve()!=R.resolve()
assert SOURCE==Path('C:/Users/admin/.gradle') and not getattr(SOURCE.lstat(),'st_file_attributes',0)&REPARSE,'Unexpected source root alias/reparse point'
assert not (R/'STOP_REQUESTED.json').exists(),'Stop request active'
census=load(R/'audit/gradle_cache_census_v1.json')
assert census['status']=='READ_ONLY_CENSUS_NOT_FROZEN'
context=load(R/'inputs/gradle40_context_v2/manifest.json')
summary=load(R/'inputs/gradle40_context_v2/summary.json')
assert summary['status']=='PASS_METADATA_ONLY' and len(context)==40
assert audit.sha(R/'inputs/gradle40_context_v2/manifest.json')==summary['manifest_sha256']
assert {j['Gradle_version'] for j in context}=={d[2] for d in DISTROS}

roots=[];markerfiles=[];distributionmap=[];exclusions=[]
for key,slot,version in DISTROS:
    relative=Path('wrapper/dists')/key/slot/('gradle-'+version)
    root=SOURCE/relative;ensure_safe(root)
    assert root.is_dir() and (root/'bin/gradle.bat').is_file(),'Complete unpacked distribution missing'
    previous=next(d for d in census['distribution_slots'] if d['version']==version)
    assert root==Path(previous['distribution_root']).resolve(),'Census distro path mismatch'
    assert not previous['whole_wrapper_slot']['reparse_points_skipped'] and not previous['whole_wrapper_slot']['read_errors']
    marker=SOURCE/'wrapper/dists'/key/slot/(key+'.zip.ok');ensure_safe(marker);assert marker.is_file()
    roots.append(root);markerfiles.append(marker)
    distributionmap.append({'version':version,'source_distribution':str(root),'destination_distribution_relative_to_private_home':relative.as_posix(),'copied_zip_ok_relative_to_private_home':marker.relative_to(SOURCE).as_posix(),'source_zip_not_copied':True,'wrapper_url_version_hash_slot_preserved':True})
modules=SOURCE/'caches/modules-2';ensure_safe(modules);assert modules.is_dir();roots.append(modules)

def enumerate_inputs():
    rows=[];excluded=[]
    for root in roots:
        for parent,dirs,files in os.walk(root,followlinks=False):
            for name in dirs:ensure_safe(Path(parent)/name)
            for name in files:
                p=Path(parent)/name;ensure_safe(p)
                relative=p.relative_to(SOURCE).as_posix()
                if name.lower().endswith(('.lock','.lck')):
                    excluded.append({'relative':relative,'reason':'live cache lock; must be newly created in private home','metadata_only':metadata(p)});continue
                rows.append({'relative':relative,**metadata(p)})
    for p in markerfiles:rows.append({'relative':p.relative_to(SOURCE).as_posix(),**metadata(p)})
    return sorted(rows,key=lambda r:r['relative']),sorted(excluded,key=lambda r:r['relative'])

rows,exclusions=enumerate_inputs();assert len({r['relative'] for r in rows})==len(rows)
total=sum(r['bytes'] for r in rows)
assert shutil.disk_usage(R).free-total>RESERVE,'Not enough room for independent cache and12GB reserve'
audit.verify()
OUT.mkdir(exist_ok=False);DEST.mkdir(exist_ok=False)
dump(OUT/'input_stat_manifest.json',rows);dump(OUT/'exclusions.json',exclusions)
pinpaths=[Path(__file__),R/'audit/gradle_cache_census_v1.json',R/'inputs/gradle40_context_v2/manifest.json',R/'inputs/gradle40_context_v2/summary.json']
protocol={'created_utc':now(),'scope':'private cache preparation only; no runtime qualification or benchmark admission','source':str(SOURCE),'destination':str(DEST),'exact_allowlisted_source_roots':[str(p) for p in roots],'exact_allowlisted_source_marker_files':[str(p) for p in markerfiles],'distribution_map':distributionmap,'source_files_to_copy':len(rows),'source_bytes_to_copy':total,'input_stat_manifest_sha256':audit.sha(OUT/'input_stat_manifest.json'),'excluded_lock_manifest_sha256':audit.sha(OUT/'exclusions.json'),'copy_workers':4,'benchmark_workers':0,'disk_reserve_bytes':RESERVE,'new_experiment_calls':0,'network_calls':0,'inputs_sha256':{str(p.resolve()):audit.sha(p) for p in pinpaths},'isolation':'Independent source-read/destination-write with SHA256 verification; no hardlinks or symlinks. Source caches never modified. User settings/init scripts/daemon state outside exact roots never read or copied. Official distribution docs/samples remain complete.','source_cache_freeze_claim':False,'next_runtime_requirements':['Pinned JDK/wrapper launchers; private GRADLE_USER_HOME','offline/no dependency refresh; no shared daemon','owned-process and task/timeouts qualification','resolved dependency/classpath audit; no credential-bearing user config import']}
dump(OUT/'protocol.json',protocol)
audit.log('B1_PRIVATE_GRADLE_CACHE_PREPARE_START',protocol_sha256=audit.sha(OUT/'protocol.json'),files=len(rows),bytes=total,experimental_calls=0)

def copy_one(row):
    stop();src=SOURCE/row['relative'];ensure_safe(src);before=metadata(src)
    assert before=={'bytes':row['bytes'],'mtime_ns':row['mtime_ns']},'Source metadata drift before copy: '+row['relative']
    dest=DEST/row['relative'];assert dest.resolve().is_relative_to(DEST.resolve()),'Destination escaped private home'
    dest.parent.mkdir(parents=True,exist_ok=True);h=hashlib.sha256()
    with src.open('rb') as f,dest.open('xb') as target:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block);target.write(block)
    assert metadata(src)==before,'Source changed while copying: '+row['relative']
    digest=h.hexdigest();assert content_sha(dest)==digest,'Destination byte hash mismatch: '+row['relative']
    assert not os.path.samefile(src,dest),'Source and destination must have independent file identity'
    assert dest.stat().st_size==row['bytes']
    return {'relative':row['relative'],'bytes':row['bytes'],'sha256':digest,'source_mtime_ns':row['mtime_ns'],'independent_copy':True}

copied=[];started=time.monotonic();tick=started
try:
    with ThreadPoolExecutor(max_workers=4) as pool:
        with (OUT/'copied.jsonl').open('x',encoding='utf-8') as journal:
            for offset in range(0,len(rows),128):
                stop()
                futures=[pool.submit(copy_one,row) for row in rows[offset:offset+128]]
                for future in futures:
                    result=future.result();copied.append(result);journal.write(json.dumps(result,ensure_ascii=False)+'\n')
                journal.flush();os.fsync(journal.fileno())
                if time.monotonic()-tick>15 or len(copied)==len(rows):
                    print(json.dumps({'private_Gradle_cache_files_copied_verified':len(copied),'target':len(rows),'experimental_calls':0}),flush=True);tick=time.monotonic()
    final_rows,_=enumerate_inputs();assert final_rows==rows,'Source file set/stat changed across complete copy'
    assert len(copied)==len(rows)
    expected={r['relative'] for r in rows};actual={p.relative_to(DEST).as_posix() for p in DEST.rglob('*') if p.is_file()}
    assert actual==expected,'Destination file census differs'
    for row in copied:
        stop();assert content_sha(DEST/row['relative'])==row['sha256'],'Final destination hash drift'
    dump(OUT/'manifest.json',copied)
    audit.verify()
    result={'status':'PASS_PRIVATE_CACHE_PREPARATION_ONLY','finished_utc':now(),'files':len(copied),'bytes':sum(r['bytes'] for r in copied),'excluded_live_lock_files':len(exclusions),'manifest_sha256':audit.sha(OUT/'manifest.json'),'copy_journal_sha256':audit.sha(OUT/'copied.jsonl'),'protocol_sha256':audit.sha(OUT/'protocol.json'),'source_stat_manifest_stable':True,'destination_final_rehash_all_files':True,'independent_copy':True,'source_modified_by_script':False,'credential_configuration_contents_read':False,'user_config_copied':False,'new_experiment_calls':0,'Java_calls':0,'Gradle_calls':0,'EvoSuite_calls':0,'GPT_API_calls':0,'network_calls':0,'benchmark_admitted':False,'runtime_qualified':False,'free_disk_bytes_after':shutil.disk_usage(R).free,'elapsed_seconds':time.monotonic()-started}
    dump(OUT/'complete.json',result)
    audit.log('B1_PRIVATE_GRADLE_CACHE_PREPARE_COMPLETE',complete_sha256=audit.sha(OUT/'complete.json'),**result)
    print(json.dumps(result,indent=2),flush=True)
except BaseException as ex:
    failure={'status':'INTERRUPTED_PRESERVE_PARTIAL','finished_utc':now(),'files_copied_journaled':len(copied),'error_type':type(ex).__name__,'detail':str(ex),'auto_resume':False,'experimental_calls':0}
    dump(OUT/'interrupted.json',failure);audit.log('B1_PRIVATE_GRADLE_CACHE_PREPARE_INTERRUPTED',**failure);raise
