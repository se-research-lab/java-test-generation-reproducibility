"""Isolated15x5 repeated-generation supplement; archived primary data remain read-only."""
import argparse,ast,copy,csv,hashlib,json,os,re,shutil,subprocess,sys,time,types,zipfile
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from xml.etree import ElementTree as ET
import pandas as pd
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B));sys.path.insert(0,str(B/'src'))
import audit,e49_driver as legacy,run_e49_supplement as frozen,replay_fixed49_measurement_v5 as replay,junit_method_inventory_v1 as inventory
driver=legacy
BASE=B
ST=B/'repeated_subset_v1';CACHE=B/'e1_compatibility_diagnostic_v1/maven_cache'
MODEL='gpt-4o-mini-2024-07-18';CURRENT={};GOALS=['clean','verify','jacoco:prepare-agent','jacoco:report','org.pitest:pitest-maven:mutationCoverage'];sha=audit.sha

def now():return datetime.now(timezone.utc).isoformat()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def dump(p,x):return legacy.write_json(Path(p),x)
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def event(kind,**kw):
    row={'timestamp_utc':now(),'kind':kind,'slot_id':CURRENT.get('slot_id'),**kw}
    with (ST/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
    audit.log('REPEAT15_'+kind,**{k:v for k,v in row.items() if k not in ['kind','timestamp_utc']})
def func_hash(p,name):
    f=next(n for n in ast.parse(Path(p).read_text(encoding='utf-8-sig')).body if isinstance(n,ast.FunctionDef) and n.name==name)
    return hashlib.sha256(ast.dump(f,include_attributes=False).encode()).hexdigest()
def response_extractor():
    source=audit.ROOT/'scripts_v2/AgoneTest/utils.py';f=next(n for n in ast.parse(source.read_text(encoding='utf-8-sig')).body if isinstance(n,ast.FunctionDef) and n.name=='make_api_call')
    start=next(i for i,n in enumerate(f.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='result' for t in n.targets))
    fn=ast.FunctionDef(name='extract_response',args=ast.arguments(posonlyargs=[],args=[ast.arg(arg=n) for n in ['result','name_test_class','package_test_class']],kwonlyargs=[],kw_defaults=[],defaults=[]),body=ast.parse('messages=[]').body+copy.deepcopy(f.body[start+1:]),decorator_list=[])
    module=ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[]));ns={'re':re};exec(compile(module,str(source)+'::parser_tail','exec'),ns)
    return ns['extract_response'],hashlib.sha256(ast.dump(module,include_attributes=False).encode()).hexdigest()
def validate_model(returned):assert returned==MODEL,'Returned model differs; no substitution allowed'
def verify_core():
    lock=load(ST/'readiness_lock.json')
    for n,h in lock['code_and_input_hashes'].items():assert sha(B/n)==h,n
    for n,h in lock['external_hashes'].items():assert sha(n)==h,n
    frozen.check_gpt();return lock

