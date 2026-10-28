"""Read-only Gradle cache/distro census. No Gradle/Java/network/cache copy.

Only metadata is inspected, except SHA256 reads of official distribution ZIPs.
Credential-bearing user configuration contents are never opened.
"""
import hashlib,json,os,shutil,sys,time
from pathlib import Path
from datetime import datetime,timezone

R=Path(__file__).resolve().parents[1]
B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit

HOME=Path('C:/Users/admin/.gradle')
REPORT=R/'audit/gradle_cache_census_v1.json'
REPARSE=getattr(__import__('stat'),'FILE_ATTRIBUTE_REPARSE_POINT',0x400)

def now():return datetime.now(timezone.utc).isoformat()
def census(root):
    root=Path(root)
    total=0;files=0;dirs=0;reparse=[];errors=[];types={};inventory=hashlib.sha256()
    if not root.exists():return {'root':str(root),'exists':False,'files':0,'bytes':0}
    todo=[root]
    while todo:
        parent=todo.pop()
        try:
            entries=sorted(os.scandir(parent),key=lambda e:e.name)
        except OSError as ex:
            errors.append({'relative':parent.relative_to(root).as_posix(),'error_type':type(ex).__name__});continue
        for e in entries:
            p=Path(e.path);rel=p.relative_to(root).as_posix()
            try:
                s=e.stat(follow_symlinks=False)
                if e.is_symlink() or getattr(s,'st_file_attributes',0)&REPARSE:
                    reparse.append(rel);continue
                if e.is_dir(follow_symlinks=False):dirs+=1;todo.append(p)
                elif e.is_file(follow_symlinks=False):
                    files+=1;total+=s.st_size
                    suffix=p.suffix.lower() or '(no suffix)';types[suffix]=types.get(suffix,0)+1
                    inventory.update(json.dumps([rel,s.st_size,s.st_mtime_ns],ensure_ascii=False,separators=(',',':')).encode('utf-8')+b'\n')
            except OSError as ex:errors.append({'relative':rel,'error_type':type(ex).__name__})
    return {'root':str(root),'exists':True,'files':files,'directories':dirs,'bytes':total,'GB_decimal':round(total/1e9,4),'GiB':round(total/1024**3,4),'reparse_points_skipped':reparse,'read_errors':errors,'suffix_counts':dict(sorted(types.items())),'stat_inventory_sha256':inventory.hexdigest(),'fingerprint_scope':'paths+sizes+mtimes, NOT file-content hashes; cache not yet frozen/copied'}

assert not REPORT.exists(),'Do not overwrite prior report'
started=now();top={};cache_components={};modules_components={};distros=[]
for p in sorted(HOME.iterdir()):
    if p.is_dir() and not p.is_symlink():top[p.name]=census(p)
for p in sorted((HOME/'caches').iterdir()):
    if p.is_dir() and not p.is_symlink():cache_components[p.name]=census(p)
for p in sorted((HOME/'caches/modules-2').iterdir()):
    if p.is_dir() and not p.is_symlink():modules_components[p.name]=census(p)

for key,version in [('gradle-2.13-all','2.13'),('gradle-5.2.1-bin','5.2.1'),('gradle-6.9.4-bin','6.9.4'),('gradle-8.14.4-bin','8.14.4')]:
    base=HOME/'wrapper/dists'/key
    for hdir in sorted(base.iterdir()):
        if not hdir.is_dir() or hdir.is_symlink():continue
        distro=hdir/('gradle-'+version)
        zips=[]
        for p in sorted(hdir.glob('*.zip')):
            if p.is_file() and not p.is_symlink():zips.append({'path':str(p),'bytes':p.stat().st_size,'sha256':audit.sha(p)})
        distros.append({'key':key,'version':version,'wrapper_hash_directory':hdir.name,'wrapper_hash_root':str(hdir),'distribution_root':str(distro),'whole_wrapper_slot':census(hdir),'unpacked_distribution':census(distro),'runtime_bin':census(distro/'bin'),'runtime_lib':census(distro/'lib'),'bin_launcher_exists':(distro/'bin/gradle.bat').is_file(),'license_files':[str(p) for p in sorted(distro.glob('*')) if p.is_file() and p.name.upper() in {'LICENSE','NOTICE','README'}],'zip_ok_paths':[str(p) for p in sorted(hdir.glob('*.zip.ok'))],'zip_lock_paths':[str(p) for p in sorted(hdir.glob('*.zip.lck'))],'zip_files':zips})

