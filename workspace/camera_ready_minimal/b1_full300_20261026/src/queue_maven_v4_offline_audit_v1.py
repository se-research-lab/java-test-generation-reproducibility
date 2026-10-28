"""One completion-bound, lock-exclusive offline audit; never starts experiments.

Waits for the existing v4 invocation only. No scheduling, benchmark resumption,
Java, Gradle, EvoSuite, API, manuscript edit, fixture or source modification.
"""
import json, msvcrt, sys, time, traceback
from datetime import datetime, timezone
from pathlib import Path
from maven_adapter_v1 import R, sha, dump
from projection_io_v1 import publish_json
from audit_maven_v4_postbatch_v1 import run as offline_audit, OUT as AUDIT_OUT

B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit
OUT=R/'runtime/maven_v4_offline_audit_queue_v1'
COMPLETION=R/'runtime/remaining_maven183_v4_completion.json'
LAUNCH=R/'launch_remaining_maven183_v4.json'

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def now():
    return datetime.now(timezone.utc).isoformat()

def eligible(value,expected_hash):
    return (isinstance(value,dict) and type(value.get('exit_code')) is int and value['exit_code'] in {0,1}
            and value.get('automatic_resume') is False
            and type(value.get('new_policy_accepted')) is int and 0<=value['new_policy_accepted']<=211
            and type(value.get('GPT_API_calls')) is int and value['GPT_API_calls']==0
            and value.get('Gradle_benchmark_admitted') is False and value.get('full300_complete') is False
            and value.get('launch_plan_sha256')==expected_hash)

def cancelled():
    return (R/'STOP_REQUESTED.json').exists() or (OUT/'CANCEL_REQUESTED.json').exists()

def pins_match(pins):
    return all(Path(p).is_file() and sha(p)==h for p,h in pins.items())

def state(name,**extra):
    record={'at_utc':now(),'state':name,'new_JVM_processes':0,'new_EvoSuite_calls':0,'GPT_API_calls':0,
            'benchmark_admitted':False,'automatic_retry':False,**extra}
    publication=publish_json(OUT/'state.json',record,label='maven_offline_audit_queue')
    audit.log('B1_V4_OFFLINE_AUDIT_QUEUE_STATE',state=name,publication=publication,**extra)
    if not publication['published']:
        raise OSError('Cannot publish private audit queue state; stop without new work')
    return record

def ui_phase(phase,result=None):
    # Caller must own dispatcher.lock and have a valid completion receipt.
    s=load(R/'status.json')
    s.update(phase=phase,updated_utc=now(),running=0,active_sample_index=None,
             benchmark_admitted=False,Gradle_benchmark_admitted=False,full300_complete=False,
             new_API_calls=0,postbatch_audit_status=(result or {}).get('status','RUNNING_OFFLINE_ONLY'))
    s['blockers']=['Chỉ audit offline sau invocation Maven đã kết thúc; không khởi động JVM/API/benchmark',
                   'Class chưa chấm vẫn thuộc300, không gán0 hoặc giảm denominator; E1-full300 chưa chốt',
                   'Gradle40 chưa admit; GPT, repeated subset và paper vẫn giữ nguyên']
    if result:
        s['blockers'].insert(0,f"Audit: {result['status']}; xác minh{result['verified_total']}/300; lỗi audit:{result['error_count']}")
        s['postbatch_verified_total']=result['verified_total']
    receipt=publish_json(R/'status.json',s,label='maven_offline_audit_phase')
    if not receipt['published']:
        audit.log('B1_V4_OFFLINE_AUDIT_UI_IO_FAILURE',publication=receipt)

