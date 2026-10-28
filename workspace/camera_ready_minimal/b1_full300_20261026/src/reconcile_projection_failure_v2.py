"""Reconcile completed13 UI snapshots only. No Java/Gradle/benchmark/API."""
import json,msvcrt,sys,re,shutil
from pathlib import Path
from datetime import datetime,timezone
from maven_adapter_v1 import R,sha,dump,GuardAbort
from checkpoint_archive_guard_v2 import verify
from run_maven_b1_v2 import guards
from projection_io_v1 import publish_json,ensure
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
O=R/'audit/projection_reconciliation_v2'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def now():return datetime.now(timezone.utc).isoformat()

def reconcile():
 ensure(not O.exists(),'No overwrite/resume of UI reconciliation')
 static=load(R/'validation/projection_io_v1/result.json');ensure(static['status']=='PASS_STATIC_MOCKED_IO_ONLY' and static['source_sha256']==sha(R/'src/projection_io_v1.py'),'Publisher static validation missing/drifted')
 guards(load(R/'admission_maven_v2.json'))
 folders=sorted(p for p in (R/'jobs').iterdir() if p.is_dir() and re.fullmatch(r'\d{3}',p.name))
 ensure(len(folders)==13,'Expected13 terminal benchmark job folders')
 archive_checks={};raw_results={};result_hashes={};generation=[]
 for folder in folders:
  index=int(folder.name);archive_checks[folder.name]=verify(folder);raw=load(folder/'result.json')
  ensure(raw['terminal'] is True and raw['sample_index_1based']==index and raw['GPT_API_calls']==0,'Unexpected/nonterminal job result')
  raw_results[index]=raw;result_hashes[folder.name]=sha(folder/'result.json')
  for plan in sorted((folder/'commands').glob('*/plan.json')):
   p=load(plan)
   if '-jar' not in p['argv']:continue
   started=(plan.parent/'started.json').exists();interrupted=load(plan.parent/'interrupted.json') if (plan.parent/'interrupted.json').exists() else None
   generation.append({'sample_index_1based':index,'command':plan.parent.relative_to(R).as_posix(),'planned':True,'actually_started':started,'interrupted':interrupted})
 diagnostic=R/'jobs/003_native_junit_diagnostic_v3';archive_checks['003_native_junit_diagnostic_v3']=verify(diagnostic)
 desired=load(R/'manifest300.json');ensure(len(desired)==300 and [j['sample_index_1based'] for j in desired]==list(range(1,301)) and len({j['class_key'] for j in desired})==300,'Original300 key/order identity invalid')
 for row in desired:
  index=row['sample_index_1based']
  if index not in raw_results:continue
  ensure(raw_results[index]['class_key']==row['class_key'],'Raw job class identity mismatch')
  result=load(diagnostic/'diagnostic_result.json') if index==3 else raw_results[index]
  row['status']='COMPLETED_E1_MAVEN' if result['legacy_process_build'] else 'TERMINAL_PIPELINE_FAILURE'
 oldtmp=R/'runtime/manifest_projection.tmp'
 ensure(oldtmp.is_file() and load(oldtmp)==desired,'Abandoned v2 manifest temp does not logically match desired300 statuses')
 started=sum(r['actually_started'] for r in generation);planned=len(generation)
 not_started=[r['sample_index_1based'] for r in generation if not r['actually_started']]
 ensure(started==11 and planned==14 and not_started==[12,16,23],'Generation counters differ from verified checkpoint13')
 ensure(all('[WinError 206]' in (r['interrupted'] or {}).get('detail','') for r in generation if not r['actually_started']),'Unstarted commands do not match documented Win206 failures')
 failure=B/'audit/b1_maven_v2_next10.stderr.txt';text=failure.read_text(encoding='utf-8')
 ensure('PermissionError' in text and 'WinError 5' in text and 'manifest_projection.tmp' in text and 'manifest_live300.json' in text,'Missing recorded v2 UI sharing failure evidence')
 O.mkdir(exist_ok=False);preserved=[]
 for label,path in [('old_manifest_projection.tmp',oldtmp),('status_before.json',R/'status.json'),('manifest_live300_before.json',R/'runtime/manifest_live300.json'),('v2_batch_stderr.txt',failure)]:
  raw=path.read_bytes();dest=O/label
  with dest.open('xb') as f:f.write(raw)
  ensure(sha(dest)==sha(path),'UI evidence backup mismatch');preserved.append({'source':str(path),'backup':str(dest),'sha256':sha(path),'bytes':len(raw)})
 dump(O/'archive_checks.json',archive_checks);dump(O/'generation_counter_evidence.json',generation)
 s=load(R/'status.json');s.update(phase='CHECKPOINT13_UI_RECONCILED_V3_PENDING',updated_utc=now(),new_completed=13,running=0,maven_pending=198,gradle_pending=40,benchmark_admitted=False,new_API_calls=0,benchmark_EvoSuite_calls=started,benchmark_EvoSuite_commands_planned=planned,benchmark_EvoSuite_commands_not_started=planned-started,benchmark_EvoSuite_not_started_sample_indices=not_started,fixture_EvoSuite_calls=2,new_EvoSuite_calls=2+started,active_sample_index=None,GPT_guard='PASS',GPT_guard_checked_utc=now(),reuse49_guard='PASS',ui_projection_health='RECONCILED',ui_technical_hold=True,automatic_v2_resume=False,Gradle_version_qualification_allowed=True,Gradle_benchmark_admitted=False,disk_free_GB=round(shutil.disk_usage(R).free/1e9,2))
 s['tasks'][5]['status']='BLOCKED';s['tasks'][5]['name']='13 class Maven terminal; chờ dispatcher v3 xử lý UI publication'
 s['blockers']=['UI technical hold: v2 kết thúc13 class; chưa cho tự tiếp tục benchmark bằng v2','Gradle40 chưa đủ build/provider qualification; kiểm version riêng vẫn được phép','E1full300 chưa hoàn tất; không sửa paper hoặc thay mẫu GPT']
 receipts={'manifest':publish_json(R/'runtime/manifest_live300.json',desired,label='reconcile13_manifest'),'status':publish_json(R/'status.json',s,label='reconcile13_status')}
 dump(O/'publication_receipts.json',receipts)
 ensure(all(r['published'] for r in receipts.values()),'Reconciliation publication failed; preserve receipts and require explicit review')
 ensure(load(R/'runtime/manifest_live300.json')==desired and load(R/'status.json')==s,'Published UI logical data differs')
 ensure(sha(oldtmp)==next(r['sha256'] for r in preserved if r['source']==str(oldtmp)),'Old v2 temp changed during reconciliation')
 for folder in folders:ensure(sha(folder/'result.json')==result_hashes[folder.name],'Raw terminal result changed');verify(folder)
 guards(load(R/'admission_maven_v2.json'))
 result={'status':'PASS_UI_RECONCILED_NO_BENCHMARK','finished_utc':now(),'phase':s['phase'],'terminal_new_classes':13,'accepted49_guard':'PASS','GPT_original585_guard':'PASS','all13_archive_checks':'PASS','old_tmp_logically_matches300':True,'preserved_files':preserved,'raw_results_unchanged':result_hashes,'benchmark_generation_planned':planned,'benchmark_generation_actually_started':started,'spawn_failures_before_start':not_started,'fixtures_EvoSuite_calls':2,'new_API_calls':0,'benchmark_admitted_in_UI':False,'global_STOP_created':False,'v2_code_admission_modified':False,'v2_exit_failure_classification':'UI snapshot replace sharing race after all10 invocation jobs terminal; no raw experiment data failure','automatic_v2_resume':False,'Gradle_version_qualification_allowed':True,'publisher_source_sha256':sha(R/'src/projection_io_v1.py'),'reconciler_source_sha256':sha(__file__)}
 dump(O/'result.json',result);audit.log('B1_CHECKPOINT13_UI_RECONCILED',result_sha256=sha(O/'result.json'),phase=s['phase'],new_classes=13,planned=planned,actually_started=started,new_experiment_calls=0)
 print(json.dumps(result,ensure_ascii=False,indent=2));return 0

def main():
 lock=R/'runtime/dispatcher.lock'
 with lock.open('r+b') as file:
  try:file.seek(0);msvcrt.locking(file.fileno(),msvcrt.LK_NBLCK,1)
  except OSError:print('NOT_STARTED: dispatcher busy; no reconciliation outputs created');return 2
  try:return reconcile()
  finally:file.seek(0);msvcrt.locking(file.fileno(),msvcrt.LK_UNLCK,1)
if __name__=='__main__':sys.exit(main())
