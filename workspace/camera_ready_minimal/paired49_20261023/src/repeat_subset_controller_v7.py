"""Final-admit G measurements with historical JVM environment; reuse all existing API realizations.
Protect all original source/build files; archive any new non-source runtime data.
"""
import ast,hashlib,json,os,re,shutil,sys,time,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
import pandas as pd
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B));sys.path.insert(0,str(B/'src'))
import audit,repeat_subset_driver_v1 as original,repeat_subset_driver_v6 as d
from dotenv import dotenv_values
from openai import OpenAI
ST=d.ST;original.verify_core();prioram=d.load(ST/'empty_classpath_guard_amendment_v1.json');assert audit.sha(B/'src/repeat_subset_driver_v5.py')==prioram['new_driver_sha256']
# Actual environment and runtime-data regression controls.
fix=ST/'role_environment_and_runtime_data_fixture_v1';fix.mkdir()
for arm in ['G','E']:
    out=fix/arm;out.mkdir();env=d.role_env(out,arm);assert (not env.get('JAVA_TOOL_OPTIONS')) if arm=='G' else ('tools.jar' in env['JAVA_TOOL_OPTIONS'])
out=fix/'sources';root=out/'repo';p=root/'src/main/java/F.java';p.parent.mkdir(parents=True);p.write_bytes(b'class F {}');expected={'src/main/java/F.java':audit.sha(p)};j={'focal_path':'src/main/java/F.java','focal_sha256':audit.sha(p)}
d.source_check(out,j,expected);runtime=root/'test-application.properties';runtime.write_text('fixture=true',encoding='utf-8');assert d.source_check(out,j,expected,True)[0]['path']=='test-application.properties';p.write_bytes(b'class Changed {}');caught=False
try:d.source_check(out,j,expected,True)
except AssertionError:caught=True
assert caught;p.write_bytes(b'class F {}');extra=root/'src/main/java/Injected.java';extra.write_text('class Injected{}',encoding='utf-8');caught=False
try:d.source_check(out,j,expected,True)
except AssertionError:caught=True
assert caught
# Preserve exact old measurement data. Three G responses exist; never call their API again.
schedule=d.load(ST/'schedule150.json');jobs={j['class_key']:j for j in d.load(ST/'input_jobs15.json')};gids=['002','003','006'];eids=['001','004','005']
assert [s['slot_id'] for s in schedule[:6] if s['arm']=='G']==gids
for sid in eids:assert d.load(ST/'slots'/sid/'complete.json')['status']=='COMPLETE'
for sid in gids:assert (ST/'slots'/sid/'api_response_attempt1.json').is_file()
assert not (ST/'slots/007').exists()
# Historical source function and original class-log JVM output have no E tools bootstrap.
logroot=audit.RUN/'class_logs';hist={}
for rel in ['20260724_022225_resume240/063_45997449_ResourceUrn.stdout.stderr.log','pilot60_resume_20260724_083102/034_64487983_App.stdout.stderr.log','20260724_022225_resume240/227_98410891_PropertiesConfiguration.stdout.stderr.log']:
    p=logroot/rel;text=p.read_text(encoding='utf-8',errors='replace');assert 'java version "1.8.0_172"' in text and 'JAVA_TOOL_OPTIONS' not in text
    hist[rel]={'sha256':audit.sha(p),'Java8u172':True,'JAVA_TOOL_OPTIONS_marker_present':False}
newam={'reason':'Restore historical G JVM environment: tools.jar bootstrap is E-only and must not propagate to G. First3G API realizations are retained and receive one final-admitted measurement in isolated copies; earlier G measurements are retained as technical diagnostics,not additional replicates. New runtime data additions are archived; original sources/build files and generated Java remain hash protected.','new_driver_sha256':audit.sha(B/'src/repeat_subset_driver_v6.py'),'controller_sha256':audit.sha(__file__),'prior_driver_v5_sha256':audit.sha(B/'src/repeat_subset_driver_v5.py'),'historical_G_JVM_log_evidence':hist,'existing_G_API_responses_reused':gids,'existing_E_slots_preserved':eids,'generator_prompt_model_seed_Maven_goals_and_score_functions_unchanged':True,'regression_controls':'G/E JVM split,accept new runtime properties,reject original source edit,reject new production Java','no_new_API_requests_for_recovery':True}
d.dump(ST/'role_environment_and_runtime_data_amendment_v1.json',newam);audit.log('REPEAT15_G_ENVIRONMENT_ISOLATION_AMENDMENT',**newam)
# Capture the already finished slot006 diagnostic before creating its final subworkspace.
s6=next(s for s in schedule if s['slot_id']=='006');j6=jobs[s6['class_key']];out6=ST/'slots/006';d.CURRENT=s6
assert not (out6/'slot_archive.zip').exists();records=[d.load(p) for p in sorted(out6.glob('command_*.json'))];assert len([r for r in records if r['argv'][-5:]==d.GOALS])==1
d.dump(out6/'diagnostic_measurement.json',{'status':'TECHNICAL_DIAGNOSTIC_NOT_FINAL_REPLICATE','reason':'E-only JVM bootstrap present; fresh runtime properties caused an overly strict postmeasurement membership guard','API_response_sha256':audit.sha(out6/'api_response_attempt1.json'),'all_prior_commands_retained':True});d.archive_slot(out6)

