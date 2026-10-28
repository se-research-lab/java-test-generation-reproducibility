"""Recover slot003 after empty compile-classpath diagnostic; reuse its existing GPT response.
Never repeat a completed generation or measurement. Preserve all earlier files and locks.
"""
import ast,hashlib,json,os,re,sys,time
from pathlib import Path
from xml.etree import ElementTree as ET
import pandas as pd
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B));sys.path.insert(0,str(B/'src'))
import audit,repeat_subset_driver_v1 as original,repeat_subset_driver_v5 as d
from dotenv import dotenv_values
from openai import OpenAI
ST=d.ST;original.verify_core();amend=d.load(ST/'windows_glob_guard_amendment_v3.json');assert audit.sha(B/'src/repeat_subset_driver_v4.py')==amend['new_driver_sha256']
# Adapter regression: existing empty CP is valid; absent/nonempty-invalid files still fail.
fix=ST/'empty_classpath_fixture_v1';fix.mkdir();p=fix/'empty.txt';p.write_text('',encoding='utf-8');assert d.repeat_cp_entries(p)==[];p=fix/'bad.txt';p.write_text('Z:/definitely_missing_fixture.jar',encoding='utf-8');caught=False
try:d.repeat_cp_entries(p)
except AssertionError:caught=True
assert caught
old=(B/'src/repeat_subset_driver_v4.py').read_text(encoding='utf-8');new=(B/'src/repeat_subset_driver_v5.py').read_text(encoding='utf-8');oldtree=ast.parse(old);newtree=ast.parse(new);changed=[]
for f in oldtree.body:
    if isinstance(f,(ast.FunctionDef,ast.ClassDef)):
        g=next(n for n in newtree.body if isinstance(n,type(f)) and n.name==f.name)
        if ast.dump(f,include_attributes=False)!=ast.dump(g,include_attributes=False):changed.append(f.name)
