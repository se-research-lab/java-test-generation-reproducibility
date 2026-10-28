"""Recover completed fixed49 slot18 after external process interruption; never remeasure it."""
import csv,json,sys
from pathlib import Path
import psutil
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));sys.path.insert(0,str(BASE/'src'))
import audit,replay_fixed49_measurement_v4 as m,analyze_measurement_compat49_v1 as a
EXPECTED='9303fab5fc6b8c6167eb39354a1c9504265371782024f109c785a1386eda1b8b'
RESUME=m.STAGE/'resume_guard01'
def main():
    assert audit.sha(BASE/'src/replay_fixed49_measurement_v4.py')==EXPECTED
    m.verify_lock();audit.verify();assert not RESUME.exists(),'Exclusive technical recovery; no second admission'
    # No competing old/new driver is allowed; this controller itself is the only recovery process.
    own=psutil.Process();ancestor_ids={p.pid for p in own.parents()}|{own.pid}
    for p in psutil.process_iter(['pid','cmdline']):
        if p.pid in ancestor_ids:continue
        try:
            args=p.info['cmdline'] or []
            scripts=[Path(v).name for v in args if v.lower().endswith('.py')]
            assert not any(v=='replay_fixed49_measurement_v4.py' or v.startswith('resume_fixed49_measurement_') for v in scripts),'Competing measurement/recovery process'
        except (psutil.NoSuchProcess,psutil.AccessDenied):pass
    jobs=m.load(m.STAGE/'input_manifest49.json');byid={j['job_index']:j for j in jobs};out=m.STAGE/'jobs/18'
    assert not (m.STAGE/'complete.json').exists() and not list(m.STAGE.glob('job_result_*.json'))
    assert (out/'result.json').is_file() and not (out/'original_E1_guard_after.json').exists() and not (out/'artifact_manifest.json').exists()
    for i in m.ORDER[1:]:
        fresh=m.STAGE/'jobs'/f'{i:02}'
        assert not (fresh/'result.json').exists() and not list(fresh.glob('command_*.json')),'Remaining slot was already attempted'
    RESUME.mkdir();prefix=m.hashes(out);m.dump(RESUME/'retained_slot18_files.json',prefix)
    admission={'kind':'technical process recovery without remeasurement','created_utc':m.now(),'controller_sha256':audit.sha(__file__),'same_driver_sha256':EXPECTED,'same_readiness_lock_sha256':audit.sha(m.STAGE/'readiness_lock.json'),'same_protocol_sha256':audit.sha(m.STAGE/'protocol.json'),'original_admission_sha256':audit.sha(m.STAGE/'admission.json'),'retained_slot18_files_sha256':audit.sha(RESUME/'retained_slot18_files.json'),'retained_measurement_calls':1,'new_measurement_calls_for18':0,'remaining_order':m.ORDER[1:],'generation_calls':0,'GPT_API_calls':0}
    m.dump(RESUME/'admission.json',admission);m.event('TECHNICAL_RECOVERY_START',admission_sha256=audit.sha(RESUME/'admission.json'),reason='Managed process/session disappeared after completed measurement/result18, before original-E1 guard closure; no competing process')
    try:
        old=m.E1/'jobs/18';after=m.hashes(old);assert after==m.load(out/'original_E1_guard_before.json'),'Original E1 slot18 changed during interrupted run'
        m.dump(out/'original_E1_guard_after.json',after);m.event('ORIGINAL_E1_GUARD',job_index=18,unchanged=True,technical_recovery=True)
        row=m.load(out/'result.json');diag=m.load(out/'measurement_audit.json')
        assert row['legacy_process_build'] and diag['complete_measurement_evidence'] and diag['focal_mutant_multiset_matches_E1'] and not diag['missing_production_classes'] and len(diag['canonical_cases'])==2
        m.archive_job(out,byid[18])
        frozen=m.legacy.read_csv(BASE/'outputs/paired49.csv');original=m.load(m.E1/'results49.json')
        a.inspect_job(m.STAGE,byid[18],frozen[17],row,original[17],a.pure_original_functions())
        for rel,value in prefix.items():assert audit.sha(out/rel)==value['sha256'] and (out/rel).stat().st_size==value['bytes'],'Retained file changed during closure'
        m.frozen.check_gpt();m.dump(RESUME/'slot18_revalidation.json',{'status':'PASS','unique_completed_measurements':1,'repeated_measurement_calls':0,'retained_files':len(prefix),'source_original_GPT_guards':'PASS','raw_analyzer_revalidation':'PASS'})
        m.dump(m.STAGE/'job_result_18.json',row);m.event('JOB_COMPLETE',job_index=18,result_sha256=audit.sha(out/'result.json'),artifact_manifest_sha256=audit.sha(out/'artifact_manifest.json'),gate=row['legacy_process_build'],suite_pass=diag['complete_suite_evidence'],technical_recovery=True)
        results={18:row};print(json.dumps({'completed':1,'n':49,'job_index':18,'resumed_without_remeasurement':True}),flush=True)
        for i in m.ORDER[1:]:
            m.frozen.check_gpt();results[i]=m.execute(byid[i]);print(json.dumps({'completed':len(results),'n':49,'job_index':i,'gate':results[i]['legacy_process_build'],'raw_score':results[i]['legacy_strict_mutation_percent'],'new_generation':False}),flush=True)
        rows=[results[i] for i in range(1,50)];m.dump(m.STAGE/'results49.json',rows)
        fields=list(dict.fromkeys(k for r in rows for k in r if not isinstance(r[k],(dict,list))))
        with (m.STAGE/'results49.csv').open('x',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
        m.frozen.check_gpt();audit.verify();m.dump(m.STAGE/'complete.json',{'status':'COMPLETE','n':49,'results49_sha256':audit.sha(m.STAGE/'results49.json'),'GPT_API_calls':0,'generation_calls':0,'technical_recovery_without_remeasurement':True});m.event('COMPLETE',n=49,results49_sha256=audit.sha(m.STAGE/'results49.json'))
    except BaseException as ex:
        m.event('ABORT',error_type=type(ex).__name__,error=str(ex),controller='resume_guard01');raise
if __name__=='__main__':main()
