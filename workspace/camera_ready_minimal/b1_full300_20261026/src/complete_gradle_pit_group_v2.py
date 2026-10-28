"""Post-outcome measurement-only amendment. Ten saved suites, one frozen attempt each."""
import json,msvcrt,sys,traceback,shutil,psutil
from pathlib import Path
from datetime import datetime,timezone
from maven_adapter_v1 import R,sha,dump,GuardAbort,native_suite
from prepare_sandbox_v1 import prepare
from gradle_execution_v2 import Commands,load,phase_recipe as unused_phase
from gradle_tool_repository_amendment_v1 import main_audit_script,measurement_script
from gradle_command_policy_v3 import CONTEXT
from maven_controller_v2 import source_hashes,archive
from gradle_measurement_parser_v1 import parse
from parallel_pin_verify_v1 import verify_pins
from run_maven_b1_v3 import guards
from projection_io_v1 import publish_json
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
A=R/'completion_amendment_v1';ADMISSION=A/'admission_gradle_pit_v2.json';RUN=A/'gradle_pit_run_v2'

def now():return datetime.now(timezone.utc).isoformat()
def ensure(v,s):
 if not v:raise GuardAbort(s)
def phase(config,out,name):
 p=out/'recipes'/name;p.mkdir(parents=True);(p/'evidence').mkdir()
 fn=main_audit_script if name=='main_audit' else measurement_script
 text=fn(config,p);(p/'init.gradle').write_text(text,encoding='utf-8',newline='\n')
 dump(p/'recipe.json',{'config':config,'phase':name,'sha256':sha(p/'init.gradle'),'post_outcome_amendment':True,'recipe_sha256':sha(R/'src/gradle_tool_repository_amendment_v1.py')})
 return p/'init.gradle',p/'evidence'
def relative_bytecode(rows,repo):
 result={}
 for k,h in rows.items():
  root,rel=k.split('::',1);p=Path(root)/rel
  result[p.relative_to(repo).as_posix()]=h
 return result