def prepare():
    assert not (ST/'protocol.json').exists();assert load(ST/'preflight_probe_access_v2.json')['access']['status']=='PASS'
    selection=load(B/'repeated_subset_selection_v1.json');selected=selection['selected'];assert len(selected)==15
    originals=load(B/'e49_driver/input_manifest49.json');prompts={r['class_key']:r for r in map(json.loads,(audit.RUN/'api_prompts.jsonl').read_text(encoding='utf-8').splitlines())};api={r['class_key']:r for r in legacy.read_csv(audit.RUN/'api_log.csv')}
    jobs=[];prompt_rows=[];candidates=selection['candidates'];assert len(candidates)==49
    for repo in {r['repo_id'] for r in selected}:
        rows=[r for r in candidates if r['repo_id']==repo]
        for r in rows:assert r['selection_digest']==hashlib.sha256(('FISAT2026-repeat-v1|'+repo+'|'+r['class_key']).encode()).hexdigest()
        assert min(rows,key=lambda r:r['selection_digest'])['class_key']==next(r['class_key'] for r in selected if r['repo_id']==repo)
    for s in selected:
        j=copy.deepcopy(originals[s['job_index']-1]);assert j['class_key']==s['class_key'];source=Path(j['source_repo'])
        for r in j['source_files']:assert sha(source/r['relative'])==r['sha256'],r['relative']
        assert sha(source/j['focal_path'])==s['focal_sha256'];p=prompts[j['class_key']];validate_model(p['model_requested']);validate_model(api[j['class_key']]['model_returned'])
        assert len(p['messages'])==2 and [m['role'] for m in p['messages']]==['system','user']
        j['messages_sha256']=digest(p['messages']);j['historical_prompt_tokens']=int(api[j['class_key']]['prompt_tokens'])
        prompt_rows.append({'class_key':j['class_key'],'model':MODEL,'messages':p['messages'],'messages_sha256':j['messages_sha256'],'historical_prompt_hash_sha256':p['prompt_hash_sha256'],'source_run_id':p.get('source_run_id')})
        old=B/'e49_driver/jobs'/f"{j['job_index']:02d}";settings=old/'settings.xml';assert settings.is_file();j['settings_source']=str(settings);j['settings_sha256']=sha(settings)
        ref=B/'e49_measurement_compat_v1/jobs'/f"{j['job_index']:02d}";j['production_baseline']=load(ref/'production_class_baseline.json');assert j['production_baseline'];j['focal_mutants_baseline']=load(ref/'focal_mutant_baseline.json');jobs.append(j)
    schedule=[]
    for rep in range(1,6):
        order=sorted(jobs,key=lambda j:hashlib.sha256(('FISAT2026-repeat-order-v1|'+str(rep)+'|'+j['class_key']).encode()).hexdigest())
        for j in order:
            arms=['G','E'] if int(hashlib.sha256(('FISAT2026-repeat-arms-v1|'+str(rep)+'|'+j['class_key']).encode()).hexdigest(),16)%2==0 else ['E','G']
            seed=int(hashlib.sha256(('FISAT2026-repeat-seed-v1|'+j['class_key']+'|'+str(rep)).encode()).hexdigest()[:12],16)%2147483646+1
            for arm in arms:schedule.append({'slot_id':f'{len(schedule)+1:03d}','job_index':j['job_index'],'class_key':j['class_key'],'repo_id':j['repo_id'],'replicate':rep,'arm':arm,'seed':seed if arm=='E' else None})
    assert len(schedule)==150 and Counter(r['arm'] for r in schedule)=={'G':75,'E':75};assert len({r['seed'] for r in schedule if r['arm']=='E'})==75
    assert Counter((r['class_key'],r['arm']) for r in schedule)==Counter({(j['class_key'],a):5 for j in jobs for a in ['G','E']})
    common=['edit_pom_file','run_maven_test_command','common_maven_skip_args','write_pom_tree']
    for n in common:assert func_hash(audit.ROOT/'scripts_v2/AgoneTest/mavenLib.py',n)==func_hash(legacy.SOURCE,n),n
    upper=sum((j['historical_prompt_tokens']*0.15+2048*0.60)/1e6*5 for j in jobs)
    protocol={'created_utc':now(),'kind':'post-review new repeated generation;15classes x5runs x2arms','selection_sha256':sha(B/'repeated_subset_selection_v1.json'),'selected_classes':15,'repositories':15,'new_replicates_per_arm':5,'planned_slots':150,'planned_GPT_requests_without_retry':75,'planned_EvoSuite_runs':75,'primary_G0_E0_E49_unchanged':True,'no_old_runs_in_repeats':True,'model':MODEL,'API':{'endpoint':'https://api.openai.com/v1/chat/completions','temperature':0,'top_p':1,'max_tokens':2048,'stream':False,'seed':None,'SDK':'openai1.51.2','SDK_implicit_retries':0,'max_explicit_attempts':5,'retry':'transient connection/timeout/429/5xx only; backoff2,4,8,16s; no content retry','stop_batch_on':[401,403,404],'timeout_seconds':120,'cost_cap_USD_estimated':2.0,'uncached_input_USD_per_million':0.15,'output_USD_per_million':0.60,'expected_upper_no_retry_USD':upper,'max5attempt_upper_USD_estimate':upper*5,'budget_accounting':'reserve max-output estimated cost before each POST; not invoice','transport_change':'direct official SDK instead of litellm; archived payload and parameters preserved, explicit observable retries'},'E_profile':'same final E49 assertion-MUTATION/scaffolding/runtime profile; BRANCH60s, archive/separateclassloader off; same conditional E-only JUnit/Surefire policy','E_generation_timeout_seconds':240,'E_retry':'original conditional sanitized-classpath retry,at most2 attempts,same scheduled seed','G_profile':'original model,prompt,response-parser and common Maven POM builder; no E-only compatibility patch','prompt':'exact archived2-message payload; no additions','response_parser_AST_sha256':response_extractor()[1],'shared_Maven_functions_AST_equal':common,'pre_generation_readiness':'fresh source/common POM and module compile; E compile in original generation adapter; G compile before API','measurement_goals':GOALS,'measurement_timeout_seconds':300,'gate':'literal BUILD SUCCESS as historical; evidence flags never replace scores','mutation_score':'KILLED/all focal SourceFile+package rows incl nested;round2;legacy gate/unavailable zero-fill','workers':1,'order':'5rounds; class hash order and alternating arm order fixed in schedule before outcomes','cache':str(CACHE),'cache_guard':'actual resolved JAR hashes/ordered CP; no install goals; final critical-cache check; not full-cache certification','disk_policy':'ZIP all new slot evidence except ephemeral temp; verify all members before removing only new repo/generation snapshot directories; preserve logs/metadata/archive','minimum_free_bytes':2000000000,'within_class_summary':['5raw outcomes','build count','mean','median','sample SD','range','unique generated hashes','status/evidence counts'],'between_arm_summary':'15paired class means over all5scheduled strict outcomes;75runs are not75independent classes','uncertainty':'exploratory whole15class/repo bootstrap20k seed20261024; retain5runs and botharms; no new NI','RQ123_membership':'61/45/300 unchanged','limits':'historical-common-build Maven subset,1class/repo,5repeats coarse variance; post-review selection protocol,not original preregistration','official_model_reference':'https://developers.openai.com/api/docs/models/gpt-4o-mini','request_reference':'https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create'}
    assert upper*5<2
    for name,obj in [('input_jobs15.json',jobs),('prompts15.json',prompt_rows),('schedule150.json',schedule),('protocol.json',protocol)]:dump(ST/name,obj)
    event('PROTOCOL_PREPARED',protocol_sha256=sha(ST/'protocol.json'),schedule_sha256=sha(ST/'schedule150.json'),expected_upper_GPT_USD_no_retry=upper);print(json.dumps({'status':'PREPARED_NOT_STARTED','slots':150,'GPT_cost_upper_no_retry_USD':upper},indent=2))

