"""Serial controller: cache/input readiness -> actual driver fixture -> lock -> E49.

Only proceeds when all gates pass. Logs failures and exits, never tunes config/seeds.
"""
import json,subprocess,sys,time
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
STAGE=BASE/'e49_driver';PY=sys.executable
status=STAGE/'controller_events.jsonl'
def event(kind,**data):
    from datetime import datetime,timezone
    r={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'kind':kind,**data}
    with status.open('a',encoding='utf-8') as f:f.write(json.dumps(r)+'\n')
    print(json.dumps(r),flush=True)
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def command(name,args,timeout):
    # The audit wrapper supplies immutable per-attempt stdout/stderr and event hashes.
    argv=[PY,'-B','-X','utf8',str(BASE/'audit.py'),'run',name,PY,'-B','-X','utf8',*args]
    r=subprocess.run(argv,cwd=audit.ROOT,timeout=timeout)
    if r.returncode:raise RuntimeError(name+' failed with '+str(r.returncode))
try:
    assert not (STAGE/'controller_admission.json').exists()
    with (STAGE/'controller_admission.json').open('x',encoding='utf-8') as f:json.dump({'scope':'E49 supplementary only; gates before generation','no_GPT_API':True},f)
    event('WAITING_INPUT_AND_CACHE_GATES',benchmark_started=False)
    deadline=time.monotonic()+3600
    while not ((STAGE/'cache_copy_parallel_result.json').exists() and (STAGE/'protocol49.json').exists()):
        if time.monotonic()>deadline:raise TimeoutError('Input/cache gate not ready within1hour; no benchmark started')
        time.sleep(5)
    # Child may have written report before the wrapper's COMMAND_END. Avoid overlapping ledger writes.
    while True:
        ends={e.get('name'):e.get('returncode') for e in audit.events() if e['kind']=='COMMAND_END'}
        if ends.get('cache_copy_parallel')==0 and ends.get('e49_prepare_manifest02')==0:break
        if time.monotonic()>deadline:raise TimeoutError('Input/cache command wrapper not completed')
        time.sleep(2)
    cache=read(STAGE/'cache_copy_parallel_result.json');jobs=read(STAGE/'input_manifest49.json')
    assert cache['status']=='PASS' and cache['all_copies_verified']
    assert len(jobs)==49 and all(j['matches_current_compiledrepos_focal'] for j in jobs),'Focal source differs from current compiledrepos; inspect before benchmark'
    event('RUNNING_ACTUAL_DRIVER_FIXTURE',benchmark_started=False)
    command('actual_e49_driver_fixture',[str(BASE/'src/e49_driver.py'),'fixture','--local-repository',cache['target']],1500)
    fixture=read(STAGE/'fixture_actual_driver_01/result.json')
    assert fixture['generation_success'] and fixture['scaffold_present'] and fixture['generated_bytes_unchanged']
    assert fixture['only_selected_suite_executed'] and fixture['measurement_evidence_complete']
    semantics=read(STAGE/'semantic_checks_03/result.json')
    assert semantics['status']=='PASS' and semantics['driver_sha256']==audit.sha(BASE/'src/e49_driver.py')
    timeout_control=read(STAGE/'timeout_tree_control_01/result.json')
    assert timeout_control['status']=='PASS' and timeout_control['driver_sha256']==audit.sha(BASE/'src/e49_driver.py')
    # Freeze all settings and toolchain context; selectors/metric definitions remain as protocol49.
    settings={}
    for j in jobs:
        sandbox=Path(j['source_repo']).parent.parent
        for p in [sandbox/'settings.xml',sandbox/'output/project_info.json',sandbox/'output/classes.csv']:
            if p.is_file():settings[str(p)]=audit.sha(p)
    tools=[Path('C:/Program Files/Java/jdk1.8.0_172/bin/java.exe'),Path('C:/Program Files/Java/jdk1.8.0_172/bin/javac.exe'),
        Path('C:/Program Files/Java/jdk1.8.0_172/lib/tools.jar'),Path('C:/Program Files/Apache/maven/bin/mvn.cmd'),
        audit.ROOT/'scripts_v2/evosuite-1.2.0.jar',audit.ROOT/'scripts_v2/evosuite-standalone-runtime-1.2.0.jar']
    for p in [Path('C:/Users/admin/.m2/settings.xml'),Path('C:/Users/admin/.m2/toolchains.xml'),Path('C:/Program Files/Apache/maven/conf/settings.xml')]:
        if p.is_file():tools.append(p)
    codes=['src/e49_driver.py','src/run_e49_supplement.py','e49_driver/input_manifest49.json','e49_driver/protocol49.json',
        'evo_patch/working/AgoneTest/mavenLib.py','evo_patch/working/AgoneTest/evosuite_profile.py']
    lock={'actual_driver_fixture_passed':True,'semantic_negative_checks_passed':True,'local_repository':cache['target'],
        'code_and_input_hashes':{p:audit.sha(BASE/p) for p in codes},'tool_hashes':{str(p):audit.sha(p) for p in tools},
        'context_source_hashes':settings,'cache_copy_manifest_sha256':cache['manifest_sha256'],
        'limit':'Gate validates synthetic driver, not arm-equivalence of historical raw reports; E49 remains supplementary',
        'fixture_result_sha256':audit.sha(STAGE/'fixture_actual_driver_01/result.json')}
    with (STAGE/'readiness_lock.json').open('x',encoding='utf-8') as f:json.dump(lock,f,indent=2)
    audit.log('E49_READINESS_LOCKED',sha256=audit.sha(STAGE/'readiness_lock.json'),fixture_passed=True,n=49)
    event('VERIFYING_BENCHMARK_ADMISSION',benchmark_started=False)
    command('e49_admission_verify',[str(BASE/'src/run_e49_supplement.py'),'verify'],180)
    event('RUNNING_FIXED49_SUPPLEMENT',benchmark_started=True,GPT_API_calls=0)
    # Preserve legacy per-job limits and conditional retry. Worst-case batch is multiple hours.
    command('e49_benchmark',[str(BASE/'src/run_e49_supplement.py'),'run'],24*3600)
    event('BENCHMARK_COMPLETE',benchmark_started=True,n=49)
except Exception as exc:
    event('PIPELINE_STOPPED',error_type=type(exc).__name__,detail=str(exc),benchmark_admission_exists=(STAGE/'benchmark_admission.json').exists())
    raise
