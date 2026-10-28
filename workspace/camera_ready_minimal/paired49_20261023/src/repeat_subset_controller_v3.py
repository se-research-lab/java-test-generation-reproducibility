"""Resume unstarted slots after Windows case-insensitive glob admission correction.
No generator/scoring/shared-function change; old source and records remain intact.
"""
import ast,json,os,shutil,sys
from pathlib import Path
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B));sys.path.insert(0,str(B/'src'))
import audit,repeat_subset_driver_v1 as old,repeat_subset_driver_v2 as d
from dotenv import dotenv_values
from openai import OpenAI
ST=d.ST;old.verify_core();assert not (ST/'api_attempts.jsonl').exists();events=[json.loads(s) for s in (ST/'events.jsonl').read_text(encoding='utf-8').splitlines()];assert not any(r['kind'] in ['SLOT_START','API_POST_START','SLOT_MEASURED','SLOT_COMPLETE'] for r in events)
# Actual regression fixture preserves a pre-existing FilesTest.java and rejects a true native suite.
fix=ST/'windows_guard_fixture_v1';src=fix/'origin/context/compiledrepos/fixture';src.mkdir(parents=True)
files={'src/main/java/Example.java':'public class Example {}','src/test/java/FilesTest.java':'public class FilesTest {}'}
for n,t in files.items():p=src/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(t,encoding='utf-8')
settings=src.parent.parent/'settings.xml';settings.write_text('<settings/>',encoding='utf-8')
j={'source_repo':str(src),'source_files':[{'relative':n,'sha256':audit.sha(src/n),'bytes':(src/n).stat().st_size} for n in files],'old_synthesized_test_relative':'src/test/java/Placeholder.java','focal_path':'src/main/java/Example.java','focal_sha256':audit.sha(src/'src/main/java/Example.java'),'settings_sha256':audit.sha(settings),'module':'.'}
module,focal=d.repeat_prepare_job_v2(j,fix/'pass');assert audit.sha(module/'src/test/java/FilesTest.java')==audit.sha(src/'src/test/java/FilesTest.java')
p=src/'src/test/java/Example_ESTest.java';p.write_text('public class Example_ESTest {}',encoding='utf-8');j['source_files'].append({'relative':p.relative_to(src).as_posix(),'sha256':audit.sha(p),'bytes':p.stat().st_size});caught=False
try:d.repeat_prepare_job_v2(j,fix/'reject')
except AssertionError:caught=True
assert caught,'True native prior suite must still be rejected'
# Only the two stated execute expressions differ from the locked v1 body.
a=(B/'src/repeat_subset_driver_v1.py').read_text(encoding='utf-8');b=(B/'src/repeat_subset_driver_v2.py').read_text(encoding='utf-8')
newtree=ast.parse(b);oldtree=ast.parse(a)
changed=[]
for f in oldtree.body:
    if isinstance(f,(ast.FunctionDef,ast.ClassDef)):
        g=next(n for n in newtree.body if isinstance(n,type(f)) and n.name==f.name)
        if ast.dump(f,include_attributes=False)!=ast.dump(g,include_attributes=False):changed.append(f.name)
assert changed==['execute'],changed
needle="selected={p.relative_to(out/'repo').as_posix():sha(p) for p in sorted((module/'src/test/java').rglob('*ESTest*.java'))}"
expected=a.replace('module,focal=frozen.prepare_job(j,out)','module,focal=repeat_prepare_job_v2(j,out)').replace(needle,"selected={p.relative_to(out/'repo').as_posix():sha(p) for p in [testjava,testjava.with_name(testjava.stem+'_scaffolding.java')] if p.is_file()}")
expected_execute=next(f for f in ast.parse(expected).body if isinstance(f,ast.FunctionDef) and f.name=='execute');actual_execute=next(f for f in newtree.body if isinstance(f,ast.FunctionDef) and f.name=='execute');assert ast.dump(expected_execute,include_attributes=False)==ast.dump(actual_execute,include_attributes=False)
auth=d.load(ST/'explicit_payload_authorization_v1.json');assert auth['payload_file_sha256']==audit.sha(ST/'prompts15.json')
partial=ST/'slots/001';assert partial.is_dir() and not list(partial.glob('command_*.json')) and not (partial/'api_request.json').exists()
backup=ST/'pre_generation_recovery_v1/001_copied_before_admission';backup.parent.mkdir();assert not backup.exists();assert partial.resolve().is_relative_to(ST.resolve()) and backup.resolve().is_relative_to(ST.resolve());shutil.move(str(partial),str(backup))
amendment={'reason':'Windows Path.glob *ESTest* matched human FilesTest.java case-insensitively. Replace admission scanner with case-sensitive native suffixes; generated manifest includes exact selected native pair. Preserve all human files. Add locked-settings check.','old_driver_sha256':audit.sha(B/'src/repeat_subset_driver_v1.py'),'new_driver_sha256':audit.sha(B/'src/repeat_subset_driver_v2.py'),'controller_sha256':audit.sha(__file__),'changed_execute_expressions':['prepare_job guard','exact selected generated-source pair'],'generator_API_scoring_and_policy_functions_byte_unchanged':True,'regression_fixture_human_FilesTest_preserved':True,'regression_fixture_true_native_suite_rejected':True,'prior_generation_API_or_measurement_calls':0,'preserved_partial_copy':str(backup),'authorization_sha256':audit.sha(ST/'explicit_payload_authorization_v1.json')}
d.dump(ST/'windows_glob_guard_amendment_v1.json',amendment);audit.log('REPEAT15_WINDOWS_GLOB_GUARD_AMENDMENT',**amendment)
key=dotenv_values(audit.ROOT/'scripts_v2/.env').get('OPENAI_API_KEY') or os.environ.get('OPENAI_API_KEY');assert key;client=OpenAI(api_key=key,max_retries=0,timeout=120,base_url='https://api.openai.com/v1');budget=d.Budget();jobs={j['class_key']:j for j in d.load(ST/'input_jobs15.json')};results=[]
for slot in d.load(ST/'schedule150.json'):
    old.verify_core();assert audit.sha(B/'src/repeat_subset_driver_v2.py')==amendment['new_driver_sha256'];assert audit.sha(__file__)==amendment['controller_sha256']
    try:r=d.execute(slot,jobs[slot['class_key']],budget,client)
    except BaseException as exc:d.event('BATCH_ABORT',controller='v3',exception_class=type(exc).__name__,detail=str(exc)[:800] if isinstance(exc,AssertionError) else 'Preserved logs; no automatic rerun of started slots');raise
    results.append(r);print(json.dumps({'completed':len(results),'n':150,'slot_id':slot['slot_id'],'job':slot['job_index'],'replicate':slot['replicate'],'arm':slot['arm'],'build':r['legacy_process_build'],'score':r['legacy_strict_mutation_percent']}),flush=True)
d.dump(ST/'results150.json',results);d.frozen.check_gpt();audit.verify();d.dump(ST/'complete.json',{'status':'COMPLETE','n':150,'results_sha256':audit.sha(ST/'results150.json'),'GPT_slots':75,'EvoSuite_slots':75,'finished_utc':d.now(),'reserved_estimated_GPT_USD':budget.reserved});d.event('BATCH_COMPLETE',n=150,results_sha256=audit.sha(ST/'results150.json'))