def production_check(module,j,gate=False):
    current={p.relative_to(module/'target/classes').as_posix():sha(p) for p in (module/'target/classes').rglob('*.class')};base={n:r['sha256'] for n,r in j['production_baseline'].items()}
    changed=[n for n in set(current)&set(base) if current[n]!=base[n]];added=sorted(set(current)-set(base));missing=sorted(set(base)-set(current))
    assert not changed and not added,{'production_bytecode_changed':changed,'production_bytecode_added':added}
    if gate:assert not missing,'BUILD SUCCESS with missing production bytecode'
    return {'count':len(current),'changed':changed,'added':added,'missing':missing,'all_available_hashes_match':True}
def source_check(out,j,expected):
    root=out/'repo';current={p.relative_to(root).as_posix():sha(p) for p in replay.compat.walk(root,replay.EXCLUDE)};issues=[p for p in sorted(set(expected)|set(current)) if expected.get(p)!=current.get(p)]
    assert not issues,{'unexpected_source_edits':issues};assert sha(root/j['focal_path'])==j['focal_sha256']

def self_test():
    assert not (ST/'readiness_lock.json').exists();extract,ph=response_extractor();bt=chr(96)*3;cases=[]
    for t in ['public class Other { }',bt+'java\npublic class Other { }\n'+bt,bt+'.java\npublic class Other { }\n'+bt,'package example;\npublic class Existing { }']:
        code,messages=extract(t,'Expected','example');assert 'class Expected' in code and 'package example;' in code and bt not in code;cases.append({'input':t,'output':code})
    wrong=False
    try:validate_model('gpt-4.1-mini')
    except AssertionError:wrong=True
    assert wrong;validate_model(MODEL)
    fixture=ST/'selftest_fixture';p=fixture/'target/classes/Example.class';p.parent.mkdir(parents=True);p.write_bytes(b'baseline');j={'production_baseline':{'Example.class':{'sha256':sha(p)}}};production_check(fixture,j,True);p.write_bytes(b'changed');caught=False
    try:production_check(fixture,j,True)
    except AssertionError:caught=True
    assert caught
    assert len({(r['class_key'],r['replicate'],r['arm']) for r in load(ST/'schedule150.json')})==150;frozen.check_gpt()
    dump(ST/'self_test.json',{'status':'PASS','parser_cases':cases,'parser_AST_sha256':ph,'wrong_model_guard_rejects':True,'production_change_guard_rejects':True,'schedule150_unique':True,'primary_GPT_guard':'PASS','generation_API_calls':0,'Java_calls':0});event('SELF_TEST_PASS',sha256=sha(ST/'self_test.json'));print(json.dumps({'status':'PASS','parser_cases':4,'negative_controls':2,'generation_API_calls':0}))

