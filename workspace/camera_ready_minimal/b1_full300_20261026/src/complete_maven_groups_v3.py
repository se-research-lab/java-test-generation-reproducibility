"""Serial completion of the two Maven groups, one sealed attempt per eligible class."""
import argparse,json,msvcrt,sys,traceback,shutil,psutil
from pathlib import Path
from datetime import datetime,timezone
import pandas as pd
from maven_adapter_v1 import R,sha,dump,GuardAbort,generation_bindings,native_suite
from prepare_sandbox_v1 import prepare
from pom_namespace_completion_v1 import restore_pom
from maven_controller_v2 import archive,bytecode,dependency,effective,ensure
from flatten_output_guard_completion_v1 import source_hashes,capture
from measurement_parser_v1 import parse
from b1_maven_commands_v3 import MavenCommands
from completion_measurement_commands_v3 import MeasurementCommands
from junit3_test_support_completion_v1 import patch as junit_patch
from parallel_pin_verify_v1 import verify_pins
from run_maven_b1_v3 import guards
from projection_io_v1 import publish_json
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
A=R/'completion_amendment_v1'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def now():return datetime.now(timezone.utc).isoformat()
def junit_measure(job,out,admission,event):
 old=R/'jobs'/('072_completion_pom_v1' if job['sample_index_1based']==72 else f"{job['sample_index_1based']:03d}");module=out/'repo'/job['module']
 oldmodule=old/'repo'/job['module'];suite=load(old/'native_generated.json');ensure(suite['complete'],'No complete saved suite')
 # Reuse the exact already-integrated POM and suite that stopped at the JUnit3 guard.
 pom=module/'pom.xml';(out/'snapshot_pom_before_reuse.xml').write_bytes(pom.read_bytes());pom.write_bytes((oldmodule/'pom.xml').read_bytes())
 for row in suite['files']:
  p=Path(row['path']);ensure(sha(p)==row['sha256'],'Native suite drift');dest=out/'repo'/p.relative_to(old/'repo');ensure(not dest.exists(),'Unexpected native suite');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
 dump(out/'suite_reuse.json',{'source':str(old),'files':suite['files'],'generation_calls':0,'test_edits':False,'original_POM_sha256':sha(oldmodule/'pom.xml')})
 lock=load(admission);specific={**lock,'job':job,'output':str(out.resolve()),'generation_allowed':False};dump(out/'measurement_admission.json',specific)
 commands=MeasurementCommands(out,job,out/'measurement_admission.json',event);ns=generation_bindings(commands,out,event)
 settings=['-s',str(out/'settings.xml')] if (out/'settings.xml').exists() else []
 skip=ns['common_maven_skip_args']();args=['mvn',*settings,'-Dtest='+job['selected_test_fqcn'],*skip]
 r=commands.run(['mvn',*settings,*skip,'-DskipTests=true','compile','dependency:build-classpath','-Dmdep.outputFile='+str(module/'target/evosuite-classpath.txt')],cwd=module,timeout=300)
 ensure(r.returncode==0,'Production verification unavailable; unresolved')
 production=bytecode(module);baseline=load(old/'production_generation_baseline.json') if (old/'production_generation_baseline.json').exists() else load(A/'stage_completion_v4_preparation/072_generation_bytecode_baseline.json');ensure(production==baseline,'Production bytecode differs from suite-generation baseline')
 before=dependency(commands,args,module,out,'before');effective(commands,args,module,out,'before')
 original=load(old/'before_dependency.json') if (old/'before_dependency.json').exists() else before
 sig=lambda d,k:[(x['path'],x['sha256']) for x in d[k]]
 for k in ['classpath','compile_classpath']:ensure(sig(before,k)==sig(original,k),'Resolved original dependency graph changed')
 if job['sample_index_1based']==72:
  capture(out,'before_measurement')
 else:junit_patch(module,out,before)
 after=dependency(commands,args,module,out,'after');effective(commands,args,module,out,'after')
 for k in ['classpath','compile_classpath']:ensure(sig(before,k)==sig(after,k),'Dependency graph changed by test support')
 expected=source_hashes(out/'repo');test=job['selected_test_fqcn']
 df=pd.DataFrame([{'Project':job['repo_id'],'Module':job['module'],'Focal_Class':job['focal_class'],'Test_Class':test.split('.')[-1],'Focal_Path':str(out/'repo'/job['focal_path']),'Test_Path':(module/'src/test/java'/Path(*test.split('.')).with_suffix('.java')).as_posix()}])
 if job['sample_index_1based']==72:
  gate=ns['run_maven_test_command'](str(module),df,'Windows')[0]
  capture(out,'after_measurement')
 else:
  r=commands.run([*args,'clean','test','jacoco:prepare-agent','jacoco:report'],cwd=module,timeout=300)
  gate=r.returncode==0 and 'BUILD SUCCESS' in r.stdout
 ensure(source_hashes(out/'repo')==expected,'Source or suite changed during measurement')
 observed=bytecode(module);ensure(not any(observed.get(k)!=v for k,v in production.items()),'Production bytecode changed/missing')
 raw=parse(module,job['focal_class'],job['package'],test,gate)
 result={'sample_index_1based':job['sample_index_1based'],'class_key':job['class_key'],'repo_id':job['repo_id'],'seed':job['seed'],'configuration':'E1_post_outcome_existing_suite_stage_completion_v2','generation_success':True,'generation_calls':0,'generation':'REUSED_EXACT_SUITE','measurement_attempted':True,'source_guard':'PASS','production_bytecode_guard':'PASS','production_dependency_graph':'UNCHANGED','GPT_API_calls':0,'post_outcome_amendment':True,'terminal':job['sample_index_1based']==72,'PIT_stage':'attempted' if job['sample_index_1based']==72 else 'UNRESOLVED_PROVIDER_NOT_QUALIFIED; measurement gate is test-only','test_only_process_gate':int(gate) if job['sample_index_1based']!=72 else None,**raw}
 dump(out/'result.json',result);archive(out);return result