def execute(job,context,out,event):
 i=job['sample_index_1based'];old=R/'jobs'/f'{i:03d}_gradle_v1'
 prepare(i,out,R/'inputs/snapshot_v3')
 dump(out/'job_admission.json',{'batch_admission_sha256':sha(ADMISSION),'job':job,'reuse_from':str(old),'new_generation_allowed':False,'attempt':1})
 suite=load(old/'native_generated.json');ensure(suite['complete'],'Incomplete historical native suite')
 for row in suite['files']:
  src=Path(row['path']);ensure(sha(src)==row['sha256'],'Old native suite hash drift')
  dest=out/'repo'/src.relative_to(old/'repo');ensure(not dest.exists(),'Existing suite in new source snapshot')
  dest.parent.mkdir(parents=True,exist_ok=True)
  with src.open('rb') as f,dest.open('xb') as g:shutil.copyfileobj(f,g)
  ensure(sha(dest)==row['sha256'],'Suite copy mismatch')
 dump(out/'suite_reuse.json',{'source_manifest':str(old/'native_generated.json'),'source_manifest_sha256':sha(old/'native_generated.json'),'files':suite['files'],'generation_calls':0,'Java_edits':False})
 commands=Commands(out,job,context,ADMISSION,event)
 cfg=load(old/'recipes/measure/recipe.json')['config'];cfg['repo_root']=str(out/'repo')
 # Retain the old decision on test support and all measurement versions/targets.
 init,before_dir=phase(cfg,out,'main_audit');prefix=context['task_prefix'];stages=[]
 r,t=commands.gradle('compile_classpath',init,[prefix+'classes',prefix+'b1WriteClasspaths']);stages.append({'stage':'compile_classpath','returncode':r.returncode,'timeout':t})
 ensure(r.returncode==0 and not t,'New main-input verification unavailable; unresolved')
 before=load(before_dir/'b1_compile_audit.json');commands.check_artifacts(before)
 orig=load(old/'recipes/main_audit/evidence/b1_compile_audit.json')
 def sig(rows,repo):
  return [(('@repo/'+Path(x['path']).relative_to(repo).as_posix()) if Path(x['path']).is_relative_to(repo) else str(Path(x['path'])),x.get('sha256'),x['kind']) for x in rows]
 for k in ['main_compile','main_runtime','test_compile']:
  ensure(sig(orig[k],old/'repo')==sig(before[k],out/'repo'),'Pre-integration dependency closure differs from original suite input: '+k)
 expected=relative_bytecode(load(old/'recipes/main_audit/evidence/b1_production_classes.json'),old/'repo')
 observed=relative_bytecode(load(before_dir/'b1_production_classes.json'),out/'repo')
 ensure(expected==observed,'Production bytecode differs from suite generation input')
 init,evidence=phase(cfg,out,'measure')
 r,t=commands.gradle('classpath',init,[prefix+'b1WriteClasspaths']);stages.append({'stage':'classpath','returncode':r.returncode,'timeout':t})
 ensure(r.returncode==0 and not t,'Tool resolution unavailable; unresolved, not build failure')
 after=load(evidence/'b1_measurement_dependency_audit.json');commands.check_artifacts(after)
 for k in ['main_compile','main_runtime']:ensure(sig(before[k],out/'repo')==sig(after[k],out/'repo'),'Production dependency closure changed')
 previous={x['path']:x.get('sha256') for x in before['test_compile']};current={x['path']:x.get('sha256') for x in after['test_compile']}
 ensure(all(current.get(k)==v for k,v in previous.items()),'Existing test dependency removed or upgraded')
 ensure(any(Path(x['path']).name=='pitest-command-line-1.3.1.jar' for x in after['pit_engine']),'PIT engine version changed')
 r,t=commands.gradle('test_jacoco',init,[prefix+'b1NativeTest',prefix+'b1NativeJacocoReport']);stages.append({'stage':'test_jacoco','returncode':r.returncode,'timeout':t})
 gate=False
 if r.returncode==0 and not t:
  r,t=commands.gradle('pit',init,[prefix+'pitest']);stages.append({'stage':'pit','returncode':r.returncode,'timeout':t});gate=not t
 ensure(source_hashes(out/'repo')==commands.source_expected,'Source or native test changed')
 for rel,h in expected.items():ensure((out/'repo'/rel).is_file() and sha(out/'repo'/rel)==h,'Production bytecode changed')
 raw=parse(commands.module,evidence,job,gate)
 result={'sample_index_1based':i,'class_key':job['class_key'],'seed':job['seed'],'repo_id':job['repo_id'],'configuration':'E1_post_outcome_PIT_repository_amendment_v1','generation_success':True,'generation_calls':0,'generation':'REUSED_EXACT_NATIVE_SUITE','compile_production':'PASS_IDENTICAL_BYTECODE','stage_outcomes':stages,'measurement_attempted':True,'source_guard':'PASS','production_bytecode_guard':'PASS','GPT_API_calls':0,'selection_rule':'single amendment attempt; replace prior unresolved measurement irrespective of score, never max','post_outcome_amendment':True,**raw}
 result['compile_test']='PASS' if raw['surefire_suites'] else 'UNRESOLVED_SEE_LOG'
 result['test_execution']='PASS' if raw['strict_suite_evidence'] else 'FAIL' if any(x['errors']+x['failures'] for x in raw['cases']) else 'UNRESOLVED_OR_SKIPPED'
 pit_ok=bool(stages[-1]['stage']=='pit' and stages[-1]['returncode']==0 and not stages[-1]['timeout'] and raw['pit_report_present'] and raw['focal_mutants'])
 result['PIT']='VALID_FOCAL_REPORT' if pit_ok else 'UNRESOLVED_OR_NO_MUTANTS'
 result['observed_mutation_percent']=raw['mutation_score_percent'] if pit_ok else None
 result['end_to_end_score_percent']=raw['mutation_score_percent'] if pit_ok and gate else 0.0 if result['test_execution']=='FAIL' else None
 result['score_basis']='OBSERVED_PIT_WITH_PROCESS_GATE' if pit_ok and gate else 'CONVENTIONAL_ZERO_TEST_EXECUTION_FAILURE' if result['test_execution']=='FAIL' else 'UNRESOLVED_NO_ZERO_FILL'
 result['terminal']=result['end_to_end_score_percent'] is not None
 dump(out/'result.json',result);archive(out);return result