def freeze():
    assert load(ST/'self_test.json')['status']=='PASS' and not (ST/'readiness_lock.json').exists()
    names=['src/repeat_subset_driver_v1.py','src/e49_driver.py','src/run_e49_supplement.py','src/replay_fixed49_measurement_v5.py','src/diagnose_e1_compatibility_v4.py','src/junit_method_inventory_v1.py','evo_patch/working/AgoneTest/mavenLib.py','evo_patch/working/AgoneTest/evosuite_profile.py','repeated_subset_selection_v1.json']+[f'repeated_subset_v1/{n}.json' for n in ['input_jobs15','prompts15','schedule150','protocol','self_test']]
    files=[audit.ROOT/'scripts_v2/AgoneTest/mavenLib.py',audit.ROOT/'scripts_v2/AgoneTest/utils.py',audit.ROOT/'scripts_v2/agone_one.py',audit.RUN/'api_prompts.jsonl',audit.RUN/'api_log.csv',legacy.JDK/'bin/java.exe',audit.ROOT/'scripts_v2/evosuite-1.2.0.jar',audit.ROOT/'scripts_v2/evosuite-standalone-runtime-1.2.0.jar']
    dump(ST/'readiness_lock.json',{'created_utc':now(),'code_and_input_hashes':{n:sha(B/n) for n in names},'external_hashes':{str(p):sha(p) for p in files},'self_test':'PASS','no_generation_before_lock':True});frozen.check_gpt();audit.verify();event('PROTOCOL_FROZEN',lock_sha256=sha(ST/'readiness_lock.json'));print(json.dumps({'status':'FROZEN_READY','slots':150}))

class Budget:
    def __init__(self):self.reserved=sum(r.get('reserved_USD',0) for r in map(json.loads,(ST/'api_attempts.jsonl').read_text(encoding='utf-8').splitlines())) if (ST/'api_attempts.jsonl').exists() else 0
    def reserve(self,amount,info):
        assert self.reserved+amount<=2,'Estimated GPT cost cap reached before POST';self.reserved+=amount;row={'timestamp_utc':now(),'slot_id':CURRENT['slot_id'],'reserved_USD':amount,'cumulative_reserved_USD':self.reserved,**info}
        with (ST/'api_attempts.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n');f.flush();os.fsync(f.fileno())