artifact_root=HOME/'caches/modules-2/files-2.1'
interesting={}
for group in sorted(artifact_root.iterdir()):
    if not group.is_dir() or group.is_symlink():continue
    if any(token in group.name.lower() for token in ['pitest','jacoco','junit','testng','evosuite']):
        interesting[group.name]={'census':census(group),'artifacts':{a.name:sorted(p.name for p in a.iterdir() if p.is_dir() and not p.is_symlink()) for a in sorted(group.iterdir()) if a.is_dir() and not a.is_symlink()}}

modules_bytes=cache_components['modules-2']['bytes']
unpacked_bytes=sum(d['unpacked_distribution']['bytes'] for d in distros)
slot_bytes=sum(d['whole_wrapper_slot']['bytes'] for d in distros)
runtime_bytes=sum(d['runtime_bin']['bytes']+d['runtime_lib']['bytes'] for d in distros)
free=shutil.disk_usage(R).free;reserve=12_000_000_000
options=[]
for label,size in [('complete wrapper slots including ZIPs + modules-2',slot_bytes+modules_bytes),('complete unpacked distributions + modules-2 (no redundant ZIPs/locks)',unpacked_bytes+modules_bytes),('runtime bin+lib subset + modules-2 (requires explicit subset qualification)',runtime_bytes+modules_bytes)]:
    options.append({'option':label,'estimated_copy_bytes':size,'estimated_GB_decimal':round(size/1e9,4),'free_after_copy_GB_decimal':round((free-size)/1e9,4),'above_12GB_reserve_now':free-size>reserve,'new_private_cache_generation_overhead_included':False})

report={'status':'READ_ONLY_CENSUS_NOT_FROZEN','started_utc':started,'finished_utc':now(),'script_sha256':audit.sha(__file__),'source':str(HOME),'network_calls':0,'Java_calls':0,'Gradle_calls':0,'EvoSuite_calls':0,'GPT_API_calls':0,'cache_copies':0,'cache_deletions':0,'credential_configuration_contents_read':False,'top_components':top,'cache_components':cache_components,'modules2_components':modules_components,'distribution_slots':distros,'relevant_artifact_inventory_not_resolution_proof':interesting,'disk':{'workspace_free_bytes':free,'workspace_free_GB_decimal':round(free/1e9,4),'minimum_reserved_bytes':reserve,'copy_options':options},'recommendation':['Use a new private GRADLE_USER_HOME with independent copied files and content hashes; no shared mutable cache, hardlinks or shared daemon.','Start with four pinned unpacked distributions plus modules-2 including all existing metadata-* formats and files-2.1. Exclude source lock files and regenerate locks privately. This is a conservative cache seed, not proof every dependency resolves offline.','Version-specific caches (2.13/5.2.1/6.9.4/8.14.4), jars-*, transforms-*, journal-* and native caches can be recomputed privately; leave source caches unchanged. Recompute requires disk headroom not included in estimates.','Keep exact wrapper URL/version/hash-slot mapping. Existing .zip.ok and unpacked distro can avoid redownloading, but verify copied distro with a bounded --version qualification under the pinned JDK before admission.','Use offline dependency resolution, no refresh-dependencies, and --no-daemon (or owned single-use daemon only when tool enforces it), with owned-process stop and explicit task allowlists.','Do not copy user gradle.properties, init.gradle/init.gradle.kts/init.d, daemon logs/state, notifications, .tmp, workers, jdks, native state, credential files or unrelated user configuration. Do not read/print their values.','Recheck D disk reserve immediately before copy and before every job; this census may overlap parent Maven execution. Prefer incremental per-wrapper independent copy if full seed leaves inadequate runtime reserve.','A runtime-only bin/lib subset saves docs/samples/ZIP duplication but must be documented and qualified; do not silently claim complete original -all distribution bytes.']}
with REPORT.open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
audit.log('B1_GRADLE_CACHE_READONLY_CENSUS',report_sha256=audit.sha(REPORT),source=str(HOME),cache_copy_bytes=0,experimental_calls=0,credential_configuration_contents_read=False)
audit.verify()
print(json.dumps({'status':report['status'],'report_sha256':audit.sha(REPORT),'distribution_versions':[d['version'] for d in distros],'modules2_bytes':modules_bytes,'unpacked_distribution_bytes':unpacked_bytes,'runtime_bin_lib_bytes':runtime_bytes,'disk':report['disk']},indent=2))
