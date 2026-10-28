"""Inspection-only recovery of already measured11; keep protocol and completed prefix immutable."""
import csv,json,sys,types
from pathlib import Path
import psutil
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));sys.path.insert(0,str(BASE/'src'))
import audit,replay_fixed49_measurement_v5 as m,analyze_measurement_compat49_v2 as a
RESUME=m.STAGE/'resume_guard02'
def main():
    m.verify_lock();audit.verify();assert not RESUME.exists(),'Single inspection amendment admission'
    own=psutil.Process();ancestors={p.pid for p in own.parents()}|{own.pid}
    for p in psutil.process_iter(['pid','cmdline']):
        if p.pid in ancestors:continue
        try:
            scripts=[Path(v).name for v in (p.info['cmdline'] or []) if v.lower().endswith('.py')]
            assert not any(v.startswith(('replay_fixed49_measurement_','resume_fixed49_measurement_')) for v in scripts),'Competing experiment/recovery process'
        except (psutil.NoSuchProcess,psutil.AccessDenied):pass
    jobs=m.load(m.STAGE/'input_manifest49.json');byid={j['job_index']:j for j in jobs};completed=m.ORDER[:12];remaining=m.ORDER[13:];assert m.ORDER[12]==11
    assert sorted(int(p.stem.rsplit('_',1)[1]) for p in m.STAGE.glob('job_result_*.json'))==sorted(completed)
    results={i:m.load(m.STAGE/f'job_result_{i:02}.json') for i in completed};prefix={}
    for i in completed:
        w=m.STAGE/'jobs'/f'{i:02}';a.verify_artifact_manifest(w)
        paths=[BASE/r['path'] for r in m.load(w/'artifact_manifest.json')]+[w/'artifact_manifest.json',m.STAGE/f'job_result_{i:02}.json']
        assert m.load(w/'result.json')==results[i]
        for p in paths:prefix[p.relative_to(BASE).as_posix()]={'sha256':audit.sha(p),'bytes':p.stat().st_size}
    out=m.STAGE/'jobs/11';j=byid[11];module=out/'repo'/j['module'];old=m.E1/'jobs/11'
    assert not (out/'result.json').exists() and not (out/'measurement_audit.json').exists() and not (out/'artifact_manifest.json').exists()
    assert (out/'generated_test_bytecode_after.json').is_file() and (out/'original_E1_guard_after.json').is_file()
    for i in remaining:
        w=m.STAGE/'jobs'/f'{i:02}';assert not (w/'result.json').exists() and not list(w.glob('command_*.json')),'Unattempted remainder violated'
    records=[m.load(p) for p in sorted(out.glob('command_*.json'))];measured=[r for r in records if any('mutationCoverage' in str(v) for v in r['argv'])];assert len(measured)==1 and measured[0] is records[-1]
    command=measured[0];oldargv=m.load(old/'command_04.json')['argv'];start=oldargv.index('-Dtest='+j['selected_test_fqcn']);flags=oldargv[start:oldargv.index('clean')];goals=m.load(m.STAGE/'protocol.json')['goals']
    expected=[str(m.legacy.MVN),'-o','-Dmaven.repo.local='+str(m.CACHE.resolve()),'-s',str(out/'settings.xml'),*flags,*goals];assert command['argv']==expected,'Measurement argv differs from locked profile'
    for rec in records:
        for key in ['stdout','stderr']:assert audit.sha(BASE/rec[key])==rec[key+'_sha256']
    assert command['returncode']==0 and not command['timeout'],'Retain only actually completed slot11 without retry'
    RESUME.mkdir();retained11=m.hashes(out);m.dump(RESUME/'retained_completed_prefix_files.json',prefix);m.dump(RESUME/'retained_slot11_files.json',retained11)
    admission={'created_utc':m.now(),'kind':'inspection-only amendment recovery, no measurement repeat','controller_sha256':audit.sha(__file__),'same_driver_v4_sha256':audit.sha(BASE/'src/replay_fixed49_measurement_v4.py'),'amended_driver_sha256':audit.sha(BASE/'src/replay_fixed49_measurement_v5.py'),'same_readiness_lock_sha256':audit.sha(m.STAGE/'readiness_lock.json'),'same_protocol_sha256':audit.sha(m.STAGE/'protocol.json'),'original_admission_sha256':audit.sha(m.STAGE/'admission.json'),'inspection_amendment_sha256':audit.sha(m.STAGE/'inspection_amendment_v1.json'),'retained_completed_prefix_sha256':audit.sha(RESUME/'retained_completed_prefix_files.json'),'retained_slot11_files_sha256':audit.sha(RESUME/'retained_slot11_files.json'),'completed_order':completed,'retained_measurement_job11':1,'new_measurement_calls_for11':0,'remaining_order':remaining,'generation_calls':0,'GPT_API_calls':0}
    m.dump(RESUME/'admission.json',admission);m.event('RESUME_AFTER_INSPECTION_AMENDMENT',admission_sha256=audit.sha(RESUME/'admission.json'),inspection_amendment_sha256=admission['inspection_amendment_sha256'],completed_order=completed,retained_measurement_job11=1)
    try:
        oldafter=m.hashes(old);assert oldafter==m.load(out/'original_E1_guard_before.json')==m.load(out/'original_E1_guard_after.json'),'Original E1 slot11 drift; no overwrite'
        policy=m.load(out/'policy_applied.json');before=m.load(out/'before_dependency.json');after=m.load(out/'after_dependency.json') if (out/'after_dependency.json').is_file() else before;m.compare_cp(before,after,policy)
        stdout=(BASE/command['stdout']).read_text(encoding='utf-8');stderr=(BASE/command['stderr']).read_text(encoding='utf-8');gate=not command['timeout'] and command['returncode']!=-999 and 'BUILD SUCCESS' in stdout
        raw,diag=m.inspect(out,j,module,gate,types.SimpleNamespace(stdout=stdout,stderr=stderr,returncode=command['returncode']))
        row={'job_index':11,'class_key':j['class_key'],'repo_id':j['repo_id'],'G0_archived_mutation_percent':j['gpt_archived_mutation_percent'],'E0_archived_mutation_percent':j['e0_archived_mutation_percent'],'E1_archived_mutation_percent':j['E1_archived_mutation_percent'],'seed':j['seed'],'archived_E1_generation_success':j['archived_E1_generation_success'],'generation_attempts':0,'generation_calls':0,'reused_E1_generated_tests':True,'generated_bytes_unchanged':True,'GPT_API_calls':0,'configuration':'frozen_E1_suite_compatibility_measurement','command_returncode':command['returncode'],**raw,'strict_suite_evidence':diag['complete_suite_evidence'],'strict_measurement_evidence':diag['complete_measurement_evidence']}
        assert raw['legacy_strict_mutation_percent']==0 and diag['JUnit_method_inventory']['no_behavior_placeholder_count']==1
        for entry in after['classpath']:assert audit.sha(entry['absolute_path'])==entry['sha256'],'Dependency JAR drift after retained measurement11'
        m.dump(out/'result.json',row);m.archive_job(out,j)
        frozen=m.legacy.read_csv(BASE/'outputs/paired49.csv');original=m.load(m.E1/'results49.json');a.inspect_job(m.STAGE,j,frozen[10],row,original[10],a.pure_original_functions())
        for rel,value in retained11.items():assert audit.sha(out/rel)==value['sha256'] and (out/rel).stat().st_size==value['bytes'],'Retained slot11 file changed'
        for rel,value in prefix.items():assert audit.sha(BASE/rel)==value['sha256'] and (BASE/rel).stat().st_size==value['bytes'],'Completed prefix changed'
        m.frozen.check_gpt();m.dump(RESUME/'slot11_revalidation.json',{'status':'PASS','unique_measurement_calls':1,'repeated_measurement_calls':0,'legacy_score':raw['legacy_strict_mutation_percent'],'no_behavior_placeholder_count':1,'non_placeholder_test_methods':0,'raw_analyzer_revalidation':'PASS','completed_prefix_unchanged':True,'existing_guard_files_not_overwritten':True})
        m.dump(m.STAGE/'job_result_11.json',row);m.event('JOB_COMPLETE',job_index=11,result_sha256=audit.sha(out/'result.json'),artifact_manifest_sha256=audit.sha(out/'artifact_manifest.json'),gate=raw['legacy_process_build'],suite_pass=diag['complete_suite_evidence'],inspection_only_recovery=True);results[11]=row
        print(json.dumps({'completed':len(results),'n':49,'job_index':11,'retained_measurement':True,'placeholder_only':True}),flush=True)
        for i in remaining:
            m.frozen.check_gpt();results[i]=m.execute(byid[i]);print(json.dumps({'completed':len(results),'n':49,'job_index':i,'gate':results[i]['legacy_process_build'],'new_generation':False}),flush=True)
        rows=[results[i] for i in range(1,50)];m.dump(m.STAGE/'results49.json',rows);fields=list(dict.fromkeys(k for r in rows for k in r if not isinstance(r[k],(dict,list))))
        with (m.STAGE/'results49.csv').open('x',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
        m.frozen.check_gpt();audit.verify();m.dump(m.STAGE/'complete.json',{'status':'COMPLETE','n':49,'results49_sha256':audit.sha(m.STAGE/'results49.json'),'GPT_API_calls':0,'generation_calls':0,'inspection_amendment_sha256':audit.sha(m.STAGE/'inspection_amendment_v1.json'),'technical_recovery_without_remeasurement':True});m.event('COMPLETE',n=49,results49_sha256=audit.sha(m.STAGE/'results49.json'))
    except BaseException as ex:m.event('ABORT',error_type=type(ex).__name__,error=str(ex),controller='resume_guard02');raise
if __name__=='__main__':main()
