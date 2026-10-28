"""Fixed49 E-only supplementary execution; locked inputs and readiness required."""
import argparse,csv,importlib.util,json,shutil,sys,time
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));sys.path.insert(0,str(BASE/'src'))
import audit,e49_driver as driver
STAGE=BASE/'e49_driver'
def json_read(p):return json.loads(p.read_text(encoding='utf-8'))
def check_gpt():
    path=audit.ROOT/'review_reports/minimal_camera_ready_20261023/guard_rq123_frozen.py'
    spec=importlib.util.spec_from_file_location('frozen_gpt_guard',path);g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
    assert g.collect()==json_read(g.LOCK),'GPT source/artifact guard changed'

def verify_lock():
    lock=json_read(STAGE/'readiness_lock.json')
    assert lock['actual_driver_fixture_passed'] and lock['semantic_negative_checks_passed']
    for path,h in lock['code_and_input_hashes'].items():assert audit.sha(BASE/path)==h,path
    for path,h in lock['tool_hashes'].items():assert audit.sha(path)==h,path
    for path,h in lock['context_source_hashes'].items():assert audit.sha(path)==h,path
    cache=Path(lock['local_repository']);assert cache.is_dir() and cache.resolve().is_relative_to(audit.ROOT)
    jobs=json_read(STAGE/'input_manifest49.json')
    expected=[r['class_key'] for r in driver.read_csv(BASE/'outputs/paired49.csv')]
    assert [j['class_key'] for j in jobs]==expected and len(jobs)==49
    assert len({j['seed'] for j in jobs})==49 and all(j['seed']==20261023+j['sample_index'] for j in jobs)
    check_gpt();audit.verify()
    return lock,jobs,cache

def prepare_job(job,out):
    out.mkdir(exist_ok=False);source=Path(job['source_repo']).resolve();repo=out/'repo';repo.mkdir()
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
    existing=[p for p in repo.rglob('*ESTest*.java') if 'src/test/java' in p.as_posix()]
    assert not existing,'Prior EvoSuite artifacts found; inspect rather than silently reuse'
    sandbox=source.parent.parent;settings=sandbox/'settings.xml'
    if settings.is_file():
        shutil.copy2(settings,out/'settings.xml');assert audit.sha(settings)==audit.sha(out/'settings.xml')
    focal=repo/job['focal_path'];assert audit.sha(focal)==job['focal_sha256']
    return repo/Path(job['module']),focal

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['verify','run']);args=p.parse_args()
    lock,jobs,cache=verify_lock()
    if args.mode=='verify':print(json.dumps({'status':'PASS','n':49,'no_generation':True},indent=2));return
    # Exclusive creation is the batch admission gate; no accidental second run/overwrite.
    admission=STAGE/'benchmark_admission.json'
    driver.write_json(admission,{'readiness_lock_sha256':audit.sha(STAGE/'readiness_lock.json'),'jobs':49,'start_utc':audit.events()[-1]['timestamp_utc'],
        'scope':'fixed49 E supplement only; no GPT API; source/RQ123 locked'})
    audit.log('E49_BENCHMARK_START',admission_sha256=audit.sha(admission),n=49,workers=1)
    root=STAGE/'jobs';root.mkdir(exist_ok=False);results=[]
    for job in jobs:
        check_gpt();out=root/('%02d'%job['job_index'])
        try:
            module,focal=prepare_job(job,out)
            r=driver.execute_job(out,cache,job['seed'],module,focal,job)
            row={'job_index':job['job_index'],'class_key':job['class_key'],'repo_id':job['repo_id'],
                 'G0_archived_mutation_percent':job['gpt_archived_mutation_percent'],
                 'E0_archived_mutation_percent':job['e0_archived_mutation_percent'],**r}
        except AssertionError as exc:
            audit.log('E49_INTEGRITY_ABORT',class_key=job['class_key'],detail=str(exc))
            raise
        except Exception as exc:
            # Keep this key in the cohort, preserve any artifacts, and expose technical failure.
            row={'job_index':job['job_index'],'class_key':job['class_key'],'repo_id':job['repo_id'],
                 'G0_archived_mutation_percent':job['gpt_archived_mutation_percent'],
                 'E0_archived_mutation_percent':job['e0_archived_mutation_percent'],
                 'error_type':type(exc).__name__,'error':str(exc),'legacy_process_build':0,
                 'legacy_strict_mutation_percent':0.0,'measurement_evidence_complete':False,'GPT_API_calls':0}
            audit.log('E49_JOB_EXCEPTION',class_key=job['class_key'],error_type=type(exc).__name__,detail=str(exc))
        driver.write_json(STAGE/('job_result_%02d.json'%job['job_index']),row);results.append(row)
        check_gpt();print(json.dumps({'completed':len(results),'n':49,'class_key':job['class_key'],'build':row.get('legacy_process_build'),'valid_evidence':row.get('measurement_evidence_complete')},ensure_ascii=False),flush=True)
    assert [r['class_key'] for r in results]==[j['class_key'] for j in jobs]
    driver.write_json(STAGE/'results49.json',results)
    fields=['job_index','class_key','repo_id','G0_archived_mutation_percent','E0_archived_mutation_percent','legacy_process_build','legacy_strict_mutation_percent','measurement_evidence_complete','generation_success','suite_pass','focal_mutants','killed_mutants','generation_attempts','seed','error_type','error']
    with (STAGE/'results49.csv').open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(results)
    check_gpt();audit.verify();audit.log('E49_BENCHMARK_END',n=49,results_sha256=audit.sha(STAGE/'results49.json'),GPT_API_calls=0)
    print('Fixed49 supplementary execution complete. Results require review; no RQ123 outputs updated.')

if __name__=='__main__':main()
