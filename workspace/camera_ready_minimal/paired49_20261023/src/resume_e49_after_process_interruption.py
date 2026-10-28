"""Resume SAME E49 protocol from job17 after prior OS processes disappeared.
Only an in-memory preparation guard changes; locked driver/profile/scoring are unchanged.
"""
import argparse,fnmatch,importlib.util,inspect,json,shutil,sys,time
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));sys.path.insert(0,str(BASE/'src'))
import audit,e49_driver as driver,run_e49_supplement as original
STAGE=BASE/'e49_driver';REC=STAGE/'resume_guard02'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def event(kind,**data):
    from datetime import datetime,timezone
    row={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'kind':kind,**data}
    with (REC/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')
    audit.log('E49_RESUME_GUARD02_'+kind,**data);print(json.dumps(row),flush=True)
def correct_guard():
    source=inspect.getsource(original.prepare_job)
    before="existing=[p for p in repo.rglob('*ESTest*.java') if 'src/test/java' in p.as_posix()]"
    after="existing=[p for p in repo.rglob('*.java') if p.is_file() and '_ESTest' in p.stem and 'src/test/java' in p.as_posix()]"
    assert source.count(before)==1,'Unexpected preparation code'
    assert '_ESTest' not in Path('BasicTypesTest.java').stem
    assert all('_ESTest' in Path(n).stem for n in ['Foo_ESTest.java','Foo_ESTest_scaffolding.java'])
    replacement=source.replace(before,after)
    namespace=original.__dict__;exec(compile(replacement,'<E49 guard-only correction>','exec'),namespace)
    return {'before':before,'after':after,'change_scope':'exact-case generated filename recognition only; human BasicTypesTest retained'}
def validate_prefix(jobs):
    prefix=[];digests={}
    for j in jobs[:16]:
        idx=j['job_index'];path=STAGE/('job_result_%02d.json'%idx);row=read(path)
        assert row['class_key']==j['class_key'] and row['seed']==j['seed'] and row['GPT_API_calls']==0
        assert row['G0_archived_mutation_percent']==j['gpt_archived_mutation_percent'] and row['E0_archived_mutation_percent']==j['e0_archived_mutation_percent']
        work=STAGE/'jobs'/('%02d'%idx)
        assert audit.sha(work/'repo'/j['focal_path'])==j['focal_sha256']
        for cmd in sorted(work.glob('command_*.json')):
            record=read(cmd)
            for label in ['stdout','stderr']:assert audit.sha(BASE/record[label])==record[label+'_sha256']
            digests[str(cmd.relative_to(BASE))]=audit.sha(cmd)
        for rel,h in read(work/'generated_manifest.json').items():assert audit.sha(work/rel)==h
        prefix.append(row);digests[str(path.relative_to(BASE))]=audit.sha(path)
    assert not (STAGE/'job_result_17.json').exists() and not list((STAGE/'jobs/17').glob('command_*.json'))
    return prefix,digests
def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['validate','run']);args=p.parse_args()
    lock,jobs,cache=original.verify_lock();prefix,digests=validate_prefix(jobs)
    guard=correct_guard();human='turin-compiler/src/test/java/me/tomassetti/turin/compiler/BasicTypesTest.java'
    row=next(r for r in jobs[9]['source_files'] if r['relative']==human)
    assert audit.sha(STAGE/'jobs/10/repo'/human)==row['sha256']
    report={'status':'PASS','same_protocol_sha256':audit.sha(STAGE/'protocol49.json'),
        'same_readiness_lock_sha256':audit.sha(STAGE/'readiness_lock.json'),
        'prefix_retained':16,'remaining':33,'retained_prefix_file_hashes':digests,'guard_correction':guard,
        'human_test_sha256':row['sha256'],'no_generation_before_interrupted_job17':True,
        'driver_profile_tools_seed_gate_and_scoring_changed':False,'source_sha256':audit.sha(__file__)}
    if args.mode=='validate':
        driver.write_json(REC/'validation.json',report);print(json.dumps(report,indent=2));return
    validation=read(REC/'validation.json');assert validation==report,'Validation context changed'
    driver.write_json(REC/'admission.json',report);event('ADMITTED',n=49,prefix_retained=16,GPT_API_calls=0)
    # Preserve the aborted copy intact; never delete or overwrite its files.
    old=(STAGE/'jobs/17').resolve();backup=(REC/'job17_interrupted_pre_generation').resolve()
    assert old.is_relative_to(STAGE.resolve()) and backup.is_relative_to(STAGE.resolve()) and not backup.exists()
    hashes={str(f.relative_to(old)):audit.sha(f) for f in sorted(old.rglob('*')) if f.is_file()}
    driver.write_json(REC/'job17_pre_move_manifest.json',hashes)
    old.rename(backup)
    assert hashes=={str(f.relative_to(backup)):audit.sha(f) for f in sorted(backup.rglob('*')) if f.is_file()}
    event('ABORTED_COPY_BACKED_UP',files=len(hashes),before_generation=True)
    results=list(prefix)
    for job in jobs[16:]:
        original.check_gpt();out=STAGE/'jobs'/('%02d'%job['job_index'])
        try:
            module,focal=original.prepare_job(job,out)
            # Guard correction MUST preserve every human source file, including the false-positive.
            if job['job_index']==10:assert audit.sha(out/'repo'/human)==row['sha256']
            r=driver.execute_job(out,cache,job['seed'],module,focal,job)
            result={'job_index':job['job_index'],'class_key':job['class_key'],'repo_id':job['repo_id'],
              'G0_archived_mutation_percent':job['gpt_archived_mutation_percent'],
              'E0_archived_mutation_percent':job['e0_archived_mutation_percent'],**r}
        except AssertionError as exc:
            event('INTEGRITY_ABORT',class_key=job['class_key'],detail=str(exc));raise
        except Exception as exc:
            result={'job_index':job['job_index'],'class_key':job['class_key'],'repo_id':job['repo_id'],
              'G0_archived_mutation_percent':job['gpt_archived_mutation_percent'],
              'E0_archived_mutation_percent':job['e0_archived_mutation_percent'],
              'error_type':type(exc).__name__,'error':str(exc),'legacy_process_build':0,
              'legacy_strict_mutation_percent':0.0,'measurement_evidence_complete':False,'GPT_API_calls':0}
            event('JOB_EXCEPTION',class_key=job['class_key'],error_type=type(exc).__name__,detail=str(exc))
        driver.write_json(STAGE/('job_result_%02d.json'%job['job_index']),result);results.append(result)
        original.check_gpt();event('JOB_COMPLETE',completed=len(results),n=49,class_key=job['class_key'],build=result.get('legacy_process_build'),valid_evidence=result.get('measurement_evidence_complete'))
    assert [r['class_key'] for r in results]==[j['class_key'] for j in jobs]
    driver.write_json(STAGE/'results49.json',results)
    import csv
    fields=['job_index','class_key','repo_id','G0_archived_mutation_percent','E0_archived_mutation_percent','legacy_process_build','legacy_strict_mutation_percent','measurement_evidence_complete','generation_success','suite_pass','focal_mutants','killed_mutants','generation_attempts','seed','error_type','error']
    with (STAGE/'results49.csv').open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(results)
    original.check_gpt();audit.verify();event('COMPLETE',n=49,results_sha256=audit.sha(STAGE/'results49.json'),GPT_API_calls=0)
if __name__=='__main__':
    try:main()
    except Exception as exc:
        event('STOPPED',error_type=type(exc).__name__,detail=str(exc));raise
