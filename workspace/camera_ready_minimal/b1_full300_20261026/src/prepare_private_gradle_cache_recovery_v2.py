"""Explicit evidence-preserving recovery of private cache preparation v1.

Only missing files are copied. Existing journaled/unjournaled files must match
source bytes; none are overwritten. No Java/Gradle/EvoSuite/API/network execution.
"""
import hashlib,json,os,re,shutil,stat,sys,threading,time
from pathlib import Path,PurePosixPath
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor

R=Path(__file__).resolve().parents[1];B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B));import audit
SOURCE=Path('C:/Users/admin/.gradle')
OUT=R/'cache_preparation_gradle_v1';DEST=OUT/'gradle_user_home';REC=OUT/'recovery_v2'
RESERVE=12_000_000_000;REPARSE=getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400)
mkdir_lock=threading.Lock();canonical_examples=[]

def now():return datetime.now(timezone.utc).isoformat()
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def dump(p,data):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def metadata(p):
    s=p.stat();return {'bytes':s.st_size,'mtime_ns':s.st_mtime_ns}
def no_reparse(p):
    s=p.lstat();assert not p.is_symlink() and not getattr(s,'st_file_attributes',0)&REPARSE,'Reparse point rejected: '+str(p)
def canonical_drive(p):
    # This is exact local-drive prefix normalization, never UNC/network decoding.
    raw=str(p)
    if raw.startswith('\\\\?\\'):
        assert re.match(r'^\\\\\?\\[A-Za-z]:\\',raw),'Unsupported extended path form'
        short=raw[4:]
        if len(canonical_examples)<20:canonical_examples.append({'resolved':raw,'drive_normalized':short})
        raw=short
    result=Path(raw)
    assert result.is_absolute() and re.match(r'^[A-Za-z]:$',result.drive),'Only local absolute drive paths allowed'
    return result

assert OUT.is_dir() and (OUT/'interrupted.json').is_file() and not (OUT/'complete.json').exists()
assert not REC.exists(),'Explicit recovery output already exists; no automatic retry'
assert (OUT/'gradle_user_home').resolve().is_relative_to(R.resolve())
no_reparse(DEST)
HOME_PHYSICAL=canonical_drive(DEST.resolve(strict=True))
assert HOME_PHYSICAL.drive.lower()==R.drive.lower() and HOME_PHYSICAL.is_relative_to(R.resolve())
protocol_v1=load(OUT/'protocol.json');rows=load(OUT/'input_stat_manifest.json')
assert audit.sha(OUT/'input_stat_manifest.json')==protocol_v1['input_stat_manifest_sha256']
assert SOURCE==Path(protocol_v1['source'])
for p,h in protocol_v1['inputs_sha256'].items():assert audit.sha(p)==h,'Pinned preparation input changed'
roots=[Path(p) for p in protocol_v1['exact_allowlisted_source_roots']]
markers=[Path(p) for p in protocol_v1['exact_allowlisted_source_marker_files']]
assert len(roots)==5 and len(markers)==4
assert all(p.is_relative_to(SOURCE) for p in roots+markers)
assert {p.name for p in roots}=={'gradle-2.13','gradle-5.2.1','gradle-6.9.4','gradle-8.14.4','modules-2'}
def parts(relative):
    posix=PurePosixPath(relative)
    assert not posix.is_absolute() and posix.parts and all(v not in {'.','..',''} and ':' not in v and '\\' not in v for v in posix.parts),'Unsafe relative cache path'
    return posix.parts
def source_file(relative):
    p=SOURCE.joinpath(*parts(relative));no_reparse(p)
    actual=canonical_drive(p.resolve(strict=True))
    assert actual==p and (any(p.is_relative_to(root) for root in roots) or p in markers),'Source outside exact allowlist or aliased'
    return p
def safe_destination(relative,create_parent=False):
    components=parts(relative);cursor=DEST
    # Serialize creation/checking of each existing parent before resolving it.
    # Never resolve the not-yet-existing long leaf as v1 did.
    with mkdir_lock:
        for component in components[:-1]:
            cursor=cursor/component
            if not cursor.exists():
                assert create_parent,'Unexpected missing destination parent';cursor.mkdir()
            no_reparse(cursor);assert cursor.is_dir()
            physical=canonical_drive(cursor.resolve(strict=True))
            assert physical.drive.lower()==HOME_PHYSICAL.drive.lower() and physical.is_relative_to(HOME_PHYSICAL),'Resolved existing parent escaped private home'
        dest=cursor/components[-1]
        if dest.exists():no_reparse(dest);assert dest.is_file()
        return dest