def gpt_generate(out,j,budget,client):
    prompt=next(r for r in load(ST/'prompts15.json') if r['class_key']==j['class_key']);assert digest(prompt['messages'])==j['messages_sha256'];payload={'model':MODEL,'messages':prompt['messages'],'temperature':0,'top_p':1,'max_tokens':2048,'stream':False};dump(out/'api_request.json',payload);start=time.monotonic();attempts=[]
    import openai
    for attempt in range(1,6):
        budget.reserve((j['historical_prompt_tokens']*0.15+2048*0.60)/1e6,{'attempt':attempt,'payload_sha256':sha(out/'api_request.json')});event('API_POST_START',attempt=attempt,request_sha256=sha(out/'api_request.json'));t=time.monotonic()
        try:
            r=client.chat.completions.create(**payload);dump(out/f'api_response_attempt{attempt}.json',r.model_dump());validate_model(r.model)
            row={'attempt':attempt,'status':'OK','model_returned':r.model,'duration_seconds':time.monotonic()-t,'usage':r.usage.model_dump() if r.usage else None,'system_fingerprint':getattr(r,'system_fingerprint',None),'response_sha256':sha(out/f'api_response_attempt{attempt}.json')};dump(out/f'api_attempt{attempt}.json',row);attempts.append(row);content=r.choices[0].message.content if r.choices else None
            code=response_extractor()[0](content,Path(j['old_synthesized_test_relative']).stem,j['package'])[0] if content and content.strip() else None
            event('API_POST_END',**row);return code,{'attempts':attempts,'api_duration_seconds':time.monotonic()-start,'model':r.model,'response_content_sha256':hashlib.sha256((content or '').encode()).hexdigest(),'generated_nonempty':bool(code)}
        except (openai.APIConnectionError,openai.APITimeoutError,openai.APIStatusError) as e:
            status=getattr(e,'status_code',None);row={'attempt':attempt,'status':'ERROR','exception_class':type(e).__name__,'http_status':status,'duration_seconds':time.monotonic()-t};dump(out/f'api_attempt{attempt}.json',row);attempts.append(row);event('API_POST_END',**row)
            if status in [401,403,404]:raise RuntimeError('API authorization/model blocked; stop, no model substitution') from None
            if attempt<5 and (status is None or status==429 or status>=500):time.sleep(2**attempt)
            else:return None,{'attempts':attempts,'api_duration_seconds':time.monotonic()-start,'generated_nonempty':False}

def repeat_cp_entries(file):
    file=Path(file);assert file.is_file(),'Missing classpath output'
    if not file.read_text(encoding='utf-8').strip():return []
    return replay.cp_entries(file)
repeat_dependency=types.FunctionType(replay.dependency.__code__,{**replay.dependency.__globals__,'cp_entries':repeat_cp_entries},'repeat_dependency')

policy_patch=types.FunctionType(replay.patch_pom.__code__,{**replay.patch_pom.__globals__,'event':event},'repeat_policy_patch')

def archive_slot(out):
    archive=out/'slot_archive.zip';assert not archive.exists();files=[p for p in sorted(out.rglob('*')) if p.is_file() and 'temp' not in p.relative_to(out).parts];members=[]
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
        for p in files:
            rel=p.relative_to(out).as_posix();h=sha(p);z.write(p,rel);assert sha(p)==h;members.append({'path':rel,'sha256':h,'bytes':p.stat().st_size})
    with zipfile.ZipFile(archive) as z:
        assert len(z.namelist())==len(members) and z.testzip() is None
        for r in members:assert hashlib.sha256(z.read(r['path'])).hexdigest()==r['sha256'],r['path']
    dump(out/'archive_manifest.json',{'archive_sha256':sha(archive),'files':members,'excluded':'ephemeral temp only','verified_all_members':True});removed=[]
    for p in [out/'repo',*out.glob('generation_attempt_*')]:
        if not p.is_dir():continue
        resolved=p.resolve();assert resolved.is_relative_to(out.resolve()) and out.resolve().is_relative_to((ST/'slots').resolve());assert p.name=='repo' or re.fullmatch(r'generation_attempt_\d+',p.name)
        shutil.rmtree(p);removed.append(str(resolved))
    dump(out/'workspace_cleanup.json',{'removed_new_directories':removed,'verified_archive_sha256':sha(archive),'original_paths_removed':False});event('SLOT_ARCHIVED',archive_sha256=sha(archive),files=len(members))