def main():
    assert not OUT.exists() and not AUDIT_OUT.exists(), 'Existing audit/queue cannot be overwritten or restarted'
    assert LAUNCH.exists()
    validation=R/'validation/maven_v4_offline_audit_preparation_v1/result.json'
    prepared=load(validation)
    assert prepared['status']=='PASS_PURE_PREPARATION_ONLY'
    for p,h in prepared['source_hashes'].items():
        assert sha(p)==h,'Prepared source drift'
    files=[Path(__file__),R/'src/audit_maven_v4_postbatch_v1.py',validation,LAUNCH,
           R/'admission_maven_v4.json',R/'src/projection_io_v1.py',R/'src/non_junit4_deferral_v1.py',
           R/'src/measurement_parser_v1.py',R/'src/checkpoint_archive_guard_v2.py',
           R/'src/classpath_transport_v1.py',R/'src/run_maven_b1_v3.py',R/'src/maven_adapter_v1.py']
    pins={str(p.resolve()):sha(p) for p in files}
    OUT.mkdir(parents=True,exist_ok=False)
    plan={'created_utc':now(),'scope':'one offline audit of the already-running Maven v4 invocation; not another experiment',
          'expected_launch_plan_sha256':sha(LAUNCH),'completion_path':str(COMPLETION),
          'source_and_input_pins':pins,'maximum_wait_seconds':43200,
          'completion_exit_codes_allowed_for_readonly_audit':[0,1],
          'dispatcher_mutex_required':True,'no_automatic_retry_or_resume':True,
          'new_JVM_processes':0,'GPT_API_calls':0,'new_EvoSuite_calls':0,
          'rules':['accept only the matching immutable invocation completion',
                   'wait for exclusive dispatcher lock before reading full job archives',
                   'keep every missing/unscored class in the fixed300 inventory without zero filling',
                   'stop on cancellation, source drift, invalid completion or a failed audit; do not restart any batch']}
    dump(OUT/'plan.json',plan)
    state('WAITING_EXISTING_MAVEN_V4_COMPLETION_NO_AUDIT_LOAD')
    deadline=time.monotonic()+plan['maximum_wait_seconds']
    incomplete_reads=0
    waiting_for_unlock=False
    while True:
        if cancelled():
            state('CANCELLED_NO_AUDIT_OR_EXPERIMENT_STARTED')
            return 0
        if time.monotonic()>=deadline:
            state('EXPIRED_NO_AUDIT_OR_EXPERIMENT_STARTED')
            return 0
        if not COMPLETION.exists():
            time.sleep(5)
            continue
        try:
            completion=load(COMPLETION)
        except json.JSONDecodeError:
            incomplete_reads+=1
            if incomplete_reads>=5:
                state('STOPPED_INVALID_COMPLETION_NO_RETRY')
                return 1
            time.sleep(.2)
            continue
        if not eligible(completion,plan['expected_launch_plan_sha256']):
            state('STOPPED_MISMATCHED_COMPLETION_NO_AUDIT')
            return 1
        if not pins_match(pins):
            state('STOPPED_SOURCE_DRIFT_NO_AUDIT')
            return 1
        with (R/'runtime/dispatcher.lock').open('r+b') as mutex:
            try:
                mutex.seek(0)
                msvcrt.locking(mutex.fileno(),msvcrt.LK_NBLCK,1)
            except OSError:
                if not waiting_for_unlock:
                    state('COMPLETION_PRESENT_WAITING_FOR_DISPATCHER_UNLOCK')
                    waiting_for_unlock=True
            else:
                try:
                    if cancelled():
                        state('CANCELLED_BEFORE_AUDIT')
                        return 0
                    assert load(COMPLETION)==completion and pins_match(pins)
                    state('AUDITING_OFFLINE_EXCLUSIVE_LOCK_NO_JVM',completion_sha256=sha(COMPLETION))
                    ui_phase('MAVEN_V4_OFFLINE_AUDIT_ONLY')
                    result=offline_audit(completion,plan['expected_launch_plan_sha256'])
                    ok=result['error_count']==0
                    state('FINISHED_OFFLINE_AUDIT' if ok else 'AUDIT_RECONCILIATION_REQUIRED_NO_RETRY',
                          result_sha256=sha(AUDIT_OUT/'result.json'),verified_total=result['verified_total'],errors=result['error_count'])
                    ui_phase('MAVEN_V4_AUDIT_PASS_PARTIAL_E1' if ok else 'MAVEN_V4_AUDIT_REVIEW_REQUIRED',result)
                    return 0 if ok else 1
                except BaseException as ex:
                    dump(OUT/'failure.json',{'at_utc':now(),'type':type(ex).__name__,'detail':str(ex),
                         'traceback':traceback.format_exc(),'automatic_retry':False,'new_JVM_processes':0,'GPT_API_calls':0})
                    state('STOPPED_AUDIT_CONTROLLER_ERROR_NO_RETRY',error_type=type(ex).__name__)
                    raise
                finally:
                    mutex.seek(0)
                    msvcrt.locking(mutex.fileno(),msvcrt.LK_UNLCK,1)
        time.sleep(5)

if __name__=='__main__':
    sys.exit(main())