def stop():
    assert not (R/'STOP_REQUESTED.json').exists() and not (OUT/'STOP_REQUESTED.json').exists() and not (REC/'STOP_REQUESTED.json').exists(),'Explicit stop; retain evidence'
    assert shutil.disk_usage(R).free>RESERVE,'Disk reserve reached'

expected={row['relative']:row for row in rows};assert len(expected)==len(rows)
oldjournal=[json.loads(line) for line in (OUT/'copied.jsonl').read_text(encoding='utf-8').splitlines()]
assert len({r['relative'] for r in oldjournal})==len(oldjournal)
assert [r['relative'] for r in oldjournal]==[r['relative'] for r in rows[:len(oldjournal)]],'Original journal no longer a committed prefix'
oldhash={r['relative']:r['sha256'] for r in oldjournal}
existing={p.relative_to(DEST).as_posix():p for p in DEST.rglob('*') if p.is_file()}
assert set(existing)<=set(expected),'Unplanned destination files found'
for parent,dirs,files in os.walk(DEST,followlinks=False):
    no_reparse(Path(parent))
    for name in dirs+files:no_reparse(Path(parent)/name)
remaining_bytes=sum(r['bytes'] for r in rows if r['relative'] not in existing)
assert shutil.disk_usage(R).free-remaining_bytes>RESERVE,'Insufficient reserve for missing files'
audit.verify();REC.mkdir(exist_ok=False)
pinpaths=[Path(__file__),OUT/'protocol.json',OUT/'input_stat_manifest.json',OUT/'copied.jsonl',OUT/'interrupted.json',OUT/'exclusions.json',R/'audit/gradle_cache_census_v1.json',R/'inputs/gradle40_context_v2/manifest.json',R/'inputs/gradle40_context_v2/summary.json']
recovery_protocol={'created_utc':now(),'scope':'explicit preparation recovery only; no runtime qualification','prior_v1_failure':load(OUT/'interrupted.json'),'v1_root_cause':'Unconfirmed false-positive at non-existing destination resolve comparison; no offending path captured by v1. Current exact destination census is confined to planned source paths.','safety_change':'Capture canonical physical private home; serialize parent creation; reject reparse points; resolve existing parents strictly and check same local-drive containment; validate lexical single leaf. Normalize only exact Windows extended local-drive prefix.','source':str(SOURCE),'private_home':str(DEST),'private_home_physical_canonical':str(HOME_PHYSICAL),'planned_files':len(rows),'journaled_v1_files':len(oldjournal),'existing_files_to_reverify':len(existing),'unjournaled_existing_files':len(existing)-len(oldjournal),'missing_files_to_copy':len(rows)-len(existing),'missing_bytes_to_copy':remaining_bytes,'existing_file_policy':'rehash source and destination, match v1 journal where present; never overwrite','new_file_policy':'exclusive xb creation and source/destination SHA256 verification','disk_floor_bytes':RESERVE,'copy_workers':4,'inputs_sha256':{str(p.resolve()):audit.sha(p) for p in pinpaths},'experimental_calls':0,'network_calls':0,'user_config_imported':False}
dump(REC/'protocol.json',recovery_protocol)
audit.log('B1_PRIVATE_GRADLE_CACHE_RECOVERY_V2_START',protocol_sha256=audit.sha(REC/'protocol.json'),journaled_v1=len(oldjournal),existing=len(existing),missing=len(rows)-len(existing),experimental_calls=0)

def verify_or_copy(row):
    stop();relative=row['relative'];src=source_file(relative);before=metadata(src)
    assert before=={'bytes':row['bytes'],'mtime_ns':row['mtime_ns']},'Source stat differs from v1 input: '+relative
    dest=safe_destination(relative,create_parent=True)
    adopted=relative in existing
    if adopted:
        source_hash=sha(src);assert sha(dest)==source_hash,'Existing copied file differs; never overwrite: '+relative
        if relative in oldhash:assert source_hash==oldhash[relative],'Source bytes differ from v1 committed evidence'
    else:
        assert not dest.exists(),'New destination unexpectedly exists'
        h=hashlib.sha256()
        with src.open('rb') as f,dest.open('xb') as target:
            for block in iter(lambda:f.read(1024*1024),b''):h.update(block);target.write(block)
        source_hash=h.hexdigest();assert sha(dest)==source_hash,'New destination hash mismatch: '+relative
    assert metadata(src)==before,'Source changed during read: '+relative
    no_reparse(dest);physical=canonical_drive(dest.resolve(strict=True))
    assert physical.is_relative_to(HOME_PHYSICAL) and physical.drive.lower()==HOME_PHYSICAL.drive.lower(),'Created file resolved outside private home'
    assert not os.path.samefile(src,dest),'Hardlink/shared source identity rejected'
    assert dest.stat().st_size==row['bytes']
    return {'relative':relative,'bytes':row['bytes'],'sha256':source_hash,'source_mtime_ns':row['mtime_ns'],'independent_copy':True,'recovery_action':'verified_existing_no_write' if adopted else 'copied_missing_exclusive','prior_v1_journaled':relative in oldhash}