def main():
 lock=load(ADMISSION);ensure(not RUN.exists(),'No automatic resume or overwrite');ensure(lock['code_and_input_hashes'][str(Path(__file__).resolve())]==sha(__file__),'Runner not sealed')
 with (R/'runtime/dispatcher.lock').open('r+b') as mutex:
  mutex.seek(0);msvcrt.locking(mutex.fileno(),msvcrt.LK_NBLCK,1)
  try:
   guards(load(R/'admission_maven_v6.json'));verify_pins(lock['code_and_input_hashes']);RUN.mkdir()
   me=psutil.Process();dump(RUN/'owner.json',{'pid':me.pid,'create_time':me.create_time(),'admission_sha256':sha(ADMISSION),'started_utc':now()})
   jobs=load(R/'manifest300.json');metadata={x['sample_index_1based']:x for x in load(R/'inputs/context251_v1/manifest.json')};contexts={x['sample_index_1based']:x for x in load(CONTEXT)};done=[]
   for i in lock['admitted_sample_indices']:
    ensure(sha(ADMISSION)==load(RUN/'owner.json')['admission_sha256'],'Admission changed mid-batch');verify_pins(lock['code_and_input_hashes'])
    out=R/'jobs'/f'{i:03d}_completion_pit_v2';ensure(not out.exists(),'Prior output exists');j=jobs[i-1];job={**j,**{k:metadata[i][k] for k in ['package','selected_test_fqcn','junit_version','testng_version']}}
    def event(kind,**kw):
     with (out/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'at_utc':now(),'kind':kind,**kw})+'\n')
     audit.log('E1_COMPLETION_PIT_'+kind,sample_index=i,**kw)
     publish_json(R/'runtime/completion_progress.json',{'phase':'PIT_MEASUREMENT_ONLY','active_index':i,'finished_indices':done,'event':kind,'updated_utc':now(),'new_GPT_calls':0,'new_generation_calls':0,'full300_complete':False},label='completion_progress')
    try:
     result=execute(job,contexts[i],out,event);done.append(i);print(json.dumps({'index':i,'observed_mutation':result['observed_mutation_percent'],'test_execution':result['test_execution'],'terminal':result['terminal'],'new_generation_calls':0}),flush=True)
    except GuardAbort as e:
     # Environment/availability failures may remain unresolved; integrity violations stop the batch.
     if not any(s in str(e) for s in ['verification unavailable','Tool resolution unavailable']):raise
     dump(out/'unresolved.json',{'index':i,'class_key':j['class_key'],'reason':str(e),'score':None,'automatic_retry':False});archive(out);done.append(i)
   guards(load(R/'admission_maven_v6.json'));verify_pins(load(A/'input_audit/baseline_pins.json'))
   dump(RUN/'complete.json',{'status':'GROUP_ONE_PASS_FINISHED','indices':done,'GPT_API_calls':0,'new_generation_calls':0,'full300_complete':False,'finished_utc':now()})
   publish_json(R/'runtime/completion_progress.json',{'phase':'PIT_GROUP_FINISHED','active_index':None,'finished_indices':done,'updated_utc':now(),'full300_complete':False},label='completion_progress')
  except BaseException as e:
   if RUN.exists():dump(RUN/'interrupted.json',{'error':str(e),'type':type(e).__name__,'traceback':traceback.format_exc(),'automatic_resume':False})
   if 'out' in locals() and out.exists() and not (out/'artifact_manifest.json').exists():archive(out)
   raise
  finally:mutex.seek(0);msvcrt.locking(mutex.fileno(),msvcrt.LK_UNLCK,1)
if __name__=='__main__':main()