def final_G(slot):
    rootout=ST/'slots'/slot['slot_id'];j=jobs[slot['class_key']];out=rootout/'final_measurement';assert not out.exists();d.CURRENT=slot
    with zipfile.ZipFile(rootout/'slot_archive.zip') as z:
        sources=d.load(rootout/'generated_sources_manifest.json');assert len(sources)==1;name=next(iter(sources));data=z.read('repo/'+name);assert hashlib.sha256(data).hexdigest()==sources[name]
    response=d.load(rootout/'api_response_attempt1.json');d.validate_model(response['model']);content=response['choices'][0]['message']['content'];code=d.response_extractor()[0](content,Path(j['old_synthesized_test_relative']).stem,j['package'])[0];assert data.decode('utf-8').replace('\r\n','\n')==code.replace('\r\n','\n')
    module,focal=d.repeat_prepare_job_v2(j,out);testjava=out/'repo'/name;testjava.parent.mkdir(parents=True,exist_ok=True);testjava.write_bytes(data)
    for p in rootout.glob('api_*.json'):shutil.copy2(p,out/p.name);assert audit.sha(p)==audit.sha(out/p.name)
    selected={name:audit.sha(testjava)};d.dump(out/'generated_sources_manifest.json',selected)
    test=(j['package']+'.' if j['package'] else '')+Path(j['old_synthesized_test_relative']).stem;df=pd.DataFrame([{'Project':j['repo_id'],'Module':j['module'],'Focal_Class':j['focal_class'],'Test_Class':test.split('.')[-1],'Focal_Path':str(focal),'Test_Path':testjava.as_posix()}]);env=d.role_env(out,'G');commands=d.legacy.Commands(out,env,d.CACHE,0);ns,phases=d.legacy.load_functions(commands,out)
    for p in (out/'repo').rglob('pom.xml'):
        backup=out/'backup_poms'/p.relative_to(out/'repo');backup.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,backup)
    assert ns['edit_pom_file'](str(module),df,j['junit_version'],j['testng_version']) is not None
    expected={r['relative']:r['sha256'] for r in j['source_files']};expected.pop(j['old_synthesized_test_relative'],None);expected.update(selected);expected[(Path(j['module'])/'pom.xml').as_posix()]=audit.sha(module/'pom.xml');d.source_check(out,j,expected)
    d.dump(out/'slot_admission.json',{'slot':slot,'lock_sha256':audit.sha(ST/'readiness_lock.json'),'start_utc':d.now(),'generation_evidence_from':str(rootout),'existing_response_sha256':audit.sha(rootout/'api_response_attempt1.json'),'new_generation_API_calls':0,'reason':'final-admitted G measurement without E-only JVM bootstrap'})
    args=['mvn','-s',str(out/'settings.xml'),'-Dtest='+test,*ns['common_maven_skip_args']()];start=time.monotonic();d.repeat_dependency(commands,args,module,out,'before');diag=time.monotonic()-start
    policy={'JUnit_rule_applied':False,'selector_rule_applied':False,'changes':[],'arm':'G'};d.dump(out/'policy_applied.json',policy);start=time.monotonic();gate=ns['run_maven_test_command'](str(module),df,'Windows')[0];measurement=time.monotonic()-start
    runtime=d.source_check(out,j,expected,True);prod=d.production_check(module,j,gate);raw=d.legacy.raw_metrics(module,test,j['focal_class'],j['package'],gate);methods=d.inventory.inventory_java_tests(testjava.read_text(encoding='utf-8'));cases=[]
    for p in sorted((module/'target/surefire-reports').glob('TEST-*.xml')):
        tree=ET.parse(p).getroot()
        for c in tree.findall('testcase'):cases.append({'suite':tree.get('name'),'class':c.get('classname'),'name':c.get('name'),'failures':len(c.findall('failure')),'errors':len(c.findall('error')),'skipped':len(c.findall('skipped'))})
    old_result=d.load(rootout/'result.json') if (rootout/'result.json').exists() else {};attempts=[d.load(p) for p in sorted(rootout.glob('api_attempt*.json'))];api={'attempts':attempts,'model':response['model'],'api_duration_seconds':sum(a['duration_seconds'] for a in attempts),'response_content_sha256':hashlib.sha256(content.encode()).hexdigest(),'generated_nonempty':True,'existing_response_reused_without_POST':True}
    r={**slot,'status':'COMPLETED','preprocessing_ok':True,'generation_success':True,'scaffold_present':False,'generated_sources':selected,'API':api,'generation_duration_seconds_including_compile':old_result.get('generation_duration_seconds_including_compile',sum(a['duration_seconds'] for a in attempts)),'measurement_duration_seconds':measurement,'integration_diagnostic_seconds':diag,'slot_duration_seconds_before_archive':None,'timing_recovered_components_not_exact_slot_wall':True,'measurement_subdirectory':'final_measurement','generation_evidence_reused_from_parent':True,'policy':policy,**raw,'method_inventory':methods,'canonical_cases':cases,'production_before':{'baseline_count':len(j['production_baseline'])},'production_after':prod,'generated_source_bytes_unchanged_during_measurement':True,'source_guard':'PASS','new_runtime_data_files':runtime,'EvoSuite_generation_attempts':0,'GPT_API_attempts':len(attempts),'configuration_labels_are_not_scoring_scales':True,'G_no_E_only_tools_bootstrap':True}
    d.dump(out/'phase_records.json',phases);d.dump(out/'result.json',r);d.archive_slot(out);d.dump(out/'complete.json',{'status':'COMPLETE','slot_id':slot['slot_id'],'result_sha256':audit.sha(out/'result.json'),'archive_manifest_sha256':audit.sha(out/'archive_manifest.json'),'finished_utc':d.now()});d.dump(rootout/'final_admitted_result_pointer.json',{'path':str((out/'result.json').relative_to(ST)),'sha256':audit.sha(out/'result.json'),'reason':'historical G environment,identical saved generation'})
    if not (rootout/'complete.json').exists():d.dump(rootout/'complete.json',{'status':'COMPLETE','slot_id':slot['slot_id'],'result_file':'final_measurement/result.json','result_sha256':audit.sha(out/'result.json'),'finished_utc':d.now()});d.event('SLOT_COMPLETE',result_sha256=audit.sha(out/'result.json'))
    d.event('G_FINAL_MEASUREMENT_ACCEPTED',existing_response_sha256=audit.sha(rootout/'api_response_attempt1.json'),result_sha256=audit.sha(out/'result.json'),new_API_calls=0)
    print(json.dumps({'final_G_slot':slot['slot_id'],'reused_generation':True,'build':r['legacy_process_build'],'score':r['legacy_strict_mutation_percent']}),flush=True);return r