def repeat_prepare_job_v2(job,out):
    out.mkdir(parents=True,exist_ok=False);source=Path(job['source_repo']).resolve();repo=out/'repo';repo.mkdir()
    copies=[]
    for row in job['source_files']:
        rel=Path(row['relative']);assert not rel.is_absolute() and '..' not in rel.parts
        src=source/rel;dest=repo/rel;assert src.resolve().is_relative_to(source)
        assert audit.sha(src)==row['sha256'],'Frozen source changed: '+str(src)
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
        assert audit.sha(dest)==row['sha256'];copies.append(row)
    driver.write_json(out/'input_snapshot_manifest.json',copies)
    old=repo/job['old_synthesized_test_relative']
    if old.exists():
        backup=out/'removed_prior_synthesized_test'/job['old_synthesized_test_relative'];backup.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(old,backup);assert audit.sha(old)==audit.sha(backup)
        audit.log('COPIED_PRIOR_TEST_REMOVED',job=str(out.relative_to(BASE)),path=str(old.relative_to(out)),backup=str(backup.relative_to(out)),sha256=audit.sha(old))
        old.unlink()
    # Expected old generated suites must have been cleaned in the frozen source snapshot.
    existing=[p for p in repo.rglob('*.java') if p.name.endswith(('_ESTest.java','_ESTest_scaffolding.java')) and 'src/test/java' in p.as_posix()]
    assert not existing,'Prior EvoSuite artifacts found; inspect rather than silently reuse'
    sandbox=source.parent.parent;settings=sandbox/'settings.xml'
    if settings.is_file():
        shutil.copy2(settings,out/'settings.xml');assert audit.sha(settings)==audit.sha(out/'settings.xml')
    focal=repo/job['focal_path'];assert audit.sha(focal)==job['focal_sha256']
    assert audit.sha(out/'settings.xml')==job['settings_sha256'],'Copied settings differ from locked E49 settings'
    return repo/Path(job['module']),focal