def main():
 p=argparse.ArgumentParser();p.add_argument('--group',choices=['pom','junit3'],required=True);group=p.parse_args().group
 admission=A/f'admission_maven_{group}_v2.json';lock=load(admission);run=A/f'maven_{group}_run_v2';ensure(not run.exists(),'No automatic resume')
 with (R/'runtime/dispatcher.lock').open('r+b') as mutex:
  mutex.seek(0);msvcrt.locking(mutex.fileno(),msvcrt.LK_NBLCK,1)
  try:
   guards(load(R/'admission_maven_v6.json'));verify_pins(lock['code_and_input_hashes']);run.mkdir();me=psutil.Process();dump(run/'owner.json',{'pid':me.pid,'create_time':me.create_time(),'started_utc':now(),'admission_sha256':sha(admission)})
   jobs=load(R/'manifest300.json');metadata={x['sample_index_1based']:x for x in load(R/'inputs/context251_v1/manifest.json')};finished=[]
   for i in lock['admitted_sample_indices']:
    ensure(sha(admission)==load(run/'owner.json')['admission_sha256'],'Admission changed');verify_pins(lock['code_and_input_hashes']);j=jobs[i-1];job={**j,**{k:metadata[i][k] for k in ['package','selected_test_fqcn','junit_version','testng_version']}}
    out=R/'jobs'/f'{i:03d}_completion_{group}_v2';ensure(not out.exists(),'Previous output exists')
    def event(kind,**kw):
     with (out/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'at_utc':now(),'kind':kind,**kw})+'\n')
     audit.log('COMPLETION_MAVEN_'+kind,group=group,sample_index=i,**kw)
     publish_json(R/'runtime/completion_progress.json',{'phase':group.upper(),'active_index':i,'finished_indices':finished,'updated_utc':now(),'event':kind,'full300_complete':False,'GPT_API_calls':0},label='completion_maven_progress')
    try:
     prepare(i,out,R/'inputs/snapshot_v3');dump(out/'job_admission.json',{'job':job,'group':group,'post_outcome':True,'admission_sha256':sha(admission)})
     if group=='pom' and i!=72:
      capture(out,'before_generation')
      from pom_completion_controller_v2 import execute
      ensure(not load(R/'runtime/pom_input_deferrals_v1'/f'{i:03d}.json')['generation_already_attempted'],'Prior generation unexpected')
      restore_pom(i,out);commands=MavenCommands(out,job,admission,event);result=execute(out,job,commands,event);capture(out,'after_generation_and_measurement')
     else:result=junit_measure(job,out,admission,event)
     finished.append(i);print(json.dumps({'group':group,'index':i,'legacy_gate':result['legacy_process_build'],'observed_report_score':result['mutation_score_percent'],'new_generation_calls':result['generation_calls']}),flush=True)
    except GuardAbort as e:
     availability=any(s in str(e) for s in ['unavailable','Unqualified dependencies structure','Unexpected Surefire shape','Dependency audit unavailable'])
     if not availability:raise
     dump(out/'unresolved.json',{'index':i,'class_key':j['class_key'],'reason':str(e),'score':None,'automatic_retry':False});archive(out);finished.append(i)
   guards(load(R/'admission_maven_v6.json'));verify_pins(load(A/'input_audit/baseline_pins.json'));dump(run/'complete.json',{'status':'GROUP_ONE_PASS_FINISHED','indices':finished,'finished_utc':now(),'full300_complete':False,'GPT_API_calls':0})
  except BaseException as e:
   if run.exists():dump(run/'interrupted.json',{'error':str(e),'type':type(e).__name__,'traceback':traceback.format_exc(),'automatic_resume':False})
   if 'out' in locals() and out.exists() and not (out/'artifact_manifest.json').exists():archive(out)
   raise
  finally:mutex.seek(0);msvcrt.locking(mutex.fileno(),msvcrt.LK_UNLCK,1)
if __name__=='__main__':main()
