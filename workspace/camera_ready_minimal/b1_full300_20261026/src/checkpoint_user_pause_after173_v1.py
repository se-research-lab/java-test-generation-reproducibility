"""User-requested pause only. No experiment execution or automatic resume."""
import json,sys,psutil,hashlib,os
from pathlib import Path
from datetime import datetime,timezone
from maven_adapter_v1 import R,sha,dump
from parallel_pin_verify_v1 import verify_pins
A=R/'completion_amendment_v1';O=A/'pause_20261027_after173_v1';B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B));import audit
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def now():return datetime.now(timezone.utc).isoformat()
def live(owner):
 try:
  p=psutil.Process(owner['pid']);return p if p.create_time()==owner['create_time'] else None
 except psutil.NoSuchProcess:return None
def archive_entries(folder):
 p=folder/'artifact_manifest.json';rows=load(p);entries={}
 for row in rows:
  rel=row['relative'] if 'relative' in row else row['path'].removeprefix(folder.relative_to(B).as_posix()+'/')
  assert rel and not rel.startswith('/') and '\\' not in rel and ':' not in rel and all(x not in {'','..','.'} for x in rel.split('/'))
  assert rel not in entries;entries[rel]=row
 return entries
def main():
 assert (R/'STOP_REQUESTED.json').exists();assert not (O/'checkpoint.json').exists()
 current=R/'jobs/173_completion_pom_v3';entries=archive_entries(current)
 actual={p.relative_to(current).as_posix():p for p in current.rglob('*') if p.is_file() and 'temp' not in p.relative_to(current).parts and p.name!='artifact_manifest.json'}
 extras=set(actual)-set(entries);assert set(entries)<=set(actual)
 assert extras=={'derived_pom_evidence/after_generation_and_measurement.json','derived_pom_evidence/after_generation_and_measurement.xml'}
 verify_pins({str(current/rel):row['sha256'] for rel,row in entries.items()})
 receipt=load(current/'derived_pom_evidence/after_generation_and_measurement.json');assert receipt['sha256']==sha(current/'derived_pom_evidence/after_generation_and_measurement.xml')==sha(current/'repo/server/.flattened-pom.xml')
 full=[{'relative':rel,'sha256':sha(p),'bytes':p.stat().st_size} for rel,p in sorted(actual.items())]+[{'relative':'artifact_manifest.json','sha256':sha(current/'artifact_manifest.json'),'bytes':(current/'artifact_manifest.json').stat().st_size}]
 dump(O/'current173_complete_archive.json',full)
 dump(O/'current173_archive_verification.json',{'status':'PASS_ALL_ORIGINAL_ARCHIVE_BYTES_AND_EXACT_POST_ARCHIVE_RECEIPTS','files_original_archive':len(entries),'extra_receipts':sorted(extras),'extra_receipts_reason':'controller captured derived POM receipt after its original archive; original manifest retained, complete external archive created here','complete_external_archive_sha256':sha(O/'current173_complete_archive.json'),'original_archive_modified':False,'result_sha256':sha(current/'result.json')})
 audit.log('USER_PAUSE_CURRENT173_CHECKPOINT_VERIFIED',result_sha256=sha(current/'result.json'),archive_sha256=sha(O/'current173_complete_archive.json'),original_archive_modified=False)
 # No in-flight measurement may be terminated. Stop only an idle/source-copy dispatcher.
 owner=load(A/'maven_pom_run_v3/owner.json');p=live(owner);termination={'dispatcher_owner':owner,'measurement_process_terminated':False,'at_utc':now()}
 if p:
  children=p.children(recursive=True);assert all(c.name().lower()=='conhost.exe' for c in children),'Wait for command completion; never kill measurement'
  nextjob=R/'jobs/211_completion_pom_v3';assert not list((nextjob/'commands').glob('*/started.json'))
  termination['idle_dispatcher_terminated']=True;termination['remaining_descendants']=[{'pid':c.pid,'create_time':c.create_time(),'name':c.name()} for c in children]
  p.terminate();p.wait(15)
 else:termination['idle_dispatcher_terminated']=False;termination['dispatcher_exited_naturally']=True
 dump(O/'dispatcher_stop.json',termination);audit.log('USER_PAUSE_DISPATCHER_STOPPED_WITHOUT_MEASUREMENT_KILL',**termination)
 # Keep the preparatory211 bytes as evidence, in their existing location.
 unstarted=R/'jobs/211_completion_pom_v3';assert not list((unstarted/'commands').glob('*/started.json'))
 draft=[{'relative':p.relative_to(unstarted).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(unstarted.rglob('*')) if p.is_file()]
 dump(O/'unstarted211_preparation_archive.json',draft)
 jobs=load(R/'manifest300.json');selected={i:R/'jobs'/f'{i:03d}_completion_pit_v2/result.json' for i in [4,40,45,129,135,156,169,170,184,197]}
 selected.update({i:R/'jobs'/f'{i:03d}_completion_junit3_v2/result.json' for i in [48,49,128,138,145,148,198,202,224,239]})
 selected.update({72:R/'jobs/072_completion_pom_v2/result.json',112:A/'result_reconciliations_v1/112/result.json',119:R/'jobs/119_completion_pom_v3/result.json',163:R/'jobs/163_completion_pom_v3/result.json',173:current/'result.json'})
 done=[];pins={}
 for i,path in sorted(selected.items()):
  d=load(path);assert d['class_key']==jobs[i-1]['class_key'] and d['seed']==jobs[i-1]['seed'];pins[str(path)]=sha(path)
  folder=Path(d['raw_job_path']) if d.get('raw_job_path') else path.parent;manifest=folder/'artifact_manifest.json';assert manifest.exists();pins[str(manifest)]=sha(manifest)
  # Recheck outcome/suite/report/finished-log anchors for the24 already accepted cases.
  for rel,row in archive_entries(folder).items():
   name=rel.rsplit('/',1)[-1]
   if name in {'result.json','native_generated.json','suite_reuse.json','mutations.csv','jacoco.csv','production_bytecode_guard.json','finished.json'} or name.endswith(('_ESTest.java','_ESTest_scaffolding.java')) or name.startswith('TEST-') and name.endswith('.xml'):pins[str(folder/rel)]=row['sha256']
  done.append({'index':i,'class_key':d['class_key'],'seed':d['seed'],'selected_result':str(path),'result_sha256':sha(path),'raw_archive':str(manifest),'raw_archive_sha256':sha(manifest),'configuration':d['configuration'],'scope':'COMPILE_TEST_ONLY_PIT_UNRESOLVED' if d.get('test_only_process_gate') is not None else 'TIMEOUT_CONVENTIONAL_E2E_ZERO_OBSERVED_NULL' if i==112 else 'VALID_PIT_REPORT','observed_mutation_percent':d.get('mutation_score_percent'),'test_suite_evidence':d.get('strict_suite_evidence'),'must_not_rerun':True})
 verify_pins(pins)
 pending=[jobs[i-1] for i in [211,220,269,275,294]]
 lock=A/'admission_maven_pom_v3.json';admission=load(lock);verify_pins(admission['code_and_input_hashes']);verify_pins(admission['tool_hashes'])
 dump(O/'accepted25.json',done);dump(O/'remaining5.json',pending);dump(O/'checkpoint_pins.json',pins)
 checkpoint={'status':'PAUSED_AFTER_CURRENT_CLASS_CHECKPOINT_VERIFIED','paused_utc':now(),'completed_current_class':173,'completed30_subset_count':25,'previous24_indices':sorted(set(selected)-{173}),'accepted25_indices':sorted(selected),'remaining_indices':[211,220,269,275,294],'remaining_count':5,'source_restoration_only211':{'path':str(unstarted),'started_commands':0,'generation_calls':0,'measurement_calls':0,'preparation_archive_sha256':sha(O/'unstarted211_preparation_archive.json'),'not_a_scored_attempt':True},'admission':str(lock),'admission_sha256':sha(lock),'policy_seed_config_changed':False,'current_archive_verified':True,'accepted_result_report_suite_pins_verified':len(pins),'automatic_resume':False,'queues_allowed':False,'STOP_requested_sha256':sha(R/'STOP_REQUESTED.json'),'GPT_API_calls':0,'full300_complete':False}
 dump(O/'checkpoint.json',checkpoint);audit.log('USER_PAUSE_CHECKPOINT_SAVED',checkpoint_sha256=sha(O/'checkpoint.json'),accepted25=checkpoint['accepted25_indices'],remaining=checkpoint['remaining_indices'],automatic_resume=False)
 print(json.dumps(checkpoint,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