def execute(slot,j,budget,client):
    global CURRENT
    CURRENT=slot;out=ST/'slots'/slot['slot_id'];assert not out.exists(),'Started slot cannot be automatically repeated';assert shutil.disk_usage(B).free>=2000000000,'Disk reserve reached before next slot'
    module,focal=repeat_prepare_job_v2(j,out);expected={r['relative']:r['sha256'] for r in j['source_files']};expected.pop(j['old_synthesized_test_relative'],None);assert not list((out/'repo').rglob('target'))
    env=legacy.isolated_env(out);commands=legacy.Commands(out,env,CACHE,slot['seed'] or 0);ns,phases=legacy.load_functions(commands,out);test=j['selected_test_fqcn'] if slot['arm']=='E' else (j['package']+'.' if j['package'] else '')+Path(j['old_synthesized_test_relative']).stem;testjava=module/'src/test/java'/Path(*test.split('.')).with_suffix('.java')
    df=pd.DataFrame([{'Project':j['repo_id'],'Module':j['module'],'Focal_Class':j['focal_class'],'Test_Class':test.split('.')[-1],'Focal_Path':str(focal),'Test_Path':testjava.as_posix()}]);poms=list((out/'repo').rglob('pom.xml'))
    for p in poms:
        backup=out/'backup_poms'/p.relative_to(out/'repo');backup.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,backup)
    dump(out/'slot_admission.json',{'slot':slot,'lock_sha256':sha(ST/'readiness_lock.json'),'start_utc':now(),'input_manifest_sha256':sha(out/'input_snapshot_manifest.json')});event('SLOT_START',**slot);started=time.monotonic();assert ns['edit_pom_file'](str(module),df,j['junit_version'],j['testng_version']) is not None
    if slot['arm']=='E':assert ns['add_evosuite_pom'](str(module)) is not None
    expected[(Path(j['module'])/'pom.xml').as_posix()]=sha(module/'pom.xml');source_check(out,j,expected);dump(out/'pom_after_integration.json',{p.relative_to(out/'repo').as_posix():sha(p) for p in poms})
    generated=False;api={};gen_start=time.monotonic();preprocessing_ok=True
    if slot['arm']=='E':generated=ns['run_evosuite_generation_maven'](str(module),str(focal),'Windows',generation_profile=legacy.evosuite_profile.REVIEWER)
    else:
        prep=commands.run(['mvn','-s',str(out/'settings.xml'),*ns['common_maven_skip_args'](),'-DskipTests=true','compile'],cwd=module,timeout=300);preprocessing_ok=prep.returncode==0
        if preprocessing_ok:
            production_check(module,j,True);code,api=gpt_generate(out,j,budget,client)
            if code:testjava.parent.mkdir(parents=True,exist_ok=True);testjava.write_text(code,encoding='utf-8');generated=True
    gen_seconds=time.monotonic()-gen_start;selected={}
    if slot['arm']=='E':selected={p.relative_to(out/'repo').as_posix():sha(p) for p in [testjava,testjava.with_name(testjava.stem+'_scaffolding.java')] if p.is_file()}
    elif generated:selected[testjava.relative_to(out/'repo').as_posix()]=sha(testjava)
    expected.update(selected);source_check(out,j,expected);dump(out/'generated_sources_manifest.json',selected)
    if generated:assert testjava.is_file()
    production_before=production_check(module,j);args=['mvn','-s',str(out/'settings.xml'),'-Dtest='+test,*ns['common_maven_skip_args']()];policy={'JUnit_rule_applied':False,'selector_rule_applied':False,'changes':[],'arm':slot['arm']};gate=False;measurement_seconds=0;measure_start=time.monotonic();scaffold=testjava.with_name(testjava.stem+'_scaffolding.java').is_file()
    if generated and (slot['arm']=='G' or scaffold):
        before_dep=repeat_dependency(commands,args,module,out,'before')
        if slot['arm']=='E':
            before_eff=replay.effective(commands,args,module,out,'before');policy=policy_patch({**j,'selected_test_fqcn':test},module,out,before_dep,before_eff)
            if policy['changes']:
                after_dep=repeat_dependency(commands,args,module,out,'after');after_eff=replay.effective(commands,args,module,out,'after');replay.compare_cp(before_dep,after_dep,policy);a=copy.deepcopy(before_eff);b=copy.deepcopy(after_eff)
                if policy['selector_rule_applied']:
                    for p in [a,b]:
                        reg=next(e for e in p.findall('m:executions/m:execution',replay.NS) if e.findtext('m:id',namespaces=replay.NS)=='regular-tests');conf=reg.find('m:configuration',replay.NS);conf.remove(conf.find('m:includes',replay.NS))
                assert replay.normalize(a)==replay.normalize(b),'Surefire drift outside allowed includes'
            expected[(Path(j['module'])/'pom.xml').as_posix()]=sha(module/'pom.xml')
        else:dump(out/'policy_applied.json',policy)
        measurement_start=time.monotonic();gate=ns['run_maven_test_command'](str(module),df,'Windows')[0];measurement_seconds=time.monotonic()-measurement_start
    else:dump(out/'policy_applied.json',policy)
    integration_seconds=time.monotonic()-measure_start-measurement_seconds;source_check(out,j,expected)
    for n,h in selected.items():assert sha(out/'repo'/n)==h
    production_after=production_check(module,j,gate);raw=legacy.raw_metrics(module,test,j['focal_class'],j['package'],gate);methods=inventory.inventory_java_tests(testjava.read_text(encoding='utf-8')) if generated else {'methods':[]};cases=[]
    for p in sorted((module/'target/surefire-reports').glob('TEST-*.xml')):
        root=ET.parse(p).getroot()
        for c in root.findall('testcase'):cases.append({'suite':root.get('name'),'class':c.get('classname'),'name':c.get('name'),'failures':len(c.findall('failure')),'errors':len(c.findall('error')),'skipped':len(c.findall('skipped'))})
    result={**slot,'status':'COMPLETED','preprocessing_ok':preprocessing_ok,'generation_success':bool(generated),'scaffold_present':scaffold,'generated_sources':selected,'API':api,'generation_duration_seconds_including_compile':gen_seconds,'measurement_duration_seconds':measurement_seconds,'integration_diagnostic_seconds':integration_seconds,'slot_duration_seconds_before_archive':time.monotonic()-started,'policy':policy,**raw,'method_inventory':methods,'canonical_cases':cases,'production_before':production_before,'production_after':production_after,'generated_source_bytes_unchanged_during_measurement':True,'source_guard':'PASS','EvoSuite_generation_attempts':sum('-jar' in r['argv'] for r in commands.records),'GPT_API_attempts':len(api.get('attempts',[])),'configuration_labels_are_not_scoring_scales':True}
    dump(out/'phase_records.json',phases);dump(out/'result.json',result);frozen.check_gpt();event('SLOT_MEASURED',legacy_score=result['legacy_strict_mutation_percent'],generation_success=bool(generated),result_sha256=sha(out/'result.json'));archive_slot(out);dump(out/'complete.json',{'status':'COMPLETE','slot_id':slot['slot_id'],'result_sha256':sha(out/'result.json'),'archive_manifest_sha256':sha(out/'archive_manifest.json'),'finished_utc':now()});event('SLOT_COMPLETE',result_sha256=sha(out/'result.json'));return result