assert changed==['execute'],changed
oldexecute=next(f for f in ast.parse(old.replace('replay.dependency(commands,','repeat_dependency(commands,')).body if isinstance(f,ast.FunctionDef) and f.name=='execute');newexecute=next(f for f in newtree.body if isinstance(f,ast.FunctionDef) and f.name=='execute');assert ast.dump(oldexecute,include_attributes=False)==ast.dump(newexecute,include_attributes=False)
schedule=d.load(ST/'schedule150.json');jobs={j['class_key']:j for j in d.load(ST/'input_jobs15.json')};slot=schedule[2];assert slot['slot_id']=='003' and slot['arm']=='G';j=jobs[slot['class_key']];out=ST/'slots/003';assert not (out/'result.json').exists();prior=[d.load(p) for p in sorted(out.glob('command_*.json'))];assert len(prior)==3 and not any(c['argv'][-5:]==d.GOALS for c in prior)
assert all(d.load(ST/'slots'/s['slot_id']/'complete.json')['status']=='COMPLETE' for s in schedule[:2])
cp=out/'before_compile_classpath.txt';assert cp.is_file() and not cp.read_text(encoding='utf-8').strip()
payload=d.load(out/'api_request.json');assert d.digest(payload['messages'])==j['messages_sha256'];response=d.load(out/'api_response_attempt1.json');d.validate_model(response['model']);row=d.load(out/'api_attempt1.json');assert row['status']=='OK'
content=response['choices'][0]['message']['content'];code=d.response_extractor()[0](content,Path(j['old_synthesized_test_relative']).stem,j['package'])[0];module=out/'repo'/j['module'];test=(j['package']+'.' if j['package'] else '')+Path(j['old_synthesized_test_relative']).stem;testjava=module/'src/test/java'/Path(*test.split('.')).with_suffix('.java');assert testjava.read_text(encoding='utf-8')==code
frozen_inputs={str(p.relative_to(B)):audit.sha(p) for p in [out/'api_request.json',out/'api_response_attempt1.json',out/'api_attempt1.json',out/'generated_sources_manifest.json',testjava,*out.glob('command_*.json')]}
newam={'reason':'Maven compile classpath is legitimately empty for bridge/App; accept only existing wholly empty files, retaining all checks on nonempty paths. Reuse existing slot003 GPT response; finish its first measurement only.','driver_v4_sha256':audit.sha(B/'src/repeat_subset_driver_v4.py'),'new_driver_sha256':audit.sha(B/'src/repeat_subset_driver_v5.py'),'controller_sha256':audit.sha(__file__),'completed_slots_preserved':2,'existing_API_response_not_repeated':True,'frozen_slot003_inputs':frozen_inputs,'positive_empty_cp_and_negative_invalid_cp_controls':'PASS','generator_model_prompt_seed_scoring_policy_unchanged':True}
d.dump(ST/'empty_classpath_guard_amendment_v1.json',newam);audit.log('REPEAT15_EMPTY_CLASSPATH_GUARD_AMENDMENT',**newam)
d.CURRENT=slot;d.event('PREMEASUREMENT_RECOVERY',reused_response_sha256=audit.sha(out/'api_response_attempt1.json'),new_API_calls=0,new_generation_calls=0)
# Reconstruct already completed dependency diagnostics without rerunning commands.
d.dump(out/'before_dependency.json',{'classpath':d.repeat_cp_entries(out/'before_test_classpath.txt'),'compile_classpath':[],'tree_sha256':audit.sha(out/'before_tree.txt'),'reconstructed_from_completed_commands':[2,3]})
env={k:v for k,v in os.environ.items() if not any(x in k.upper() for x in ['API_KEY','API_TOKEN','OPENAI','ANTHROPIC'])};env['JAVA_HOME']=str(d.legacy.JDK);env['PATH']=str(d.legacy.JDK/'bin')+os.pathsep+env.get('PATH','');assert not env.get('_JAVA_OPTIONS') and not env.get('JDK_JAVA_OPTIONS');env['JAVA_TOOL_OPTIONS']='-Xbootclasspath/a:"'+str(d.legacy.JDK/'lib/tools.jar')+'"';env['TMP']=env['TEMP']=str(out/'temp')
commands=d.replay.compat.DiagnosticCommands(out,env,d.CACHE,0);ns,phases=d.legacy.load_functions(commands,out);df=pd.DataFrame([{'Project':j['repo_id'],'Module':j['module'],'Focal_Class':j['focal_class'],'Test_Class':test.split('.')[-1],'Focal_Path':str(module/Path(j['focal_path']).relative_to(j['module'])),'Test_Path':testjava.as_posix()}]);expected={r['relative']:r['sha256'] for r in j['source_files']};expected.pop(j['old_synthesized_test_relative'],None);selected=d.load(out/'generated_sources_manifest.json');expected.update(selected);expected[(Path(j['module'])/'pom.xml').as_posix()]=audit.sha(module/'pom.xml');d.source_check(out,j,expected)
prod_before=d.production_check(module,j,True);policy={'JUnit_rule_applied':False,'selector_rule_applied':False,'changes':[],'arm':'G'};d.dump(out/'policy_applied.json',policy);start=time.monotonic();gate=ns['run_maven_test_command'](str(module),df,'Windows')[0];measurement_seconds=time.monotonic()-start;d.source_check(out,j,expected)
for n,h in selected.items():assert audit.sha(out/'repo'/n)==h
prod_after=d.production_check(module,j,gate);raw=d.legacy.raw_metrics(module,test,j['focal_class'],j['package'],gate);methods=d.inventory.inventory_java_tests(testjava.read_text(encoding='utf-8'));cases=[]
for p in sorted((module/'target/surefire-reports').glob('TEST-*.xml')):
    root=ET.parse(p).getroot()
    for c in root.findall('testcase'):cases.append({'suite':root.get('name'),'class':c.get('classname'),'name':c.get('name'),'failures':len(c.findall('failure')),'errors':len(c.findall('error')),'skipped':len(c.findall('skipped'))})
