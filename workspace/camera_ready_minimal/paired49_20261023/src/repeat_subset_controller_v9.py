"""Recover final slot006 solely from existing raw commands; continue remaining fixed schedule."""
import ast,hashlib,json,os,sys,time,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B));sys.path.insert(0,str(B/'src'))
import audit,repeat_subset_driver_v1 as original,repeat_subset_driver_v7 as d
from dotenv import dotenv_values
from openai import OpenAI
ST=d.ST;original.verify_core();prior=d.load(ST/'role_environment_and_runtime_data_amendment_v1.json');assert audit.sha(B/'src/repeat_subset_driver_v6.py')==prior['new_driver_sha256']
fix=ST/'mutable_runtime_fixture_controls_v3';root=fix/'repo';p=root/'src/main/java/F.java';p.parent.mkdir(parents=True);p.write_bytes(b'class F{}');test=root/'src/test/java/FTest.java';test.parent.mkdir(parents=True);test.write_text('class FTest { String f="test-application.properties"; }',encoding='utf-8');data=root/'test-application.properties';data.write_bytes(b'initial=true')
j={'source_repo':str(root),'focal_path':'src/main/java/F.java','focal_sha256':audit.sha(p),'source_files':[{'relative':'src/main/java/F.java','sha256':audit.sha(p)},{'relative':'test-application.properties','sha256':audit.sha(data)}]};expected={'src/main/java/F.java':audit.sha(p),'src/test/java/FTest.java':audit.sha(test),'test-application.properties':audit.sha(data)}
d.backup_runtime_inputs(fix,j,expected);data.write_bytes(b'fixture=changed');assert d.source_check(fix,j,expected,True)[0]['path']=='test-application.properties';p.write_bytes(b'class Bad{}');caught=False
try:d.source_check(fix,j,expected,True)
except AssertionError:caught=True
assert caught
schedule=d.load(ST/'schedule150.json');jobs={j['class_key']:j for j in d.load(ST/'input_jobs15.json')};slot=schedule[5];assert slot['slot_id']=='006' and slot['arm']=='G';j=jobs[slot['class_key']];rootout=ST/'slots/006';out=rootout/'final_measurement';assert not (out/'result.json').exists() and not (ST/'slots/007').exists()
records=[d.load(p) for p in sorted(out.glob('command_*.json'))];measure=[c for c in records if c['argv'][-5:]==d.GOALS];assert len(measure)==1;assert d.load(out/'environment_allowlist.json')['JAVA_TOOL_OPTIONS'] is None
# Reuse the already audited post-measurement finisher AST; it contains no API or Maven invocation.
source=B/'src/repeat_subset_controller_v7.py';tree=ast.parse(source.read_text(encoding='utf-8'));f=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='final_G');idx=next(i for i,n in enumerate(f.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='runtime' for t in n.targets));tail=f.body[idx:]
assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ['run_maven_test_command','gpt_generate'] for q in tail for n in ast.walk(q))
args=['slot','rootout','j','out','module','test','testjava','selected','expected','measurement','diag','phases'];fn=ast.FunctionDef(name='finish_existing_measurement',args=ast.arguments(posonlyargs=[],args=[ast.arg(arg=n) for n in args],kwonlyargs=[],kw_defaults=[],defaults=[]),body=tail,decorator_list=[]);module_ast=ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[]));ns=dict(globals());exec(compile(module_ast,str(source)+'::postmeasurement','exec'),ns)
am={'reason':'PropertiesConfiguration generated test rewrites an existing test-application.properties fixture,including timestamp. Record mutable declared test-data changes with exact initial backups; retain immutable production Java/build/generated-test guards. Final006 API and Maven measurement are reused,not repeated.','new_driver_sha256':audit.sha(B/'src/repeat_subset_driver_v7.py'),'controller_sha256':audit.sha(__file__),'finisher_source_sha256':audit.sha(source),'finisher_AST_sha256':hashlib.sha256(ast.dump(module_ast,include_attributes=False).encode()).hexdigest(),'no_new_API_or_measurement_for_recovery':True,'runtime_fixture_positive_and_Java_edit_negative_controls':'PASS'}
d.dump(ST/'mutable_runtime_data_guard_amendment_v2.json',am);audit.log('REPEAT15_MUTABLE_TEST_DATA_GUARD_AMENDMENT',**am)
d.CURRENT=slot;module=out/'repo'/j['module'];test=(j['package']+'.' if j['package'] else '')+Path(j['old_synthesized_test_relative']).stem;testjava=module/'src/test/java'/Path(*test.split('.')).with_suffix('.java');selected=d.load(out/'generated_sources_manifest.json');expected={r['relative']:r['sha256'] for r in j['source_files']};expected.pop(j['old_synthesized_test_relative'],None);expected.update(selected);expected[(Path(j['module'])/'pom.xml').as_posix()]=audit.sha(module/'pom.xml');d.backup_runtime_inputs(out,j,expected,from_canonical_input=True)
m=measure[0];stdout=(B/m['stdout']).read_text(encoding='utf-8');gate=bool('BUILD SUCCESS' in stdout and not m['timeout']);measurement=sum(c['duration_seconds'] for c in records if c['argv'][-5:]==d.GOALS or c['argv'][-1:]==['-version']);diag=sum(c['duration_seconds'] for c in records if c['argv'][-5:]!=d.GOALS and c['argv'][-1:]!=['-version'])
# The finisher's original local gate is supplied explicitly; no score is chosen between measurements.
ns['gate']=gate
ns['response']=d.load(rootout/'api_response_attempt1.json');ns['content']=ns['response']['choices'][0]['message']['content'];ns['policy']=d.load(out/'policy_applied.json')
r=ns['finish_existing_measurement'](slot,rootout,j,out,module,test,testjava,selected,expected,measurement,diag,[{'phase':'recovered_from_existing_final_measurement','new_API_calls':0,'new_measurements':0}])
admitted={s['slot_id']:d.load(ST/'slots'/s['slot_id']/('final_measurement/result.json' if s['arm']=='G' else 'result.json')) for s in schedule[:6]}
key=dotenv_values(audit.ROOT/'scripts_v2/.env').get('OPENAI_API_KEY') or os.environ.get('OPENAI_API_KEY');assert key;client=OpenAI(api_key=key,max_retries=0,timeout=120,base_url='https://api.openai.com/v1');budget=d.Budget()
for slot in schedule[6:]:
    original.verify_core();assert audit.sha(B/'src/repeat_subset_driver_v7.py')==am['new_driver_sha256'];assert audit.sha(__file__)==am['controller_sha256']
    try:r=d.execute(slot,jobs[slot['class_key']],budget,client)
    except BaseException as exc:d.event('BATCH_ABORT',controller='v9',exception_class=type(exc).__name__,detail=str(exc)[:800] if isinstance(exc,AssertionError) else 'Preserved logs; no automatic rerun of started slots');raise
    admitted[slot['slot_id']]=r;print(json.dumps({'completed':len(admitted),'n':150,'slot_id':slot['slot_id'],'job':slot['job_index'],'replicate':slot['replicate'],'arm':slot['arm'],'build':r['legacy_process_build'],'score':r['legacy_strict_mutation_percent']}),flush=True)
results=[admitted[s['slot_id']] for s in schedule];d.dump(ST/'results150.json',results);d.frozen.check_gpt();audit.verify();d.dump(ST/'complete.json',{'status':'COMPLETE','n':150,'results_sha256':audit.sha(ST/'results150.json'),'GPT_slots':75,'EvoSuite_slots':75,'finished_utc':d.now(),'reserved_estimated_GPT_USD':budget.reserved,'first3G_realizations_admitted_subdir':'final_measurement','earlier_G_measurements_retained_as_diagnostics':True});d.event('BATCH_COMPLETE',n=150,results_sha256=audit.sha(ST/'results150.json'))