completed=[];started=time.monotonic();tick=started
try:
    with ThreadPoolExecutor(max_workers=4) as pool:
        with (REC/'copied_verified.jsonl').open('x',encoding='utf-8') as journal:
            for offset in range(0,len(rows),128):
                stop();futures=[pool.submit(verify_or_copy,row) for row in rows[offset:offset+128]]
                for future in futures:
                    result=future.result();completed.append(result);journal.write(json.dumps(result,ensure_ascii=False)+'\n')
                journal.flush();os.fsync(journal.fileno())
                if time.monotonic()-tick>15 or len(completed)==len(rows):
                    print(json.dumps({'private_Gradle_cache_recovered_verified':len(completed),'target':len(rows),'new_experiment_calls':0}),flush=True);tick=time.monotonic()
    # Verify exact source census+stats after every read, excluding only declared locks.
    source_rows=[]
    for root in roots:
        for parent,dirs,files in os.walk(root,followlinks=False):
            no_reparse(Path(parent))
            for name in dirs:no_reparse(Path(parent)/name)
            for name in files:
                p=Path(parent)/name;no_reparse(p)
                if not name.lower().endswith(('.lock','.lck')):source_rows.append({'relative':p.relative_to(SOURCE).as_posix(),**metadata(p)})
    for p in markers:source_rows.append({'relative':p.relative_to(SOURCE).as_posix(),**metadata(p)})
    assert sorted(source_rows,key=lambda r:r['relative'])==rows,'Source file set/stat changed since v1'
    actual={p.relative_to(DEST).as_posix() for p in DEST.rglob('*') if p.is_file()}
    assert actual==set(expected),'Final destination census differs'
    for row in completed:
        stop();p=safe_destination(row['relative']);assert sha(p)==row['sha256'],'Final full destination rehash failed'
    assert len(completed)==len(rows)
    dump(REC/'manifest.json',completed)
    audit.verify()
    result={'status':'PASS_PRIVATE_CACHE_PREPARATION_ONLY','finished_utc':now(),'private_Gradle_user_home':str(DEST),'files':len(completed),'bytes':sum(r['bytes'] for r in completed),'verified_v1_committed_files':len(oldjournal),'verified_v1_unjournaled_files':len(existing)-len(oldjournal),'new_missing_files_copied':len(rows)-len(existing),'v1_evidence_preserved':True,'existing_files_overwritten':0,'excluded_live_locks':len(load(OUT/'exclusions.json')),'source_file_set_stat_stable_since_v1':True,'source_modified_by_script':False,'all_destination_hashes_verified_twice':True,'exact_local_drive_prefix_normalization_examples':canonical_examples,'manifest_sha256':audit.sha(REC/'manifest.json'),'recovery_journal_sha256':audit.sha(REC/'copied_verified.jsonl'),'protocol_sha256':audit.sha(REC/'protocol.json'),'runtime_qualified':False,'benchmark_admitted':False,'new_experiment_calls':0,'Java_Gradle_EvoSuite_calls':0,'GPT_API_calls':0,'network_calls':0,'user_config_copied':False,'free_disk_bytes_after':shutil.disk_usage(R).free,'elapsed_seconds':time.monotonic()-started}
    dump(REC/'complete.json',result);audit.log('B1_PRIVATE_GRADLE_CACHE_RECOVERY_V2_COMPLETE',complete_sha256=audit.sha(REC/'complete.json'),**result)
    print(json.dumps(result,indent=2),flush=True)
except BaseException as ex:
    failure={'status':'INTERRUPTED_PRESERVE_ALL_EVIDENCE','at_utc':now(),'verified_journaled_files':len(completed),'error_type':type(ex).__name__,'detail':str(ex),'auto_resume':False,'experimental_calls':0}
    dump(REC/'interrupted.json',failure);audit.log('B1_PRIVATE_GRADLE_CACHE_RECOVERY_V2_INTERRUPTED',**failure);raise