api={'attempts':[row],'api_duration_seconds':row['duration_seconds'],'model':response['model'],'response_content_sha256':hashlib.sha256(content.encode()).hexdigest(),'generated_nonempty':True,'existing_response_reused_without_POST':True}
r={**slot,'status':'COMPLETED','preprocessing_ok':True,'generation_success':True,'scaffold_present':False,'generated_sources':selected,'API':api,'generation_duration_seconds_including_compile':prior[0]['duration_seconds']+row['duration_seconds'],'measurement_duration_seconds':measurement_seconds,'integration_diagnostic_seconds':sum(c['duration_seconds'] for c in prior[1:]),'slot_duration_seconds_before_archive':None,'timing_reconstructed_from_command_components':True,'timing_limit':'Recovery pause and Python overhead excluded; component sum is not exact original slot wall time','policy':policy,**raw,'method_inventory':methods,'canonical_cases':cases,'production_before':prod_before,'production_after':prod_after,'generated_source_bytes_unchanged_during_measurement':True,'source_guard':'PASS','EvoSuite_generation_attempts':0,'GPT_API_attempts':1,'configuration_labels_are_not_scoring_scales':True}
d.dump(out/'phase_records.json',phases);d.dump(out/'result.json',r);d.frozen.check_gpt();d.event('SLOT_MEASURED',legacy_score=r['legacy_strict_mutation_percent'],generation_success=True,result_sha256=audit.sha(out/'result.json'));d.archive_slot(out);d.dump(out/'complete.json',{'status':'COMPLETE','slot_id':'003','result_sha256':audit.sha(out/'result.json'),'archive_manifest_sha256':audit.sha(out/'archive_manifest.json'),'finished_utc':d.now()});d.event('SLOT_COMPLETE',result_sha256=audit.sha(out/'result.json'))
print(json.dumps({'completed':3,'n':150,'slot_id':'003','reused_API_response':True,'build':r['legacy_process_build'],'score':r['legacy_strict_mutation_percent']}),flush=True)
key=dotenv_values(audit.ROOT/'scripts_v2/.env').get('OPENAI_API_KEY') or os.environ.get('OPENAI_API_KEY');assert key;client=OpenAI(api_key=key,max_retries=0,timeout=120,base_url='https://api.openai.com/v1');budget=d.Budget();results=[d.load(ST/'slots'/s['slot_id']/'result.json') for s in schedule[:3]]
for slot in schedule[3:]:
    original.verify_core();assert audit.sha(B/'src/repeat_subset_driver_v5.py')==newam['new_driver_sha256'];assert audit.sha(__file__)==newam['controller_sha256']
    try:r=d.execute(slot,jobs[slot['class_key']],budget,client)
    except BaseException as exc:d.event('BATCH_ABORT',controller='v6',exception_class=type(exc).__name__,detail=str(exc)[:800] if isinstance(exc,AssertionError) else 'Preserved logs; no automatic rerun of started slots');raise
    results.append(r);print(json.dumps({'completed':len(results),'n':150,'slot_id':slot['slot_id'],'job':slot['job_index'],'replicate':slot['replicate'],'arm':slot['arm'],'build':r['legacy_process_build'],'score':r['legacy_strict_mutation_percent']}),flush=True)
d.dump(ST/'results150.json',results);d.frozen.check_gpt();audit.verify();d.dump(ST/'complete.json',{'status':'COMPLETE','n':150,'results_sha256':audit.sha(ST/'results150.json'),'GPT_slots':75,'EvoSuite_slots':75,'finished_utc':d.now(),'reserved_estimated_GPT_USD':budget.reserved});d.event('BATCH_COMPLETE',n=150,results_sha256=audit.sha(ST/'results150.json'))
