"""Recover Gradle metadata solely from frozen blobs; no build/process execution.

Writes a new supplement, never edits v1 contexts, source, snapshot or admissions.
SQLite is opened read-only and every selected blob is rehashed before parsing.
"""
import json,re,sqlite3,sys
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path,PurePosixPath
from snapshot_store_v1 import digest,safe_relative,IntegrityError

R=Path(__file__).resolve().parents[1]
B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit

def load(path):return json.loads(path.read_text(encoding='utf-8'))
def ensure(ok,why):
 if not ok:raise IntegrityError(why)
def relative(value):
 ensure(isinstance(value,str),'Metadata path must be text')
 if value in {'','.'}:return ''
 ensure(value==value.strip('/') and '\\' not in value,'Noncanonical metadata path')
 safe_relative(value)
 return value
def joined(prefix,name):return '/'.join(x for x in [prefix,name] if x)
def dump(path,value):
 with path.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2)

def main():
 out=R/'inputs/gradle40_context_v2'
 ensure(not out.exists(),'Supplement already exists; no overwrite or implicit resume')
 report=R/'audit/gradle40_independent_review_v1.md'
 ensure(report.is_file(),'Independent review report missing')
 audit.verify()
 paths=[R/'manifest300.json',R/'inputs/context251_v1/manifest.json',R/'inputs/snapshot_v3/index.json',R/'inputs/snapshot_v3/complete.json',R/'src/snapshot_store_v1.py',report,Path(__file__)]
 fixed={str(p.resolve()):audit.sha(p) for p in paths}
 jobs=[j for j in load(R/'manifest300.json') if j['build_tool']=='gradle']
 ensure(len(jobs)==40 and len({j['class_key'] for j in jobs})==40,'Gradle40 membership mismatch')
 ensure(Counter(j['repo_id'] for j in jobs)=={'74999474':10,'41627638':10,'85795396':10,'6944525':10},'Unexpected repository membership')
 ensure(all(not j['reused_result'] for j in jobs),'Accepted49 reuse cannot enter new Gradle supplement')
 contexts={x['sample_index_1based']:x for x in load(R/'inputs/context251_v1/manifest.json')}
 S=R/'inputs/snapshot_v3';completion=load(S/'complete.json')
 ensure(completion['status']=='PASS' and completion['every_blob_rehashed'],'Snapshot incomplete')
 ensure(audit.sha(S/'index.json')==completion['index_sha256'],'Snapshot index drift')
 mappings=load(S/'index.json');store=S/'content.sqlite3';store_stat=store.stat()
 ensure(store_stat.st_size==completion['store_bytes'],'Snapshot store size drift')
 verified_blob_hashes=set();metadata_blob_hashes=set();rows=[];all_input_hashes=dict(fixed)
 with sqlite3.connect(store.as_uri()+'?mode=ro',uri=True) as conn:
  conn.execute('PRAGMA query_only=ON')
  ensure(conn.execute("SELECT value FROM metadata WHERE name='schema'").fetchone()==('b1-cas-v1',),'Unexpected CAS schema')
  def read_blob(record):
   safe_relative(record['relative'])
   blob=conn.execute('SELECT nbytes,data FROM blobs WHERE sha256=?',(record['sha256'],)).fetchone()
   ensure(blob is not None and blob[0]==record['bytes'] and len(blob[1])==record['bytes'],'Snapshot blob size mismatch')
   ensure(digest(blob[1])==record['sha256'],'Snapshot blob digest mismatch')
   verified_blob_hashes.add(record['sha256'])
   return blob[1]
  for j in jobs:
   index=j['sample_index_1based'];ctx=contexts[index]
   ensure(ctx['class_key']==j['class_key'] and ctx['module']==j['module'],'Context membership drift')
   sources=[s for s in ctx['metadata_sources'] if Path(s['path']).name=='project_info.json']
   ensure(len(sources)==1,'Ambiguous frozen project_info source')
   source=sources[0];blob_path=(R/Path(source['backup'])).resolve()
   ensure(blob_path.is_relative_to((R/'inputs/context251_v1/blobs').resolve()),'Metadata blob outside frozen blob directory')
   blob=blob_path.read_bytes();ensure(digest(blob)==source['sha256'],'Frozen project_info blob drift')
   metadata_blob_hashes.add(source['sha256']);all_input_hashes[str(blob_path)]=source['sha256']
   metadata=json.loads(blob.decode('utf-8'));ensure(ctx['framework_key'] in metadata,'Missing exact framework key')
   cfg=metadata[ctx['framework_key']]
   ensure(str(cfg.get('type','')).lower()=='gradle','Metadata build tool mismatch')
   version=str(cfg.get('version',''));java=str(cfg.get('java_version',''))
   ensure(re.fullmatch(r'\d+(?:\.\d+)+',version) is not None,'Missing numeric Gradle version')
   ensure(java=='1.8','Different Java metadata requires independent review')
   build_root=relative(cfg.get('build_root'));module_dir=relative(cfg.get('module_dir'));selector=relative(cfg.get('module_selector'))
   ensure(module_dir==relative(j['module']),'Metadata module_dir differs from original sampling module')
   derived_module='/'.join(x for x in [build_root,selector] if x)
   ensure(derived_module==module_dir,'Build root/module selector does not resolve to sampled module')
   matches=[m for m in mappings if index in m['class_indices']];ensure(len(matches)==1,'Ambiguous snapshot mapping')
   mapping=matches[0];snapshot_path=(R/safe_relative(mapping['manifest'])).resolve()
   ensure(snapshot_path.is_relative_to(S.resolve()),'Snapshot manifest outside completed store')
   ensure(audit.sha(snapshot_path)==mapping['sha256'],'Snapshot manifest drift')
   all_input_hashes[str(snapshot_path)]=mapping['sha256'];snapshot=load(snapshot_path)
   ensure(index in snapshot['class_indices'],'Snapshot class membership mismatch')
   files={f['relative']:f for f in snapshot['files']}
   ensure(len(files)==len(snapshot['files']),'Duplicate snapshot file path')
   focal=files[j['focal_path']];ensure(focal['sha256']==j['source_candidate']['focal_sha256'],'Focal hash differs from manifest300')
   read_blob(focal)
   required=[joined(build_root,'gradlew.bat'),joined(build_root,'gradle/wrapper/gradle-wrapper.jar'),joined(build_root,'gradle/wrapper/gradle-wrapper.properties')]
   ensure(all(p in files for p in required),'Wrapper incomplete at declared build root')
   properties_path=required[-1];properties=read_blob(files[properties_path]).decode('utf-8')
   match=re.search(r'^distributionUrl\s*=\s*(\S+)',properties,re.M)
   ensure(match is not None,'Wrapper distribution URL absent')
   url=match.group(1).replace('\\:',':');dist=re.search(r'/gradle-([\d.]+)-(bin|all)\.zip$',url)
   ensure(dist is not None and dist.group(1)==version,'Wrapper version differs from frozen project_info')
   configured_sha=re.search(r'^distributionSha256Sum\s*=\s*([0-9a-fA-F]{64})\s*$',properties,re.M)
   descriptors=[]
   root_build=[joined(build_root,n) for n in ['build.gradle','build.gradle.kts'] if joined(build_root,n) in files]
   module_build=[joined(module_dir,n) for n in ['build.gradle','build.gradle.kts'] if joined(module_dir,n) in files]
   settings=[joined(build_root,n) for n in ['settings.gradle','settings.gradle.kts'] if joined(build_root,n) in files]
   ensure(len(root_build)==1 and len(module_build)==1 and len(settings)==1,'Unexpected descriptor shape')
   names=set(required+root_build+module_build+settings)
   for prefix in {build_root,module_dir}:
    p=joined(prefix,'gradle.properties')
    if p in files:names.add(p)
   optional_shell=joined(build_root,'gradlew')
   if optional_shell in files:names.add(optional_shell)
   for name in sorted(names):
    record=files[name];data=read_blob(record)
    descriptors.append({'relative_to_repo':name,'relative_to_build_root':str(PurePosixPath(name).relative_to(PurePosixPath(build_root or '.'))),'sha256':record['sha256'],'bytes':len(data),'CAS_blob_rehashed':True})
   task_prefix=':'+selector.replace('/',':')+':' if selector else ''
   rows.append({'sample_index_1based':index,'class_key':j['class_key'],'repo_id':j['repo_id'],'original_seed':j['seed'],'sampled_module':j['module'],'framework_key':ctx['framework_key'],'Gradle_version':version,'Java_version_metadata':java,'build_root_relative_to_repo':build_root or '.','module_dir_relative_to_repo':module_dir or '.','module_selector':selector or '.','task_prefix':task_prefix,'wrapper_windows_relative_to_repo':required[0],'wrapper_properties_relative_to_repo':properties_path,'wrapper_distribution_url':url,'wrapper_distribution_type':dist.group(2),'wrapper_distribution_SHA256_if_declared':configured_sha.group(1).lower() if configured_sha else None,'junit_version_metadata':cfg.get('junit_version'),'testng_version_metadata':cfg.get('testng_version'),'dependency_interpretation':'metadata labels only; resolved classpath controls later additions','metadata_evidence':{'frozen_blob_relative_to_B1':blob_path.relative_to(R).as_posix(),'source_label_only_not_read':source['path'],'sha256':source['sha256'],'bytes':len(blob),'exact_framework_key':ctx['framework_key']},'snapshot_evidence':{'manifest_relative_to_B1':mapping['manifest'],'manifest_sha256':mapping['sha256'],'snapshot_index':mapping['snapshot_index'],'focal_path':j['focal_path'],'focal_sha256':focal['sha256'],'selected_files':descriptors},'status':'METADATA_VERIFIED_EXECUTION_NOT_ADMITTED'})
 after=store.stat();ensure((after.st_size,after.st_mtime_ns)==(store_stat.st_size,store_stat.st_mtime_ns),'Snapshot store changed during read-only supplement')
 for p,h in all_input_hashes.items():ensure(audit.sha(p)==h,'Frozen input changed during metadata supplement')
 audit.verify()
 out.mkdir(exist_ok=False)
 manifest=out/'manifest.json';dump(manifest,rows)
 groups={}
 for row in rows:
  key=(row['repo_id'],row['build_root_relative_to_repo'],row['module_selector'],row['Gradle_version'])
  groups.setdefault(key,[]).append(row['sample_index_1based'])
 summary={'status':'PASS_METADATA_ONLY','created_utc':datetime.now(timezone.utc).isoformat(),'class_count':40,'repositories':4,'new_experiment_calls':0,'GPT_API_calls':0,'Java_Gradle_EvoSuite_calls':0,'benchmark_admitted':False,'original_context_edited':False,'snapshot_store_open_mode':'read-only URI and query_only=ON','snapshot_store_completion_sha256':completion['store_sha256'],'snapshot_store_whole_file_rehashed_by_this_supplement':False,'selected_unique_snapshot_blobs_rehashed':len(verified_blob_hashes),'distinct_frozen_project_info_blobs_verified':len(metadata_blob_hashes),'manifest_sha256':audit.sha(manifest),'groups':[{'repo_id':key[0],'build_root':key[1],'module_selector':key[2],'Gradle_version':key[3],'sample_indices':indices} for key,indices in groups.items()],'fixed_input_hashes':all_input_hashes,'independent_review':{'path':str(report.resolve()),'sha256':audit.sha(report)},'blockers_before_execution':['Qualify wrapper/JDK and per-version DSL/provider recipes; metadata PASS is not runtime admission','Prepare independent private GRADLE_USER_HOME/distributions/dependency/plugin cache with hashes; no shared daemon/cache writes','Seal Gradle-specific supervisor/command allowlist and legacy gate/900s timeout mapping before outcomes','Verify actual resolved JUnit/TestNG/runtime classpath and native JUnit4 discovery; do not upgrade from metadata labels','Do not assign score0 to unattempted40 or use E0 as E1']}
 summary_path=out/'summary.json';dump(summary_path,summary)
 audit.log('B1_GRADLE_METADATA_SUPPLEMENT_CREATED',manifest_path=str(manifest.resolve()),manifest_sha256=audit.sha(manifest),summary_path=str(summary_path.resolve()),summary_sha256=audit.sha(summary_path),script_sha256=audit.sha(__file__),independent_report_path=str(report.resolve()),independent_report_sha256=audit.sha(report),classes=40,new_experiment_calls=0,GPT_API_calls=0,snapshot_SQLite_read_only=True)
 audit.verify()
 print(json.dumps({'status':summary['status'],'classes':40,'groups':summary['groups'],'manifest_sha256':audit.sha(manifest),'summary_sha256':audit.sha(summary_path),'selected_unique_snapshot_blobs_rehashed':len(verified_blob_hashes),'report_sha256':audit.sha(report),'new_experiment_calls':0,'benchmark_admitted':False},indent=2))

if __name__=='__main__':main()