def run():
    verify_core();assert not (ST/'batch_admission.json').exists(),'Second batch cannot overwrite started slots'
    from dotenv import dotenv_values
    from openai import OpenAI
    key=dotenv_values(audit.ROOT/'scripts_v2/.env').get('OPENAI_API_KEY') or os.environ.get('OPENAI_API_KEY');assert key;client=OpenAI(api_key=key,max_retries=0,timeout=120,base_url='https://api.openai.com/v1')
    dump(ST/'batch_admission.json',{'timestamp_utc':now(),'lock_sha256':sha(ST/'readiness_lock.json'),'slots':150,'workers':1});jobs={j['class_key']:j for j in load(ST/'input_jobs15.json')};budget=Budget();results=[]
    for slot in load(ST/'schedule150.json'):
        verify_core()
        try:result=execute(slot,jobs[slot['class_key']],budget,client)
        except BaseException as exc:event('BATCH_ABORT',exception_class=type(exc).__name__,detail=str(exc)[:800] if isinstance(exc,AssertionError) else 'Preserved logs; no automatic repeat of started slots');raise
        results.append(result);print(json.dumps({'completed':len(results),'n':150,'slot_id':slot['slot_id'],'job':slot['job_index'],'replicate':slot['replicate'],'arm':slot['arm'],'build':result['legacy_process_build'],'score':result['legacy_strict_mutation_percent']}),flush=True)
    dump(ST/'results150.json',results);frozen.check_gpt();audit.verify();dump(ST/'complete.json',{'status':'COMPLETE','n':150,'results_sha256':sha(ST/'results150.json'),'GPT_slots':75,'EvoSuite_slots':75,'finished_utc':now(),'reserved_estimated_GPT_USD':budget.reserved});event('BATCH_COMPLETE',n=150,results_sha256=sha(ST/'results150.json'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','self-test','freeze','run']);a=p.parse_args();{'prepare':prepare,'self-test':self_test,'freeze':freeze,'run':run}[a.mode]()