admitted={}
for s in schedule[:6]:
    if s['arm']=='G':admitted[s['slot_id']]=final_G(s)
    else:admitted[s['slot_id']]=d.load(ST/'slots'/s['slot_id']/'result.json')
key=dotenv_values(audit.ROOT/'scripts_v2/.env').get('OPENAI_API_KEY') or os.environ.get('OPENAI_API_KEY');assert key;client=OpenAI(api_key=key,max_retries=0,timeout=120,base_url='https://api.openai.com/v1');budget=d.Budget()
for slot in schedule[6:]:
    original.verify_core();assert audit.sha(B/'src/repeat_subset_driver_v6.py')==newam['new_driver_sha256'];assert audit.sha(__file__)==newam['controller_sha256']
    try:r=d.execute(slot,jobs[slot['class_key']],budget,client)
    except BaseException as exc:d.event('BATCH_ABORT',controller='v7',exception_class=type(exc).__name__,detail=str(exc)[:800] if isinstance(exc,AssertionError) else 'Preserved logs; no automatic rerun of started slots');raise
    admitted[slot['slot_id']]=r;print(json.dumps({'completed':len(admitted),'n':150,'slot_id':slot['slot_id'],'job':slot['job_index'],'replicate':slot['replicate'],'arm':slot['arm'],'build':r['legacy_process_build'],'score':r['legacy_strict_mutation_percent']}),flush=True)
results=[admitted[s['slot_id']] for s in schedule];d.dump(ST/'results150.json',results);d.frozen.check_gpt();audit.verify();d.dump(ST/'complete.json',{'status':'COMPLETE','n':150,'results_sha256':audit.sha(ST/'results150.json'),'GPT_slots':75,'EvoSuite_slots':75,'finished_utc':d.now(),'reserved_estimated_GPT_USD':budget.reserved,'first3G_realizations_measured_once_in_final_profile':gids,'earlier_measurements_retained_as_diagnostics':True});d.event('BATCH_COMPLETE',n=150,results_sha256=audit.sha(ST/'results150.json'))
